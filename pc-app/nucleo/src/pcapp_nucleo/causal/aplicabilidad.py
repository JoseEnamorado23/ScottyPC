"""Verificación de que el resultado de PC y los datos permiten construir el modelo causal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pcapp_nucleo.causal.configuracion import ConfiguracionModeloCausal
from pcapp_nucleo.causal.subgrafo import MAXIMO_CICLOS, Subgrafo, subgrafo_objetivo
from pcapp_nucleo.modelos import TipoObjetivo
from pcapp_nucleo.preparacion import DatosPreparados

BLOQUEANTE, ADVERTENCIA = "bloqueante", "advertencia"
CICLOS_MOSTRADOS = 3

# Pantalla donde se resuelve cada problema (la interfaz lleva a ella).
RESULTADOS, DECISIONES, PREPARACION, ANALISIS, MODELO = (
    "resultados", "decisiones", "preparacion", "analisis", "modelo_causal",
)


@dataclass(frozen=True)
class ProblemaAplicabilidad:
    codigo: str
    severidad: str
    mensaje: str
    accion: str
    destino: str | None = None
    variables: list[str] = field(default_factory=list)


def es_binaria(valores: np.ndarray) -> bool:
    presentes = valores[~np.isnan(valores)]
    return len(presentes) > 0 and set(np.unique(presentes)).issubset({0.0, 1.0})


def evaluar_aplicabilidad(
    resultado_pc: dict[str, Any],
    datos: DatosPreparados,
    configuracion: ConfiguracionModeloCausal | None = None,
    desactualizado: bool = False,
) -> list[ProblemaAplicabilidad]:
    """Problemas que impiden (bloqueantes) o condicionan (advertencias) el modelo causal.

    ``resultado_pc`` es el contenido de ``resultado.json`` de la versión que se usará.
    ``desactualizado`` indica que el análisis o una etapa anterior cambió desde PC.
    """
    configuracion = configuracion or ConfiguracionModeloCausal()
    objetivo = datos.objetivo
    problemas: list[ProblemaAplicabilidad] = []

    if desactualizado:
        problemas.append(ProblemaAplicabilidad(
            "RESULTADO_DESACTUALIZADO", BLOQUEANTE,
            "El resultado de PC está desactualizado: alguna etapa anterior cambió después del análisis.",
            "Vuelva a ejecutar el análisis.", ANALISIS,
        ))
    if not (resultado_pc.get("corridas") or {}).get("completo", False):
        problemas.append(ProblemaAplicabilidad(
            "RESULTADO_INCOMPLETO", BLOQUEANTE,
            "El análisis de PC no completó todas sus corridas.",
            "Reanude el análisis hasta completarlo.", ANALISIS,
        ))

    tipo = datos.tipo_objetivo
    clases = np.unique(datos.train[objetivo].dropna().to_numpy(dtype=float))
    if tipo == TipoObjetivo.MULTICLASE or (tipo != TipoObjetivo.CONTINUO and len(clases) > 2):
        problemas.append(ProblemaAplicabilidad(
            "OBJETIVO_MULTICLASE", BLOQUEANTE,
            f"El objetivo '{objetivo}' tiene {len(clases)} clases; el modelo causal necesita un objetivo "
            "binario o continuo.",
            f"Agrupe las clases de '{objetivo}' en dos en Decisiones (codificación por agrupación).",
            DECISIONES, [objetivo],
        ))

    sub = subgrafo_objetivo(list(resultado_pc["variables"]), list(resultado_pc["aristas"]), objetivo)
    problemas.extend(_problemas_grafo(sub))
    if not sub.ciclos and not sub.sin_orientar:
        problemas.extend(_problemas_datos(sub, datos, configuracion, tipo))
    problemas.extend(_advertencias(sub, datos))
    return problemas


def _problemas_grafo(sub: Subgrafo) -> list[ProblemaAplicabilidad]:
    problemas = []
    if not sub.padres.get(sub.objetivo):
        problemas.append(ProblemaAplicabilidad(
            "SIN_CAUSAS", BLOQUEANTE,
            f"El objetivo '{sub.objetivo}' no tiene ninguna causa directa en el grafo.",
            "Revise el resultado en Resultados (umbral de frecuencia u orientaciones) o la "
            "configuración de PC.", RESULTADOS, [sub.objetivo],
        ))
    for origen, destino in sub.sin_orientar:
        problemas.append(ProblemaAplicabilidad(
            "ARISTA_SIN_ORIENTAR", BLOQUEANTE,
            f"La arista {origen} — {destino} está sin orientar y toca al objetivo o a sus ancestros: no "
            "se sabe qué variable causa a cuál.",
            f"Oriente la arista {origen} — {destino} en Resultados.", RESULTADOS, [origen, destino],
        ))
    if sub.ciclos:
        ejemplos = "; ".join(" → ".join([*c, c[0]]) for c in sub.ciclos[:CICLOS_MOSTRADOS])
        cantidad = f"{len(sub.ciclos)}{' o más' if len(sub.ciclos) >= MAXIMO_CICLOS else ''}"
        variables = sorted({v for c in sub.ciclos for v in c})
        problemas.append(ProblemaAplicabilidad(
            "CICLO", BLOQUEANTE,
            f"Hay {'un ciclo' if len(sub.ciclos) == 1 else f'{cantidad} ciclos'} entre los ancestros del objetivo"
            f"{'' if len(sub.ciclos) <= CICLOS_MOSTRADOS else f' (se muestran {CICLOS_MOSTRADOS})'}: {ejemplos}.",
            "Rompa los ciclos en Resultados (orientaciones o umbral) o con niveles más detallados en la "
            "configuración de PC.", RESULTADOS, variables,
        ))
    return problemas


def _problemas_datos(
    sub: Subgrafo, datos: DatosPreparados, configuracion: ConfiguracionModeloCausal, tipo: str | None
) -> list[ProblemaAplicabilidad]:
    problemas = []
    train = datos.train
    for variable in sub.variables:
        padres = sub.padres[variable]
        if not padres:
            continue
        filas = int(train[variable].notna().sum())
        if filas < configuracion.filas_por_padre * len(padres):
            problemas.append(ProblemaAplicabilidad(
                "DATOS_INSUFICIENTES", BLOQUEANTE,
                f"El mecanismo de '{variable}' tiene {len(padres)} padre(s) y solo {filas} filas de "
                f"entrenamiento con '{variable}' observado; se necesitan al menos "
                f"{configuracion.filas_por_padre} por padre ({configuracion.filas_por_padre * len(padres)}).",
                "Reduzca los padres (Resultados) o conserve más filas en la preparación.",
                RESULTADOS, [variable, *padres],
            ))
    padres_objetivo = sub.padres.get(sub.objetivo) or []
    if tipo == TipoObjetivo.BINARIO and padres_objetivo:
        conteos = train[sub.objetivo].value_counts()
        minoritaria = int(conteos.min()) if len(conteos) == 2 else 0
        necesarios = configuracion.minoritaria_por_padre * len(padres_objetivo)
        if minoritaria < necesarios:
            problemas.append(ProblemaAplicabilidad(
                "MINORITARIA_INSUFICIENTE", BLOQUEANTE,
                f"La clase minoritaria de '{sub.objetivo}' tiene {minoritaria} casos en entrenamiento; con "
                f"{len(padres_objetivo)} padre(s) se necesitan al menos {necesarios} "
                f"({configuracion.minoritaria_por_padre} por padre).",
                "Reduzca las causas directas del objetivo en Resultados o use un dataset con más casos.",
                RESULTADOS, [sub.objetivo, *padres_objetivo],
            ))
    return problemas


def _advertencias(sub: Subgrafo, datos: DatosPreparados) -> list[ProblemaAplicabilidad]:
    problemas = []
    train = datos.train
    presentes = [v for v in sub.variables if v in train]
    con_faltantes = [v for v in presentes if train[v].isna().any()]
    if con_faltantes:
        detalle = ", ".join(f"{v} ({int(train[v].isna().sum())})" for v in con_faltantes)
        problemas.append(ProblemaAplicabilidad(
            "FALTANTES_SIN_IMPUTAR", ADVERTENCIA,
            f"Quedan faltantes sin imputar en variables del modelo: {detalle}. Se imputarán dentro del "
            "modelo con la mediana de entrenamiento.",
            "Si prefiere otra imputación, elíjala en Decisiones y vuelva a preparar.", DECISIONES, con_faltantes,
        ))
    binarias = [
        v for v in sub.variables
        if v != sub.objetivo and sub.padres[v] and v in train and es_binaria(train[v].to_numpy(dtype=float))
    ]
    if binarias:
        problemas.append(ProblemaAplicabilidad(
            "INTERMEDIAS_BINARIAS", ADVERTENCIA,
            f"Hay variables intermedias binarias ({', '.join(binarias)}): el contrafactual se aproxima "
            "promediando muestras del ruido compatible con el valor observado.",
            "No requiere acción; interprete los escenarios como aproximados.", None, binarias,
        ))
    if sub.fuera:
        problemas.append(ProblemaAplicabilidad(
            "FUERA_DEL_SUBGRAFO", ADVERTENCIA,
            f"Estas variables no son ancestros del objetivo y el modelo las ignora: {', '.join(sub.fuera)}.",
            "No requiere acción.", None, list(sub.fuera),
        ))
    return problemas


def hay_bloqueantes(problemas: list[ProblemaAplicabilidad]) -> bool:
    return any(p.severidad == BLOQUEANTE for p in problemas)

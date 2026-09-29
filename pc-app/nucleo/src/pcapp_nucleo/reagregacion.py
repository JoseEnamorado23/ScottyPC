"""Reagregación del resultado de PC con otro umbral u otras orientaciones manuales.

No vuelve a ejecutar PC ni necesita los datos: parte de las cuentas exactas del
bootstrap y de la matriz de Spearman guardadas en ``resultado.json`` y aplica las
mismas reglas que el análisis original (``pc_bootstrap.agregar_cuentas`` y
``caracterizacion.caracterizar``). Con el umbral y las orientaciones de la
ejecución, el resultado es idéntico al original.

Los resultados anteriores a la reagregación (sin ``cuentas``) se completan con
``migrar_resultado``: las cuentas se reconstruyen desde las frecuencias
redondeadas a 4 decimales, lo que es exacto con menos de 10 000 corridas válidas.

``avisos_resultado`` reúne las advertencias de interpretación del resultado (la
pestaña «Advertencias» de la aplicación y el informe HTML).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

from pcapp_nucleo.caracterizacion import Caracterizacion, caracterizar
from pcapp_nucleo.modelos import TipoHallazgo
from pcapp_nucleo.pc_bootstrap import (
    CorridaFallida,
    GrafoAgregado,
    ResultadoBootstrap,
    agregar_cuentas,
)
from pcapp_nucleo.pc_config import (
    ConfiguracionPC,
    ErrorConfiguracionPC,
    OrientacionManual,
    ProblemaConfiguracion,
    configuracion_desde_diccionario,
    problemas_configuracion,
)
from pcapp_nucleo.utilidades import a_diccionario_serializable

UMBRAL_ARISTA_DEBIL = 0.4
"""Frecuencia desde la que una arista no aceptada se considera «débil» (y se informa)."""

MAXIMO_VALIDAS_MIGRACION = 10_000
"""Por debajo, las cuentas se reconstruyen exactas desde frecuencias con 4 decimales."""

_TOLERANCIA = 1e-9


class ErrorReagregacion(ErrorConfiguracionPC):
    """Umbral u orientaciones no válidos; ``problemas`` lleva cada error con su campo."""

    def __init__(self, problemas: list[ProblemaConfiguracion]) -> None:
        super().__init__(problemas[0].mensaje)
        self.problemas = problemas


@dataclass(frozen=True)
class Reagregacion:
    """Resultado reagregado: ``contenido`` es el nuevo ``resultado.json``; el resto
    sirve para escribir los demás archivos (``escribir_reagregacion``)."""

    contenido: dict[str, Any]
    resultado: ResultadoBootstrap
    grafo: GrafoAgregado
    caracterizacion: Caracterizacion
    configuracion: ConfiguracionPC


# --- Cuentas y migración ------------------------------------------------------------------------


def tiene_cuentas(contenido: dict[str, Any]) -> bool:
    return "cuentas" in contenido and "spearman" in contenido and "agregacion" in contenido


def migrar_resultado(contenido: dict[str, Any], spearman: list[list[float | None]]) -> dict[str, Any]:
    """Completa un resultado sin cuentas (anterior a la reagregación).

    - Cuentas: ``round(frecuencia × válidas)`` de las matrices guardadas.
    - ``spearman``: matriz calculada con el conjunto de entrenamiento de la receta
      (``pc_bootstrap.matriz_spearman``); las aristas aceptadas conservan el ρ guardado.
    - Conflictos de orientación: se leen de la advertencia correspondiente.

    Raises:
        ErrorReagregacion: si hay demasiadas corridas para reconstruir las cuentas.
    """
    if tiene_cuentas(contenido):
        return contenido
    validas = int(contenido["corridas"]["validas"])
    if validas >= MAXIMO_VALIDAS_MIGRACION:
        raise ErrorReagregacion([ProblemaConfiguracion(
            "", f"No se pueden reconstruir las cuentas de {validas} corridas desde las frecuencias "
            "guardadas: vuelva a ejecutar el análisis para poder ajustarlo.",
        )])
    matrices = contenido["matrices"]
    dirigidas = np.rint(np.asarray(matrices["frecuencia_dirigida"], dtype=float) * validas).astype(int)
    sin_orientar = np.rint(np.asarray(matrices["frecuencia_sin_orientar"], dtype=float) * validas).astype(int)
    conflictos = 0
    for advertencia in contenido.get("advertencias", []):
        encontrado = re.search(r"Hubo (\d+) conflictos de orientación", advertencia)
        if encontrado:
            conflictos = int(encontrado.group(1))
    variables = contenido["variables"]
    posicion = {v: i for i, v in enumerate(variables)}
    rho = [list(fila) for fila in spearman]
    for arista in contenido["aristas"]:
        i, j = posicion[arista["origen"]], posicion[arista["destino"]]
        rho[i][j] = rho[j][i] = arista["spearman"]
    configuracion = contenido["configuracion"]
    return {
        **contenido,
        "agregacion": {
            "umbral_frecuencia": configuracion["umbral_frecuencia"],
            "orientaciones_manuales": configuracion.get("orientaciones_manuales", []),
        },
        "cuentas": {
            "dirigidas": dirigidas.tolist(),
            "sin_orientar": sin_orientar.tolist(),
            "bidireccionales": conflictos,
        },
        "spearman": rho,
    }


def resultado_desde_contenido(contenido: dict[str, Any]) -> ResultadoBootstrap:
    """``ResultadoBootstrap`` con las cuentas guardadas en ``resultado.json``."""
    corridas = contenido["corridas"]
    cuentas = contenido["cuentas"]
    return ResultadoBootstrap(
        variables=list(contenido["variables"]),
        objetivo=contenido["receta"]["objetivo"],
        corridas_totales=corridas["totales"],
        corridas_completadas=corridas["completadas"],
        corridas_validas=corridas["validas"],
        corridas_fallidas=[CorridaFallida(**f) for f in corridas["fallidas"]],
        completo=corridas["completo"],
        dirigidas=cuentas["dirigidas"],
        sin_orientar=cuentas["sin_orientar"],
        bidireccionales=cuentas["bidireccionales"],
        tiempo_s=contenido.get("tiempo_s", 0.0),
        limites_discretizacion=contenido.get("limites_discretizacion", {}),
    )


def _frecuencias_par(contenido: dict[str, Any]) -> tuple[np.ndarray, int]:
    """(cuentas totales por par, simétrica; corridas válidas)."""
    dirigidas = np.asarray(contenido["cuentas"]["dirigidas"])
    sin_orientar = np.asarray(contenido["cuentas"]["sin_orientar"])
    return dirigidas + dirigidas.T + sin_orientar, int(contenido["corridas"]["validas"])


# --- Reagregación -----------------------------------------------------------------------------


def orientaciones_desde_lista(datos: list[Any]) -> list[OrientacionManual]:
    orientaciones = []
    for i, valor in enumerate(datos):
        if isinstance(valor, OrientacionManual):
            orientaciones.append(valor)
            continue
        try:
            orientaciones.append(OrientacionManual(**valor))
        except TypeError as error:
            raise ErrorReagregacion([ProblemaConfiguracion(
                f"orientaciones_manuales.{i}", f"La orientación manual {i + 1} no es válida: {error}."
            )]) from error
    return orientaciones


def problemas_reagregacion(
    contenido: dict[str, Any], umbral_frecuencia: float, orientaciones: list[OrientacionManual]
) -> list[ProblemaConfiguracion]:
    """Errores del umbral y de las orientaciones manuales, con las mismas reglas que la
    configuración de PC (p. ej., una orientación no puede contradecir los niveles).

    Además, cada orientación necesita una justificación (salvo las que ya venían en la
    configuración de la ejecución) y no puede repetirse un par.
    """
    configuracion = configuracion_desde_diccionario(contenido["configuracion"])
    propuesta = replace(
        configuracion, umbral_frecuencia=umbral_frecuencia, orientaciones_manuales=orientaciones
    )
    problemas = [
        p for p in problemas_configuracion(propuesta, list(contenido["variables"]), contenido["receta"]["objetivo"])
        if p.campo == "umbral_frecuencia" or p.campo.startswith("orientaciones_manuales")
    ]
    con_error = {p.campo for p in problemas}
    originales = set(configuracion.orientaciones_manuales)
    vistos: set[frozenset[str]] = set()
    for i, orientacion in enumerate(orientaciones):
        campo = f"orientaciones_manuales.{i}"
        if campo in con_error:
            continue
        par = frozenset((orientacion.origen, orientacion.destino))
        if orientacion.origen == orientacion.destino:
            problemas.append(ProblemaConfiguracion(campo, "El origen y el destino deben ser distintos."))
        elif par in vistos:
            problemas.append(ProblemaConfiguracion(
                campo, f"La arista {orientacion.origen} — {orientacion.destino} ya tiene una orientación manual.",
            ))
        elif not orientacion.justificacion.strip() and orientacion not in originales:
            problemas.append(ProblemaConfiguracion(
                f"{campo}.justificacion",
                f"Justifique la orientación {orientacion.origen} → {orientacion.destino}.",
            ))
        vistos.add(par)
    return problemas


def reagregar(
    contenido: dict[str, Any],
    umbral_frecuencia: float,
    orientaciones_manuales: list[OrientacionManual] | list[dict[str, Any]],
) -> Reagregacion:
    """Rehace el grafo y la caracterización con otro umbral u otras orientaciones.

    ``contenido`` es un ``resultado.json`` con cuentas (ver ``migrar_resultado``). El
    resultado conserva la configuración de la ejecución y guarda el umbral y las
    orientaciones usados en ``agregacion``.

    Raises:
        ErrorReagregacion: con todos los problemas del umbral o de las orientaciones.
    """
    if not tiene_cuentas(contenido):
        raise ErrorReagregacion([ProblemaConfiguracion(
            "", "Este resultado no tiene las cuentas del bootstrap; migre el resultado antes de ajustarlo.",
        )])
    orientaciones = orientaciones_desde_lista(list(orientaciones_manuales))
    problemas = problemas_reagregacion(contenido, umbral_frecuencia, orientaciones)
    if problemas:
        raise ErrorReagregacion(problemas)
    configuracion = configuracion_desde_diccionario(contenido["configuracion"])
    resultado = resultado_desde_contenido(contenido)
    grafo = agregar_cuentas(resultado, umbral_frecuencia, orientaciones, contenido["spearman"])
    # Los grupos redundantes (de la revisión) son los mismos que en el resultado guardado.
    grupos = {
        v["variable"]: v["grupo_redundante"] for v in contenido["caracterizacion"]["variables"]
    }
    caracterizacion = caracterizar(grafo, resultado, configuracion.modificables)
    caracterizacion = replace(caracterizacion, variables=[
        replace(v, grupo_redundante=grupos.get(v.variable)) for v in caracterizacion.variables
    ])
    nuevo = {
        **contenido,
        "aristas": a_diccionario_serializable(grafo.aristas),
        "ciclos": grafo.ciclos,
        "caracterizacion": a_diccionario_serializable(caracterizacion),
        "advertencias": grafo.advertencias,
        "agregacion": {
            "umbral_frecuencia": umbral_frecuencia,
            "orientaciones_manuales": a_diccionario_serializable(orientaciones),
        },
    }
    return Reagregacion(nuevo, resultado, grafo, caracterizacion, configuracion)


def escribir_reagregacion(carpeta: str | Path, reagregacion: Reagregacion) -> dict[str, Path]:
    """Escribe ``resultado.json``, ``aristas.csv``, ``mascara.csv``,
    ``matriz_frecuencias.csv`` y ``grafo.png`` de una versión reagregada."""
    from pcapp_nucleo.exportacion import escribir_resultados

    r = reagregacion
    return escribir_resultados(carpeta, r.contenido, r.resultado, r.grafo, r.caracterizacion, r.configuracion)


# --- Advertencias de interpretación -----------------------------------------------------------


@dataclass(frozen=True)
class ParVariables:
    """Par de variables con su frecuencia total (cualquier orientación)."""

    variable_a: str
    variable_b: str
    frecuencia: float
    con_objetivo: bool


@dataclass(frozen=True)
class AvisoResultado:
    """Advertencia para interpretar el resultado. ``nivel``: ``advertencia`` o ``info``."""

    codigo: str
    nivel: str
    titulo: str
    mensaje: str
    variables: list[str] = field(default_factory=list)
    pares: list[ParVariables] = field(default_factory=list)


def _pares_entre(
    contenido: dict[str, Any], desde: float, hasta: float | None
) -> list[ParVariables]:
    """Pares con frecuencia en [desde, hasta) (con la misma tolerancia que la agregación),
    de mayor a menor frecuencia."""
    totales, validas = _frecuencias_par(contenido)
    if validas == 0:
        return []
    variables = contenido["variables"]
    objetivo = contenido["receta"]["objetivo"]
    pares = []
    for i in range(len(variables)):
        for j in range(i + 1, len(variables)):
            cuenta = int(totales[i, j])
            if cuenta < desde * validas - _TOLERANCIA:
                continue
            if hasta is not None and cuenta >= hasta * validas - _TOLERANCIA:
                continue
            a, b = variables[i], variables[j]
            if b == objetivo:
                a, b = b, a
            pares.append(ParVariables(a, b, round(cuenta / validas, 4), objetivo in (a, b)))
    return sorted(pares, key=lambda p: (not p.con_objetivo, -p.frecuencia, p.variable_a, p.variable_b))


def _porcentaje(valor: float) -> str:
    return f"{100 * valor:.0f} %"


def avisos_resultado(
    contenido: dict[str, Any],
    hallazgos_revision: list[dict[str, Any]] | None = None,
    prueba_recomendada: str | None = None,
) -> list[AvisoResultado]:
    """Advertencias de interpretación de un ``resultado.json`` (con cuentas).

    - corridas fallidas y resultado parcial;
    - ciclos dirigidos y conflictos de orientación;
    - orientaciones manuales que no se pudieron aplicar;
    - aristas débiles: entre el 40 % y el umbral (destacando las que llegan al objetivo);
    - aristas que solo aparecen porque se bajó el umbral respecto al original;
    - grupos redundantes y tamaño efectivo insuficiente (de la revisión);
    - prueba de independencia distinta de la recomendada.
    """
    avisos: list[AvisoResultado] = []
    corridas = contenido["corridas"]
    configuracion = contenido["configuracion"]
    objetivo = contenido["receta"]["objetivo"]
    umbral = contenido["agregacion"]["umbral_frecuencia"]
    umbral_original = configuracion["umbral_frecuencia"]

    if not corridas["completo"]:
        avisos.append(AvisoResultado(
            "RESULTADO_PARCIAL", "advertencia", "Resultado parcial",
            f"Solo se completaron {corridas['completadas']} de {corridas['totales']} corridas.",
        ))
    if corridas["fallidas"]:
        motivos = sorted({f["motivo"] for f in corridas["fallidas"]})
        avisos.append(AvisoResultado(
            "CORRIDAS_FALLIDAS", "advertencia", "Corridas fallidas",
            f"{len(corridas['fallidas'])} de {corridas['completadas']} corridas fallaron y se "
            f"descartaron; las frecuencias se calculan sobre {corridas['validas']} corridas válidas. "
            f"Motivos: {'; '.join(motivos[:3])}" + (" (entre otros)." if len(motivos) > 3 else "."),
        ))
    if contenido["ciclos"]:
        descripcion = "; ".join(" → ".join(ciclo + ciclo[:1]) for ciclo in contenido["ciclos"][:5])
        avisos.append(AvisoResultado(
            "CICLOS", "advertencia", "Ciclos en el grafo",
            f"El grafo dirigido tiene {len(contenido['ciclos'])} ciclo(s): {descripcion}. Un ciclo "
            "no es un grafo causal válido: revise las orientaciones (no se corrigen automáticamente).",
            variables=sorted({v for ciclo in contenido["ciclos"] for v in ciclo}),
        ))
    bidireccionales = contenido["cuentas"]["bidireccionales"]
    if bidireccionales:
        avisos.append(AvisoResultado(
            "CONFLICTOS_ORIENTACION", "info", "Conflictos de orientación",
            f"Hubo {bidireccionales} conflictos de orientación (aristas bidireccionales) en las "
            "corridas; se contaron como aristas sin orientar.",
        ))
    for advertencia in contenido.get("advertencias", []):
        if advertencia.startswith("Orientación manual"):
            avisos.append(AvisoResultado(
                "ORIENTACION_NO_APLICADA", "advertencia", "Orientación manual no aplicada", advertencia,
            ))

    if umbral > UMBRAL_ARISTA_DEBIL + _TOLERANCIA:
        debiles = _pares_entre(contenido, UMBRAL_ARISTA_DEBIL, umbral)
        con_objetivo = [p for p in debiles if p.con_objetivo]
        if con_objetivo:
            avisos.append(AvisoResultado(
                "ARISTAS_DEBILES_OBJETIVO", "advertencia", "Aristas débiles con el objetivo",
                f"Estas relaciones con '{objetivo}' aparecen en al menos el "
                f"{_porcentaje(UMBRAL_ARISTA_DEBIL)} de las corridas, pero no alcanzan el umbral "
                f"({_porcentaje(umbral)}), así que no están en el grafo. Pueden ser causas reales "
                "que PC detecta con poca potencia (pocos casos, efectos moderados) o relaciones "
                "espurias: no las descarte sin revisarlas. Bajar el umbral las incluiría, a costa "
                "de aceptar más aristas espurias.",
                variables=[p.variable_b for p in con_objetivo],
                pares=con_objetivo,
            ))
        otras = [p for p in debiles if not p.con_objetivo]
        if otras:
            avisos.append(AvisoResultado(
                "ARISTAS_DEBILES", "info", "Aristas débiles",
                f"Aparecen en al menos el {_porcentaje(UMBRAL_ARISTA_DEBIL)} de las corridas, pero "
                f"no alcanzan el umbral ({_porcentaje(umbral)}); no están en el grafo.",
                pares=otras,
            ))
    if umbral < umbral_original - _TOLERANCIA:
        por_umbral = _pares_entre(contenido, umbral, umbral_original)
        if por_umbral:
            avisos.append(AvisoResultado(
                "ARISTAS_POR_UMBRAL_BAJO", "advertencia", "Aristas añadidas al bajar el umbral",
                f"Estas aristas solo aparecen porque el umbral se bajó de {_porcentaje(umbral_original)} "
                f"(el de la ejecución) a {_porcentaje(umbral)}. Interprételas con más cautela que el "
                "resto: cuanto más bajo el umbral, más aristas espurias.",
                pares=por_umbral,
            ))

    grupos: list[list[str]] = []
    for variable in contenido["caracterizacion"]["variables"]:
        grupo = variable.get("grupo_redundante")
        if grupo and grupo not in grupos:
            grupos.append(grupo)
    for grupo in grupos:
        avisos.append(AvisoResultado(
            "GRUPO_REDUNDANTE", "advertencia", "Grupo de variables redundantes",
            f"{', '.join(grupo)} miden casi lo mismo. PC puede repartir las aristas entre ellas "
            "o quedarse con una sola: la ausencia de una arista en una de ellas no significa que "
            "no tenga relación.",
            variables=list(grupo),
        ))
    for hallazgo in hallazgos_revision or []:
        if hallazgo.get("tipo") == TipoHallazgo.TAMANO_EFECTIVO_INSUFICIENTE:
            avisos.append(AvisoResultado(
                "TAMANO_EFECTIVO", "advertencia", "Tamaño efectivo insuficiente",
                f"{hallazgo['detalle']} La revisión de los datos lo advirtió: la ausencia de una "
                "arista no demuestra que no haya relación.",
                variables=list(hallazgo.get("columnas_involucradas", [])),
            ))
    if prueba_recomendada and prueba_recomendada != configuracion["prueba"]:
        avisos.append(AvisoResultado(
            "PRUEBA_DISTINTA", "advertencia", "Prueba distinta de la recomendada",
            f"El análisis usó {configuracion['prueba']}, pero para estos datos se recomendó "
            f"{prueba_recomendada}. Si la prueba no se ajusta a los datos (faltantes, relaciones no "
            "monótonas, variables categóricas), las aristas pueden ser menos fiables.",
        ))
    return avisos

"""Prescripción por lotes y evaluación del prescriptor sobre test.

Ambos reparten los casos en bloques (opcionalmente entre procesos, con ``ejecutor``); el
resultado de cada caso no depende de los demás, así que es idéntico en paralelo y en secuencial.

La evaluación es INTERNA: mide qué haría el prescriptor según el modelo causal, no el efecto real
de las intervenciones.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import Executor, FIRST_COMPLETED, wait
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from pcapp_nucleo.causal.contrafactuales import caso_desde_test
from pcapp_nucleo.causal.modelo import ModeloCausal, modelo_desde_diccionario
from pcapp_nucleo.prescripcion.configuracion import (
    GENETICO, GRADIENTE, ConfiguracionPrescripcion, configuracion_desde_diccionario, rango_original,
)
from pcapp_nucleo.prescripcion.optimizadores import crear_optimizador
from pcapp_nucleo.prescripcion.prescriptor import ResultadoPrescripcion, prescribir_caso
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion
from pcapp_nucleo.prescripcion.referencia import ModeloReferencia, referencia_desde_diccionario
from pcapp_nucleo.utilidades import a_diccionario_serializable

CASOS_POR_BLOQUE = 20
FRACCIONES_CAMBIO_MAXIMO = (0.10, 0.25, 0.40)
FACTORES_MU = (0.5, 1.0, 2.0)
TEXTO_EVALUACION_INTERNA = (
    "Esta es una evaluación INTERNA: indica qué lograría el prescriptor según el modelo causal, suponiendo "
    "que el modelo es correcto. No mide el efecto real de las intervenciones; para eso hace falta una "
    "validación experimental o un seguimiento de los casos."
)


class LoteCancelado(Exception):
    pass


def _en_bloques(
    funcion: Callable[..., list[Any]], argumentos: tuple, filas: pd.DataFrame, ejecutor: Executor | None,
    progreso: Callable[[int, int], None] | None, cancelacion: Any,
) -> list[Any]:
    avisar = progreso or (lambda *_: None)
    bloques = [filas.iloc[i:i + CASOS_POR_BLOQUE] for i in range(0, len(filas), CASOS_POR_BLOQUE)]
    resultados: list[list[Any] | None] = [None] * len(bloques)
    hechos = 0
    if ejecutor is None:
        for i, bloque in enumerate(bloques):
            if cancelacion is not None and cancelacion.is_set():
                raise LoteCancelado()
            resultados[i] = funcion(*argumentos, bloque)
            hechos += len(bloque)
            avisar(hechos, len(filas))
    else:
        pendientes = {ejecutor.submit(funcion, *argumentos, bloque): i for i, bloque in enumerate(bloques)}
        while pendientes:
            if cancelacion is not None and cancelacion.is_set():
                for futuro in pendientes:
                    futuro.cancel()
                raise LoteCancelado()
            listos, _ = wait(pendientes, timeout=0.5, return_when=FIRST_COMPLETED)
            for futuro in listos:
                i = pendientes.pop(futuro)
                resultados[i] = futuro.result()
                hechos += len(bloques[i])
                avisar(hechos, len(filas))
    return [r for bloque in resultados for r in bloque]


def _materializar(modelo, configuracion, referencia):
    if isinstance(modelo, dict):
        modelo = modelo_desde_diccionario(modelo)
    if isinstance(configuracion, dict):
        configuracion = configuracion_desde_diccionario(configuracion)
    if isinstance(referencia, dict):
        referencia = referencia_desde_diccionario(referencia)
    return modelo, configuracion, referencia


def _argumentos(modelo, configuracion, referencia, ejecutor) -> tuple:
    """En paralelo se envían diccionarios (se reconstruyen en cada proceso)."""
    if ejecutor is None:
        return modelo, configuracion, referencia
    return modelo.datos, a_diccionario_serializable(configuracion), a_diccionario_serializable(referencia)


# --- Lote ------------------------------------------------------------------------------------


def _lote_bloque(modelo, configuracion, referencia, mu: float, filas: pd.DataFrame) -> list[dict[str, Any]]:
    modelo, configuracion, referencia = _materializar(modelo, configuracion, referencia)
    salida = []
    for indice in filas.index:
        caso = caso_desde_test(modelo, filas, int(indice))
        resultado = prescribir_caso(modelo, caso, configuracion, mu, referencia, filas.loc[[indice]])
        salida.append(a_diccionario_serializable(resultado))
    return salida


def prescribir_lote(
    modelo: ModeloCausal, filas: pd.DataFrame, configuracion: ConfiguracionPrescripcion, mu: float,
    referencia: ModeloReferencia | None, progreso=None, cancelacion=None, ejecutor: Executor | None = None,
) -> list[dict[str, Any]]:
    """Prescripción de cada fila (preparada; el índice identifica el caso). Devuelve los resultados
    serializados, en el orden de ``filas``."""
    filas = filas.drop(columns=[modelo.objetivo], errors="ignore")
    argumentos = (*_argumentos(modelo, configuracion, referencia, ejecutor), mu)
    return _en_bloques(_lote_bloque, argumentos, filas, ejecutor, progreso, cancelacion)


def que_no_cumplen(modelo: ModeloCausal, filas: pd.DataFrame, configuracion: ConfiguracionPrescripcion) -> pd.DataFrame:
    """Filas cuyo valor predicho sin intervenir NO cumple el objetivo."""
    conservar = []
    for indice in filas.index:
        caso = caso_desde_test(modelo, filas, int(indice))
        problema = ProblemaPrescripcion(modelo, caso, configuracion, 0.0)
        if not problema.alcanzado(float(problema.p([np.zeros(problema.k)], [problema.actual])[0])):
            conservar.append(indice)
    return filas.loc[conservar]


# --- Evaluación ------------------------------------------------------------------------------


def _con_cambio_maximo(modelo: ModeloCausal, c: ConfiguracionPrescripcion, fraccion: float) -> ConfiguracionPrescripcion:
    acciones = {}
    for v, a in c.acciones.items():
        rango = rango_original(modelo, v)
        acciones[v] = replace(a, cambio_maximo=fraccion * (rango[1] - rango[0])) if rango else a
    return replace(c, acciones=acciones)


def _resumen_caso(r: ResultadoPrescripcion, segundos: float) -> dict[str, Any]:
    return {
        "alcanzado": r.alcanzado, "costo": r.costo_total, "segundos": segundos,
        "requiere_revision": r.requiere_revision, "extrapolacion": r.extrapolacion,
        "cambios": {a.variable: a.cambio for a in r.acciones},
        "acciones_usadas": len(r.acciones), "acciones_posibles": len(r.acciones) + len(r.sin_cambio),
    }


def _evaluacion_bloque(modelo, configuracion, referencia, mu: float, filas: pd.DataFrame) -> list[dict[str, Any]]:
    modelo, configuracion, referencia = _materializar(modelo, configuracion, referencia)
    variantes: dict[str, tuple[ConfiguracionPrescripcion, float, str]] = {
        "base": (configuracion, mu, configuracion.optimizador),
    }
    for fraccion in FRACCIONES_CAMBIO_MAXIMO:
        variantes[f"cambio_maximo_{fraccion:.2f}"] = (_con_cambio_maximo(modelo, configuracion, fraccion), mu, configuracion.optimizador)
    for factor in FACTORES_MU:
        variantes[f"mu_x{factor:g}"] = (configuracion, mu * factor, configuracion.optimizador)
    for nombre in (GRADIENTE, GENETICO):
        variantes[f"optimizador_{nombre}"] = (configuracion, mu, nombre)
    salida = []
    for indice in filas.index:
        caso = caso_desde_test(modelo, filas, int(indice))
        fila = filas.loc[[indice]]
        registro = {"indice": int(indice)}
        cache: dict[tuple, dict[str, Any]] = {}
        for nombre, (c, m, optimizador) in variantes.items():
            clave = (id(c), m, optimizador)
            if clave not in cache:
                t = time.perf_counter()
                r = prescribir_caso(modelo, caso, c, m, referencia, fila, crear_optimizador(optimizador, c))
                cache[clave] = _resumen_caso(r, time.perf_counter() - t)
            registro[nombre] = cache[clave]
        salida.append(registro)
    return salida


@dataclass(frozen=True)
class ComparacionOptimizadores:
    optimizador: str
    tasa_exito: float
    costo_medio: float
    segundos_medios: float


@dataclass(frozen=True)
class EvaluacionPrescriptor:
    casos: int
    tasa_exito: float
    no_alcanzables: int
    cambio_medio: dict[str, dict[str, float]]
    porcentaje_acciones_en_cero: float
    porcentaje_requiere_revision: float
    porcentaje_extrapolacion: float
    sensibilidad_cambio_maximo: list[dict[str, Any]]
    sensibilidad_mu: list[dict[str, Any]]
    comparacion_optimizadores: list[ComparacionOptimizadores]
    mcnemar: dict[str, Any]
    mu: float
    texto: str = TEXTO_EVALUACION_INTERNA


def _tasa(registros, variante) -> float:
    return float(np.mean([r[variante]["alcanzado"] for r in registros])) if registros else 0.0


def _costo(registros, variante) -> float:
    return float(np.mean([r[variante]["costo"] for r in registros])) if registros else 0.0


def evaluar_prescriptor(
    modelo: ModeloCausal, test: pd.DataFrame, configuracion: ConfiguracionPrescripcion, mu: float,
    referencia: ModeloReferencia | None, progreso=None, cancelacion=None, ejecutor: Executor | None = None,
) -> EvaluacionPrescriptor:
    """Evalúa sobre los casos de test que no cumplen el objetivo (sin reajustar nada)."""
    casos = que_no_cumplen(modelo, test.drop(columns=[modelo.objetivo], errors="ignore"), configuracion)
    argumentos = (*_argumentos(modelo, configuracion, referencia, ejecutor), mu)
    registros = _en_bloques(_evaluacion_bloque, argumentos, casos, ejecutor, progreso, cancelacion)
    base = [r["base"] for r in registros]
    cambios: dict[str, list[float]] = {}
    for r in base:
        for variable, cambio in r["cambios"].items():
            if cambio is not None:
                cambios.setdefault(variable, []).append(cambio)
    posibles = sum(r["acciones_posibles"] for r in base)
    usadas = sum(r["acciones_usadas"] for r in base)
    rangos = {v: rango_original(modelo, v) for v in configuracion.acciones}
    sensibilidad_cambio = [
        {
            "fraccion_rango": f, "tasa_exito": _tasa(registros, f"cambio_maximo_{f:.2f}"),
            "costo_medio": _costo(registros, f"cambio_maximo_{f:.2f}"),
        }
        for f in FRACCIONES_CAMBIO_MAXIMO
    ]
    sensibilidad_mu = [
        {"mu": mu * f, "factor": f, "tasa_exito": _tasa(registros, f"mu_x{f:g}"), "costo_medio": _costo(registros, f"mu_x{f:g}")}
        for f in FACTORES_MU
    ]
    comparacion = [
        ComparacionOptimizadores(
            nombre, _tasa(registros, f"optimizador_{nombre}"), _costo(registros, f"optimizador_{nombre}"),
            float(np.mean([r[f"optimizador_{nombre}"]["segundos"] for r in registros])) if registros else 0.0,
        )
        for nombre in (GRADIENTE, GENETICO)
    ]
    solo_gradiente = sum(1 for r in registros if r[f"optimizador_{GRADIENTE}"]["alcanzado"] and not r[f"optimizador_{GENETICO}"]["alcanzado"])
    solo_genetico = sum(1 for r in registros if r[f"optimizador_{GENETICO}"]["alcanzado"] and not r[f"optimizador_{GRADIENTE}"]["alcanzado"])
    discordantes = solo_gradiente + solo_genetico
    p = float(binomtest(min(solo_gradiente, solo_genetico), discordantes, 0.5).pvalue) if discordantes else 1.0
    return EvaluacionPrescriptor(
        casos=len(registros),
        tasa_exito=_tasa(registros, "base"),
        no_alcanzables=sum(1 for r in base if not r["alcanzado"]),
        cambio_medio={
            v: {
                "cambio_medio": float(np.mean(x)), "cambio_absoluto_medio": float(np.mean(np.abs(x))),
                "usos": len(x), "rango_train": (rangos[v][1] - rangos[v][0]) if rangos.get(v) else None,
            }
            for v, x in cambios.items()
        },
        porcentaje_acciones_en_cero=100.0 * (1 - usadas / posibles) if posibles else 100.0,
        porcentaje_requiere_revision=100.0 * float(np.mean([r["requiere_revision"] for r in base])) if base else 0.0,
        porcentaje_extrapolacion=100.0 * float(np.mean([r["extrapolacion"] for r in base])) if base else 0.0,
        sensibilidad_cambio_maximo=sensibilidad_cambio,
        sensibilidad_mu=sensibilidad_mu,
        comparacion_optimizadores=comparacion,
        mcnemar={"solo_gradiente": solo_gradiente, "solo_genetico": solo_genetico, "p_valor": p,
                 "prueba": "McNemar exacta (binomial sobre los pares discordantes)"},
        mu=mu,
    )

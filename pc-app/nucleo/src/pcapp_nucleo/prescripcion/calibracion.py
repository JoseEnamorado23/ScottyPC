"""Calibración automática de μ (peso de la intervención mínima), solo con train.

Sobre los casos de train que NO cumplen el objetivo, se elige el μ más grande de la rejilla con
el que al menos ``exito_calibracion`` (95 %) de esos casos alcanza el objetivo. Si ningún μ lo
consigue, se usa el más pequeño y se advierte.

La tasa se calcula sobre los casos **alcanzables**: los que alcanzan el objetivo con μ = 0 (sin
penalizar el costo), dentro de los límites, el cambio máximo y la dirección permitidos. Un caso
que no se puede alcanzar con ningún μ no dice nada sobre μ; se cuenta aparte.

Para que no tarde demasiado:
- la abducción de cada caso se hace una sola vez y se reutiliza para todos los μ;
- cada caso resuelve primero con μ = 0 y después la rejilla de menor a mayor μ, arrancando desde
  su solución con el μ anterior (un solo arranque, sin puntos aleatorios);
- los casos se reparten en bloques entre procesos (``ejecutor``). Como la cadena de cada caso no
  depende de los demás, el resultado es idéntico en paralelo y en secuencial.

La prescripción final usa multiarranque, y el informe lo indica.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, FIRST_COMPLETED, wait
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo.causal.configuracion import decimal
from pcapp_nucleo.causal.contrafactuales import caso_desde_test
from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.prescripcion.configuracion import ConfiguracionPrescripcion, configuracion_desde_diccionario
from pcapp_nucleo.prescripcion.optimizadores import GradienteProximal, optimizar_caso
from pcapp_nucleo.prescripcion.prescriptor import semilla_de_caso
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion
from pcapp_nucleo.utilidades import a_diccionario_serializable

NOTA_CALIBRACION = (
    "La calibración usa solo casos de entrenamiento y un solo arranque por caso (el valor actual, o la "
    "solución obtenida con el μ anterior de la rejilla); la prescripción final usa multiarranque. La tasa de "
    "éxito se calcula sobre los casos alcanzables (los que alcanzan el objetivo sin penalizar el costo, "
    "dentro de las restricciones)."
)
CASOS_POR_BLOQUE = 25


class CalibracionCancelada(Exception):
    pass


@dataclass(frozen=True)
class PuntoRejilla:
    mu: float
    tasa_exito: float | None
    exitos: int
    evaluados: int


@dataclass(frozen=True)
class CalibracionMu:
    mu: float
    rejilla: list[PuntoRejilla]
    casos: int
    alcanzables: int
    no_alcanzables: int
    casos_que_ya_cumplen: int
    exito_requerido: float
    advertencia: str | None
    nota: str = NOTA_CALIBRACION


def _calibrar_bloque(
    modelo: ModeloCausal | dict[str, Any], configuracion: ConfiguracionPrescripcion | dict[str, Any],
    filas: pd.DataFrame, rejilla: list[float],
) -> list[tuple[bool, bool, list[bool]]]:
    """Para cada fila: (ya cumple, alcanzable con μ = 0, éxito con cada μ de la rejilla)."""
    if isinstance(modelo, dict):
        from pcapp_nucleo.causal.modelo import modelo_desde_diccionario

        modelo = modelo_desde_diccionario(modelo)
    if isinstance(configuracion, dict):
        configuracion = configuracion_desde_diccionario(configuracion)
    optimizador = GradienteProximal.desde(configuracion, arranques_aleatorios=0)
    salida = []
    for indice in filas.index:
        caso = caso_desde_test(modelo, filas, int(indice))
        problema = ProblemaPrescripcion(modelo, caso, configuracion, 0.0)
        if problema.alcanzado(float(problema.p([np.zeros(problema.k)], [problema.actual])[0])):
            salida.append((True, False, []))
            continue
        semilla = semilla_de_caso(modelo, caso)
        solucion, _ = optimizar_caso(problema, optimizador, semilla)
        alcanzable = problema.alcanzado(float(problema.p([solucion.d], [solucion.estado])[0]))
        exitos = []
        if alcanzable:
            for mu in rejilla:
                con_mu = problema.con_mu(mu)
                solucion, _ = optimizar_caso(con_mu, optimizador, semilla, solucion)
                exitos.append(con_mu.alcanzado(float(con_mu.p([solucion.d], [solucion.estado])[0])))
        salida.append((False, alcanzable, exitos))
    return salida


def calibrar_mu(
    modelo: ModeloCausal,
    train: pd.DataFrame,
    configuracion: ConfiguracionPrescripcion,
    progreso: Callable[[int, int], None] | None = None,
    cancelacion: Any = None,
    ejecutor: Executor | None = None,
) -> CalibracionMu:
    """``train`` son las filas preparadas de ENTRENAMIENTO (nunca test)."""
    avisar = progreso or (lambda *_: None)
    rejilla = sorted(float(m) for m in configuracion.rejilla_mu)
    bloques = [train.iloc[i:i + CASOS_POR_BLOQUE] for i in range(0, len(train), CASOS_POR_BLOQUE)]
    resultados: list[list[tuple[bool, bool, list[bool]]] | None] = [None] * len(bloques)
    hechos = 0
    if ejecutor is None:
        for i, bloque in enumerate(bloques):
            if cancelacion is not None and cancelacion.is_set():
                raise CalibracionCancelada()
            resultados[i] = _calibrar_bloque(modelo, configuracion, bloque, rejilla)
            hechos += len(bloque)
            avisar(hechos, len(train))
    else:
        modelo_json, configuracion_json = modelo.datos, a_diccionario_serializable(configuracion)
        pendientes = {
            ejecutor.submit(_calibrar_bloque, modelo_json, configuracion_json, bloque, rejilla): i
            for i, bloque in enumerate(bloques)
        }
        while pendientes:
            if cancelacion is not None and cancelacion.is_set():
                for futuro in pendientes:
                    futuro.cancel()
                raise CalibracionCancelada()
            listos, _ = wait(pendientes, timeout=0.5, return_when=FIRST_COMPLETED)
            for futuro in listos:
                i = pendientes.pop(futuro)
                resultados[i] = futuro.result()
                hechos += len(bloques[i])
                avisar(hechos, len(train))

    filas = [r for bloque in resultados for r in bloque]
    ya_cumplen = sum(1 for cumple, _, _ in filas if cumple)
    casos = [r for r in filas if not r[0]]
    alcanzables = [r[2] for r in casos if r[1]]
    n = len(alcanzables)
    puntos = [
        PuntoRejilla(mu, (sum(e[j] for e in alcanzables) / n) if n else None, sum(e[j] for e in alcanzables), n)
        for j, mu in enumerate(rejilla)
    ]
    validos = [p for p in puntos if n and p.exitos >= configuracion.exito_calibracion * n - 1e-9]
    advertencia = None
    if n == 0:
        elegido = rejilla[0]
        advertencia = (
            "Ningún caso de entrenamiento que no cumple el objetivo lo puede alcanzar con estas restricciones: "
            f"se usa el μ más pequeño ({decimal(rejilla[0], 'g')}). Revise el objetivo deseado y las restricciones."
        )
    elif validos:
        elegido = max(p.mu for p in validos)
    else:
        elegido = rejilla[0]
        advertencia = (
            f"Con ningún μ de la rejilla alcanza el objetivo al menos el {100 * configuracion.exito_calibracion:.0f} % "
            f"de los casos alcanzables: se usa el más pequeño ({decimal(rejilla[0], 'g')})."
        )
    return CalibracionMu(
        elegido, puntos, len(casos), n, len(casos) - n, ya_cumplen, configuracion.exito_calibracion, advertencia,
    )

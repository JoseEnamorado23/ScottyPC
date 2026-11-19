"""Comparador de métodos de prescripción sobre los mismos casos.

Cada método propone una intervención con el MISMO espacio de acciones, restricciones y costos que
el prescriptor; solo cambia cómo la elige:

- **prescriptor**: el optimizador sobre el modelo causal (propaga por el grafo);
- **sin_causalidad**: el mismo optimizador sobre el modelo de referencia (todas las variables), que
  no propaga: mover una acción no cambia sus mediadoras;
- **imitar_exitosos**: lleva cada acción hacia la media (o el estado más frecuente) de los casos de
  train que cumplen el objetivo, dentro de los límites;
- **aleatoria**: un valor al azar dentro de los límites (y del rango de train);
- **sin_intervencion**: no cambia nada (punto de partida).

Y cada intervención se juzga con tres criterios independientes del método:

- el **modelo causal** (¿alcanza el objetivo según el grafo?);
- el **modelo de referencia** sobre el perfil propagado (el juez de ``requiere_revision``);
- los **vecinos** de train (resultado observado de los casos parecidos con esas acciones).

Ningún criterio es la verdad: el causal favorece al prescriptor y la referencia al método sin
causalidad; los vecinos son el árbitro observacional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import t as student_t
from scipy.stats import wilcoxon

from pcapp_nucleo.causal.contrafactuales import Caso
from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.prescripcion.configuracion import ConfiguracionPrescripcion
from pcapp_nucleo.prescripcion.evidencia import TEXTO_EVIDENCIA, IndiceVecinos, evidencia_caso
from pcapp_nucleo.prescripcion.optimizadores import Optimizador, Solucion
from pcapp_nucleo.prescripcion.prescriptor import (
    _perfil_referencia, fijadas_de, resolver, semilla_de_caso, valores_actuales,
)
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion
from pcapp_nucleo.prescripcion.referencia import ModeloReferencia

PRESCRIPTOR, SIN_CAUSALIDAD, IMITAR, ALEATORIA, SIN_INTERVENCION = (
    "prescriptor", "sin_causalidad", "imitar_exitosos", "aleatoria", "sin_intervencion",
)
METODOS = (PRESCRIPTOR, SIN_CAUSALIDAD, IMITAR, ALEATORIA, SIN_INTERVENCION)
NOMBRES_METODOS = {
    PRESCRIPTOR: "Prescriptor causal",
    SIN_CAUSALIDAD: "Sin causalidad (modelo de referencia)",
    IMITAR: "Imitar a los casos exitosos",
    ALEATORIA: "Intervención aleatoria",
    SIN_INTERVENCION: "Sin intervención",
}
TEXTO_COMPARADOR = (
    "Todos los métodos usan las mismas acciones, límites y costos. El modelo causal favorece al prescriptor y "
    "el modelo de referencia al método sin causalidad, porque cada uno optimiza con su propio modelo; los "
    "vecinos de train (resultado observado) son el árbitro común. La p compara, caso a caso, el resultado "
    "observado en los vecinos de cada método con el del prescriptor (Wilcoxon de rangos con signo)."
)


class ProblemaSinCausalidad(ProblemaPrescripcion):
    """Mismas acciones y restricciones que el problema causal; el logro lo da el modelo de
    referencia con las acciones cambiadas y todo lo demás como en el caso (sin propagar)."""

    def __init__(
        self, modelo: ModeloCausal, caso: Caso, configuracion: ConfiguracionPrescripcion, mu: float,
        referencia: ModeloReferencia, fila: pd.DataFrame | None, abduccion=None,
    ) -> None:
        super().__init__(modelo, caso, configuracion, mu, abduccion)
        actuales = valores_actuales(self)
        base = {**dict(zip(referencia.columnas, referencia.medianas)), **actuales}
        if fila is not None:
            base.update({c: float(fila.iloc[0][c]) for c in referencia.columnas if c in fila.columns and pd.notna(fila.iloc[0][c])})
        self._x = np.array([base.get(c, m) for c, m in zip(referencia.columnas, referencia.medianas)], dtype=float)
        self._w = np.asarray(referencia.coeficientes, dtype=float)
        self._b = float(referencia.intercepto)
        self._binario = referencia.binario
        self._posicion = {c: i for i, c in enumerate(referencia.columnas)}

    def p(self, D: np.ndarray, estados: np.ndarray, suave: bool = False) -> np.ndarray:
        D, estados = self.matrices(D, estados)
        X = np.tile(self._x, (D.shape[0], 1))
        for columna, (valores, mascara) in self.fijadas(D, estados).items():
            j = self._posicion.get(columna)
            if j is not None:
                X[:, j] = np.where(mascara, valores, X[:, j])
        eta = X @ self._w + self._b
        return self.a_clase(expit(eta) if self._binario else eta)


# --- Intervenciones de cada método ----------------------------------------------------------------


def _sin_intervencion(problema: ProblemaPrescripcion) -> Solucion:
    return Solucion(np.zeros(problema.k), problema.actual, 0.0, 0.0)


def _rango_train(problema: ProblemaPrescripcion) -> tuple[np.ndarray, np.ndarray]:
    """Límites de d dentro de las restricciones y del rango de train."""
    info = problema.modelo.info_variables
    lo = np.array([max(a.lo, (info[a.columna]["minimo"] - a.x0) / a.escala) for a in problema.continuas])
    hi = np.array([min(a.hi, (info[a.columna]["maximo"] - a.x0) / a.escala) for a in problema.continuas])
    return np.minimum(lo, hi), np.maximum(lo, hi)


def _aleatoria(problema: ProblemaPrescripcion, semilla: np.random.SeedSequence) -> Solucion:
    rng = np.random.default_rng(semilla.spawn(2)[1])
    lo, hi = _rango_train(problema)
    d = rng.uniform(lo, hi) if problema.k else np.zeros(0)
    estado = tuple(int(rng.integers(len(a.estados))) for a in problema.discretas)
    return Solucion(problema.proyectar(d), estado, 0.0, 0.0)


def medias_exitosos(indice: IndiceVecinos) -> dict[str, float] | None:
    """Media (unidades preparadas) de cada columna de acción entre los casos de train que cumplen."""
    if not indice.exito.any():
        return None
    columnas = indice.columnas
    exitosos = indice.X[indice.exito] * indice.escalas
    return {c: float(exitosos[:, columnas.index(c)].mean()) for c in indice.columnas_accion}


def _imitar(problema: ProblemaPrescripcion, medias: dict[str, float]) -> Solucion:
    d = np.array([(medias.get(a.columna, a.x0) - a.x0) / a.escala for a in problema.continuas])
    estado = []
    for a in problema.discretas:
        objetivo = np.array([medias.get(c, 0.0) for c in a.columnas])
        distancias = [np.sum((np.array([e[c] for c in a.columnas]) - objetivo) ** 2) for e in a.estados]
        estado.append(int(np.argmin(distancias)))
    return Solucion(problema.proyectar(d) if problema.k else np.zeros(0), tuple(estado), 0.0, 0.0)


# --- Juicio de una intervención -------------------------------------------------------------------


@dataclass(frozen=True)
class Juicio:
    alcanzado_causal: bool
    alcanzado_referencia: bool | None
    valor_vecinos: float | None
    actual_vecinos: float | None
    cumple_vecinos: bool | None
    con_respaldo: bool | None
    mejora_vecinos: float | None
    costo: float
    acciones: int


def juzgar(
    problema: ProblemaPrescripcion, solucion: Solucion, referencia: ModeloReferencia | None,
    fila: pd.DataFrame | None, vecinos: IndiceVecinos | None,
) -> Juicio:
    D, E = problema.matrices([solucion.d], [solucion.estado])
    alcanzado = problema.alcanzado(float(problema.p(D, E)[0]))
    fijadas = fijadas_de(problema, solucion)
    alcanzado_ref = None
    if referencia is not None:
        perfil = _perfil_referencia(problema, fila, fijadas, referencia)
        alcanzado_ref = problema.alcanzado(float(problema.a_clase(referencia.predecir(perfil))[0]))
    evidencia = (
        evidencia_caso(vecinos, valores_actuales(problema), fijadas, problema.modelo.objetivo, problema.clase_positiva)
        if vecinos is not None else None
    )
    acciones = int(np.count_nonzero(solucion.d)) + sum(
        1 for j, a in enumerate(problema.discretas) if solucion.estado[j] != a.actual
    )
    return Juicio(
        alcanzado, alcanzado_ref,
        evidencia.prescrita.valor if evidencia else None,
        evidencia.actual.valor if evidencia else None,
        evidencia.prescrita.cumple if evidencia else None,
        evidencia.prescrita.con_respaldo if evidencia else None,
        evidencia.mejora if evidencia else None,
        float(problema.con_mu(1.0).penalizacion(D, E)[0]), acciones,
    )


def comparar_caso(
    modelo: ModeloCausal, caso: Caso, configuracion: ConfiguracionPrescripcion, problema: ProblemaPrescripcion,
    solucion_prescriptor: Solucion, referencia: ModeloReferencia | None, fila: pd.DataFrame | None,
    vecinos: IndiceVecinos | None, medias: dict[str, float] | None, optimizador: Optimizador,
) -> dict[str, dict[str, Any]]:
    """Juicio de cada método en un caso (diccionarios serializables)."""
    semilla = semilla_de_caso(modelo, caso)
    soluciones: dict[str, Solucion] = {
        PRESCRIPTOR: solucion_prescriptor,
        ALEATORIA: _aleatoria(problema, semilla),
        SIN_INTERVENCION: _sin_intervencion(problema),
    }
    if referencia is not None:
        sin_causalidad = ProblemaSinCausalidad(modelo, caso, configuracion, problema.mu, referencia, fila, problema.abduccion)
        soluciones[SIN_CAUSALIDAD] = resolver(sin_causalidad, optimizador, semilla)[0]
    if medias is not None:
        soluciones[IMITAR] = _imitar(problema, medias)
    return {
        metodo: juzgar(problema, soluciones[metodo], referencia, fila, vecinos).__dict__
        for metodo in METODOS if metodo in soluciones
    }


# --- Resumen ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MetodoComparado:
    metodo: str
    nombre: str
    casos: int
    tasa_exito_causal: float
    tasa_exito_referencia: float | None
    porcentaje_con_respaldo: float | None
    tasa_cumple_vecinos: float | None
    valor_vecinos_medio: float | None
    mejora_vecinos_media: float | None
    p_valor_frente_prescriptor: float | None
    costo_medio: float
    acciones_medias: float


@dataclass(frozen=True)
class ResumenEvidencia:
    """Evidencia de vecinos del prescriptor, sobre los casos cuya prescripción tiene respaldo."""

    k: int
    umbral_respaldo: float
    medida: str  # "proporcion" (clase de interés) | "media"
    casos: int
    con_respaldo: int
    porcentaje_con_respaldo: float
    porcentaje_cumple: float | None
    valor_prescrita_medio: float | None
    valor_actual_medio: float | None
    mejora_media: float | None
    intervalo_mejora: list[float] | None
    porcentaje_mejora_positiva: float | None
    p_valor: float | None
    coincidencia_modelo: float | None  # % en que el modelo causal y los vecinos coinciden en si se cumple
    texto: str = TEXTO_EVIDENCIA


def _media(x: list[float]) -> float | None:
    return float(np.mean(x)) if x else None


def _p_wilcoxon(diferencias: np.ndarray) -> float | None:
    if len(diferencias) == 0:
        return None
    if not np.any(np.abs(diferencias) > 1e-12):
        return 1.0
    return float(wilcoxon(diferencias, zero_method="zsplit").pvalue)


def _intervalo(x: np.ndarray) -> list[float] | None:
    if len(x) < 2:
        return None
    media, error = float(np.mean(x)), float(np.std(x, ddof=1) / np.sqrt(len(x)))
    margen = float(student_t.ppf(0.975, len(x) - 1)) * error
    return [media - margen, media + margen]


def resumir_comparador(registros: list[dict[str, dict[str, Any]]], indice: IndiceVecinos | None) -> list[MetodoComparado]:
    salida = []
    for metodo in METODOS:
        filas = [r[metodo] for r in registros if metodo in r]
        if not filas:
            continue
        con_vecinos = [f for f in filas if f["valor_vecinos"] is not None]
        p = None
        if metodo != PRESCRIPTOR and indice is not None:
            pares = [
                (r[metodo]["valor_vecinos"], r[PRESCRIPTOR]["valor_vecinos"]) for r in registros
                if metodo in r and r[metodo]["valor_vecinos"] is not None and r[PRESCRIPTOR]["valor_vecinos"] is not None
            ]
            p = _p_wilcoxon(np.array([indice.favorable(b - a) for a, b in pares]))
        referencias = [f["alcanzado_referencia"] for f in filas if f["alcanzado_referencia"] is not None]
        salida.append(MetodoComparado(
            metodo, NOMBRES_METODOS[metodo], len(filas),
            float(np.mean([f["alcanzado_causal"] for f in filas])),
            _media([float(x) for x in referencias]),
            100.0 * float(np.mean([f["con_respaldo"] for f in con_vecinos])) if con_vecinos else None,
            _media([float(f["cumple_vecinos"]) for f in con_vecinos]),
            _media([f["valor_vecinos"] for f in con_vecinos]),
            _media([f["mejora_vecinos"] for f in con_vecinos]),
            p,
            float(np.mean([f["costo"] for f in filas])),
            float(np.mean([f["acciones"] for f in filas])),
        ))
    return salida


def resumir_evidencia(registros: list[dict[str, dict[str, Any]]], indice: IndiceVecinos | None) -> ResumenEvidencia | None:
    if indice is None or not registros:
        return None
    filas = [r[PRESCRIPTOR] for r in registros]
    apoyadas = [f for f in filas if f["con_respaldo"]]
    mejoras = np.array([f["mejora_vecinos"] for f in apoyadas], dtype=float)
    coinciden = [f["alcanzado_causal"] == f["cumple_vecinos"] for f in apoyadas]
    return ResumenEvidencia(
        k=indice.k,
        umbral_respaldo=indice.umbral_respaldo,
        medida="proporcion" if indice.binario else "media",
        casos=len(filas),
        con_respaldo=len(apoyadas),
        porcentaje_con_respaldo=100.0 * len(apoyadas) / len(filas),
        porcentaje_cumple=100.0 * float(np.mean([f["cumple_vecinos"] for f in apoyadas])) if apoyadas else None,
        valor_prescrita_medio=_media([f["valor_vecinos"] for f in apoyadas]),
        valor_actual_medio=_media([f["actual_vecinos"] for f in apoyadas]),
        mejora_media=float(np.mean(mejoras)) if len(mejoras) else None,
        intervalo_mejora=_intervalo(mejoras),
        porcentaje_mejora_positiva=100.0 * float(np.mean(mejoras > 1e-12)) if len(mejoras) else None,
        p_valor=_p_wilcoxon(mejoras),
        coincidencia_modelo=100.0 * float(np.mean(coinciden)) if coinciden else None,
    )

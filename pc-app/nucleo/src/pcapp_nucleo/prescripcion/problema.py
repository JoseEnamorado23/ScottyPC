"""Problema de prescripción de un caso: acciones, restricciones y función objetivo.

Escala normalizada: una acción continua se mueve en d = (x − x₀) / rango de train (unidades
preparadas), así que el costo por unidad es comparable entre variables. Las acciones discretas
(binarias, ordinales con pocos niveles y categorías one-hot como grupo) eligen uno de sus
estados permitidos; cambiar de estado cuesta su costo.

    pérdida = max(0, brecha)² + μ · (Σ costo_i · |d_i| + Σ costo_j · [estado_j ≠ actual_j])

con brecha = deseado − p (subir) o p − deseado (bajar), dividida por el rango del objetivo si es
continuo. p sale de la propagación completa por el grafo con la abducción del caso.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
from scipy.special import expit

from pcapp_nucleo.causal.contrafactuales import Abduccion, Caso, abducir
from pcapp_nucleo.causal.modelo import BINARIA, OBJETIVO, RAIZ, ModeloCausal
from pcapp_nucleo.causal.unidades import CATEGORICA, NUMERICA, ORDINAL, ErrorUnidades
from pcapp_nucleo.prescripcion.configuracion import (
    AMBAS, BAJAR, MAXIMO_NIVELES_DISCRETOS, SUBIR, ConfiguracionAccion, ConfiguracionPrescripcion, _igual,
    columnas_de, variables_prescriptivas,
)

MAXIMO_COMBINACIONES = 16
LIMITE, CAMBIO_MAXIMO, DIRECCION = "limite", "cambio_maximo", "direccion"


class EvaluadorCaso:
    """Propagación vectorizada: evalúa muchas combinaciones de acciones en una sola llamada.

    ``fijadas``: columna → (valores (m,), máscara (m,)); donde la máscara es falsa la columna no
    se interviene. Con ``suave`` las intermedias binarias usan σ((η + U)/τ) en vez de
    1[η + U > 0] (para que el gradiente no sea cero); el resultado final se evalúa siempre exacto.
    """

    def __init__(
        self, modelo: ModeloCausal, abduccion: Abduccion, tau: float, acciones: list[str] | None = None
    ) -> None:
        self.modelo, self.abduccion, self.tau = modelo, abduccion, tau
        self.evaluaciones = 0
        # Solo cambian las columnas intervenibles y sus descendientes; el resto conserva su
        # valor factual (no hace falta recalcular sus mecanismos).
        self.afectables = set(modelo.variables) if acciones is None else _descendientes(modelo, acciones)

    def _factual(self, v: str, m: int, suave: bool) -> np.ndarray:
        # Una variable que no puede cambiar conserva su valor exacto también en la versión suave:
        # el suavizado solo hace falta donde pasa el efecto de una acción.
        return np.broadcast_to(self.abduccion.antes[v], (m, self.abduccion.muestras))

    def valores(
        self, fijadas: dict[str, tuple[np.ndarray, np.ndarray]], m: int, suave: bool = False
    ) -> dict[str, np.ndarray]:
        modelo, abd = self.modelo, self.abduccion
        S = abd.muestras
        valores: dict[str, np.ndarray] = {}
        for v in modelo.variables:
            rol = modelo.info_variables[v]["rol"]
            factual = None if v in self.afectables else self._factual(v, m, suave)
            if rol == RAIZ:
                actual = np.broadcast_to(abd.antes[v], (m, S))
            elif factual is not None:
                actual = factual
            else:
                X = np.column_stack([valores[p].reshape(-1) for p in modelo.padres[v]])
                mecanismo = modelo.mecanismos[v]
                if rol == OBJETIVO:
                    actual = mecanismo.media(X).reshape(m, S)
                else:
                    eta = mecanismo.eta(X).reshape(m, S) + abd.residuos[v]
                    if modelo.tipo(v) == BINARIA:
                        actual = expit(eta / self.tau) if suave else (eta > 0).astype(float)
                    else:
                        actual = eta
            if v in fijadas:
                fijos, mascara = fijadas[v]
                actual = np.where(mascara[:, None], fijos[:, None], actual)
            valores[v] = actual
        self.evaluaciones += m
        return valores

    def objetivo(self, fijadas, m: int, suave: bool = False) -> np.ndarray:
        return self.valores(fijadas, m, suave)[self.modelo.objetivo].mean(axis=1)


def _descendientes(modelo: ModeloCausal, columnas: list[str]) -> set[str]:
    """Columnas y todo lo que depende de ellas dentro del subgrafo."""
    afectables = set(columnas)
    for v in modelo.variables:  # orden topológico
        if any(p in afectables for p in modelo.padres[v]):
            afectables.add(v)
    return afectables


@dataclass
class AccionContinua:
    nombre: str
    columna: str
    x0: float
    escala: float
    lo: float
    hi: float
    costo: float
    motivo_lo: str | None = None
    motivo_hi: str | None = None


@dataclass
class AccionDiscreta:
    nombre: str
    columnas: list[str]
    estados: list[dict[str, float]]
    etiquetas: list[Any]
    actual: int
    costo: float
    excluidos: list[dict[str, float]] = field(default_factory=list)  # estados no permitidos


def _preparado(modelo: ModeloCausal, columna: str, valor: float, respaldo: float) -> float:
    try:
        return modelo.unidades.a_preparada(columna, valor)
    except ErrorUnidades:
        return respaldo


def _accion_continua(
    modelo: ModeloCausal, nombre: str, x0: float, a: ConfiguracionAccion
) -> AccionContinua:
    info = modelo.info_variables[nombre]
    escala = max(info["maximo"] - info["minimo"], 1e-12)
    u = modelo.unidades
    x0o = u.a_original_numerico(nombre, x0)
    bajos, altos = [], []
    if a.minimo is not None:
        bajos.append((a.minimo, LIMITE))
    if a.maximo is not None:
        altos.append((a.maximo, LIMITE))
    if a.cambio_maximo is not None:
        bajos.append((x0o - a.cambio_maximo, CAMBIO_MAXIMO))
        altos.append((x0o + a.cambio_maximo, CAMBIO_MAXIMO))
    if a.direccion == SUBIR:
        bajos.append((x0o, DIRECCION))
    elif a.direccion == BAJAR:
        altos.append((x0o, DIRECCION))
    bajo = max(bajos, key=lambda b: b[0]) if bajos else (None, None)
    alto = min(altos, key=lambda b: b[0]) if altos else (None, None)
    lo = (_preparado(modelo, nombre, bajo[0], x0) - x0) / escala if bajo[0] is not None else -10.0
    hi = (_preparado(modelo, nombre, alto[0], x0) - x0) / escala if alto[0] is not None else 10.0
    if lo > hi:  # restricciones incompatibles: la variable no puede cambiar
        lo = hi = 0.0
    return AccionContinua(nombre, nombre, x0, escala, lo, hi, a.costo, bajo[1], alto[1])


def _codigo_preparado(modelo: ModeloCausal, columna: str, etiqueta: Any) -> float:
    return modelo.unidades.a_preparada(columna, etiqueta)


def _accion_discreta(
    modelo: ModeloCausal, nombre: str, caso_valores: dict[str, float], a: ConfiguracionAccion
) -> AccionDiscreta | None:
    u = modelo.unidades
    permitidos = a.estados_permitidos
    if nombre in u.grupos:
        columnas = columnas_de(modelo, nombre)
        grupo = u.grupos[nombre]
        actual_valores = {c: caso_valores.get(c, 0.0) for c in columnas}
        todos = [(cat, {c: x for c, x in u.dummies_de_categoria(nombre, cat).items() if c in columnas}) for cat in grupo.categorias]
    else:
        columnas = [nombre]
        x0 = caso_valores[nombre]
        etiquetas = u.describir(nombre).categorias or [0, 1]
        todos = [(e, {nombre: _codigo_preparado(modelo, nombre, e)}) for e in etiquetas]
        actual_valores = {nombre: x0}
        codigos = {i: u.codigo(nombre, e) for i, (e, _) in enumerate(todos)}
        codigo_actual = u.a_original_numerico(nombre, x0)
        if u.control(nombre) == ORDINAL and a.cambio_maximo is not None:
            todos = [t for i, t in enumerate(todos) if abs(codigos[i] - codigo_actual) <= a.cambio_maximo + 1e-9]
            codigos = {i: u.codigo(nombre, e) for i, (e, _) in enumerate(todos)}
        if a.direccion == SUBIR:
            todos = [t for i, t in enumerate(todos) if codigos[i] >= codigo_actual - 1e-9]
        elif a.direccion == BAJAR:
            todos = [t for i, t in enumerate(todos) if codigos[i] <= codigo_actual + 1e-9]
        if a.minimo is not None or a.maximo is not None:
            todos = [
                t for t in todos
                if (a.minimo is None or u.codigo(nombre, t[0]) >= a.minimo - 1e-9)
                and (a.maximo is None or u.codigo(nombre, t[0]) <= a.maximo + 1e-9)
            ] or todos
    actual = next((i for i, (_, vals) in enumerate(todos) if all(abs(vals[c] - actual_valores[c]) < 1e-9 for c in columnas)), None)
    estados = [vals for _, vals in todos]
    etiquetas = [e for e, _ in todos]
    if actual is None:  # el valor actual no está entre los estados (p. ej. fuera de los límites)
        estados.insert(0, dict(actual_valores))
        etiquetas.insert(0, None)
        actual = 0
    excluidos = []
    if permitidos is not None:
        conservar = [i for i, e in enumerate(etiquetas) if i == actual or any(_igual(e, p) for p in permitidos)]
        excluidos = [estados[i] for i in range(len(estados)) if i not in conservar]
        estados = [estados[i] for i in conservar]
        etiquetas = [etiquetas[i] for i in conservar]
        actual = conservar.index(actual)
    if len(estados) < 2:
        return None
    return AccionDiscreta(nombre, columnas, estados, etiquetas, actual, a.costo, excluidos)


def es_discreta(modelo: ModeloCausal, nombre: str) -> bool:
    u = modelo.unidades
    if nombre in u.grupos:
        return True
    control = u.control(nombre)
    if control == CATEGORICA:
        return True
    if control == ORDINAL:
        return len(u.mapeo(nombre) or []) <= MAXIMO_NIVELES_DISCRETOS
    return modelo.tipo(nombre) == BINARIA


class ProblemaPrescripcion:
    def __init__(
        self, modelo: ModeloCausal, caso: Caso, configuracion: ConfiguracionPrescripcion, mu: float,
        abduccion: Abduccion | None = None,
    ) -> None:
        self.modelo, self.caso, self.configuracion, self.mu = modelo, caso, configuracion, float(mu)
        self.abduccion = abduccion or abducir(modelo, caso)
        valores_caso = {c: float(np.mean(self.abduccion.antes[c])) for c in modelo.variables if c != modelo.objetivo}
        self.continuas: list[AccionContinua] = []
        self.discretas: list[AccionDiscreta] = []
        for nombre in variables_prescriptivas(modelo, configuracion.modificables).prescriptivas:
            accion = configuracion.acciones.get(nombre) or ConfiguracionAccion(nombre)
            if not accion.permitida:
                continue
            if es_discreta(modelo, nombre):
                discreta = _accion_discreta(modelo, nombre, valores_caso, accion)
                if discreta is not None:
                    self.discretas.append(discreta)
            else:
                self.continuas.append(_accion_continua(modelo, nombre, valores_caso[nombre], accion))
        columnas_acciones = [a.columna for a in self.continuas] + [c for a in self.discretas for c in a.columnas]
        self.evaluador = EvaluadorCaso(modelo, self.abduccion, configuracion.tau_suavizado, columnas_acciones)
        self.lo =np.array([a.lo for a in self.continuas])
        self.hi = np.array([a.hi for a in self.continuas])
        self.costos = np.array([a.costo for a in self.continuas])
        self.actual = tuple(a.actual for a in self.discretas)
        objetivo = configuracion.objetivo
        self.direccion = objetivo.direccion  # explícita (la elige el usuario), sin heurística
        # Binario: p es la probabilidad de la clase de interés (clase_positiva).
        self.clase_positiva = int(objetivo.clase_positiva) if modelo.binario else 1
        if modelo.binario:
            self.deseado, self.escala_objetivo = float(objetivo.valor), 1.0
        else:
            info = modelo.info_variables[modelo.objetivo]
            self.deseado = modelo.unidades.a_preparada(modelo.objetivo, objetivo.valor)
            self.escala_objetivo = max(info["maximo"] - info["minimo"], 1e-12)

    # --- Espacio de acciones -----------------------------------------------------------------

    @property
    def k(self) -> int:
        return len(self.continuas)

    def combinaciones(self) -> list[tuple[int, ...]] | None:
        """Todas las combinaciones de estados discretos, o ``None`` si son más de 16."""
        total = math.prod(len(a.estados) for a in self.discretas) if self.discretas else 1
        if total > MAXIMO_COMBINACIONES:
            return None
        return list(itertools.product(*[range(len(a.estados)) for a in self.discretas]))

    def proyectar(self, D: np.ndarray) -> np.ndarray:
        return np.clip(D, self.lo, self.hi)

    def con_mu(self, mu: float) -> ProblemaPrescripcion:
        copia = object.__new__(ProblemaPrescripcion)
        copia.__dict__.update(self.__dict__)
        copia.mu = float(mu)
        return copia

    # --- Evaluación --------------------------------------------------------------------------

    def fijadas(self, D: np.ndarray, estados: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        m = D.shape[0]
        fijadas: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for i, a in enumerate(self.continuas):
            fijadas[a.columna] = (a.x0 + D[:, i] * a.escala, D[:, i] != 0)
        for j, a in enumerate(self.discretas):
            cambia = estados[:, j] != a.actual
            for c in a.columnas:
                valores = np.array([a.estados[e][c] for e in estados[:, j]]) if m else np.zeros(0)
                fijadas[c] = (valores, cambia)
        return fijadas

    def matrices(self, D: Any, estados: Any) -> tuple[np.ndarray, np.ndarray]:
        """Acciones como matrices (m, k) y (m, discretas), aunque alguna dimensión sea 0."""
        if isinstance(estados, np.ndarray) and estados.ndim == 2:
            m = estados.shape[0]
        elif isinstance(D, np.ndarray) and D.ndim == 2:
            m = D.shape[0]
        else:
            m = len(estados)  # listas de filas (una por candidato)
        return (
            np.asarray(D, dtype=float).reshape(m, self.k),
            np.asarray(estados, dtype=int).reshape(m, len(self.discretas)),
        )

    def a_clase(self, p1: np.ndarray) -> np.ndarray:
        """Probabilidad de la clase 1 (la del modelo) → probabilidad de la clase de interés."""
        return p1 if self.clase_positiva == 1 else 1.0 - p1

    def p(self, D: np.ndarray, estados: np.ndarray, suave: bool = False) -> np.ndarray:
        D, estados = self.matrices(D, estados)
        return self.a_clase(self.evaluador.objetivo(self.fijadas(D, estados), D.shape[0], suave))

    def brecha(self, p: np.ndarray) -> np.ndarray:
        diferencia = (self.deseado - p) if self.direccion == SUBIR else (p - self.deseado)
        return diferencia / self.escala_objetivo

    def penalizacion(self, D: np.ndarray, estados: np.ndarray) -> np.ndarray:
        continua = np.abs(D) @ self.costos if self.k else np.zeros(D.shape[0])
        discreta = sum(
            (estados[:, j] != a.actual) * a.costo for j, a in enumerate(self.discretas)
        ) if self.discretas else 0.0
        return self.mu * (continua + discreta)

    def perdida(self, D: np.ndarray, estados: np.ndarray, suave: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """(pérdida, p) de cada fila."""
        D, estados = self.matrices(D, estados)
        p = self.p(D, estados, suave)
        return np.maximum(0.0, self.brecha(p)) ** 2 + self.penalizacion(D, estados), p

    def alcanzado(self, p: float) -> bool:
        return float(self.brecha(np.array([p]))[0]) <= 1e-12

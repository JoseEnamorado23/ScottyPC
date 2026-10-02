"""Optimizadores de la prescripción: gradiente proximal y genético, con la misma interfaz.

Ambos reciben el mismo ``ProblemaPrescripcion`` (función objetivo y restricciones) y devuelven
una ``Solucion``. Después, los dos pasan por el mismo post-proceso:

- ``pulir``: vuelve a cero cada acción cuya retirada no empeora la pérdida (así el porcentaje de
  acciones en cero es comparable entre optimizadores);
- ``cerrar``: con la penalización, el óptimo se queda un poco antes del objetivo; si con el mismo
  soporte (las mismas acciones, en la misma dirección) se puede alcanzar sin salir de las
  restricciones, se escala hasta el mínimo que lo alcanza (evaluación exacta).

Las dos implementaciones son deterministas con la misma semilla.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Protocol

import numpy as np

from pcapp_nucleo.prescripcion.configuracion import GENETICO, GRADIENTE, ConfiguracionPrescripcion
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion

PASO_DIFERENCIAS = 1e-4
MAXIMAS_RONDAS_COORDENADAS = 10


@dataclass(frozen=True)
class Solucion:
    d: np.ndarray
    estado: tuple[int, ...]
    perdida: float
    p: float
    iteraciones: int = 0


class Optimizador(Protocol):
    nombre: str

    def optimizar(
        self, problema: ProblemaPrescripcion, semilla: np.random.SeedSequence, inicio: Solucion | None = None
    ) -> Solucion: ...


def _evaluar(problema: ProblemaPrescripcion, d: np.ndarray, estado: tuple[int, ...], suave: bool = True) -> Solucion:
    perdida, p = problema.perdida([d], [estado], suave)
    return Solucion(d.copy(), tuple(estado), float(perdida[0]), float(p[0]))


# --- Gradiente proximal ------------------------------------------------------------------------


class GradienteProximal:
    """Diferencias finitas + paso proximal (soft-threshold) + proyección a la caja.

    Las acciones discretas se enumeran (≤ 16 combinaciones, optimizando las continuas en cada
    una) o se recorren por coordenadas. Multiarranque: el valor actual (y ``inicio``, si se da) y
    ``arranques_aleatorios`` puntos al azar dentro de la caja.
    """

    nombre = GRADIENTE

    def __init__(self, arranques_aleatorios: int = 4, iteraciones_maximas: int = 300, tolerancia: float = 1e-8) -> None:
        self.arranques_aleatorios, self.iteraciones_maximas, self.tolerancia = (
            arranques_aleatorios, iteraciones_maximas, tolerancia,
        )

    @classmethod
    def desde(cls, c: ConfiguracionPrescripcion, arranques_aleatorios: int | None = None) -> GradienteProximal:
        return cls(c.arranques_aleatorios if arranques_aleatorios is None else arranques_aleatorios,
                   c.iteraciones_maximas, c.tolerancia)

    def optimizar(self, problema, semilla, inicio=None) -> Solucion:
        rng = np.random.default_rng(semilla)
        combinaciones = problema.combinaciones()
        if combinaciones is not None:
            soluciones = [self._continuas(problema, estado, rng, inicio) for estado in combinaciones]
            return min(soluciones, key=lambda s: s.perdida)
        return self._coordenadas(problema, rng, inicio)

    def _arranques(self, problema, estado, rng, inicio) -> list[np.ndarray]:
        arranques = [np.zeros(problema.k)]
        if inicio is not None and inicio.estado == tuple(estado):
            arranques.append(np.asarray(inicio.d, dtype=float))
        for _ in range(self.arranques_aleatorios if problema.k else 0):
            arranques.append(rng.uniform(problema.lo, problema.hi))
        return arranques

    def _continuas(self, problema, estado, rng, inicio) -> Solucion:
        return min(
            (self.descenso(problema, estado, d0) for d0 in self._arranques(problema, estado, rng, inicio)),
            key=lambda s: s.perdida,
        )

    def _coordenadas(self, problema, rng, inicio) -> Solucion:
        mejor = self._continuas(problema, problema.actual, rng, inicio)
        for _ in range(MAXIMAS_RONDAS_COORDENADAS):
            mejoro = False
            for j, accion in enumerate(problema.discretas):
                for s in range(len(accion.estados)):
                    if s == mejor.estado[j]:
                        continue
                    estado = list(mejor.estado)
                    estado[j] = s
                    candidata = self.descenso(problema, tuple(estado), mejor.d)
                    if candidata.perdida < mejor.perdida - 1e-12:
                        mejor, mejoro = candidata, True
            if not mejoro:
                break
        return mejor

    def _gradiente(self, problema, d, estado) -> np.ndarray:
        """Gradiente de la parte suave (max(0, brecha)²) por diferencias finitas, en un lote."""
        k = problema.k
        pasos = np.where(d + PASO_DIFERENCIAS <= problema.hi, PASO_DIFERENCIAS, -PASO_DIFERENCIAS)
        D = np.repeat(d[None, :], k + 1, axis=0)
        D[np.arange(1, k + 1), np.arange(k)] += pasos
        p = problema.p(D, [estado] * (k + 1), suave=True)
        suave = np.maximum(0.0, problema.brecha(p)) ** 2
        return (suave[1:] - suave[0]) / pasos

    def descenso(self, problema: ProblemaPrescripcion, estado, d0: np.ndarray) -> Solucion:
        estado = tuple(estado)
        d = problema.proyectar(np.asarray(d0, dtype=float))
        actual = _evaluar(problema, d, estado)
        if problema.k == 0:
            return actual
        umbrales = problema.mu * problema.costos
        paso = 1.0
        iteraciones = 0
        for iteraciones in range(1, self.iteraciones_maximas + 1):
            g = self._gradiente(problema, actual.d, estado)
            while True:
                z = actual.d - paso * g
                candidata = problema.proyectar(np.sign(z) * np.maximum(np.abs(z) - paso * umbrales, 0.0))
                nueva = _evaluar(problema, candidata, estado)
                if nueva.perdida <= actual.perdida - 1e-14 or paso < 1e-10:
                    break
                paso *= 0.5
            if nueva.perdida > actual.perdida - 1e-14:
                break
            mejora = actual.perdida - nueva.perdida
            actual = nueva
            paso = min(paso * 2.0, 50.0)
            if mejora < self.tolerancia:
                break
        return replace(actual, iteraciones=iteraciones)


# --- Genético ------------------------------------------------------------------------------------


class Genetico:
    """Población, torneo, cruce BLX-α (continuas) y uniforme (discretas), mutación y elitismo.

    Los individuos que salen de la caja se reparan recortándolos. La población se evalúa en un
    solo lote. El primer individuo es «no cambiar nada» (y ``inicio``, si se da).
    """

    nombre = GENETICO

    def __init__(self, poblacion=40, generaciones=60, alfa=0.5, probabilidad_mutacion=0.2, elite=2) -> None:
        self.poblacion, self.generaciones, self.alfa = poblacion, generaciones, alfa
        self.probabilidad_mutacion, self.elite = probabilidad_mutacion, elite

    @classmethod
    def desde(cls, c: ConfiguracionPrescripcion) -> Genetico:
        return cls(c.poblacion, c.generaciones, c.alfa_blx, c.probabilidad_mutacion, c.elite)

    def optimizar(self, problema, semilla, inicio=None) -> Solucion:
        rng = np.random.default_rng(semilla)
        P, k = self.poblacion, problema.k
        tamanos = np.array([len(a.estados) for a in problema.discretas], dtype=int)
        D = rng.uniform(problema.lo, problema.hi, size=(P, k)) if k else np.zeros((P, 0))
        E = rng.integers(0, tamanos, size=(P, len(tamanos))) if len(tamanos) else np.zeros((P, 0), dtype=int)
        D[0] = 0.0
        E[0] = problema.actual
        if inicio is not None:
            D[1], E[1] = problema.proyectar(inicio.d), inicio.estado
        perdidas, _ = problema.perdida(D, E)
        for _ in range(self.generaciones):
            orden = np.argsort(perdidas, kind="stable")
            hijos_D, hijos_E = [], []
            while len(hijos_D) < P - self.elite:
                a, b = self._torneo(perdidas, rng), self._torneo(perdidas, rng)
                bajo, alto = np.minimum(D[a], D[b]), np.maximum(D[a], D[b])
                amplitud = alto - bajo
                hijo_d = rng.uniform(bajo - self.alfa * amplitud, alto + self.alfa * amplitud) if k else np.zeros(0)
                hijo_e = np.where(rng.random(len(tamanos)) < 0.5, E[a], E[b]) if len(tamanos) else np.zeros(0, dtype=int)
                if k:
                    muta = rng.random(k) < self.probabilidad_mutacion
                    hijo_d = hijo_d + muta * rng.normal(0.0, 0.1 * (problema.hi - problema.lo + 1e-12))
                    # Mutación hacia «sin cambio» para que la intervención mínima sea alcanzable.
                    hijo_d = np.where(rng.random(k) < self.probabilidad_mutacion / 2, 0.0, hijo_d)
                if len(tamanos):
                    muta = rng.random(len(tamanos)) < self.probabilidad_mutacion
                    hijo_e = np.where(muta, rng.integers(0, tamanos), hijo_e)
                hijos_D.append(problema.proyectar(hijo_d))
                hijos_E.append(hijo_e)
            hijos_D, hijos_E = problema.matrices(hijos_D, hijos_E)
            perdidas_hijos, _ = problema.perdida(hijos_D, hijos_E)
            elite = orden[: self.elite]
            D = np.vstack([D[elite], hijos_D])
            E = np.vstack([E[elite], hijos_E])
            perdidas = np.concatenate([perdidas[elite], perdidas_hijos])
        mejor = int(np.argmin(perdidas))
        return replace(_evaluar(problema, D[mejor], tuple(int(x) for x in E[mejor])), iteraciones=self.generaciones)

    def _torneo(self, perdidas, rng, tamano: int = 3) -> int:
        candidatos = rng.integers(0, len(perdidas), size=tamano)
        return int(candidatos[np.argmin(perdidas[candidatos])])


def crear_optimizador(nombre: str, configuracion: ConfiguracionPrescripcion) -> Optimizador:
    return Genetico.desde(configuracion) if nombre == GENETICO else GradienteProximal.desde(configuracion)


# --- Post-proceso común ----------------------------------------------------------------------------


def pulir(problema: ProblemaPrescripcion, solucion: Solucion) -> Solucion:
    """Quita (una a una, empezando por la que menos empeora) las acciones innecesarias."""
    actual = solucion
    while True:
        candidatos = []
        for i in np.flatnonzero(actual.d != 0):
            d = actual.d.copy()
            d[i] = 0.0
            candidatos.append((d, actual.estado))
        for j, accion in enumerate(problema.discretas):
            if actual.estado[j] != accion.actual:
                estado = list(actual.estado)
                estado[j] = accion.actual
                candidatos.append((actual.d.copy(), tuple(estado)))
        if not candidatos:
            return actual
        D, E = problema.matrices([c[0] for c in candidatos], [c[1] for c in candidatos])
        perdidas, p = problema.perdida(D, E)
        mejor = int(np.argmin(perdidas))
        if perdidas[mejor] > actual.perdida + 1e-12:
            return actual
        actual = Solucion(D[mejor], tuple(int(x) for x in E[mejor]), float(perdidas[mejor]), float(p[mejor]), actual.iteraciones)


def cerrar(problema: ProblemaPrescripcion, solucion: Solucion, iteraciones: int = 40) -> Solucion:
    """Escala las acciones continuas (mismo soporte) hasta el mínimo que alcanza el objetivo."""
    exacta = float(problema.p([solucion.d], [solucion.estado])[0])
    if problema.alcanzado(exacta) or not np.any(solucion.d != 0):
        return solucion
    d = solucion.d
    soporte = d != 0
    tope = np.min(np.where(d[soporte] > 0, problema.hi[soporte] / d[soporte], problema.lo[soporte] / d[soporte]))
    if not tope > 1 + 1e-12:
        return solucion
    estado = [solucion.estado]
    if not problema.alcanzado(float(problema.p([tope * d], estado)[0])):
        return solucion
    bajo, alto = 1.0, float(tope)
    for _ in range(iteraciones):
        medio = (bajo + alto) / 2
        if problema.alcanzado(float(problema.p([medio * d], estado)[0])):
            alto = medio
        else:
            bajo = medio
    return _evaluar(problema, alto * d, solucion.estado)


TOLERANCIA_COSTO_RECORTE = 1e-3


def _costo(problema: ProblemaPrescripcion, s: Solucion) -> float:
    return float(problema.con_mu(1.0).penalizacion(*problema.matrices([s.d], [s.estado]))[0])


def recortar(problema: ProblemaPrescripcion, solucion: Solucion) -> Solucion:
    """Si el objetivo se alcanza, intenta quitar cada acción (de la más barata a la más cara):
    se acepta si, volviendo a cerrar con las restantes, se sigue alcanzando sin que el costo total
    suba más de un 0,1 %. Así no quedan acciones insignificantes (el cierre deja la solución justo en
    la frontera, donde quitar incluso un cambio minúsculo haría fallar por muy poco)."""
    if not problema.alcanzado(float(problema.p([solucion.d], [solucion.estado])[0])):
        return solucion
    actual = solucion
    candidatas = [("c", i, problema.costos[i] * abs(actual.d[i])) for i in np.flatnonzero(actual.d != 0)]
    candidatas += [("d", j, a.costo) for j, a in enumerate(problema.discretas) if actual.estado[j] != a.actual]
    for tipo, indice, _ in sorted(candidatas, key=lambda c: c[2]):
        d, estado = actual.d.copy(), list(actual.estado)
        if tipo == "c":
            d[indice] = 0.0
        else:
            estado[indice] = problema.discretas[indice].actual
        prueba = cerrar(problema, _evaluar(problema, d, tuple(estado)))
        alcanza = problema.alcanzado(float(problema.p([prueba.d], [prueba.estado])[0]))
        if alcanza and _costo(problema, prueba) <= _costo(problema, actual) * (1 + TOLERANCIA_COSTO_RECORTE) + 1e-12:
            actual = prueba
    return actual


def optimizar_caso(
    problema: ProblemaPrescripcion, optimizador: Optimizador, semilla: np.random.SeedSequence,
    inicio: Solucion | None = None,
) -> tuple[Solucion, float]:
    """Optimiza, pule, cierra y recorta; devuelve la solución y los segundos empleados."""
    t = time.perf_counter()
    solucion = cerrar(problema, pulir(problema, optimizador.optimizar(problema, semilla, inicio)))
    solucion = recortar(problema, solucion)
    return solucion, time.perf_counter() - t

"""Ajuste de una solución continua a la rejilla de valores permitidos de cada acción.

Una acción con ``paso`` solo puede proponer valores k·paso (en unidades originales; en las
ordinales, niveles enteros). El optimizador resuelve la relajación continua y aquí se pasa a la
rejilla así:

1. Cada acción se redondea HACIA LA MEJORA (en el sentido de su cambio, al siguiente punto de la
   rejilla), sin salirse de sus límites, de su cambio máximo ni de su dirección.
2. Si no se alcanza el objetivo, búsqueda local: se avanza un punto de la rejilla en la acción
   que más acerca al objetivo, hasta alcanzarlo, no mejorar más o agotar ``MAXIMO_EVALUACIONES``.
3. Si se alcanza, se recorta sobre la rejilla: se retrocede un punto en la acción que más costo
   ahorra mientras se siga alcanzando (con un punto menos desaparece el cambio).

Todo se evalúa con el motor exacto. El resultado nunca tiene valores fuera de la rejilla.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from pcapp_nucleo.causal.unidades import ErrorUnidades
from pcapp_nucleo.prescripcion.configuracion import SUBIR

MAXIMO_EVALUACIONES = 400
TOLERANCIA = 1e-9


class ErrorRejilla(RuntimeError):
    """Error interno: una acción quedó fuera de su rejilla de valores permitidos."""


@dataclass(frozen=True)
class Tramo:
    """Puntos de la rejilla que una acción puede alcanzar en un sentido: ``maximo`` pasos (el
    primer paso es el primer punto k·paso estrictamente más allá del valor actual)."""

    indice: int
    sentido: int
    primero: int  # índice k del primer punto
    maximo: int

    def d(self, problema, pasos: int) -> float:
        """Cambio normalizado de la acción tras ``pasos`` puntos de la rejilla (0 = sin cambio)."""
        if pasos <= 0:
            return 0.0
        a = problema.continuas[self.indice]
        k = self.primero + self.sentido * (pasos - 1)
        return (a.a_preparada(k * a.paso) - a.x0) / a.escala


def _tramo(problema, i: int, sentido: int) -> Tramo:
    a = problema.continuas[i]
    k0 = a.a_original(a.x0) / a.paso
    primero = math.floor(k0 + TOLERANCIA) + 1 if sentido > 0 else math.ceil(k0 - TOLERANCIA) - 1
    limite = a.hi if sentido > 0 else a.lo
    maximo = 0
    if (limite > 0) if sentido > 0 else (limite < 0):
        try:
            kl = a.a_original(a.x0 + limite * a.escala) / a.paso
        except (ValueError, OverflowError):
            kl = None
        if kl is not None:
            ultimo = math.floor(kl + TOLERANCIA) if sentido > 0 else math.ceil(kl - TOLERANCIA)
            maximo = max(0, sentido * (ultimo - primero) + 1)
    # Un punto cuya conversión no existe (p. ej. ≤ 0 con logaritmo) recorta el tramo.
    while maximo > 0:
        try:
            a.a_preparada((primero + sentido * (maximo - 1)) * a.paso)
            break
        except (ErrorUnidades, ValueError):
            maximo -= 1
    return Tramo(i, sentido, primero, maximo)


def _pasos_objetivo(problema, tramo: Tramo, d: float) -> int:
    """Pasos hasta el primer punto de la rejilla que alcanza (o rebasa) el cambio continuo ``d``."""
    a = problema.continuas[tramo.indice]
    k = a.a_original(a.x0 + d * a.escala) / a.paso
    k = math.ceil(k - TOLERANCIA) if tramo.sentido > 0 else math.floor(k + TOLERANCIA)
    return min(tramo.maximo, max(1, tramo.sentido * (k - tramo.primero) + 1))


def ajustar_a_rejilla(problema, solucion, evaluar):
    """Solución sobre la rejilla. Devuelve ``solucion`` sin cambios si ninguna acción cambiada
    tiene paso. ``evaluar(problema, d, estado)`` construye la ``Solucion`` de un ``d``."""
    con_paso = [
        i for i, a in enumerate(problema.continuas)
        if a.paso is not None and a.a_original is not None and solucion.d[i] != 0
    ]
    if not con_paso:
        return solucion
    estado = solucion.estado
    tramos = {i: _tramo(problema, i, 1 if solucion.d[i] > 0 else -1) for i in con_paso}
    claves = list(tramos)
    pasos = np.array(
        [_pasos_objetivo(problema, tramos[i], float(solucion.d[i])) if tramos[i].maximo else 0 for i in claves]
    )
    maximos = np.array([tramos[i].maximo for i in claves])
    fijas = solucion.d.copy()
    for i in claves:
        fijas[i] = 0.0

    def a_d(p: np.ndarray) -> np.ndarray:
        d = fijas.copy()
        for n, i in enumerate(claves):
            d[i] = tramos[i].d(problema, int(p[n]))
        return d

    def logros(lote: list[np.ndarray]) -> np.ndarray:
        D, E = problema.matrices(lote, [estado] * len(lote))
        p = problema.p(D, E)
        return p if problema.direccion == SUBIR else -p

    def costo(d: np.ndarray) -> float:
        return float(problema.con_mu(1.0).penalizacion(*problema.matrices([d], [estado]))[0])

    def alcanza(logro: float) -> bool:
        return problema.alcanzado(logro if problema.direccion == SUBIR else -logro)

    evaluaciones = 1
    d_actual = a_d(pasos)
    logro = float(logros([d_actual])[0])

    # 2. Búsqueda local hacia adelante si no se alcanza.
    while not alcanza(logro) and evaluaciones < MAXIMO_EVALUACIONES:
        candidatos = [n for n in range(len(claves)) if pasos[n] < maximos[n]]
        if not candidatos:
            break
        lote = []
        for n in candidatos:
            p = pasos.copy()
            p[n] += 1
            lote.append(a_d(p))
        valores = logros(lote)
        evaluaciones += len(lote)
        mejor = int(np.argmax(valores))
        if valores[mejor] <= logro + 1e-12:
            break
        pasos[candidatos[mejor]] += 1
        d_actual, logro = lote[mejor], float(valores[mejor])

    # 3. Recorte hacia atrás si se alcanza: se quita el paso que más costo ahorra sin perder el objetivo.
    if alcanza(logro):
        while evaluaciones < MAXIMO_EVALUACIONES:
            candidatos = [n for n in range(len(claves)) if pasos[n] > 0]
            if not candidatos:
                break
            lote = []
            for n in candidatos:
                p = pasos.copy()
                p[n] -= 1
                lote.append(a_d(p))
            valores = logros(lote)
            evaluaciones += len(lote)
            validos = [(costo(lote[k]), k) for k in range(len(lote)) if alcanza(float(valores[k]))]
            if not validos:
                break
            _, k = min(validos)
            pasos[candidatos[k]] -= 1
            d_actual, logro = lote[k], float(valores[k])

    resultado = evaluar(problema, d_actual, estado)
    comprobar_rejilla(problema, resultado.d)
    return resultado


def comprobar_rejilla(problema, d: np.ndarray) -> None:
    """Lanza ``ErrorRejilla`` si alguna acción con paso quedó fuera de su rejilla."""
    for i, a in enumerate(problema.continuas):
        if a.paso is None or a.a_original is None or d[i] == 0:
            continue
        valor = a.a_original(a.x0 + d[i] * a.escala)
        k = valor / a.paso
        if abs(k - round(k)) > 1e-6 * max(1.0, abs(k)):
            raise ErrorRejilla(f"La acción sobre '{a.nombre}' quedó fuera de su rejilla (paso {a.paso:g}): {valor:.10g}.")

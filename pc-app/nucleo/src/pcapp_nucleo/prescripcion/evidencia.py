"""Evidencia de vecinos: ¿qué les pasó, en los datos reales, a los casos parecidos que ya tenían las
acciones prescritas?

Para un caso se buscan los k casos de train más cercanos en dos puntos:

- **con las acciones prescritas**: el perfil del caso (variables del modelo que no son acciones ni
  dependen de ellas) y las acciones con su valor prescrito;
- **con las acciones actuales**: el mismo perfil y las acciones con su valor actual.

Se compara el resultado OBSERVADO de cada grupo (proporción de la clase de interés o media del
objetivo). Las variables que dependen de las acciones (mediadoras) no se usan para buscar: en
los vecinos toman el valor que les dio su propia historia.

    distancia(a, b) = √( media_j ((a_j − b_j) / rango_j)² )

con el rango de train de cada columna (unidades preparadas). Una prescripción **tiene respaldo** si
su k-ésimo vecino está tan cerca como el de un caso típico de train: la distancia al k-ésimo
vecino no supera el percentil 95 de esa misma distancia en una muestra de train.

Es evidencia OBSERVACIONAL: los vecinos pueden diferir en factores no medidos. Indica si la
recomendación tiene respaldo en los datos, no prueba su efecto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.prescripcion.configuracion import SUBIR, ConfiguracionPrescripcion, columnas_de, variables_prescriptivas
from pcapp_nucleo.prescripcion.problema import _descendientes

K_VECINOS = 20
K_MINIMO = 5
PERCENTIL_RESPALDO = 95
MUESTRA_RESPALDO = 500
BLOQUE_DISTANCIAS = 64
TEXTO_EVIDENCIA = (
    "Evidencia OBSERVACIONAL: compara el resultado real de casos de train parecidos que ya tenían valores "
    "cercanos a los prescritos con el de los parecidos que tenían los valores actuales. Los vecinos pueden "
    "diferir en factores no medidos: indica si la recomendación tiene respaldo en los datos, no prueba su efecto."
)


@dataclass(frozen=True)
class IndiceVecinos:
    """Train listo para buscar vecinos (columnas del modelo, escaladas por su rango)."""

    columnas_perfil: list[str]
    columnas_accion: list[str]
    escalas: np.ndarray
    medianas: np.ndarray
    X: np.ndarray  # (n, d) ya dividida por las escalas
    valor: np.ndarray  # (n,) 1/0 si es de la clase de interés (binario) u objetivo en unidades originales
    exito: np.ndarray  # (n,) bool: el caso observado cumple el objetivo
    k: int
    umbral_respaldo: float
    binario: bool
    direccion: str
    deseado: float

    @property
    def columnas(self) -> list[str]:
        return [*self.columnas_perfil, *self.columnas_accion]

    def punto(self, valores: dict[str, float]) -> np.ndarray:
        x = np.array([valores.get(c, np.nan) for c in self.columnas], dtype=float)
        x = np.where(np.isnan(x), self.medianas, x)
        return x / self.escalas

    def vecinos(self, punto: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Índices y distancias de los k más cercanos (ordenados)."""
        distancias = np.sqrt(np.mean((self.X - punto) ** 2, axis=1))
        cercanos = np.argpartition(distancias, self.k - 1)[: self.k]
        cercanos = cercanos[np.argsort(distancias[cercanos], kind="stable")]
        return cercanos, distancias[cercanos]

    def cumple(self, valor: float) -> bool:
        return valor >= self.deseado if self.direccion == SUBIR else valor <= self.deseado

    def favorable(self, diferencia: float) -> float:
        """Diferencia con el signo del objetivo: positiva = mejor."""
        return diferencia if self.direccion == SUBIR else -diferencia


@dataclass(frozen=True)
class GrupoVecinos:
    """``valor``: proporción de la clase de interés (binario) o media del objetivo (unidades originales)."""

    valor: float
    distancia_media: float
    distancia_maxima: float
    con_respaldo: bool
    cumple: bool


@dataclass(frozen=True)
class EvidenciaVecinos:
    k: int
    umbral_respaldo: float
    prescrita: GrupoVecinos
    actual: GrupoVecinos
    mejora: float  # (prescrita − actual) con el signo del objetivo: positiva = los vecinos están mejor
    texto: str


def acciones_del_indice(modelo: ModeloCausal, configuracion: ConfiguracionPrescripcion) -> list[str]:
    """Columnas de las acciones permitidas."""
    columnas: list[str] = []
    for v in variables_prescriptivas(modelo, configuracion.modificables).prescriptivas:
        accion = configuracion.acciones.get(v)
        if accion is not None and not accion.permitida:
            continue
        columnas.extend(c for c in columnas_de(modelo, v) if c not in columnas)
    return columnas


def construir_indice(
    modelo: ModeloCausal, train: pd.DataFrame, configuracion: ConfiguracionPrescripcion
) -> IndiceVecinos | None:
    """``None`` si no hay acciones o train es demasiado pequeño para tener vecinos."""
    acciones = acciones_del_indice(modelo, configuracion)
    if not acciones or modelo.objetivo not in train.columns:
        return None
    train = train[train[modelo.objetivo].notna()]
    k = min(K_VECINOS, max(K_MINIMO, len(train) // 20))
    if len(train) < 2 * k:
        return None
    afectables = _descendientes(modelo, acciones)
    perfil = [c for c in modelo.ancestros if c not in afectables]
    columnas = [*perfil, *acciones]
    escalas = np.array(
        [max(modelo.info_variables[c]["maximo"] - modelo.info_variables[c]["minimo"], 1e-12) for c in columnas]
    )
    medianas = np.array([modelo.info_variables[c]["mediana"] for c in columnas], dtype=float)
    bruto = train[columnas].to_numpy(dtype=float)
    bruto = np.where(np.isnan(bruto), medianas, bruto)
    X = bruto / escalas
    y = train[modelo.objetivo].to_numpy(dtype=float)
    objetivo = configuracion.objetivo
    if modelo.binario:
        valor = (np.round(y) == objetivo.clase_positiva).astype(float)
        deseado = float(objetivo.valor)
        exito = valor == 1 if objetivo.direccion == SUBIR else valor == 0
    else:
        valor = np.array([modelo.unidades.a_original_numerico(modelo.objetivo, v) for v in y])
        deseado = float(objetivo.valor)
        exito = valor >= deseado if objetivo.direccion == SUBIR else valor <= deseado
    return IndiceVecinos(
        perfil, acciones, escalas, medianas, X, valor, exito, k,
        _umbral_respaldo(X, k, modelo.semilla), modelo.binario, objetivo.direccion, deseado,
    )


def _umbral_respaldo(X: np.ndarray, k: int, semilla: int) -> float:
    """Percentil 95 de la distancia al k-ésimo vecino (sin contarse a sí mismo) en una muestra de train."""
    rng = np.random.default_rng([int(semilla), 7])
    muestra = rng.choice(len(X), size=min(MUESTRA_RESPALDO, len(X)), replace=False)
    normas = np.sum(X**2, axis=1)
    distancias = []
    for inicio in range(0, len(muestra), BLOQUE_DISTANCIAS):
        filas = muestra[inicio:inicio + BLOQUE_DISTANCIAS]
        # ‖a − b‖² = ‖a‖² + ‖b‖² − 2·a·b, sin materializar las diferencias (n × d por fila).
        cuadrados = normas[filas, None] + normas[None, :] - 2.0 * (X[filas] @ X.T)
        d = np.sqrt(np.maximum(cuadrados, 0.0) / X.shape[1])
        d[np.arange(len(filas)), filas] = np.inf
        distancias.append(np.partition(d, k - 1, axis=1)[:, k - 1])
    return float(np.percentile(np.concatenate(distancias), PERCENTIL_RESPALDO))


def grupo(indice: IndiceVecinos, valores: dict[str, float]) -> GrupoVecinos:
    cercanos, distancias = indice.vecinos(indice.punto(valores))
    valor = float(np.mean(indice.valor[cercanos]))
    return GrupoVecinos(
        valor, float(np.mean(distancias)), float(distancias[-1]),
        bool(distancias[-1] <= indice.umbral_respaldo), indice.cumple(valor),
    )


def evidencia_caso(
    indice: IndiceVecinos, valores_actuales: dict[str, float], fijadas: dict[str, float],
    objetivo: str, clase_positiva: int,
) -> EvidenciaVecinos:
    """``valores_actuales``: columnas preparadas del caso; ``fijadas``: acciones prescritas que cambian."""
    actual = grupo(indice, valores_actuales)
    prescrita = grupo(indice, {**valores_actuales, **fijadas}) if fijadas else actual
    mejora = indice.favorable(prescrita.valor - actual.valor)
    return EvidenciaVecinos(
        indice.k, indice.umbral_respaldo, prescrita, actual, mejora,
        texto_evidencia(indice, prescrita, actual, bool(fijadas), objetivo, clase_positiva),
    )


def _formato(indice: IndiceVecinos, valor: float) -> str:
    from pcapp_nucleo.causal.configuracion import decimal
    from pcapp_nucleo.prescripcion.prescriptor import numero

    return f"{decimal(100 * valor, '.0f')} %" if indice.binario else numero(valor)


def texto_evidencia(
    indice: IndiceVecinos, prescrita: GrupoVecinos, actual: GrupoVecinos, hay_cambios: bool,
    objetivo: str, clase_positiva: int,
) -> str:
    medida = (lambda v: f"el {_formato(indice, v)} tuvo {objetivo}={clase_positiva}") if indice.binario else (
        lambda v: f"la media de {objetivo} fue {_formato(indice, v)}"
    )
    if not hay_cambios:
        return f"De los {indice.k} casos de train más parecidos (con los mismos valores de las acciones), {medida(actual.valor)}."
    texto = (
        f"De los {indice.k} casos de train más parecidos que ya tenían valores cercanos a los prescritos, "
        f"{medida(prescrita.valor)}; entre los {indice.k} parecidos con los valores actuales, {medida(actual.valor)}."
    )
    diferencia = indice.favorable(prescrita.valor - actual.valor)
    if diferencia > 0:
        texto += " Los datos observados van en la dirección de la prescripción."
    elif diferencia < 0:
        texto += " Los datos observados NO van en la dirección de la prescripción."
    else:
        texto += " En los datos observados no hay diferencia."
    if not prescrita.con_respaldo:
        texto += (
            " Pocos casos reales tienen esa combinación: los más parecidos están lejos del perfil prescrito, así "
            "que la evidencia es débil."
        )
    return texto


def valores_de_columnas(abduccion_antes: dict[str, Any], columnas: list[str]) -> dict[str, float]:
    return {c: float(np.mean(abduccion_antes[c])) for c in columnas if c in abduccion_antes}

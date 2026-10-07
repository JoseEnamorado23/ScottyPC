"""Estructuras comunes del explorador de fórmulas.

Cada etapa del flujo expone una *traza*: la lista ordenada de pasos que siguió, con la
fórmula general (LaTeX), la misma fórmula con los valores reales del dataset y el resultado.
El frontend solo las dibuja; todo número sale del núcleo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

ORIGEN_DATASET, ORIGEN_UMBRAL, ORIGEN_CALCULADO = "dataset", "umbral", "calculado"


@dataclass(frozen=True)
class Termino:
    """Una cantidad de la fórmula, con su valor real y de dónde sale."""

    simbolo: str  # LaTeX
    descripcion: str
    valor: str | None
    origen: str = ORIGEN_CALCULADO


@dataclass(frozen=True)
class PasoFormula:
    id: str
    titulo: str
    formula: str  # LaTeX general
    sustituida: str | None  # LaTeX con los valores reales
    resultado: str
    cumple: bool | None = None
    terminos: list[Termino] = field(default_factory=list)
    nota: str | None = None


@dataclass(frozen=True)
class Umbral:
    """Parámetro que el usuario puede mover para ver cómo cambia la decisión."""

    nombre: str
    simbolo: str
    descripcion: str
    valor: float
    original: float
    minimo: float
    maximo: float
    paso: float
    entero: bool = False


def num(valor: float | None, decimales: int = 3) -> str:
    """Número para LaTeX con coma decimal; notación científica si es muy pequeño."""
    if valor is None or (isinstance(valor, float) and not math.isfinite(valor)):
        return r"\text{n/d}"
    if valor != 0 and abs(valor) < 10 ** -decimales:
        mantisa, exponente = f"{valor:.2e}".split("e")
        return rf"{mantisa.replace('.', '{,}')}\times 10^{{{int(exponente)}}}"
    return f"{valor:.{decimales}f}".replace(".", "{,}")


def texto(valor: float | None, decimales: int = 3) -> str | None:
    """Número para mostrar fuera de LaTeX (coma decimal)."""
    if valor is None:
        return None
    return f"{valor:.{decimales}g}".replace(".", ",")

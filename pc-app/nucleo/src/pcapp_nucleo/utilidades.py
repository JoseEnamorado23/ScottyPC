"""Utilidades generales del núcleo."""

from __future__ import annotations

import dataclasses
import datetime
import math
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


def a_diccionario_serializable(valor: Any) -> Any:
    """Convierte un valor del núcleo a estructuras compatibles con JSON.

    Maneja de forma recursiva dataclasses, enumeraciones, diccionarios,
    listas, tuplas, conjuntos, escalares/arreglos de NumPy y fechas. Los
    valores faltantes (``NaN``, infinito, ``pd.NA``, ``NaT``) se convierten
    en ``None`` porque JSON estándar no los admite. Las fechas se expresan en
    formato ISO 8601 y cualquier otro objeto, como texto.

    El valor recibido no se modifica.
    """
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return None
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {
            campo.name: a_diccionario_serializable(getattr(valor, campo.name))
            for campo in dataclasses.fields(valor)
        }
    if isinstance(valor, Enum):
        return a_diccionario_serializable(valor.value)
    if isinstance(valor, dict):
        return {str(clave): a_diccionario_serializable(v) for clave, v in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [a_diccionario_serializable(v) for v in valor]
    if isinstance(valor, np.ndarray):
        return [a_diccionario_serializable(v) for v in valor.tolist()]
    if isinstance(valor, (bool, np.bool_)):
        return bool(valor)
    if isinstance(valor, (int, np.integer)):
        return int(valor)
    if isinstance(valor, (float, np.floating)):
        numero = float(valor)
        return numero if math.isfinite(numero) else None
    if isinstance(valor, np.datetime64):
        return a_diccionario_serializable(pd.Timestamp(valor))
    if isinstance(valor, (datetime.date, datetime.time)):
        return valor.isoformat()
    if isinstance(valor, str):
        return valor
    return str(valor)

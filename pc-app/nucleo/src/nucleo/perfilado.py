"""Perfilado básico de columnas.

El perfil es preliminar: clasifica cada columna con reglas simples y
calcula métricas descriptivas. No interpreta valores como faltantes más
allá de lo que pandas considera faltante (``NaN``, ``None``, ``NaT``,
``pd.NA``); cadenas como ``"NA"`` o ``"?"`` se cuentan como valores.

Todas las funciones tratan los datos como solo lectura.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Hashable
from typing import Any

import numpy as np
import pandas as pd
from pandas.api import types as tipos_pandas

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.modelos import PerfilColumna, TipoColumna

# Formatos de fecha habituales escritos como texto (ISO y día/mes/año).
_PATRON_FECHA_TEXTO = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?)?"
    r"|\d{4}/\d{1,2}/\d{1,2}"
    r"|\d{1,2}/\d{1,2}/\d{4}( \d{1,2}:\d{2}(:\d{2})?)?"
)


def perfilar_columnas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion | None = None,
) -> list[PerfilColumna]:
    """Devuelve un ``PerfilColumna`` por columna, en el orden del DataFrame.

    Las columnas se recorren por posición, de modo que los nombres
    repetidos no provocan errores.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    return [
        perfilar_columna(dataframe.iloc[:, posicion], columna, configuracion)
        for posicion, columna in enumerate(dataframe.columns)
    ]


def perfilar_columna(
    serie: pd.Series,
    nombre: Hashable,
    configuracion: ConfiguracionValidacion | None = None,
) -> PerfilColumna:
    """Calcula el perfil básico de una columna.

    - ``faltantes``: valores que pandas considera faltantes.
    - ``porcentaje_faltantes``: respecto al total de filas (0–100).
    - ``valores_unicos``: valores distintos **excluyendo faltantes**.
    - ``minimo``/``maximo``: solo para columnas numéricas; ``None`` en otro caso.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    tipo = detectar_tipo_columna(serie, configuracion)
    faltantes = int(serie.isna().sum())
    minimo, maximo = _rango_numerico(serie) if tipo == TipoColumna.NUMERICA else (None, None)
    return PerfilColumna(
        nombre="" if nombre is None else str(nombre),
        tipo_detectado=tipo,
        faltantes=faltantes,
        porcentaje_faltantes=_porcentaje(faltantes, len(serie)),
        valores_unicos=contar_valores_unicos(serie),
        minimo=minimo,
        maximo=maximo,
    )


def detectar_tipo_columna(
    serie: pd.Series,
    configuracion: ConfiguracionValidacion | None = None,
) -> str:
    """Clasifica una columna en un ``TipoColumna`` preliminar.

    Primero se usa el dtype de pandas; si no es concluyente (columnas
    ``object``), se inspeccionan los valores: booleanos, fechas (objetos o
    texto con formato de fecha) y, por último, categórica o texto según
    ``maximo_valores_categorica``.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    valores = serie.dropna()
    if valores.empty:
        return TipoColumna.VACIA
    if tipos_pandas.is_bool_dtype(serie.dtype):
        return TipoColumna.BOOLEANA
    if tipos_pandas.is_datetime64_any_dtype(serie.dtype):
        return TipoColumna.FECHA
    if tipos_pandas.is_numeric_dtype(serie.dtype):
        return TipoColumna.NUMERICA
    if isinstance(serie.dtype, pd.CategoricalDtype):
        return TipoColumna.CATEGORICA
    if _todos_son(valores, (bool, np.bool_)):
        return TipoColumna.BOOLEANA
    if _todos_son(valores, (datetime.date, np.datetime64)) or _son_fechas_como_texto(valores):
        return TipoColumna.FECHA
    if contar_valores_unicos(valores) <= configuracion.maximo_valores_categorica:
        return TipoColumna.CATEGORICA
    return TipoColumna.TEXTO


def contar_valores_unicos(serie: pd.Series) -> int:
    """Cuenta valores distintos excluyendo faltantes.

    Si la columna contiene objetos no hashables (listas, diccionarios), se
    comparan por su representación de texto.
    """
    try:
        return int(serie.nunique(dropna=True))
    except TypeError:
        return int(serie.dropna().map(repr).nunique())


# --- Auxiliares --------------------------------------------------------------


def _porcentaje(parte: int, total: int) -> float:
    return round(100.0 * parte / total, 2) if total else 0.0


def _todos_son(valores: pd.Series, clases: tuple[type, ...]) -> bool:
    return all(isinstance(valor, clases) for valor in valores)


def _son_fechas_como_texto(valores: pd.Series) -> bool:
    return _todos_son(valores, (str,)) and all(
        _PATRON_FECHA_TEXTO.fullmatch(valor.strip()) for valor in valores
    )


def _a_nativo(valor: Any) -> Any:
    return valor.item() if isinstance(valor, np.generic) else valor


def _rango_numerico(serie: pd.Series) -> tuple[Any, Any]:
    valores = serie.dropna()
    if valores.empty:
        return None, None
    return _a_nativo(valores.min()), _a_nativo(valores.max())

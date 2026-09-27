"""Validación estructural de datasets.

Responde a una sola pregunta: ¿el dataset cumple las condiciones mínimas
para continuar? Las reglas solo observan el DataFrame y reportan errores
(bloqueantes) o advertencias (no bloqueantes); nunca lo modifican.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Hashable

import pandas as pd

from nucleo.carga import ErrorCarga, cargar_dataset
from nucleo.configuracion import ConfiguracionValidacion
from nucleo.modelos import (
    CodigoValidacion,
    NivelProblema,
    ProblemaValidacion,
    ResultadoValidacion,
)

_PATRON_SIN_NOMBRE = re.compile(r"^Unnamed: \d+(_level_\d+)?$")


def validar_dataset(
    dataframe: pd.DataFrame,
    objetivo: str,
    configuracion: ConfiguracionValidacion | None = None,
) -> ResultadoValidacion:
    """Valida un dataset ya cargado sin modificarlo.

    Args:
        dataframe: datos a validar. No se modifica.
        objetivo: nombre de la columna objetivo.
        configuracion: umbrales a utilizar; por defecto
            ``ConfiguracionValidacion()``.

    Returns:
        Un ``ResultadoValidacion``; ``valido`` es ``True`` solo si no hay errores.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    if dataframe.shape[0] == 0 or dataframe.shape[1] == 0:
        return construir_resultado([_problema_dataset_vacio(dataframe)])
    return construir_resultado(
        [
            *_validar_nombres_columnas(dataframe),
            *_validar_dimensiones(dataframe, configuracion),
            *_validar_objetivo(dataframe, objetivo),
        ]
    )


def validar_archivo(
    ruta: str | Path,
    objetivo: str,
    hoja: str | None = None,
    configuracion: ConfiguracionValidacion | None = None,
) -> ResultadoValidacion:
    """Carga un archivo y valida su contenido.

    Los errores de carga se devuelven como errores del resultado en lugar
    de propagarse como excepción.
    """
    try:
        dataframe = cargar_dataset(ruta, hoja, configuracion)
    except ErrorCarga as error:
        return construir_resultado([error.problema])
    return validar_dataset(dataframe, objetivo, configuracion)


def construir_resultado(problemas: list[ProblemaValidacion]) -> ResultadoValidacion:
    """Agrupa los problemas por nivel; el resultado es válido si no hay errores."""
    errores = [p for p in problemas if p.nivel == NivelProblema.ERROR]
    advertencias = [p for p in problemas if p.nivel == NivelProblema.ADVERTENCIA]
    return ResultadoValidacion(valido=not errores, errores=errores, advertencias=advertencias)


# --- Auxiliares --------------------------------------------------------------


def _error(
    codigo: str,
    mensaje: str,
    columnas: list[str] | None = None,
    evidencia: dict[str, Any] | None = None,
) -> ProblemaValidacion:
    return ProblemaValidacion(
        nivel=NivelProblema.ERROR,
        codigo=codigo,
        mensaje=mensaje,
        columnas=columnas or [],
        evidencia=evidencia or {},
    )


def _advertencia(
    codigo: str,
    mensaje: str,
    columnas: list[str] | None = None,
    evidencia: dict[str, Any] | None = None,
) -> ProblemaValidacion:
    return ProblemaValidacion(
        nivel=NivelProblema.ADVERTENCIA,
        codigo=codigo,
        mensaje=mensaje,
        columnas=columnas or [],
        evidencia=evidencia or {},
    )


def _es_sin_nombre(columna: Hashable) -> bool:
    if isinstance(columna, str):
        return not columna.strip() or bool(_PATRON_SIN_NOMBRE.match(columna))
    return columna is None or (isinstance(columna, float) and math.isnan(columna))


def _texto_columna(columna: Hashable) -> str:
    return "" if columna is None else str(columna)


def _enumerar(elementos: list[str]) -> str:
    return ", ".join(elementos)


# --- Reglas ------------------------------------------------------------------


def _problema_dataset_vacio(dataframe: pd.DataFrame) -> ProblemaValidacion:
    filas, columnas = dataframe.shape
    mensaje = (
        "El dataset no contiene columnas."
        if columnas == 0
        else "El dataset no contiene filas de datos."
    )
    return _error(
        CodigoValidacion.DATASET_VACIO,
        mensaje,
        evidencia={"filas": int(filas), "columnas": int(columnas)},
    )


def _validar_nombres_columnas(dataframe: pd.DataFrame) -> list[ProblemaValidacion]:
    return [
        *_validar_columnas_sin_nombre(dataframe),
        *_validar_columnas_repetidas(dataframe),
        *_validar_nombres_con_espacios(dataframe),
    ]


def _validar_columnas_sin_nombre(dataframe: pd.DataFrame) -> list[ProblemaValidacion]:
    sin_nombre = [
        (posicion, columna)
        for posicion, columna in enumerate(dataframe.columns, start=1)
        if _es_sin_nombre(columna)
    ]
    if not sin_nombre:
        return []
    posiciones = [posicion for posicion, _ in sin_nombre]
    if len(posiciones) == 1:
        mensaje = f"La columna en la posición {posiciones[0]} no tiene nombre."
    else:
        mensaje = (
            f"Hay {len(posiciones)} columnas sin nombre en las posiciones "
            f"{_enumerar([str(p) for p in posiciones])}."
        )
    mensaje += " Todas las columnas deben tener un encabezado."
    return [
        _error(
            CodigoValidacion.COLUMNAS_SIN_NOMBRE,
            mensaje,
            columnas=[_texto_columna(columna) for _, columna in sin_nombre],
            evidencia={"posiciones": posiciones},
        )
    ]


def _validar_columnas_repetidas(dataframe: pd.DataFrame) -> list[ProblemaValidacion]:
    conteo = Counter(c for c in dataframe.columns if not _es_sin_nombre(c))
    repetidas = {_texto_columna(c): n for c, n in conteo.items() if n > 1}
    if not repetidas:
        return []
    detalle = _enumerar([f"'{nombre}' ({n} veces)" for nombre, n in repetidas.items()])
    return [
        _error(
            CodigoValidacion.COLUMNAS_REPETIDAS,
            f"Hay nombres de columnas repetidos: {detalle}. "
            "Cada columna debe tener un nombre único.",
            columnas=list(repetidas),
            evidencia={"repeticiones": repetidas},
        )
    ]


def _validar_nombres_con_espacios(dataframe: pd.DataFrame) -> list[ProblemaValidacion]:
    con_espacios = [
        c
        for c in dataframe.columns
        if isinstance(c, str) and c.strip() and c != c.strip()
    ]
    if not con_espacios:
        return []
    return [
        _advertencia(
            CodigoValidacion.NOMBRES_CON_ESPACIOS,
            "Algunos nombres de columna tienen espacios al inicio o al final: "
            f"{_enumerar([repr(c) for c in con_espacios])}.",
            columnas=con_espacios,
        )
    ]


def _validar_dimensiones(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
) -> list[ProblemaValidacion]:
    filas, columnas = (int(n) for n in dataframe.shape)
    problemas = []
    if filas < configuracion.minimo_filas:
        problemas.append(
            _error(
                CodigoValidacion.FILAS_INSUFICIENTES,
                f"El dataset contiene {filas} filas y se requieren al menos "
                f"{configuracion.minimo_filas}.",
                evidencia={"filas": filas, "minimo_filas": configuracion.minimo_filas},
            )
        )
    if columnas > configuracion.maximo_columnas:
        problemas.append(
            _error(
                CodigoValidacion.COLUMNAS_EXCESIVAS,
                f"El dataset contiene {columnas} columnas y el máximo permitido es "
                f"{configuracion.maximo_columnas}.",
                evidencia={
                    "columnas": columnas,
                    "maximo_columnas": configuracion.maximo_columnas,
                },
            )
        )
    return problemas


def _validar_objetivo(dataframe: pd.DataFrame, objetivo: str) -> list[ProblemaValidacion]:
    posiciones = [i for i, columna in enumerate(dataframe.columns) if columna == objetivo]
    if not posiciones:
        return [
            _error(
                CodigoValidacion.OBJETIVO_INEXISTENTE,
                f"La variable objetivo '{objetivo}' no existe en el dataset.",
                columnas=[objetivo],
            )
        ]
    if len(posiciones) > 1:
        # Ambigua: ya se informa como COLUMNAS_REPETIDAS.
        return []
    serie = dataframe.iloc[:, posiciones[0]]
    return [
        *_validar_faltantes_objetivo(serie, objetivo),
        *_validar_constancia_objetivo(serie, objetivo),
    ]


def _validar_faltantes_objetivo(serie: pd.Series, objetivo: str) -> list[ProblemaValidacion]:
    faltantes = int(serie.isna().sum())
    if faltantes == 0:
        return []
    porcentaje = 100.0 * faltantes / len(serie)
    return [
        _error(
            CodigoValidacion.OBJETIVO_CON_FALTANTES,
            f"La variable objetivo contiene {faltantes} "
            f"{'valor faltante' if faltantes == 1 else 'valores faltantes'} "
            f"({porcentaje:.1f} %).",
            columnas=[objetivo],
            evidencia={"faltantes": faltantes, "porcentaje_faltantes": round(porcentaje, 2)},
        )
    ]


def _validar_constancia_objetivo(serie: pd.Series, objetivo: str) -> list[ProblemaValidacion]:
    if int(serie.nunique(dropna=True)) != 1:
        return []
    return [
        _error(
            CodigoValidacion.OBJETIVO_CONSTANTE,
            f"La variable objetivo '{objetivo}' es constante. "
            "Se requiere variabilidad para realizar el análisis.",
            columnas=[objetivo],
            evidencia={"valor": str(serie.dropna().iloc[0])},
        )
    ]

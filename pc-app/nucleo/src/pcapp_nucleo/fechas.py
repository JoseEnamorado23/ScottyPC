"""Interpretación de fechas escritas como texto.

Lo usan el perfilado, el detector de fechas y la separación temporal, para
que las tres partes interpreten las fechas exactamente igual. Ninguna
función modifica la serie recibida: las conversiones devuelven series nuevas.

Formatos probados: separadores ``-``, ``/`` y ``.``; año de 4 o 2 dígitos;
año primero, día primero o mes primero. Solo se interpreta la parte de la
fecha: la hora (lo que sigue a un espacio o a una ``T``) se ignora, de modo
que una columna que mezcla valores con y sin hora se reconoce igual. Valores
sin separadores (como ``20240101``) nunca se consideran fechas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

_SEPARADORES = ("-", "/", ".")
# Orden de preferencia ante empates: año primero, luego día primero (uso
# habitual en español) y por último mes primero.
FORMATOS_FECHA: tuple[str, ...] = tuple(
    formato
    for s in _SEPARADORES
    for formato in (
        f"%Y{s}%m{s}%d",
        f"%d{s}%m{s}%Y",
        f"%d{s}%m{s}%y",
        f"%m{s}%d{s}%Y",
        f"%m{s}%d{s}%y",
    )
)
_PATRON_CANDIDATO = re.compile(
    r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?)?"
)
# Años plausibles: evita que "01.01.23" se lea como el año 1 con "%Y".
_ANIO_MINIMO, _ANIO_MAXIMO = 1900, 2100


@dataclass(frozen=True)
class InterpretacionFechas:
    """Formato elegido para una columna de texto y su cobertura."""

    formato: str
    porcentaje_convertible: float
    formatos_alternativos: tuple[str, ...] = ()


def _parte_fecha(valor: object) -> object:
    """Texto sin espacios ni hora; los valores que no son texto no cambian."""
    if not isinstance(valor, str):
        return valor
    return re.split(r"[ T]", valor.strip(), maxsplit=1)[0]


def _textos(valores: pd.Series) -> list[str] | None:
    presentes = valores.dropna()
    if presentes.empty or not all(isinstance(v, str) for v in presentes):
        return None
    return [v.strip() for v in presentes]


def convertir_fechas(serie: pd.Series, formato: str) -> pd.Series:
    """Serie de fechas (``NaT`` si un valor no se interpreta) con el mismo índice."""
    textos = serie.map(_parte_fecha)
    fechas = pd.to_datetime(textos, format=formato, errors="coerce")
    plausibles = fechas.dt.year.between(_ANIO_MINIMO, _ANIO_MAXIMO)
    return fechas.where(plausibles)


def interpretar_fechas_texto(
    valores: pd.Series, porcentaje_minimo: float
) -> InterpretacionFechas | None:
    """Mejor formato para una serie de textos, o ``None`` si no son fechas.

    Se acepta el formato que interpreta el mayor porcentaje de valores no
    faltantes, siempre que alcance ``porcentaje_minimo``. Si otros formatos
    empatan (p. ej. día y mes intercambiables cuando todos los días son
    <= 12), se elige según el orden de preferencia y se informan como
    alternativos.
    """
    textos = _textos(valores)
    if textos is None:
        return None
    candidatos = sum(bool(_PATRON_CANDIDATO.fullmatch(t)) for t in textos)
    if 100.0 * candidatos / len(textos) < porcentaje_minimo:
        return None
    serie = pd.Series(textos, dtype=object)
    porcentajes = {
        formato: round(100.0 * int(convertir_fechas(serie, formato).notna().sum()) / len(textos), 2)
        for formato in FORMATOS_FECHA
    }
    mejor = max(porcentajes.values())
    if mejor < porcentaje_minimo:
        return None
    empatados = [formato for formato in FORMATOS_FECHA if porcentajes[formato] == mejor]
    return InterpretacionFechas(empatados[0], mejor, tuple(empatados[1:]))

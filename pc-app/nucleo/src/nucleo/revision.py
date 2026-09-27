"""Revisión de datasets.

La revisión perfila cada columna, resume el dataset, identifica el tipo
preliminar del objetivo y ejecuta una colección de detectores
independientes que producen ``Hallazgo``. Nunca modifica los datos.

Los detectores se ejecutan en el orden de ``DETECTORES``,
``DETECTORES_OBJETIVO`` y ``DETECTORES_RELACIONES``, de modo que el informe
es reproducible.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.detectores import (
    detectar_casi_constantes,
    detectar_categoricas,
    detectar_ceros_sospechosos,
    detectar_constantes,
    detectar_desbalance_objetivo,
    detectar_distribucion_objetivo,
    detectar_fechas,
    detectar_filas_duplicadas,
    detectar_posibles_identificadores,
    detectar_texto_libre,
    detectar_valores_faltantes,
)
from nucleo.detectores_relaciones import (
    detectar_binarias_derivadas,
    detectar_copias_exactas,
    detectar_correlaciones_casi_perfectas,
    detectar_mezcla_unidades,
    detectar_recodificaciones,
    detectar_relaciones_matematicas,
)
from nucleo.modelos import (
    Hallazgo,
    InformeRevision,
    PerfilColumna,
    TipoColumna,
    TipoObjetivo,
)
from nucleo.perfilado import perfilar_columnas

Detector = Callable[
    [pd.DataFrame, ConfiguracionValidacion, list[PerfilColumna]],
    list[Hallazgo],
]
"""Interfaz de un detector: recibe datos, configuración y perfiles; devuelve hallazgos."""

DetectorObjetivo = Callable[
    [pd.Series, "str | None", ConfiguracionValidacion],
    list[Hallazgo],
]
"""Interfaz de un detector del objetivo: recibe la serie, su tipo y la configuración."""

DETECTORES: tuple[Detector, ...] = (
    detectar_filas_duplicadas,
    detectar_valores_faltantes,
    detectar_ceros_sospechosos,
    detectar_constantes,
    detectar_casi_constantes,
    detectar_posibles_identificadores,
    detectar_texto_libre,
    detectar_fechas,
    detectar_categoricas,
)

DETECTORES_OBJETIVO: tuple[DetectorObjetivo, ...] = (
    detectar_distribucion_objetivo,
    detectar_desbalance_objetivo,
)

DETECTORES_RELACIONES: tuple[Detector, ...] = (
    detectar_copias_exactas,
    detectar_recodificaciones,
    detectar_relaciones_matematicas,
    detectar_binarias_derivadas,
    detectar_correlaciones_casi_perfectas,
    detectar_mezcla_unidades,
)


def revisar_dataset(
    dataframe: pd.DataFrame,
    objetivo: str | None = None,
    configuracion: ConfiguracionValidacion | None = None,
    detectores: Sequence[Detector] = DETECTORES,
    detectores_objetivo: Sequence[DetectorObjetivo] = DETECTORES_OBJETIVO,
    detectores_relaciones: Sequence[Detector] = DETECTORES_RELACIONES,
) -> InformeRevision:
    """Revisa un dataset y genera un informe sin modificar los datos.

    Args:
        dataframe: datos a revisar. No se modifica.
        objetivo: nombre de la columna objetivo, si existe.
        configuracion: umbrales a utilizar; por defecto
            ``ConfiguracionValidacion()``.
        detectores: detectores de columnas; por defecto ``DETECTORES``.
        detectores_objetivo: detectores del objetivo; por defecto
            ``DETECTORES_OBJETIVO``. Solo se ejecutan si el objetivo existe
            en una única columna.
        detectores_relaciones: detectores de relaciones entre columnas y
            mezclas de unidades; por defecto ``DETECTORES_RELACIONES``.

    Returns:
        Un ``InformeRevision`` con resumen, hallazgos y perfiles de columnas.
        Si el objetivo no existe o está repetido, ``tipo_objetivo`` es ``None``.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    perfiles = perfilar_columnas(dataframe, configuracion)
    informacion_objetivo = analizar_objetivo(dataframe, objetivo, perfiles, configuracion)
    return InformeRevision(
        resumen=construir_resumen(dataframe, perfiles, objetivo, informacion_objetivo),
        hallazgos=[
            *_ejecutar_detectores(dataframe, configuracion, perfiles, detectores),
            *_ejecutar_detectores_objetivo(
                dataframe, objetivo, informacion_objetivo, configuracion, detectores_objetivo
            ),
            *_ejecutar_detectores(dataframe, configuracion, perfiles, detectores_relaciones),
        ],
        perfiles_columnas=perfiles,
        objetivo=objetivo,
        informacion_objetivo=informacion_objetivo,
    )


def construir_resumen(
    dataframe: pd.DataFrame,
    perfiles: list[PerfilColumna],
    objetivo: str | None,
    informacion_objetivo: dict[str, Any],
) -> dict[str, Any]:
    """Resume dimensiones, tipos de columnas y faltantes del dataset."""
    conteo_tipos = Counter(perfil.tipo_detectado for perfil in perfiles)
    return {
        "filas": int(dataframe.shape[0]),
        "columnas": int(dataframe.shape[1]),
        "columnas_numericas": conteo_tipos[TipoColumna.NUMERICA],
        "columnas_categoricas": conteo_tipos[TipoColumna.CATEGORICA],
        "columnas_texto": conteo_tipos[TipoColumna.TEXTO],
        "columnas_fecha": conteo_tipos[TipoColumna.FECHA],
        "columnas_booleanas": conteo_tipos[TipoColumna.BOOLEANA],
        "columnas_vacias": conteo_tipos[TipoColumna.VACIA],
        "total_faltantes": sum(perfil.faltantes for perfil in perfiles),
        "objetivo": objetivo,
        "tipo_objetivo": informacion_objetivo.get("tipo"),
    }


def analizar_objetivo(
    dataframe: pd.DataFrame,
    objetivo: str | None,
    perfiles: list[PerfilColumna],
    configuracion: ConfiguracionValidacion,
) -> dict[str, Any]:
    """Describe preliminarmente el objetivo sin lanzar excepciones.

    Si el objetivo no se indicó, no existe o está repetido, devuelve
    ``tipo = None`` y el motivo.
    """
    if objetivo is None:
        return {"encontrado": False, "tipo": None, "motivo": "No se indicó variable objetivo."}
    posicion = _posicion_objetivo(dataframe, objetivo)
    if posicion is None:
        motivo = (
            f"La variable objetivo '{objetivo}' aparece en varias columnas."
            if objetivo in dataframe.columns
            else f"La variable objetivo '{objetivo}' no existe en el dataset."
        )
        return {"encontrado": False, "tipo": None, "motivo": motivo}
    perfil = perfiles[posicion]
    return {
        "encontrado": True,
        "tipo": detectar_tipo_objetivo(
            dataframe.iloc[:, posicion], perfil.tipo_detectado, configuracion
        ),
        "tipo_columna": perfil.tipo_detectado,
        "valores_unicos": perfil.valores_unicos,
    }


def detectar_tipo_objetivo(
    serie: pd.Series,
    tipo_columna: str,
    configuracion: ConfiguracionValidacion,
) -> str | None:
    """Clasifica el objetivo como binario, multiclase o continuo.

    - Dos valores distintos: binario.
    - Numérico con más de ``maximo_clases_objetivo`` valores distintos o con
      valores no enteros: continuo.
    - Resto con más de dos valores distintos: multiclase.
    - Menos de dos valores distintos: ``None`` (no clasificable).
    """
    valores = serie.dropna()
    unicos = int(valores.nunique())
    if unicos < 2:
        return None
    if unicos == 2:
        return TipoObjetivo.BINARIO
    if tipo_columna == TipoColumna.NUMERICA:
        enteros = bool((valores % 1 == 0).all())
        if unicos > configuracion.maximo_clases_objetivo or not enteros:
            return TipoObjetivo.CONTINUO
    return TipoObjetivo.MULTICLASE


def _ejecutar_detectores(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
    detectores: Sequence[Detector],
) -> list[Hallazgo]:
    """Ejecuta cada detector de forma independiente y concatena sus hallazgos."""
    return [
        hallazgo
        for detector in detectores
        for hallazgo in detector(dataframe, configuracion, perfiles)
    ]


def _posicion_objetivo(dataframe: pd.DataFrame, objetivo: str | None) -> int | None:
    """Posición del objetivo si aparece exactamente una vez; si no, ``None``."""
    posiciones = [i for i, columna in enumerate(dataframe.columns) if columna == objetivo]
    return posiciones[0] if objetivo is not None and len(posiciones) == 1 else None


def _ejecutar_detectores_objetivo(
    dataframe: pd.DataFrame,
    objetivo: str | None,
    informacion_objetivo: dict[str, Any],
    configuracion: ConfiguracionValidacion,
    detectores: Sequence[DetectorObjetivo],
) -> list[Hallazgo]:
    """Ejecuta los detectores del objetivo si este existe en una única columna."""
    posicion = _posicion_objetivo(dataframe, objetivo)
    if posicion is None:
        return []
    serie = dataframe.iloc[:, posicion]
    return [
        hallazgo
        for detector in detectores
        for hallazgo in detector(serie, informacion_objetivo["tipo"], configuracion)
    ]

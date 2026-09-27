"""Flujo completo del núcleo: validación y, si procede, revisión.

Este módulo integra las dos etapas sin mezclar sus responsabilidades y es
el punto de entrada recomendado para cualquier consumidor (CLI, futura API,
pruebas). No lee archivos: recibe un DataFrame ya cargado (ver
``pcapp_nucleo.carga``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.modelos import ResultadoAnalisis
from pcapp_nucleo.revision import revisar_dataset
from pcapp_nucleo.utilidades import a_diccionario_serializable
from pcapp_nucleo.validacion import validar_dataset


def analizar_dataset(
    dataframe: pd.DataFrame,
    objetivo: str,
    configuracion: ConfiguracionValidacion | None = None,
) -> ResultadoAnalisis:
    """Valida el dataset y, solo si no hay errores bloqueantes, lo revisa.

    Args:
        dataframe: datos a analizar. No se modifica.
        objetivo: nombre de la columna objetivo.
        configuracion: umbrales; por defecto ``ConfiguracionValidacion()``.

    Returns:
        Un ``ResultadoAnalisis``. Si la validación falla, ``valido`` es
        ``False``, ``informe`` es ``None`` y los detectores no se ejecutan.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    validacion = validar_dataset(dataframe, objetivo, configuracion)
    if not validacion.valido:
        return ResultadoAnalisis(valido=False, validacion=validacion)
    informe = revisar_dataset(dataframe, objetivo, configuracion)
    return ResultadoAnalisis(valido=True, validacion=validacion, informe=informe)


def resultado_a_diccionario(resultado: ResultadoAnalisis) -> dict[str, Any]:
    """Convierte un ``ResultadoAnalisis`` en un diccionario compatible con JSON.

    Estructura: ``valido`` y ``validacion`` y, si hubo revisión, los campos
    del ``InformeRevision`` en el nivel superior (``resumen``,
    ``hallazgos``, ``perfiles_columnas``, ``objetivo``,
    ``informacion_objetivo``).
    """
    datos: dict[str, Any] = {
        "valido": resultado.valido,
        "validacion": a_diccionario_serializable(resultado.validacion),
    }
    if resultado.informe is not None:
        datos.update(a_diccionario_serializable(resultado.informe))
    return datos

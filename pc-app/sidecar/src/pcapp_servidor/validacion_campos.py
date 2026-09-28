"""Validación por campo de las decisiones y de la configuración de PC.

Pydantic ya valida tipos y valores permitidos; aquí se comprueba lo que
depende de los datos (que las columnas existan, que el objetivo no se trate
como una variable más) y se devuelve cada error con la ruta de su campo para
que la interfaz lo muestre junto al control correspondiente.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def validar_decisiones(datos: dict[str, Any], columnas: list[str], objetivo: str) -> list[dict[str, str]]:
    existentes = set(columnas)
    errores: list[dict[str, str]] = []

    def error(campo: str, mensaje: str) -> None:
        errores.append({"campo": campo, "mensaje": mensaje})

    def comprobar(campo: str, columna: str) -> bool:
        if columna not in existentes:
            error(campo, f"La columna '{columna}' no existe en el dataset.")
            return False
        return True

    for i, columna in enumerate(datos.get("columnas_excluidas", [])):
        if comprobar(f"columnas_excluidas.{i}", columna) and columna == objetivo:
            error(f"columnas_excluidas.{i}", "La variable objetivo no puede excluirse.")
    for columna in datos.get("faltantes", {}):
        if comprobar(f"faltantes.{columna}", columna) and columna == objetivo:
            error(f"faltantes.{columna}", "La variable objetivo no admite tratamiento de faltantes.")
    for columna, codificacion in datos.get("codificaciones", {}).items():
        comprobar(f"codificaciones.{columna}", columna)
        if codificacion.get("tipo") == "ordinal" and not codificacion.get("orden"):
            error(f"codificaciones.{columna}.orden", "La codificación ordinal necesita el orden de los valores.")
        if codificacion.get("tipo") == "agrupacion" and not codificacion.get("grupos"):
            error(f"codificaciones.{columna}.grupos", "La agrupación necesita los grupos {valor: nuevo_valor}.")
    for i, conversion in enumerate(datos.get("conversiones", [])):
        comprobar(f"conversiones.{i}.columna", conversion.get("columna", ""))
    for i, columna in enumerate(datos.get("logaritmos", [])):
        comprobar(f"logaritmos.{i}", columna)
    return errores


def validar_separacion_campos(
    separacion: dict[str, Any], fechas_disponibles: list[str]
) -> list[dict[str, str]]:
    """Errores por campo de la separación elegida al preparar."""
    errores: list[dict[str, str]] = []
    if separacion.get("tipo") != "temporal":
        return errores
    fecha = separacion.get("columna_fecha")
    if not fecha:
        errores.append({"campo": "separacion.columna_fecha", "mensaje": "Elija la columna de fecha."})
    elif fecha not in fechas_disponibles:
        errores.append({
            "campo": "separacion.columna_fecha",
            "mensaje": "No es una columna de fecha detectada"
            + (f"; opciones: {', '.join(fechas_disponibles)}." if fechas_disponibles else "."),
        })
    corte = separacion.get("corte")
    if corte is not None and not str(corte).strip():
        errores.append({"campo": "separacion.corte", "mensaje": "Elija la fecha de corte."})
    elif corte is not None:
        try:
            date.fromisoformat(corte)
        except (TypeError, ValueError):
            errores.append({"campo": "separacion.corte", "mensaje": "Use una fecha con el formato AAAA-MM-DD."})
    return errores

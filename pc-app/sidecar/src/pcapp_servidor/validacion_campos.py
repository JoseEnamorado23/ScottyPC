"""Validación por campo de las decisiones y de la configuración de PC.

Pydantic ya valida tipos y valores permitidos; aquí se comprueba lo que
depende de los datos (que las columnas existan, que el objetivo no se trate
como una variable más) y se devuelve cada error con la ruta de su campo para
que la interfaz lo muestre junto al control correspondiente.
"""

from __future__ import annotations

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
    separacion = datos.get("separacion", {})
    fecha = separacion.get("columna_fecha")
    if separacion.get("tipo") == "temporal" and not fecha:
        error("separacion.columna_fecha", "La separación temporal necesita una columna de fecha.")
    elif fecha:
        comprobar("separacion.columna_fecha", fecha)
    return errores


# Mensajes de ErrorConfiguracionPC → campo de la configuración.
_CAMPOS_CONFIGURACION = (
    ("Prueba no válida", "prueba"),
    ("alpha", "alpha"),
    ("corridas_bootstrap", "corridas_bootstrap"),
    ("fraccion_submuestra", "fraccion_submuestra"),
    ("umbral_frecuencia", "umbral_frecuencia"),
    ("max_k", "max_k"),
    ("procesos", "procesos"),
    ("punto_control_cada", "punto_control_cada"),
    ("Modo de ejecución", "modo_ejecucion"),
    ("umbral_paralelo_s", "umbral_paralelo_s"),
    ("modificables", "modificables"),
    ("orientación manual", "orientaciones_manuales"),
    ("nivel", "niveles"),
    ("objetivo", "niveles"),
)


def campo_de_configuracion(mensaje: str) -> str:
    for fragmento, campo in _CAMPOS_CONFIGURACION:
        if fragmento.lower() in mensaje.lower():
            return campo
    return ""

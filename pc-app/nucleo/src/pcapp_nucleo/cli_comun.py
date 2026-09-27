"""Utilidades compartidas por los comandos de la CLI: salida, errores y archivos."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

import pandas as pd

from pcapp_nucleo.carga import ErrorCarga, cargar_dataset
from pcapp_nucleo.modelos import CodigoValidacion, ProblemaValidacion, ResultadoValidacion

SALIDA_CORRECTA = 0
SALIDA_ERROR = 1
SALIDA_DATASET_INVALIDO = 2

SEPARADOR = "=" * 48


def error(texto: str) -> None:
    """Escribe en stderr tras vaciar stdout, para conservar el orden de los mensajes."""
    sys.stdout.flush()
    print(texto, file=sys.stderr, flush=True)


def imprimir_error_carga(problema: ProblemaValidacion, ruta: Path) -> None:
    evidencia = problema.evidencia
    if problema.codigo == CodigoValidacion.ARCHIVO_NO_ENCONTRADO:
        mensaje = f"el archivo no existe ({ruta})"
    elif problema.codigo == CodigoValidacion.FORMATO_NO_SOPORTADO:
        mensaje = "formato de archivo no soportado.\nFormatos aceptados: CSV y XLSX"
    elif problema.codigo == CodigoValidacion.HOJA_NO_ENCONTRADA:
        mensaje = f'la hoja "{evidencia["hoja"]}" no existe'
    elif problema.codigo == CodigoValidacion.HOJA_NO_ESPECIFICADA:
        mensaje = "el archivo contiene varias hojas; indique cuál analizar con --hoja"
    else:
        mensaje = problema.mensaje.rstrip(".")
    error(f"Error: {mensaje}.")
    if "hojas_disponibles" in evidencia:
        error("\nHojas disponibles:")
        for nombre in evidencia["hojas_disponibles"]:
            error(f"- {nombre}")


def cargar(ruta: Path, hoja: str | None) -> pd.DataFrame | None:
    """Carga el archivo o informa el error y devuelve ``None``."""
    try:
        return cargar_dataset(ruta, hoja=hoja)
    except ErrorCarga as problema:
        imprimir_error_carga(problema.problema, ruta)
        return None


def imprimir_problemas(titulo: str, problemas: list[ProblemaValidacion], flujo: TextIO) -> None:
    if not problemas:
        return
    sys.stdout.flush()
    print(f"\n{titulo}:", file=flujo)
    for problema in problemas:
        print(f"- [{problema.codigo}] {problema.mensaje}", file=flujo)
    flujo.flush()


def imprimir_dataset_invalido(
    validacion: ResultadoValidacion, forma: tuple[int, int], consecuencia: str
) -> None:
    print(f"Filas: {forma[0]}")
    print(f"Columnas: {forma[1]}")
    imprimir_problemas("Errores bloqueantes", validacion.errores, sys.stderr)
    imprimir_problemas("Advertencias", validacion.advertencias, sys.stdout)
    print(f"\nResultado:\nDATASET NO VÁLIDO: {consecuencia}")


def rutas_libres(ruta: Path, sufijos: list[str], base: str | None = None) -> list[Path]:
    """Rutas ``<base><sufijo>`` junto a ``ruta`` que no existen todavía.

    Si alguna ya existe, se prueba ``<base><sufijo sin extensión>_2.<ext>``,
    ``_3``... con el mismo número para todos los sufijos, de modo que los
    archivos de una misma ejecución quedan emparejados. Nunca se sobrescribe.
    """
    base = base or ruta.stem
    numero = 1
    while True:
        extra = "" if numero == 1 else f"_{numero}"
        candidatas = []
        for sufijo in sufijos:
            nombre, extension = sufijo.rsplit(".", 1)
            candidatas.append(ruta.with_name(f"{base}{nombre}{extra}.{extension}"))
        if not any(c.exists() for c in candidatas):
            return candidatas
        numero += 1


def escribir_json(ruta: Path, datos: Any) -> bool:
    """Guarda ``datos`` como JSON legible; informa el error y devuelve ``False`` si falla."""
    try:
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as problema:
        error(f"Error: no se pudo guardar '{ruta}': {problema}.")
        return False
    return True


def leer_json(ruta: Path, descripcion: str) -> Any | None:
    """Lee un JSON o informa el error y devuelve ``None``."""
    try:
        with open(ruta, encoding="utf-8") as archivo:
            return json.load(archivo)
    except FileNotFoundError:
        error(f"Error: el archivo de {descripcion} no existe ({ruta}).")
    except (OSError, json.JSONDecodeError) as problema:
        error(f"Error: no se pudo leer el archivo de {descripcion} ({ruta}): {problema}.")
    return None


def carpetas_numeradas(ruta: Path, nombre: str) -> list[Path]:
    """Carpetas existentes ``<nombre>``, ``<nombre>_2``... junto a ``ruta``, en orden."""
    existentes = []
    numero = 1
    while True:
        candidata = ruta.with_name(nombre if numero == 1 else f"{nombre}_{numero}")
        if not candidata.exists():
            return existentes
        existentes.append(candidata)
        numero += 1


def carpeta_libre(ruta: Path, nombre: str) -> Path:
    """Primera carpeta ``<nombre>``, ``<nombre>_2``... junto a ``ruta`` que no existe."""
    existentes = carpetas_numeradas(ruta, nombre)
    numero = len(existentes) + 1
    return ruta.with_name(nombre if numero == 1 else f"{nombre}_{numero}")

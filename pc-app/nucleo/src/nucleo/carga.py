"""Carga de archivos CSV y XLSX a DataFrames.

Este módulo solo lee archivos; no aplica reglas de validación ni corrige
datos. Los encabezados se conservan tal como aparecen en el archivo (sin
renombrar repetidos ni vacíos) para que la validación pueda detectarlos.

Los problemas de lectura se comunican mediante ``ErrorCarga``, que contiene
un ``ProblemaValidacion`` para el usuario y conserva la excepción original
como causa (``__cause__``) para depuración.
"""

from __future__ import annotations

import codecs
import csv
import io
import zipfile
from itertools import islice
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.modelos import CodigoValidacion, NivelProblema, ProblemaValidacion

_ERRORES_EXCEL = (OSError, ValueError, KeyError, zipfile.BadZipFile, InvalidFileException)


class ErrorCarga(Exception):
    """Error controlado al cargar un archivo."""

    def __init__(self, problema: ProblemaValidacion) -> None:
        super().__init__(problema.mensaje)
        self.problema = problema


def _error_carga(
    codigo: str,
    mensaje: str,
    evidencia: dict[str, Any] | None = None,
    causa: BaseException | None = None,
) -> ErrorCarga:
    evidencia = dict(evidencia or {})
    if causa is not None:
        evidencia["detalle_tecnico"] = f"{type(causa).__name__}: {causa}"
    return ErrorCarga(
        ProblemaValidacion(
            nivel=NivelProblema.ERROR,
            codigo=codigo,
            mensaje=mensaje,
            evidencia=evidencia,
        )
    )


def _describir_formatos(formatos: tuple[str, ...]) -> str:
    nombres = [formato.lstrip(".").upper() for formato in formatos]
    if len(nombres) == 1:
        return nombres[0]
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _comprobar_existencia(ruta: Path) -> None:
    if not ruta.is_file():
        raise _error_carga(
            CodigoValidacion.ARCHIVO_NO_ENCONTRADO,
            f"No se encontró el archivo '{ruta}'.",
            {"ruta": str(ruta)},
        )


def cargar_dataset(
    ruta: str | Path,
    hoja: str | None = None,
    configuracion: ConfiguracionValidacion | None = None,
) -> pd.DataFrame:
    """Carga un archivo CSV o XLSX según su extensión.

    Args:
        ruta: ruta del archivo.
        hoja: nombre de la hoja (solo XLSX). Obligatoria si el libro tiene
            varias hojas.
        configuracion: parámetros de lectura; por defecto
            ``ConfiguracionValidacion()``.

    Raises:
        ErrorCarga: si el formato no es soportado o el archivo no puede leerse.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    ruta = Path(ruta)
    extension = ruta.suffix.lower()
    formatos = tuple(f.lower() for f in configuracion.formatos_aceptados)
    if extension not in formatos or extension not in (".csv", ".xlsx"):
        raise _error_carga(
            CodigoValidacion.FORMATO_NO_SOPORTADO,
            "Formato de archivo no soportado. Los formatos aceptados son "
            f"{_describir_formatos(formatos)}.",
            {"extension": extension, "formatos_aceptados": list(formatos)},
        )
    if extension == ".csv":
        if hoja is not None:
            raise _error_carga(
                CodigoValidacion.HOJA_NO_APLICABLE,
                "La selección de hoja solo se aplica a archivos XLSX.",
                {"hoja": hoja},
            )
        return cargar_csv(ruta, configuracion)
    return cargar_excel(ruta, hoja)


# --- CSV ---------------------------------------------------------------------


def detectar_codificacion(contenido: bytes, codificaciones: tuple[str, ...]) -> str:
    """Devuelve la primera codificación que decodifica el contenido sin errores.

    Un BOM UTF-16 se reconoce directamente. ``utf-8-sig`` acepta UTF-8 con y
    sin BOM y elimina el BOM al decodificar.
    """
    if contenido.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    for codificacion in codificaciones:
        try:
            contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
        return codificacion
    raise _error_carga(
        CodigoValidacion.CODIFICACION_NO_RECONOCIDA,
        "No se pudo determinar la codificación del archivo CSV. "
        "Guárdelo como UTF-8 e inténtelo de nuevo.",
        {"codificaciones_probadas": list(codificaciones)},
    )


def _ancho_constante(texto: str, separador: str, filas_muestra: int) -> int | None:
    """Número de campos si todas las filas de la muestra tienen el mismo ancho."""
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    try:
        anchos = {len(fila) for fila in islice(lector, filas_muestra) if fila}
    except csv.Error:
        return None
    return anchos.pop() if len(anchos) == 1 else None


def detectar_separador(
    texto: str,
    candidatos: tuple[str, ...],
    filas_muestra: int,
) -> str:
    """Detecta el separador de un CSV ya decodificado.

    Un candidato es válido si produce el mismo número de campos (más de uno)
    en todas las filas de la muestra. Si ningún candidato o más de uno es
    válido, el separador se considera indeterminado. Si todos producen una
    única columna, el archivo se trata como de una sola columna.

    Raises:
        ErrorCarga: si el separador no puede determinarse de forma confiable.
    """
    anchos = {sep: _ancho_constante(texto, sep, filas_muestra) for sep in candidatos}
    validos = [sep for sep, ancho in anchos.items() if ancho is not None and ancho > 1]
    if len(validos) == 1:
        return validos[0]
    if not validos and all(ancho == 1 for ancho in anchos.values()):
        return candidatos[0]
    raise _error_carga(
        CodigoValidacion.SEPARADOR_NO_DETECTADO,
        "No se pudo determinar el separador del archivo CSV de forma confiable. "
        "Compruebe que todas las filas tengan el mismo número de columnas.",
        {"candidatos_probados": list(candidatos), "candidatos_compatibles": validos},
    )


def cargar_csv(
    ruta: str | Path,
    configuracion: ConfiguracionValidacion | None = None,
) -> pd.DataFrame:
    """Carga un CSV detectando codificación y separador.

    La primera fila no vacía se interpreta como encabezado y se conserva sin
    modificaciones.

    Raises:
        ErrorCarga: si el archivo no existe, está vacío o no puede leerse.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    ruta = Path(ruta)
    _comprobar_existencia(ruta)
    try:
        contenido = ruta.read_bytes()
    except OSError as exc:
        raise _error_carga(
            CodigoValidacion.ARCHIVO_ILEGIBLE,
            f"No se pudo leer el archivo '{ruta.name}'.",
            causa=exc,
        ) from exc

    codificacion = detectar_codificacion(contenido, configuracion.codificaciones_csv)
    texto = contenido.decode(codificacion)
    if not texto.strip():
        raise _error_carga(CodigoValidacion.ARCHIVO_VACIO, f"El archivo '{ruta.name}' está vacío.")
    if "\x00" in texto:
        raise _error_carga(
            CodigoValidacion.ARCHIVO_ILEGIBLE,
            f"El archivo '{ruta.name}' no parece ser un CSV de texto.",
        )

    separador = detectar_separador(
        texto, configuracion.separadores_csv, configuracion.filas_muestra_separador
    )
    encabezado = next(fila for fila in csv.reader(io.StringIO(texto), delimiter=separador) if fila)
    try:
        dataframe = pd.read_csv(io.StringIO(texto), sep=separador)
    except (pd.errors.ParserError, ValueError) as exc:
        raise _error_carga(
            CodigoValidacion.ARCHIVO_ILEGIBLE,
            f"No se pudo interpretar el archivo CSV '{ruta.name}'. "
            "Compruebe que todas las filas tengan el mismo número de columnas.",
            {"separador": separador, "codificacion": codificacion},
            causa=exc,
        ) from exc
    if len(encabezado) != dataframe.shape[1]:
        raise _error_carga(
            CodigoValidacion.ARCHIVO_ILEGIBLE,
            f"El encabezado del archivo CSV '{ruta.name}' no coincide con el número de columnas.",
            {"columnas_encabezado": len(encabezado), "columnas_datos": dataframe.shape[1]},
        )
    # Restaurar los nombres originales: pandas renombra repetidos y vacíos.
    dataframe.columns = encabezado
    return dataframe


# --- XLSX --------------------------------------------------------------------


def _error_excel_ilegible(ruta: Path, causa: BaseException) -> ErrorCarga:
    return _error_carga(
        CodigoValidacion.ARCHIVO_ILEGIBLE,
        f"No se pudo leer el archivo Excel '{ruta.name}'. "
        "Compruebe que sea un archivo XLSX válido.",
        causa=causa,
    )


def _seleccionar_hoja(hojas: list[str], hoja: str | None) -> str:
    if hoja is None:
        if len(hojas) == 1:
            return hojas[0]
        raise _error_carga(
            CodigoValidacion.HOJA_NO_ESPECIFICADA,
            "El archivo contiene varias hojas; indique cuál desea utilizar. "
            f"Hojas disponibles: {', '.join(hojas)}.",
            {"hojas_disponibles": hojas},
        )
    if hoja not in hojas:
        raise _error_carga(
            CodigoValidacion.HOJA_NO_ENCONTRADA,
            f"La hoja '{hoja}' no existe en el archivo. "
            f"Hojas disponibles: {', '.join(hojas)}.",
            {"hoja": hoja, "hojas_disponibles": hojas},
        )
    return hoja


def _separar_encabezado(crudo: pd.DataFrame) -> pd.DataFrame:
    """Usa la primera fila como encabezado sin renombrar sus valores."""
    if crudo.empty:
        return pd.DataFrame()
    encabezado = list(crudo.iloc[0])
    # Las columnas quedan como object al leer con header=None; se recupera
    # el tipo que pandas habría inferido con el encabezado normal.
    datos = crudo.iloc[1:].reset_index(drop=True).infer_objects()
    datos.columns = encabezado
    return datos


def obtener_hojas_excel(ruta: str | Path) -> list[str]:
    """Devuelve los nombres de las hojas de un archivo XLSX, en orden.

    Raises:
        ErrorCarga: si el archivo no existe o no puede leerse.
    """
    ruta = Path(ruta)
    _comprobar_existencia(ruta)
    try:
        with pd.ExcelFile(ruta, engine="openpyxl") as libro:
            return [str(nombre) for nombre in libro.sheet_names]
    except _ERRORES_EXCEL as exc:
        raise _error_excel_ilegible(ruta, exc) from exc


def cargar_excel(ruta: str | Path, hoja: str | None = None) -> pd.DataFrame:
    """Carga una hoja de un archivo XLSX.

    Si el libro tiene una sola hoja, ``hoja`` puede omitirse. Si tiene
    varias, es obligatoria: nunca se elige una hoja automáticamente.

    Raises:
        ErrorCarga: si el archivo no puede leerse o la hoja no existe o no
            se especificó.
    """
    ruta = Path(ruta)
    _comprobar_existencia(ruta)
    try:
        with pd.ExcelFile(ruta, engine="openpyxl") as libro:
            nombre = _seleccionar_hoja([str(h) for h in libro.sheet_names], hoja)
            crudo = libro.parse(nombre, header=None)
    except _ERRORES_EXCEL as exc:
        raise _error_excel_ilegible(ruta, exc) from exc
    return _separar_encabezado(crudo)

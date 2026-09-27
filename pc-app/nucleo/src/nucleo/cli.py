"""Interfaz de línea de comandos del núcleo.

Uso::

    python -m nucleo revisar <archivo> --objetivo <columna> [--hoja <nombre>]

Códigos de salida:

- 0: análisis completado (el dataset es válido y se generó el informe).
- 1: error de argumentos o de ejecución (archivo inexistente, formato no
  soportado, hoja inexistente, error al escribir el informe...).
- 2: dataset no válido (errores bloqueantes de validación). No se genera
  informe de revisión.

El informe se guarda como ``<nombre>_revision.json`` junto al archivo
analizado. Si ese archivo ya existe no se sobrescribe: se usa
``<nombre>_revision_2.json``, ``<nombre>_revision_3.json``, etc.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, TextIO

from nucleo.analisis import analizar_dataset, resultado_a_diccionario
from nucleo.carga import ErrorCarga, cargar_dataset
from nucleo.modelos import CodigoValidacion, ProblemaValidacion, ResultadoAnalisis, TipoHallazgo

SALIDA_CORRECTA = 0
SALIDA_ERROR = 1
SALIDA_DATASET_INVALIDO = 2

_SEPARADOR = "=" * 48

_ETIQUETAS_HALLAZGO = {
    TipoHallazgo.FILAS_DUPLICADAS: "Filas duplicadas",
    TipoHallazgo.VALORES_FALTANTES: "Columnas con valores faltantes",
    TipoHallazgo.ALTA_PROPORCION_FALTANTES: "Columnas con alta proporción de faltantes",
    TipoHallazgo.CEROS_SOSPECHOSOS: "Ceros sospechosos",
    TipoHallazgo.CONSTANTE: "Columnas constantes",
    TipoHallazgo.CASI_CONSTANTE: "Columnas casi constantes",
    TipoHallazgo.POSIBLE_IDENTIFICADOR: "Posibles identificadores",
    TipoHallazgo.TEXTO_LIBRE: "Texto libre",
    TipoHallazgo.POSIBLE_FECHA: "Posibles fechas",
    TipoHallazgo.VARIABLE_CATEGORICA: "Variables categóricas",
    TipoHallazgo.POSIBLE_VARIABLE_ORDINAL: "Posibles variables ordinales",
    TipoHallazgo.DISTRIBUCION_OBJETIVO: "Distribución del objetivo",
    TipoHallazgo.DESBALANCE_CLASES: "Desbalance de clases",
    TipoHallazgo.COLUMNAS_REDUNDANTES: "Columnas copiadas",
    TipoHallazgo.RECODIFICACION_UNO_A_UNO: "Recodificaciones uno a uno",
    TipoHallazgo.COLUMNA_DERIVADA: "Variables derivadas (suma/resta)",
    TipoHallazgo.BINARIA_DERIVADA: "Binarias derivadas de un umbral",
    TipoHallazgo.CORRELACION_CASI_PERFECTA: "Correlaciones casi perfectas",
    TipoHallazgo.POSIBLE_MEZCLA_UNIDADES: "Posibles mezclas de unidades",
}

# Mensajes de argparse traducidos al español.
_TRADUCCIONES_ARGPARSE = (
    ("the following arguments are required", "faltan argumentos obligatorios"),
    ("unrecognized arguments", "argumentos no reconocidos"),
    ("invalid choice", "opción no válida"),
    ("choose from", "opciones"),
    ("expected one argument", "se esperaba un valor"),
    ("argument ", "argumento "),
)


class _ErrorArgumentos(Exception):
    """Error de uso de la CLI (argumentos faltantes o inválidos)."""


class _FormatoAyuda(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):  # noqa: ANN001
        super().add_usage(usage, actions, groups, prefix or "uso: ")


class _Parser(argparse.ArgumentParser):
    """``ArgumentParser`` con mensajes en español y sin terminar el proceso."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", _FormatoAyuda)
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "argumentos"
        self._optionals.title = "opciones"
        self.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y termina.")

    def error(self, message: str) -> None:  # type: ignore[override]
        for original, traduccion in _TRADUCCIONES_ARGPARSE:
            message = message.replace(original, traduccion)
        raise _ErrorArgumentos(message)


def construir_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m nucleo",
        description="Validación y revisión de datasets para modelos prescriptivos.",
    )
    comandos = parser.add_subparsers(dest="comando", title="comandos", metavar="COMANDO")
    revisar = comandos.add_parser(
        "revisar",
        help="Valida y revisa un dataset CSV o XLSX y guarda el informe en JSON.",
        description="Valida y revisa un dataset CSV o XLSX y guarda el informe en JSON.",
    )
    revisar.add_argument("archivo", help="Ruta del archivo CSV o XLSX.")
    revisar.add_argument("--objetivo", required=True, help="Nombre de la columna objetivo.")
    revisar.add_argument("--hoja", help="Hoja a analizar (solo XLSX con varias hojas).")
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Ejecuta la CLI y devuelve el código de salida."""
    parser = construir_parser()
    try:
        opciones = parser.parse_args(argumentos)
    except _ErrorArgumentos as error:
        _error(f"Error: {error}.")
        _error("Use 'python -m nucleo revisar --help' para ver la ayuda.")
        return SALIDA_ERROR
    except SystemExit as salida:  # --help
        return int(salida.code or 0)
    if opciones.comando is None:
        parser.print_help()
        return SALIDA_ERROR
    return ejecutar_revisar(Path(opciones.archivo), opciones.objetivo, opciones.hoja)


def ejecutar_revisar(ruta: Path, objetivo: str, hoja: str | None) -> int:
    """Carga, analiza, muestra el resumen y guarda el informe JSON."""
    print("Analizando dataset...")
    print(f"Archivo: {ruta}")
    if hoja is not None:
        print(f"Hoja: {hoja}")
    try:
        dataframe = cargar_dataset(ruta, hoja=hoja)
    except ErrorCarga as error:
        _imprimir_error_carga(error.problema, ruta)
        return SALIDA_ERROR

    resultado = analizar_dataset(dataframe, objetivo)
    if not resultado.valido:
        _imprimir_dataset_invalido(resultado, dataframe.shape)
        return SALIDA_DATASET_INVALIDO

    salida = ruta_informe(ruta)
    datos = {"origen": {"archivo": ruta.name, "hoja": hoja}, **resultado_a_diccionario(resultado)}
    try:
        salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as error:
        _error(f"Error: no se pudo guardar el informe en '{salida}': {error}.")
        return SALIDA_ERROR
    _imprimir_resumen(ruta, hoja, resultado, salida)
    return SALIDA_CORRECTA


def ruta_informe(ruta: Path) -> Path:
    """``<nombre>_revision.json`` junto al archivo; nunca un archivo existente."""
    candidata = ruta.with_name(f"{ruta.stem}_revision.json")
    numero = 2
    while candidata.exists():
        candidata = ruta.with_name(f"{ruta.stem}_revision_{numero}.json")
        numero += 1
    return candidata


# --- Presentación --------------------------------------------------------------


def _error(texto: str) -> None:
    """Escribe en stderr tras vaciar stdout, para conservar el orden de los mensajes."""
    sys.stdout.flush()
    print(texto, file=sys.stderr, flush=True)


def _imprimir_error_carga(problema: ProblemaValidacion, ruta: Path) -> None:
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
    _error(f"Error: {mensaje}.")
    if "hojas_disponibles" in evidencia:
        _error("\nHojas disponibles:")
        for nombre in evidencia["hojas_disponibles"]:
            _error(f"- {nombre}")


def _imprimir_problemas(titulo: str, problemas: list[ProblemaValidacion], flujo: TextIO) -> None:
    if not problemas:
        return
    sys.stdout.flush()
    print(f"\n{titulo}:", file=flujo)
    for problema in problemas:
        print(f"- [{problema.codigo}] {problema.mensaje}", file=flujo)
    flujo.flush()


def _imprimir_dataset_invalido(resultado: ResultadoAnalisis, forma: tuple[int, int]) -> None:
    print(f"Filas: {forma[0]}")
    print(f"Columnas: {forma[1]}")
    _imprimir_problemas("Errores bloqueantes", resultado.validacion.errores, sys.stderr)
    _imprimir_problemas("Advertencias", resultado.validacion.advertencias, sys.stdout)
    print("\nResultado:\nDATASET NO VÁLIDO: no se realizó la revisión ni se generó el informe.")


def _imprimir_resumen(
    ruta: Path, hoja: str | None, resultado: ResultadoAnalisis, salida: Path
) -> None:
    informe = resultado.informe
    assert informe is not None
    resumen = informe.resumen
    lineas = [
        "",
        _SEPARADOR,
        "REVISIÓN DEL DATASET",
        _SEPARADOR,
        "",
        f"Archivo: {ruta.name}" + (f" (hoja: {hoja})" if hoja else ""),
        f"Filas: {resumen['filas']}",
        f"Columnas: {resumen['columnas']}",
        "",
        f"Objetivo: {resumen['objetivo']}",
        f"Tipo de objetivo: {resumen['tipo_objetivo'] or 'no determinado'}",
        "",
        f"Columnas numéricas: {resumen['columnas_numericas']}",
        f"Columnas categóricas/texto: {resumen['columnas_categoricas'] + resumen['columnas_texto']}",
        f"Columnas fecha: {resumen['columnas_fecha']}",
        f"Columnas booleanas: {resumen['columnas_booleanas']}",
        "",
        f"Valores faltantes: {resumen['total_faltantes']}",
        "",
    ]
    conteo = Counter(h.tipo for h in informe.hallazgos)
    if conteo:
        lineas.append(f"Hallazgos ({len(informe.hallazgos)}):")
        lineas += [
            f"- {etiqueta}: {conteo[tipo]}"
            for tipo, etiqueta in _ETIQUETAS_HALLAZGO.items()
            if conteo[tipo]
        ]
    else:
        lineas.append("Hallazgos: ninguno")
    severidades = Counter(h.severidad.value for h in informe.hallazgos)
    if severidades:
        lineas.append(
            "Por severidad: "
            + ", ".join(f"{nivel} {severidades[nivel]}" for nivel in ("alta", "media", "baja"))
        )
    if resultado.validacion.advertencias:
        lineas.append("")
        lineas.append("Advertencias de validación:")
        lineas += [f"- {p.mensaje}" for p in resultado.validacion.advertencias]
    lineas += ["", f"Informe completo: {salida}", "", "Resultado:", "REVISIÓN COMPLETADA"]
    print("\n".join(lineas))

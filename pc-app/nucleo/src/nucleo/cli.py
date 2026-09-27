"""Interfaz de línea de comandos del núcleo.

Uso::

    python -m nucleo revisar <archivo> --objetivo <columna> [--hoja <nombre>]
    python -m nucleo plantilla <archivo> --objetivo <columna> [--hoja <nombre>]
    python -m nucleo preparar <archivo> --objetivo <columna> --decisiones <json>
        [--hoja <nombre>] [--test 0.3] [--semilla 42] [--fecha <col> [--corte <fecha>]]
    python -m nucleo sugerir-prueba <receta.json> [--sin-estimacion]

Códigos de salida:

- 0: comando completado.
- 1: error de argumentos o de ejecución (archivo inexistente, formato no
  soportado, hoja inexistente, decisiones no aplicables, error al escribir...).
- 2: dataset no válido (errores bloqueantes de validación). No se genera
  ningún archivo.

Los archivos generados se guardan junto al archivo de entrada y nunca
sobrescriben uno existente: se añade ``_2``, ``_3``, etc. al nombre.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from nucleo.analisis import analizar_dataset, resultado_a_diccionario
from nucleo.cli_comun import (
    SALIDA_CORRECTA,
    SALIDA_DATASET_INVALIDO,
    SALIDA_ERROR,
    SEPARADOR,
    cargar,
    error,
    escribir_json,
    imprimir_dataset_invalido,
    rutas_libres,
)
from nucleo.modelos import ResultadoAnalisis, TipoHallazgo

__all__ = ["SALIDA_CORRECTA", "SALIDA_DATASET_INVALIDO", "SALIDA_ERROR", "main"]

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
    TipoHallazgo.ASIMETRIA_FUERTE: "Variables muy asimétricas",
    TipoHallazgo.DISTRIBUCION_OBJETIVO: "Distribución del objetivo",
    TipoHallazgo.DESBALANCE_CLASES: "Desbalance de clases",
    TipoHallazgo.FALTANTES_DEPENDIENTES_OBJETIVO: "Faltantes que dependen del objetivo",
    TipoHallazgo.TAMANO_EFECTIVO_INSUFICIENTE: "Tamaño efectivo insuficiente",
    TipoHallazgo.GRUPO_REDUNDANTE: "Grupos de variables redundantes",
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
    ("invalid float value", "número no válido"),
    ("invalid int value", "número entero no válido"),
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


def _argumentos_dataset(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("archivo", help="Ruta del archivo CSV o XLSX.")
    parser.add_argument("--objetivo", required=True, help="Nombre de la columna objetivo.")
    parser.add_argument("--hoja", help="Hoja a usar (solo XLSX con varias hojas).")


def construir_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="python -m nucleo",
        description="Validación, revisión y preparación de datasets para modelos prescriptivos.",
    )
    comandos = parser.add_subparsers(dest="comando", title="comandos", metavar="COMANDO")

    texto = "Valida y revisa un dataset CSV o XLSX y guarda el informe en JSON."
    _argumentos_dataset(comandos.add_parser("revisar", help=texto, description=texto))

    texto = "Genera <nombre>_decisiones.json con las acciones sugeridas para cada hallazgo."
    _argumentos_dataset(comandos.add_parser("plantilla", help=texto, description=texto))

    texto = "Aplica las decisiones y genera la receta y los CSV de entrenamiento y test."
    preparar = comandos.add_parser("preparar", help=texto, description=texto)
    _argumentos_dataset(preparar)
    preparar.add_argument("--decisiones", required=True, help="JSON de decisiones (ver 'plantilla').")
    preparar.add_argument("--test", type=float, help="Proporción de test (por defecto 0.3).")
    preparar.add_argument("--semilla", type=int, help="Semilla de la separación (por defecto 42).")
    preparar.add_argument("--fecha", help="Columna de fecha para una separación temporal.")
    preparar.add_argument(
        "--corte", help="Fecha de corte AAAA-MM-DD (con --fecha); sin ella, el primer 70 %% cronológico."
    )

    texto = "Recomienda la prueba de independencia para PC a partir de una receta."
    sugerir = comandos.add_parser("sugerir-prueba", help=texto, description=texto)
    sugerir.add_argument("receta", help="Receta JSON generada por 'preparar'.")
    sugerir.add_argument(
        "--sin-estimacion", action="store_true",
        help="No estimar el tiempo de PC (la estimación puede tardar varios minutos).",
    )
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Ejecuta la CLI y devuelve el código de salida."""
    parser = construir_parser()
    try:
        opciones = parser.parse_args(argumentos)
    except _ErrorArgumentos as problema:
        error(f"Error: {problema}.")
        error("Use 'python -m nucleo <comando> --help' para ver la ayuda.")
        return SALIDA_ERROR
    except SystemExit as salida:  # --help
        return int(salida.code or 0)
    if opciones.comando is None:
        parser.print_help()
        return SALIDA_ERROR
    if opciones.comando == "revisar":
        return ejecutar_revisar(Path(opciones.archivo), opciones.objetivo, opciones.hoja)

    from nucleo import cli_preparacion  # importación diferida: carga scikit-learn y causal-learn

    if opciones.comando == "plantilla":
        return cli_preparacion.ejecutar_plantilla(Path(opciones.archivo), opciones.objetivo, opciones.hoja)
    if opciones.comando == "preparar":
        return cli_preparacion.ejecutar_preparar(
            Path(opciones.archivo), opciones.objetivo, opciones.hoja, Path(opciones.decisiones),
            opciones.test, opciones.semilla, opciones.fecha, opciones.corte,
        )
    return cli_preparacion.ejecutar_sugerir(Path(opciones.receta), not opciones.sin_estimacion)


def ejecutar_revisar(ruta: Path, objetivo: str, hoja: str | None) -> int:
    """Carga, analiza, muestra el resumen y guarda el informe JSON."""
    print("Analizando dataset...")
    print(f"Archivo: {ruta}")
    if hoja is not None:
        print(f"Hoja: {hoja}")
    dataframe = cargar(ruta, hoja)
    if dataframe is None:
        return SALIDA_ERROR
    resultado = analizar_dataset(dataframe, objetivo)
    if not resultado.valido:
        imprimir_dataset_invalido(
            resultado.validacion, dataframe.shape,
            "no se realizó la revisión ni se generó el informe.",
        )
        return SALIDA_DATASET_INVALIDO
    [salida] = rutas_libres(ruta, ["_revision.json"])
    datos = {"origen": {"archivo": ruta.name, "hoja": hoja}, **resultado_a_diccionario(resultado)}
    if not escribir_json(salida, datos):
        return SALIDA_ERROR
    _imprimir_resumen(ruta, hoja, resultado, salida)
    return SALIDA_CORRECTA


def ruta_informe(ruta: Path) -> Path:
    """``<nombre>_revision.json`` junto al archivo; nunca un archivo existente."""
    return rutas_libres(ruta, ["_revision.json"])[0]


def _imprimir_resumen(
    ruta: Path, hoja: str | None, resultado: ResultadoAnalisis, salida: Path
) -> None:
    informe = resultado.informe
    assert informe is not None
    resumen = informe.resumen
    lineas = [
        "",
        SEPARADOR,
        "REVISIÓN DEL DATASET",
        SEPARADOR,
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
    sys.stdout.flush()

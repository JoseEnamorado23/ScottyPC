"""Comandos ``plantilla``, ``preparar`` y ``sugerir-prueba`` de la CLI."""

from __future__ import annotations

import os
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pandas as pd

from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.cli_comun import (
    SALIDA_CORRECTA,
    SALIDA_DATASET_INVALIDO,
    SALIDA_ERROR,
    SEPARADOR,
    cargar,
    error,
    escribir_json,
    imprimir_dataset_invalido,
    leer_json,
    rutas_libres,
)
from pcapp_nucleo.plantilla import generar_plantilla
from pcapp_nucleo.preparacion import (
    DatosPreparados,
    DecisionesUsuario,
    ErrorPreparacion,
    OrigenDatos,
    aplicar_receta,
    calcular_sha256,
    decisiones_desde_diccionario,
    preparar,
    receta_a_diccionario,
    receta_desde_diccionario,
)
from pcapp_nucleo.seleccion_prueba import RecomendacionPrueba, formatear_duracion, recomendar_prueba
from pcapp_nucleo.utilidades import a_diccionario_serializable
from pcapp_nucleo.validacion import validar_dataset


# --- plantilla -------------------------------------------------------------------------------


def ejecutar_plantilla(ruta: Path, objetivo: str, hoja: str | None) -> int:
    """Revisa el dataset y guarda ``<nombre>_decisiones.json`` con las acciones sugeridas."""
    print("Generando plantilla de decisiones...")
    print(f"Archivo: {ruta}")
    dataframe = cargar(ruta, hoja)
    if dataframe is None:
        return SALIDA_ERROR
    resultado = analizar_dataset(dataframe, objetivo)
    if not resultado.valido:
        imprimir_dataset_invalido(
            resultado.validacion, dataframe.shape, "no se generó la plantilla."
        )
        return SALIDA_DATASET_INVALIDO
    decisiones = generar_plantilla(resultado.informe)
    [salida] = rutas_libres(ruta, ["_decisiones.json"])
    if not escribir_json(salida, a_diccionario_serializable(decisiones)):
        return SALIDA_ERROR
    _imprimir_plantilla(decisiones, salida, ruta, objetivo, hoja)
    return SALIDA_CORRECTA


def _imprimir_plantilla(
    decisiones: DecisionesUsuario, salida: Path, ruta: Path, objetivo: str, hoja: str | None
) -> None:
    lineas = ["", SEPARADOR, "PLANTILLA DE DECISIONES", SEPARADOR, ""]
    lineas.append(f"Eliminar filas duplicadas: {'sí' if decisiones.eliminar_duplicados else 'no'}")
    lineas.append(f"Columnas excluidas: {', '.join(decisiones.columnas_excluidas) or 'ninguna'}")
    if decisiones.codificaciones:
        lineas.append(
            "Codificaciones: "
            + ", ".join(f"{c} ({k.tipo})" for c, k in decisiones.codificaciones.items())
        )
    if decisiones.faltantes:
        lineas.append(
            "Faltantes: "
            + ", ".join(
                f"{c} ({t.imputacion or 'conservar'}{' + indicador' if t.indicador_medido else ''})"
                for c, t in decisiones.faltantes.items()
            )
        )
    if decisiones.logaritmos:
        lineas.append(f"Logaritmo: {', '.join(decisiones.logaritmos)}")
    if decisiones.columnas_fecha_disponibles:
        lineas.append(
            "Columnas de fecha disponibles para una separación temporal: "
            + ", ".join(decisiones.columnas_fecha_disponibles)
        )
    confirmar = {k: a for k, a in decisiones.acciones_hallazgos.items() if a.requiere_confirmacion}
    if confirmar:
        lineas += ["", f"Decisiones que requieren su confirmación ({len(confirmar)}):"]
        lineas += [f"- {clave}: {accion.accion}. {accion.descripcion}" for clave, accion in confirmar.items()]
    if decisiones.notas:
        lineas += ["", "Notas:"] + [f"- {nota}" for nota in decisiones.notas]
    comando = f'python -m pcapp_nucleo preparar "{ruta}" --objetivo "{objetivo}" --decisiones "{salida}"'
    if hoja:
        comando += f' --hoja "{hoja}"'
    lineas += [
        "", f"Plantilla guardada en: {salida}", "",
        "Revise y edite el archivo; después ejecute:", f"  {comando}",
    ]
    print("\n".join(lineas))
    sys.stdout.flush()


# --- preparar --------------------------------------------------------------------------------


def _aplicar_opciones(
    decisiones: DecisionesUsuario,
    test: float | None,
    semilla: int | None,
    fecha: str | None,
    corte: str | None,
) -> DecisionesUsuario:
    """Las opciones de la línea de comandos sustituyen a las del JSON de decisiones."""
    separacion = decisiones.separacion
    if corte is not None and fecha is None and separacion.columna_fecha is None:
        raise ErrorPreparacion("--corte requiere indicar la columna de fecha con --fecha.")
    cambios: dict = {}
    if test is not None:
        cambios["proporcion_test"] = test
    if semilla is not None:
        cambios["semilla"] = semilla
    if fecha is not None:
        cambios.update(tipo="temporal", columna_fecha=fecha)
    if corte is not None:
        cambios.update(tipo="temporal", corte=corte)
    return replace(decisiones, separacion=replace(separacion, **cambios))


def ejecutar_preparar(
    ruta: Path,
    objetivo: str,
    hoja: str | None,
    ruta_decisiones: Path,
    test: float | None,
    semilla: int | None,
    fecha: str | None,
    corte: str | None,
) -> int:
    """Aplica las decisiones y guarda la receta y los CSV de entrenamiento y test."""
    print("Preparando datos...")
    print(f"Archivo: {ruta}")
    datos_json = leer_json(ruta_decisiones, "decisiones")
    if datos_json is None:
        return SALIDA_ERROR
    try:
        decisiones = _aplicar_opciones(
            decisiones_desde_diccionario(datos_json), test, semilla, fecha, corte
        )
    except ErrorPreparacion as problema:
        error(f"Error: {problema}")
        return SALIDA_ERROR
    dataframe = cargar(ruta, hoja)
    if dataframe is None:
        return SALIDA_ERROR
    validacion = validar_dataset(dataframe, objetivo)
    if not validacion.valido:
        imprimir_dataset_invalido(validacion, dataframe.shape, "no se prepararon los datos.")
        return SALIDA_DATASET_INVALIDO
    rutas = rutas_libres(ruta, ["_receta.json", "_train.csv", "_test.csv"])
    receta_ruta, train_ruta, test_ruta = rutas
    origen = OrigenDatos(
        archivo=os.path.relpath(ruta.resolve(), receta_ruta.resolve().parent),
        hoja=hoja,
        sha256=calcular_sha256(ruta),
    )
    try:
        datos = preparar(dataframe, objetivo, decisiones, origen=origen)
    except ErrorPreparacion as problema:
        error(f"Error: {problema}")
        return SALIDA_ERROR
    try:
        datos.train.to_csv(train_ruta, index=False)
        datos.test.to_csv(test_ruta, index=False)
    except OSError as problema:
        error(f"Error: no se pudieron guardar los CSV: {problema}.")
        return SALIDA_ERROR
    if not escribir_json(receta_ruta, receta_a_diccionario(datos.receta)):
        return SALIDA_ERROR
    _imprimir_preparacion(datos, decisiones, rutas)
    return SALIDA_CORRECTA


def _imprimir_preparacion(
    datos: DatosPreparados, decisiones: DecisionesUsuario, rutas: list[Path]
) -> None:
    receta = datos.receta
    separacion = receta.separacion_aplicada
    tipos = Counter(m.tipo_final for m in datos.columnas if m.nombre != datos.objetivo)
    lineas = ["", SEPARADOR, "DATOS PREPARADOS", SEPARADOR, ""]
    if receta.parametros_previos.get("filas_duplicadas_eliminadas"):
        lineas.append(f"Filas duplicadas eliminadas: {receta.parametros_previos['filas_duplicadas_eliminadas']}")
    if receta.parametros_previos.get("filas_eliminadas_por_faltantes"):
        lineas.append(f"Filas eliminadas por faltantes: {receta.parametros_previos['filas_eliminadas_por_faltantes']}")
    descripcion = separacion["tipo"]
    if separacion["tipo"] == "temporal":
        descripcion += f" por '{separacion['columna_fecha']}' (corte {separacion['corte']})"
    lineas += [
        f"Separación: {descripcion}",
        f"Entrenamiento: {separacion['filas_train']} filas | Test: {separacion['filas_test']} filas",
        f"Objetivo: {datos.objetivo} ({datos.tipo_objetivo or 'tipo no determinado'})",
        f"Variables: {sum(tipos.values())} ("
        + ", ".join(f"{tipo}: {n}" for tipo, n in sorted(tipos.items())) + ")",
    ]
    faltantes = int(datos.train.drop(columns=[datos.objetivo]).isna().sum().sum())
    if faltantes:
        lineas.append(f"Faltantes conservados en entrenamiento: {faltantes}")
    if receta.advertencias:
        lineas += ["", "Advertencias:"] + [f"- {a}" for a in receta.advertencias]
    confirmar = [k for k, a in decisiones.acciones_hallazgos.items() if a.requiere_confirmacion]
    if confirmar:
        lineas += ["", f"Nota: {len(confirmar)} decisiones requerían confirmación del usuario "
                   "(ver 'acciones_hallazgos' en las decisiones)."]
    lineas += [
        "",
        f"Receta: {rutas[0]}",
        f"Entrenamiento: {rutas[1]}",
        f"Test: {rutas[2]}",
        "",
        "Siguiente paso:",
        f'  python -m pcapp_nucleo sugerir-prueba "{rutas[0]}"',
    ]
    print("\n".join(lineas))
    sys.stdout.flush()


# --- sugerir-prueba ----------------------------------------------------------------------------


def cargar_desde_receta(ruta_receta: Path) -> tuple[pd.DataFrame, DatosPreparados] | None:
    """Lee la receta, verifica el hash del archivo original y reproduce la preparación.

    Devuelve (datos originales, datos preparados) o ``None`` tras informar el error.
    """
    print("Cargando receta...")
    print(f"Receta: {ruta_receta}")
    datos_json = leer_json(ruta_receta, "receta")
    if datos_json is None:
        return None
    try:
        receta = receta_desde_diccionario(datos_json)
    except ErrorPreparacion as problema:
        error(f"Error: {problema}")
        return None
    if receta.origen.archivo is None:
        error("Error: la receta no indica el archivo de datos original.")
        return None
    archivo = ruta_receta.parent / receta.origen.archivo
    if not archivo.is_file():
        error(f"Error: no se encontró el archivo original de la receta ({archivo}).")
        return None
    if receta.origen.sha256 and calcular_sha256(archivo) != receta.origen.sha256:
        error(
            f"Error: el archivo '{archivo}' cambió desde que se creó la receta "
            "(el hash SHA-256 no coincide). Vuelva a ejecutar 'preparar'."
        )
        return None
    dataframe = cargar(archivo, receta.origen.hoja)
    if dataframe is None:
        return None
    try:
        return dataframe, aplicar_receta(dataframe, receta)
    except ErrorPreparacion as problema:
        error(f"Error: {problema}")
        return None


def ejecutar_sugerir(ruta_receta: Path, estimar: bool) -> int:
    """Reproduce la preparación desde la receta y recomienda la prueba de independencia."""
    cargados = cargar_desde_receta(ruta_receta)
    if cargados is None:
        return SALIDA_ERROR
    _, datos = cargados
    if estimar:
        print("Estimando el tiempo de PC (varias ejecuciones; puede tardar algunos minutos)...")
        sys.stdout.flush()
    recomendacion = recomendar_prueba(datos, estimar=estimar)
    base = ruta_receta.stem.removesuffix("_receta")
    [salida] = rutas_libres(ruta_receta, ["_recomendacion.json"], base=base)
    if not escribir_json(salida, a_diccionario_serializable(recomendacion)):
        return SALIDA_ERROR
    _imprimir_recomendacion(recomendacion, salida)
    return SALIDA_CORRECTA


def _imprimir_recomendacion(recomendacion: RecomendacionPrueba, salida: Path) -> None:
    lineas = [
        "", SEPARADOR, "PRUEBA DE INDEPENDENCIA SUGERIDA", SEPARADOR, "",
        f"Prueba sugerida: {recomendacion.prueba}"
        + (f" (continuas discretizadas en {recomendacion.discretizacion})" if recomendacion.discretizacion else ""),
        f"Motivo: {recomendacion.motivo}",
        "",
        f"Entrenamiento: {recomendacion.filas_train} filas, {recomendacion.variables} variables "
        f"({100 * recomendacion.proporcion_categoricas:.0f} % categóricas o binarias)",
    ]
    if recomendacion.faltantes_restantes:
        lineas.append(
            "Faltantes restantes: "
            + ", ".join(f"{c} ({n})" for c, n in recomendacion.faltantes_restantes.items())
        )
    no_monotonas = [d for d in recomendacion.diagnosticos if d.monotona is False]
    if no_monotonas:
        lineas += ["", "Variables con relación no monótona con el objetivo:"]
        for diagnostico in no_monotonas:
            curva = " → ".join(f"{v:g}" for v in diagnostico.valores_por_intervalo)
            lineas.append(f"- {diagnostico.nombre}: {diagnostico.medida} por sextil {curva}")
    lineas += ["", "Alternativas:"]
    for alternativa in recomendacion.alternativas:
        lineas.append(f"- {alternativa.prueba}: + {alternativa.ventajas} − {alternativa.desventajas}")
    lineas.append("")
    if recomendacion.tiempo_por_ejecucion_s is not None:
        lineas.append(
            f"Tiempo estimado: {formatear_duracion(recomendacion.tiempo_por_ejecucion_s)} por ejecución; "
            f"unos {formatear_duracion(recomendacion.tiempo_estimado_bootstrap_s)} para 100 corridas de bootstrap."
        )
    elif recomendacion.nota_tiempo is None:
        lineas.append("Tiempo estimado: no calculado (--sin-estimacion).")
    if recomendacion.nota_tiempo:
        lineas.append(recomendacion.nota_tiempo)
    lineas += [
        "",
        "La recomendación es una sugerencia: puede elegir otra prueba.",
        f"Recomendación completa: {salida}",
    ]
    print("\n".join(lineas))
    sys.stdout.flush()

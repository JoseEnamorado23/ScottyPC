"""Comandos ``plantilla-pc`` y ``pc`` de la CLI."""

from __future__ import annotations

import signal
import sys
import threading
from collections import Counter
from dataclasses import replace
from pathlib import Path

from nucleo.caracterizacion import (
    AMBIGUA,
    CAUSA_DIRECTA,
    CAUSA_INDIRECTA,
    CONSECUENCIA,
    SIN_CAMINO,
    Caracterizacion,
    caracterizar,
)
from nucleo.cli_comun import (
    SALIDA_CORRECTA,
    SALIDA_ERROR,
    SEPARADOR,
    carpeta_libre,
    carpetas_numeradas,
    error,
    escribir_json,
    leer_json,
    rutas_libres,
)
from nucleo.cli_preparacion import cargar_desde_receta
from nucleo.exportacion import exportar
from nucleo.modelos import TipoHallazgo
from nucleo.pc_bootstrap import GrafoAgregado, ResultadoBootstrap, agregar, ejecutar_bootstrap
from nucleo.pc_config import (
    ConfiguracionPC,
    ErrorConfiguracionPC,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    validar_configuracion,
)
from nucleo.revision import revisar_dataset
from nucleo.seleccion_prueba import formatear_duracion, recomendar_prueba
from nucleo.utilidades import a_diccionario_serializable

PUNTO_CONTROL = "punto_control.json"


def _base(ruta_receta: Path) -> str:
    return ruta_receta.stem.removesuffix("_receta")


# --- plantilla-pc ----------------------------------------------------------------------------


def ejecutar_plantilla_pc(ruta_receta: Path) -> int:
    """Guarda ``<nombre>_pc.json`` con la configuración por defecto y la prueba recomendada."""
    cargados = cargar_desde_receta(ruta_receta)
    if cargados is None:
        return SALIDA_ERROR
    _, datos = cargados
    base = _base(ruta_receta)
    ruta_recomendacion = ruta_receta.with_name(f"{base}_recomendacion.json")
    recomendacion = leer_json(ruta_recomendacion, "recomendación") if ruta_recomendacion.is_file() else None
    if recomendacion is not None:
        prueba, max_k = recomendacion["prueba"], recomendacion.get("max_k_sugerido")
        fuente = f"de {ruta_recomendacion.name}"
    else:
        prueba, max_k = recomendar_prueba(datos, estimar=False).prueba, None
        fuente = "recomendada para estos datos (sin estimación de tiempo)"
    configuracion = configuracion_por_defecto(list(datos.train.columns), datos.objetivo, prueba, max_k)
    [salida] = rutas_libres(ruta_receta, ["_pc.json"], base=base)
    if not escribir_json(salida, a_diccionario_serializable(configuracion)):
        return SALIDA_ERROR
    lineas = [
        "", SEPARADOR, "CONFIGURACIÓN DE PC", SEPARADOR, "",
        f"Prueba: {prueba} ({fuente})" + (f", max_k = {max_k}" if max_k is not None else ""),
        f"Corridas de bootstrap: {configuracion.corridas_bootstrap} · umbral de frecuencia: "
        f"{configuracion.umbral_frecuencia} · procesos: {configuracion.procesos}",
        f"Niveles: {len(configuracion.niveles[0])} variables en el nivel 1 y el objetivo "
        f"'{datos.objetivo}' en el nivel 2.",
        "",
        f"Configuración guardada en: {salida}",
        "",
        "Revise y edite el archivo: ordene las variables en 'niveles' (nada de un nivel",
        "posterior puede causar algo de uno anterior) y marque las 'modificables'. Después:",
        f'  python -m nucleo pc "{ruta_receta}" --config "{salida}"',
    ]
    print("\n".join(lineas))
    sys.stdout.flush()
    return SALIDA_CORRECTA


# --- pc ------------------------------------------------------------------------------------------


def _mostrar_avance(completadas: int, total: int, segundos: float) -> None:
    faltan = segundos / completadas * (total - completadas) if completadas else 0.0
    texto = (
        f"\rCorrida {completadas}/{total} · {formatear_duracion(segundos)} transcurridos"
        + (f" · faltan ~{formatear_duracion(faltan)}" if completadas < total else "")
    )
    print(texto.ljust(72), end="", flush=True)


def _carpeta_para_reanudar(ruta_receta: Path) -> Path | None:
    con_punto = [c for c in carpetas_numeradas(ruta_receta, f"{_base(ruta_receta)}_pc") if (c / PUNTO_CONTROL).is_file()]
    return con_punto[-1] if con_punto else None


def _grupos_redundantes(original, objetivo: str) -> list[list[str]]:
    informe = revisar_dataset(original, objetivo)
    return [h.columnas_involucradas for h in informe.hallazgos if h.tipo == TipoHallazgo.GRUPO_REDUNDANTE]


def ejecutar_pc(
    ruta_receta: Path, ruta_config: Path, procesos: int | None, reanudar: bool
) -> int:
    """Ejecuta PC con bootstrap y guarda los resultados en ``<nombre>_pc/``."""
    datos_config = leer_json(ruta_config, "configuración de PC")
    if datos_config is None:
        return SALIDA_ERROR
    try:
        configuracion = configuracion_desde_diccionario(datos_config)
        if procesos is not None:
            configuracion = replace(configuracion, procesos=procesos)
    except ErrorConfiguracionPC as problema:
        error(f"Error: {problema}")
        return SALIDA_ERROR
    cargados = cargar_desde_receta(ruta_receta)
    if cargados is None:
        return SALIDA_ERROR
    original, datos = cargados
    try:
        validar_configuracion(configuracion, list(datos.train.columns), datos.objetivo)
    except ErrorConfiguracionPC as problema:
        error(f"Error: {problema}")
        return SALIDA_ERROR

    if reanudar:
        carpeta = _carpeta_para_reanudar(ruta_receta)
        if carpeta is None:
            error(
                f"Error: no hay un análisis interrumpido que reanudar ({_base(ruta_receta)}_pc/"
                f"{PUNTO_CONTROL} no existe)."
            )
            return SALIDA_ERROR
    else:
        carpeta = carpeta_libre(ruta_receta, f"{_base(ruta_receta)}_pc")
        carpeta.mkdir()

    print(
        f"Ejecutando PC ({configuracion.prueba}, {configuracion.corridas_bootstrap} corridas, "
        f"{configuracion.procesos} proceso(s)){' desde el punto de control' if reanudar else ''}. "
        "Pulse Ctrl+C para cancelar."
    )
    cancelacion = threading.Event()

    def al_interrumpir(_senal, _marco) -> None:
        cancelacion.set()

    anterior = signal.signal(signal.SIGINT, al_interrumpir)
    try:
        resultado = ejecutar_bootstrap(
            datos, configuracion, _mostrar_avance, cancelacion, carpeta / PUNTO_CONTROL, reanudar
        )
    except ErrorConfiguracionPC as problema:
        print()
        error(f"Error: {problema}")
        return SALIDA_ERROR
    finally:
        signal.signal(signal.SIGINT, anterior)
    print()

    if not resultado.completo:
        print(
            f"\nAnálisis cancelado tras {resultado.corridas_completadas} de "
            f"{resultado.corridas_totales} corridas. El avance quedó guardado en "
            f"{carpeta / PUNTO_CONTROL}. Para continuar:\n"
            f'  python -m nucleo pc "{ruta_receta}" --config "{ruta_config}" --reanudar'
        )
        return SALIDA_ERROR

    grafo = agregar(resultado, datos, configuracion)
    caracterizacion = caracterizar(
        grafo, resultado, configuracion.modificables, _grupos_redundantes(original, datos.objetivo)
    )
    exportar(carpeta, configuracion, datos.receta, resultado, grafo, caracterizacion)
    _imprimir_resultado(configuracion, resultado, grafo, caracterizacion, carpeta)
    return SALIDA_CORRECTA


def _imprimir_resultado(
    configuracion: ConfiguracionPC,
    resultado: ResultadoBootstrap,
    grafo: GrafoAgregado,
    caracterizacion: Caracterizacion,
    carpeta: Path,
) -> None:
    tipos = Counter(a.tipo for a in grafo.aristas)
    por_categoria: dict[str, list[str]] = {}
    for variable in caracterizacion.variables:
        texto = variable.variable
        if variable.a_traves_de:
            texto += f" (a través de {', '.join(variable.a_traves_de)})"
        por_categoria.setdefault(variable.categoria, []).append(texto)
    fallidas = len(resultado.corridas_fallidas)
    lineas = [
        "", SEPARADOR, "RESULTADO DE PC", SEPARADOR, "",
        f"Prueba: {configuracion.prueba} (alpha {configuracion.alpha}"
        + (f", max_k {configuracion.max_k}" if configuracion.max_k is not None else "") + ")",
        f"Corridas: {resultado.corridas_validas} válidas"
        + (f", {fallidas} fallidas" if fallidas else "")
        + f" · tiempo {formatear_duracion(resultado.tiempo_s)}",
        f"Aristas aceptadas (frecuencia >= {configuracion.umbral_frecuencia}): {len(grafo.aristas)} "
        f"({tipos['dirigida']} dirigidas, {tipos['sin_orientar']} sin orientar, {tipos['manual']} manuales)",
        "",
        f"Respecto a '{caracterizacion.objetivo}':",
    ]
    etiquetas = {
        CAUSA_DIRECTA: "Causas directas", CAUSA_INDIRECTA: "Causas indirectas",
        CONSECUENCIA: "Consecuencias", AMBIGUA: "Ambiguas (aristas sin orientar)",
        SIN_CAMINO: "Sin camino",
    }
    for categoria, etiqueta in etiquetas.items():
        lineas.append(f"- {etiqueta}: {', '.join(por_categoria.get(categoria, [])) or 'ninguna'}")
    lineas += ["", caracterizacion.mensaje]
    if grafo.advertencias:
        lineas += ["", "Advertencias:"] + [f"- {a}" for a in grafo.advertencias]
    lineas += ["", f"Resultados en: {carpeta}"]
    print("\n".join(lineas))
    sys.stdout.flush()

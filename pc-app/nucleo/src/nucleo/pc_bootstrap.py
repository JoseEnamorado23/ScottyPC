"""PC con bootstrap y agregación de las aristas.

``ejecutar_bootstrap`` repite PC sobre submuestras del conjunto de
entrenamiento y acumula, por par de variables, cuántas corridas dieron
i→j, j→i o i—j. ``agregar`` convierte esas cuentas en el grafo final.

Reproducibilidad: la corrida ``k`` usa un generador derivado solo de
``(semilla, k)`` mediante ``numpy.random.SeedSequence`` y PC es determinista
(``stable=True``); como las matrices son sumas de enteros, el resultado no
depende del número de procesos, del orden de ejecución ni de si el análisis
se reanudó desde un punto de control.

Cancelación: ``cancelacion`` es cualquier objeto con ``is_set()`` (p. ej. un
``threading.Event``). Con un proceso, se atiende entre corridas; en paralelo,
se cancelan las corridas pendientes y se terminan los procesos con corridas
en curso (PC no puede interrumpirse desde dentro). El resultado parcial solo
incluye las corridas terminadas y se marca ``completo=False``.
"""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
import signal
import time
import warnings
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Executor, ProcessPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
from scipy import stats

from nucleo.pc_config import (
    ConfiguracionPC,
    ErrorConfiguracionPC,
    nivel_por_variable,
    validar_configuracion,
)
from nucleo.preparacion import CONTINUA, DatosPreparados
from nucleo.seleccion_prueba import discretizar
from nucleo.utilidades import a_diccionario_serializable

VERSION_PUNTO_CONTROL = 1
_INTERVALOS_CHISQ = 5

Progreso = Callable[[int, int, float], None]
"""callback(corridas_completadas, corridas_totales, segundos_transcurridos)."""


class Cancelacion(Protocol):
    def is_set(self) -> bool: ...


# --- Resultados ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CorridaFallida:
    corrida: int
    motivo: str


@dataclass(frozen=True)
class ProgresoBootstrap:
    """Avance del bootstrap tras cada corrida (para ``progreso_detallado``).

    ``completadas`` incluye las fallidas y las de sesiones anteriores al
    reanudar (``completadas_al_inicio``); ``segundos`` también acumula el
    tiempo previo, mientras que ``segundos_esta_sesion`` sirve para estimar el
    tiempo restante con el ritmo actual.
    """

    completadas: int
    total: int
    fallidas: int
    segundos: float
    completadas_al_inicio: int = 0
    segundos_esta_sesion: float = 0.0


@dataclass(frozen=True)
class EjecucionBootstrap:
    """Cómo se ejecutaron las corridas y por qué (no afecta al resultado)."""

    modo_solicitado: str
    modo_usado: str  # "secuencial" | "paralelo"
    procesos: int
    motivo: str
    segundos_primera_corrida: float | None = None
    segundos_segunda_corrida: float | None = None
    segundos_estimados_restantes: float | None = None


@dataclass(frozen=True)
class ResultadoBootstrap:
    """Cuentas acumuladas del bootstrap.

    ``dirigidas[i][j]``: corridas con i→j. ``sin_orientar[i][j]`` (simétrica):
    corridas con i—j; incluye las aristas bidireccionales (conflictos de
    orientación), cuyo total se informa en ``bidireccionales``.
    """

    variables: list[str]
    objetivo: str
    corridas_totales: int
    corridas_completadas: int
    corridas_validas: int
    corridas_fallidas: list[CorridaFallida]
    completo: bool
    dirigidas: list[list[int]]
    sin_orientar: list[list[int]]
    bidireccionales: int
    tiempo_s: float
    limites_discretizacion: dict[str, list[float]] = field(default_factory=dict)
    ejecucion: EjecucionBootstrap | None = None


@dataclass(frozen=True)
class AristaAgregada:
    """Arista aceptada. Las frecuencias son fracciones de las corridas válidas;
    ``frecuencia_origen_destino`` y ``frecuencia_destino_origen`` se refieren a
    ``origen`` y ``destino`` tal como aparecen en la arista."""

    origen: str
    destino: str
    tipo: str  # "dirigida" | "sin_orientar" | "manual"
    frecuencia_total: float
    frecuencia_origen_destino: float
    frecuencia_destino_origen: float
    frecuencia_sin_orientar: float
    spearman: float | None
    signo: int
    justificacion: str | None = None


@dataclass(frozen=True)
class GrafoAgregado:
    variables: list[str]
    objetivo: str
    umbral_frecuencia: float
    corridas_validas: int
    aristas: list[AristaAgregada]
    ciclos: list[list[str]]
    advertencias: list[str] = field(default_factory=list)


# --- Datos para PC ------------------------------------------------------------------------------


def matriz_para_pc(
    datos: DatosPreparados, configuracion: ConfiguracionPC
) -> tuple[np.ndarray, list[str], dict[str, list[float]]]:
    """Matriz de entrenamiento (variables en el orden del train) y límites de
    discretización. Con ``chisq`` las variables continuas (y un objetivo
    continuo) se discretizan en quintiles calculados con train."""
    train = datos.train
    variables = [str(c) for c in train.columns]
    faltantes = [c for c in variables if train[c].isna().any()]
    if faltantes and configuracion.prueba != "mv_fisherz":
        raise ErrorConfiguracionPC(
            f"La prueba {configuracion.prueba} no admite faltantes y quedan en: "
            f"{', '.join(faltantes)}. Use mv_fisherz o impútelos en la preparación."
        )
    limites: dict[str, list[float]] = {}
    if configuracion.prueba == "chisq":
        tipos = {m.nombre: m.tipo_final for m in datos.columnas}
        continuas = [c for c in variables if tipos.get(c) == CONTINUA]
        if datos.tipo_objetivo == "continuo":
            continuas.append(datos.objetivo)
        train, limites = discretizar(train, continuas, _INTERVALOS_CHISQ)
    return train[variables].to_numpy(dtype=float), variables, limites


def prohibiciones_por_niveles(configuracion: ConfiguracionPC) -> list[tuple[str, str]]:
    """Pares (a, b) prohibidos como a→b: ``a`` está en un nivel posterior a ``b``."""
    nivel = nivel_por_variable(configuracion)
    return [(a, b) for a in nivel for b in nivel if nivel[a] > nivel[b]]


# --- Una corrida -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _ResultadoCorrida:
    corrida: int
    dirigidas: np.ndarray | None
    sin_orientar: np.ndarray | None
    bidireccionales: int
    fallo: str | None


def submuestra(n: int, fraccion: float, semilla: int, corrida: int) -> np.ndarray:
    """Índices (ordenados) de la submuestra sin reemplazo de la corrida ``corrida``."""
    generador = np.random.default_rng(np.random.SeedSequence([semilla, corrida]))
    tamano = min(n, max(2, int(round(n * fraccion))))
    return np.sort(generador.choice(n, size=tamano, replace=False))


def ejecutar_corrida(
    matriz: np.ndarray,
    variables: list[str],
    prohibidos: list[tuple[str, str]],
    configuracion: ConfiguracionPC,
    corrida: int,
) -> _ResultadoCorrida:
    """Ejecuta PC sobre la submuestra de la corrida ``corrida`` (función pura)."""
    from causallearn.graph.GraphNode import GraphNode
    from causallearn.search.ConstraintBased.PC import pc
    from causallearn.utils.PCUtils.BackgroundKnowledge import BackgroundKnowledge

    datos = matriz[submuestra(len(matriz), configuracion.fraccion_submuestra, configuracion.semilla, corrida)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        dispersion = np.nanstd(datos, axis=0)
    constantes = [v for v, s in zip(variables, dispersion) if not s > 0]
    if constantes:
        return _ResultadoCorrida(
            corrida, None, None, 0,
            f"columna constante en la submuestra: {', '.join(constantes)}",
        )
    conocimiento = None
    if prohibidos:
        conocimiento = BackgroundKnowledge()
        for a, b in prohibidos:
            conocimiento.add_forbidden_by_node(GraphNode(a), GraphNode(b))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            grafo = pc(
                datos, configuracion.alpha, configuracion.prueba, stable=True,
                background_knowledge=conocimiento, verbose=False, show_progress=False,
                node_names=variables, max_k=configuracion.max_k,
            )
    except Exception as error:  # noqa: BLE001 - cualquier fallo de PC descarta la corrida
        return _ResultadoCorrida(corrida, None, None, 0, f"{type(error).__name__}: {error}")
    g = np.asarray(grafo.G.graph)
    dirigidas = ((g == -1) & (g.T == 1)).astype(np.int64)
    sin_orientar = ((g == -1) & (g.T == -1)).astype(np.int64)
    bidireccional = ((g == 1) & (g.T == 1)).astype(np.int64)
    return _ResultadoCorrida(
        corrida, dirigidas, sin_orientar + bidireccional, int(np.triu(bidireccional, 1).sum()), None
    )


# --- Trabajadores en paralelo ------------------------------------------------------------------------

_TRABAJADOR: dict[str, Any] = {}


def _inicializar_trabajador(matriz, variables, prohibidos, configuracion) -> None:
    # Ctrl+C lo gestiona el proceso principal (activa la cancelación).
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _TRABAJADOR.update(matriz=matriz, variables=variables, prohibidos=prohibidos, configuracion=configuracion)


def _corrida_en_trabajador(corrida: int) -> _ResultadoCorrida:
    return ejecutar_corrida(
        _TRABAJADOR["matriz"], _TRABAJADOR["variables"], _TRABAJADOR["prohibidos"],
        _TRABAJADOR["configuracion"], corrida,
    )


def _ignorar_interrupcion() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def crear_grupo_procesos(procesos: int) -> ProcessPoolExecutor:
    """Grupo de procesos para reutilizar entre análisis (``ejecutor`` de
    ``ejecutar_bootstrap``): contexto ``spawn`` y Ctrl+C ignorado en los
    procesos de trabajo. Quien lo crea es responsable de cerrarlo."""
    return ProcessPoolExecutor(
        max_workers=procesos,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_ignorar_interrupcion,
    )


def _terminar_procesos(ejecutor: ProcessPoolExecutor) -> None:
    """Termina los procesos de trabajo aunque tengan corridas en curso."""
    if hasattr(ejecutor, "terminate_workers"):  # Python >= 3.14
        ejecutor.terminate_workers()
        return
    for proceso in list(getattr(ejecutor, "_processes", {}).values()):
        proceso.terminate()
    ejecutor.shutdown(wait=False, cancel_futures=True)


# --- Estado acumulado y puntos de control -------------------------------------------------------------


class _Estado:
    def __init__(self, n: int) -> None:
        self.dirigidas = np.zeros((n, n), dtype=np.int64)
        self.sin_orientar = np.zeros((n, n), dtype=np.int64)
        self.bidireccionales = 0
        self.completadas: set[int] = set()
        self.fallidas: dict[int, str] = {}
        self.tiempo_previo = 0.0

    def sumar(self, resultado: _ResultadoCorrida) -> None:
        self.completadas.add(resultado.corrida)
        if resultado.fallo is not None:
            self.fallidas[resultado.corrida] = resultado.fallo
            return
        self.dirigidas += resultado.dirigidas
        self.sin_orientar += resultado.sin_orientar
        self.bidireccionales += resultado.bidireccionales


def firma_analisis(
    configuracion: ConfiguracionPC, datos: DatosPreparados, matriz: np.ndarray, variables: list[str]
) -> str:
    """Huella de todo lo que determina el resultado (no incluye ``procesos``)."""
    relevante = a_diccionario_serializable(configuracion)
    for campo in (
        "procesos", "punto_control_cada", "modificables", "orientaciones_manuales",
        "modo_ejecucion", "umbral_paralelo_s",
    ):
        relevante.pop(campo, None)
    contenido = json.dumps(
        {"configuracion": relevante, "origen": datos.receta.origen.sha256, "variables": variables},
        sort_keys=True,
    ).encode("utf-8")
    resumen = hashlib.sha256(contenido)
    resumen.update(np.ascontiguousarray(matriz).tobytes())
    return resumen.hexdigest()


def _guardar_punto_control(ruta: Path, estado: _Estado, firma: str, variables: list[str],
                           total: int, tiempo: float, limites: dict[str, list[float]]) -> None:
    contenido = {
        "version": VERSION_PUNTO_CONTROL,
        "firma": firma,
        "variables": variables,
        "corridas_totales": total,
        "corridas_completadas": sorted(estado.completadas),
        "corridas_fallidas": [{"corrida": k, "motivo": m} for k, m in sorted(estado.fallidas.items())],
        "dirigidas": estado.dirigidas.tolist(),
        "sin_orientar": estado.sin_orientar.tolist(),
        "bidireccionales": estado.bidireccionales,
        "tiempo_acumulado_s": tiempo,
        "limites_discretizacion": limites,
    }
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(contenido), encoding="utf-8")
    os.replace(temporal, ruta)


def _cargar_punto_control(ruta: Path, firma: str, n: int) -> _Estado:
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ErrorConfiguracionPC(f"No se pudo leer el punto de control '{ruta}': {error}.") from error
    if contenido.get("version") != VERSION_PUNTO_CONTROL or contenido.get("firma") != firma:
        raise ErrorConfiguracionPC(
            "El punto de control no corresponde a esta configuración o a estos datos; no se "
            "puede reanudar. Ejecute el análisis desde el principio."
        )
    estado = _Estado(n)
    estado.dirigidas = np.asarray(contenido["dirigidas"], dtype=np.int64)
    estado.sin_orientar = np.asarray(contenido["sin_orientar"], dtype=np.int64)
    estado.bidireccionales = int(contenido["bidireccionales"])
    estado.completadas = set(contenido["corridas_completadas"])
    estado.fallidas = {f["corrida"]: f["motivo"] for f in contenido["corridas_fallidas"]}
    estado.tiempo_previo = float(contenido["tiempo_acumulado_s"])
    return estado


# --- Bootstrap ------------------------------------------------------------------------------------------


def ejecutar_bootstrap(
    datos: DatosPreparados,
    configuracion: ConfiguracionPC,
    progreso: Progreso | None = None,
    cancelacion: Cancelacion | None = None,
    punto_control: str | Path | None = None,
    reanudar: bool = False,
    progreso_detallado: Callable[[ProgresoBootstrap], None] | None = None,
    ejecutor: Executor | None = None,
) -> ResultadoBootstrap:
    """Ejecuta PC en ``corridas_bootstrap`` submuestras del conjunto de entrenamiento.

    Args:
        progreso: se llama al terminar cada corrida con (completadas, total, segundos).
        progreso_detallado: como ``progreso``, pero recibe un ``ProgresoBootstrap``
            que incluye también las corridas fallidas.
        ejecutor: grupo de procesos externo (p. ej. de ``crear_grupo_procesos``) para
            reutilizarlo entre análisis y evitar el costo de arrancar procesos. Solo
            se usa si el análisis va en paralelo; no se cierra ni se terminan sus
            procesos. El resultado es idéntico con o sin él.
        cancelacion: objeto con ``is_set()``; al activarse se devuelve el resultado parcial.
        punto_control: archivo donde guardar el estado cada ``punto_control_cada``
            corridas y al cancelar; se borra al terminar con éxito.
        reanudar: continuar desde ``punto_control`` si existe.

    Raises:
        ErrorConfiguracionPC: si la configuración no es válida para los datos o el
            punto de control no corresponde a este análisis.
    """
    variables_train = [str(c) for c in datos.train.columns]
    validar_configuracion(configuracion, variables_train, datos.objetivo)
    matriz, variables, limites = matriz_para_pc(datos, configuracion)
    prohibidos = prohibiciones_por_niveles(configuracion)
    firma = firma_analisis(configuracion, datos, matriz, variables)
    total = configuracion.corridas_bootstrap
    ruta = Path(punto_control) if punto_control is not None else None
    if reanudar and ruta is not None and ruta.exists():
        estado = _cargar_punto_control(ruta, firma, len(variables))
    else:
        estado = _Estado(len(variables))
    pendientes = [k for k in range(total) if k not in estado.completadas]
    completadas_al_inicio = len(estado.completadas)
    inicio = time.perf_counter()

    def transcurrido() -> float:
        return estado.tiempo_previo + time.perf_counter() - inicio

    def guardar() -> None:
        if ruta is not None:
            _guardar_punto_control(ruta, estado, firma, variables, total, transcurrido(), limites)

    def registrar(resultado: _ResultadoCorrida) -> None:
        estado.sumar(resultado)
        if progreso is not None:
            progreso(len(estado.completadas), total, transcurrido())
        if progreso_detallado is not None:
            progreso_detallado(
                ProgresoBootstrap(
                    completadas=len(estado.completadas),
                    total=total,
                    fallidas=len(estado.fallidas),
                    segundos=transcurrido(),
                    completadas_al_inicio=completadas_al_inicio,
                    segundos_esta_sesion=time.perf_counter() - inicio,
                )
            )
        if len(estado.completadas) % configuracion.punto_control_cada == 0 and len(estado.completadas) < total:
            guardar()

    def cancelado() -> bool:
        return cancelacion is not None and cancelacion.is_set()

    def secuencial(corridas: list[int]) -> None:
        for corrida in corridas:
            if cancelado():
                break
            registrar(ejecutar_corrida(matriz, variables, prohibidos, configuracion, corrida))

    ejecucion = _decidir_y_ejecutar(
        configuracion, pendientes, secuencial,
        lambda corridas: _en_paralelo(
            matriz, variables, prohibidos, configuracion, corridas, registrar, cancelado, ejecutor
        ),
        cancelado,
    )

    completo = len(estado.completadas) == total
    if ruta is not None:
        if completo:
            ruta.unlink(missing_ok=True)
        else:
            guardar()
    return ResultadoBootstrap(
        variables=variables,
        objetivo=datos.objetivo,
        corridas_totales=total,
        corridas_completadas=len(estado.completadas),
        corridas_validas=len(estado.completadas) - len(estado.fallidas),
        corridas_fallidas=[CorridaFallida(k, m) for k, m in sorted(estado.fallidas.items())],
        completo=completo,
        dirigidas=estado.dirigidas.tolist(),
        sin_orientar=estado.sin_orientar.tolist(),
        bidireccionales=estado.bidireccionales,
        tiempo_s=round(transcurrido(), 3),
        limites_discretizacion=limites,
        ejecucion=ejecucion,
    )


def _decidir_y_ejecutar(
    configuracion: ConfiguracionPC,
    pendientes: list[int],
    secuencial: Callable[[list[int]], None],
    paralelo: Callable[[list[int]], None],
    cancelado: Callable[[], bool],
) -> EjecucionBootstrap:
    """Ejecuta las corridas pendientes en el modo configurado y explica la elección.

    En modo adaptativo, la primera corrida se ejecuta en este proceso y se
    mide; el resto va en paralelo solo si su tiempo estimado supera
    ``umbral_paralelo_s``.
    """
    solicitado = configuracion.modo_ejecucion
    procesos = configuracion.procesos

    def registro(usado: str, motivo: str, **tiempos: float | None) -> EjecucionBootstrap:
        return EjecucionBootstrap(
            solicitado, usado, procesos if usado == "paralelo" else 1, motivo, **tiempos
        )

    if len(pendientes) <= 1:
        secuencial(pendientes)
        return registro("secuencial", "Como mucho quedaba una corrida pendiente.")
    if procesos == 1:
        secuencial(pendientes)
        return registro("secuencial", "Se configuró un solo proceso.")
    if solicitado == "secuencial":
        secuencial(pendientes)
        return registro("secuencial", "Modo secuencial forzado en la configuración.")
    if solicitado == "paralelo":
        paralelo(pendientes)
        return registro("paralelo", f"Modo paralelo forzado en la configuración ({procesos} procesos).")

    def medir(corrida: int) -> float:
        inicio = time.perf_counter()
        secuencial([corrida])
        return time.perf_counter() - inicio

    umbral = configuracion.umbral_paralelo_s
    primera = medir(pendientes[0])
    tiempos: dict[str, float | None] = {"segundos_primera_corrida": round(primera, 3)}
    restantes = pendientes[1:]
    referencia = primera
    # La primera corrida incluye costos de arranque (importaciones, cachés) que
    # pueden multiplicar su duración; si con ella se superaría el umbral, se mide
    # una segunda corrida y se usa la más rápida.
    if not cancelado() and primera * len(restantes) > umbral and len(restantes) > 1:
        segunda = medir(restantes[0])
        tiempos["segundos_segunda_corrida"] = round(segunda, 3)
        restantes = restantes[1:]
        referencia = min(primera, segunda)
    if cancelado():
        return registro("secuencial", "Cancelado durante las corridas de medición.", **tiempos)
    estimado = referencia * len(restantes)
    tiempos["segundos_estimados_restantes"] = round(estimado, 1)
    medicion = f"Cada corrida tarda unos {referencia:.2f} s; las {len(restantes)} restantes tardarían unos {estimado:.0f} s en secuencial"
    if estimado > umbral:
        paralelo(restantes)
        return registro(
            "paralelo",
            f"{medicion}, más que el umbral de {umbral:g} s, así que se repartieron entre "
            f"{procesos} procesos.",
            **tiempos,
        )
    secuencial(restantes)
    return registro(
        "secuencial",
        f"{medicion}, sin superar el umbral de {umbral:g} s, así que no compensaba el costo de "
        "abrir procesos.",
        **tiempos,
    )


def _en_paralelo(
    matriz: np.ndarray,
    variables: list[str],
    prohibidos: list[tuple[str, str]],
    configuracion: ConfiguracionPC,
    pendientes: list[int],
    registrar: Callable[[_ResultadoCorrida], None],
    cancelado: Callable[[], bool],
    externo: Executor | None = None,
) -> None:
    """Como mucho ``procesos`` corridas en vuelo; revisa la cancelación cada 0,5 s.

    Con un ejecutor ``externo`` cada tarea lleva sus datos (los procesos no se
    inicializan con este análisis) y, al cancelar, solo se descartan las
    tareas pendientes: los procesos no se terminan porque no son de esta función.
    """
    procesos = min(configuracion.procesos, len(pendientes))
    if externo is not None:
        ejecutor = externo

        def tarea(corrida: int):
            return ejecutor.submit(ejecutar_corrida, matriz, variables, prohibidos, configuracion, corrida)
    else:
        ejecutor = ProcessPoolExecutor(
            max_workers=procesos,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_inicializar_trabajador,
            initargs=(matriz, variables, prohibidos, configuracion),
        )

        def tarea(corrida: int):
            return ejecutor.submit(_corrida_en_trabajador, corrida)

    siguientes = iter(pendientes)
    en_vuelo: dict[Any, int] = {}

    def enviar() -> None:
        while len(en_vuelo) < procesos:
            corrida = next(siguientes, None)
            if corrida is None:
                return
            en_vuelo[tarea(corrida)] = corrida

    terminado = False
    try:
        enviar()
        while en_vuelo:
            if cancelado():
                if externo is None:
                    _terminar_procesos(ejecutor)
                    terminado = True
                else:
                    for futuro in en_vuelo:
                        futuro.cancel()
                return
            listos, _ = wait(en_vuelo, timeout=0.5, return_when=FIRST_COMPLETED)
            for futuro in listos:
                del en_vuelo[futuro]
                registrar(futuro.result())
            if not cancelado():
                enviar()
    finally:
        if externo is None and not terminado:
            ejecutor.shutdown(wait=True, cancel_futures=True)


# --- Agregación ---------------------------------------------------------------------------------


def _spearman(train: pd.DataFrame, a: str, b: str) -> float | None:
    completas = train[[a, b]].dropna()
    if len(completas) < 3 or completas[a].nunique() < 2 or completas[b].nunique() < 2:
        return None
    rho = float(stats.spearmanr(completas[a], completas[b])[0])
    return None if math.isnan(rho) else round(rho, 4)


def agregar(
    resultado: ResultadoBootstrap, datos: DatosPreparados, configuracion: ConfiguracionPC
) -> GrafoAgregado:
    """Aristas aceptadas, orientación mayoritaria, orientaciones manuales, signo y ciclos.

    Una arista se acepta si i→j + j→i + i—j aparece en al menos
    ``umbral_frecuencia`` de las corridas válidas. Su orientación es la más
    frecuente de las tres; ante un empate queda sin orientar. Las
    orientaciones manuales solo se aplican a aristas aceptadas sin orientar.
    """
    variables = resultado.variables
    validas = resultado.corridas_validas
    advertencias = []
    if not resultado.completo:
        advertencias.append(
            f"Resultado parcial: {resultado.corridas_completadas} de "
            f"{resultado.corridas_totales} corridas."
        )
    if resultado.corridas_fallidas:
        advertencias.append(
            f"{len(resultado.corridas_fallidas)} corridas fallaron y se descartaron; las "
            f"frecuencias se calculan sobre {validas} corridas válidas."
        )
    if resultado.bidireccionales:
        advertencias.append(
            f"Hubo {resultado.bidireccionales} conflictos de orientación (aristas "
            "bidireccionales); se contaron como aristas sin orientar."
        )
    if validas == 0:
        advertencias.append("No hubo corridas válidas: no se puede construir el grafo.")
        return GrafoAgregado(variables, resultado.objetivo, configuracion.umbral_frecuencia, 0, [], [], advertencias)

    dirigidas = np.asarray(resultado.dirigidas)
    sin_orientar = np.asarray(resultado.sin_orientar)
    minimo = configuracion.umbral_frecuencia * validas - 1e-9
    aristas: dict[frozenset[str], AristaAgregada] = {}
    for i in range(len(variables)):
        for j in range(i + 1, len(variables)):
            ij, ji, u = int(dirigidas[i, j]), int(dirigidas[j, i]), int(sin_orientar[i, j])
            if ij + ji + u < minimo:
                continue
            if ij > max(ji, u):
                origen, destino, tipo, directa, inversa = i, j, "dirigida", ij, ji
            elif ji > max(ij, u):
                origen, destino, tipo, directa, inversa = j, i, "dirigida", ji, ij
            else:
                origen, destino, tipo, directa, inversa = i, j, "sin_orientar", ij, ji
            rho = _spearman(datos.train, variables[origen], variables[destino])
            aristas[frozenset((variables[i], variables[j]))] = AristaAgregada(
                origen=variables[origen],
                destino=variables[destino],
                tipo=tipo,
                frecuencia_total=round((ij + ji + u) / validas, 4),
                frecuencia_origen_destino=round(directa / validas, 4),
                frecuencia_destino_origen=round(inversa / validas, 4),
                frecuencia_sin_orientar=round(u / validas, 4),
                spearman=rho,
                signo=0 if rho is None else int(np.sign(rho)),
            )

    for manual in configuracion.orientaciones_manuales:
        clave = frozenset((manual.origen, manual.destino))
        arista = aristas.get(clave)
        if arista is None:
            advertencias.append(
                f"Orientación manual {manual.origen} → {manual.destino} no aplicada: la arista no "
                "fue aceptada."
            )
        elif arista.tipo != "sin_orientar":
            advertencias.append(
                f"Orientación manual {manual.origen} → {manual.destino} no aplicada: PC ya orientó "
                f"la arista como {arista.origen} → {arista.destino}."
            )
        else:
            invertir = arista.origen != manual.origen
            aristas[clave] = AristaAgregada(
                origen=manual.origen,
                destino=manual.destino,
                tipo="manual",
                frecuencia_total=arista.frecuencia_total,
                frecuencia_origen_destino=arista.frecuencia_destino_origen if invertir else arista.frecuencia_origen_destino,
                frecuencia_destino_origen=arista.frecuencia_origen_destino if invertir else arista.frecuencia_destino_origen,
                frecuencia_sin_orientar=arista.frecuencia_sin_orientar,
                spearman=arista.spearman,
                signo=arista.signo,
                justificacion=manual.justificacion,
            )

    orden = {v: k for k, v in enumerate(variables)}
    lista = sorted(aristas.values(), key=lambda a: (orden[a.origen], orden[a.destino]))
    ciclos = ciclos_dirigidos(lista)
    if ciclos:
        advertencias.append(
            f"El grafo dirigido tiene {len(ciclos)} ciclo(s); revise las orientaciones "
            "(no se corrigen automáticamente)."
        )
    return GrafoAgregado(
        variables, resultado.objetivo, configuracion.umbral_frecuencia, validas, lista, ciclos, advertencias
    )


def ciclos_dirigidos(aristas: list[AristaAgregada], maximo: int = 20) -> list[list[str]]:
    """Ciclos simples formados por aristas dirigidas o manuales (como mucho ``maximo``)."""
    import networkx as nx

    grafo = nx.DiGraph()
    grafo.add_edges_from((a.origen, a.destino) for a in aristas if a.tipo != "sin_orientar")
    ciclos = []
    for ciclo in nx.simple_cycles(grafo):
        ciclos.append(list(ciclo))
        if len(ciclos) >= maximo:
            break
    return ciclos


def frecuencia_par(resultado: ResultadoBootstrap, a: str, b: str) -> float:
    """Fracción de corridas válidas con una arista entre ``a`` y ``b`` (cualquier orientación)."""
    if resultado.corridas_validas == 0:
        return 0.0
    i, j = resultado.variables.index(a), resultado.variables.index(b)
    cuenta = resultado.dirigidas[i][j] + resultado.dirigidas[j][i] + resultado.sin_orientar[i][j]
    return round(cuenta / resultado.corridas_validas, 4)

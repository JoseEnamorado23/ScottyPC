"""Selección de la prueba de independencia condicional para PC.

``recomendar_prueba`` usa SOLO el conjunto de entrenamiento de unos
``DatosPreparados`` y devuelve una ``RecomendacionPrueba`` con la prueba
sugerida, el motivo, la evidencia por variable, las alternativas y el tiempo
estimado. Es una sugerencia: el usuario siempre puede elegir otra prueba.

Reglas (en este orden):

1. Quedan faltantes → ``mv_fisherz``.
2. Más de ``proporcion_maxima_categoricas`` de variables categóricas o
   binarias → ``chisq`` (con las continuas discretizadas en quintiles).
3. Alguna variable con relación no monótona con el objetivo → ``chisq``
   sobre quintiles, citando esas variables.
4. En otro caso → ``fisherz``.

No linealidad: cada variable continua se divide en sextiles (límites de
entrenamiento) y se calcula la tasa (objetivo binario) o la media
(multiclase o continuo) del objetivo en cada intervalo. La dependencia por
intervalos es significativa si p < ``alfa_no_linealidad`` (chi-cuadrado
sobre la tabla intervalos × clases, o Kruskal-Wallis si el objetivo es
continuo). La variable se marca "no monótona" si, además:

- la curva sube y baja: tiene un extremo interior cuya subida y bajada
  miden cada una al menos ``proporcion_minima_inversion`` de la amplitud y
  al menos ``efecto_minimo_no_linealidad`` desviaciones estándar del
  objetivo, y ambas son significativas; o
- la correlación de Spearman es débil (``|ρ| < spearman_debil``) mientras
  la amplitud de la curva alcanza ``efecto_minimo_no_linealidad``
  desviaciones estándar (dependencia fuerte).

El tamaño de efecto evita que, con miles de filas, ondulaciones pequeñas
pero significativas se tomen como no linealidad. Los empates en un límite
de cuantil van al intervalo inferior y los intervalos vacíos se descartan.
"""

from __future__ import annotations

import multiprocessing
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.modelos import TipoObjetivo
from nucleo.preparacion import BINARIA, CONTINUA, INDICADOR, ONE_HOT, ORDINAL, DatosPreparados

FISHERZ, CHISQ, MV_FISHERZ, KCI = "fisherz", "chisq", "mv_fisherz", "kci"

_VENTAJAS_DESVENTAJAS = {
    FISHERZ: (
        "Muy rápida y con buena potencia si las relaciones son lineales.",
        "Supone relaciones lineales y datos aproximadamente normales; puede omitir relaciones "
        "no monótonas; no admite faltantes.",
    ),
    CHISQ: (
        "No supone linealidad; adecuada para variables categóricas o discretizadas.",
        "Discretizar pierde información; necesita muchas filas por celda y se vuelve lenta con "
        "muchas variables de condicionamiento.",
    ),
    MV_FISHERZ: (
        "Admite faltantes sin imputar (usa en cada prueba las filas completas).",
        "Supone relaciones lineales; con muchos faltantes cada prueba usa menos filas.",
    ),
    KCI: (
        "Detecta dependencias no lineales generales sin discretizar.",
        "Mucho más lenta; práctica solo con pocas filas y pocas variables.",
    ),
}


@dataclass(frozen=True)
class DiagnosticoVariable:
    """Evidencia de la forma de la relación entre una variable y el objetivo."""

    nombre: str
    tipo_final: str
    spearman: float | None = None
    p_intervalos: float | None = None
    limites_intervalos: list[float] = field(default_factory=list)
    valores_por_intervalo: list[float] = field(default_factory=list)
    filas_por_intervalo: list[int] = field(default_factory=list)
    medida: str | None = None
    amplitud_en_desviaciones: float | None = None
    monotona: bool | None = None
    motivo: str | None = None


@dataclass(frozen=True)
class AlternativaPrueba:
    prueba: str
    ventajas: str
    desventajas: str


@dataclass(frozen=True)
class RecomendacionPrueba:
    """Prueba sugerida para PC, con su justificación y el tiempo estimado."""

    prueba: str
    motivo: str
    discretizacion: str | None
    variables_no_monotonas: list[str]
    faltantes_restantes: dict[str, int]
    proporcion_categoricas: float
    filas_train: int
    variables: int
    diagnosticos: list[DiagnosticoVariable]
    alternativas: list[AlternativaPrueba]
    limites_discretizacion: dict[str, list[float]] = field(default_factory=dict)
    tiempo_por_ejecucion_s: float | None = None
    tiempo_estimado_bootstrap_s: float | None = None
    estimacion_completa: bool = False
    max_k_sugerido: int | None = None
    tiempo_estimado_bootstrap_max_k_s: float | None = None
    nota_tiempo: str | None = None


# --- Diagnóstico de no linealidad ----------------------------------------------------------


def _limites_cuantiles(valores: np.ndarray, intervalos: int) -> list[float]:
    """Límites interiores de los cuantiles (sin repetidos)."""
    cuantiles = np.quantile(valores, np.linspace(0, 1, intervalos + 1)[1:-1])
    return [float(c) for c in np.unique(cuantiles)]


def _intervalo(valores: np.ndarray, limites: list[float]) -> np.ndarray:
    """Intervalo de cada valor; un valor igual a un límite va al intervalo inferior."""
    return np.searchsorted(np.asarray(limites), valores, side="left")


def _diferencia_significativa(
    grupo_a: np.ndarray, grupo_b: np.ndarray, binario: bool, alfa: float
) -> bool:
    if len(grupo_a) < 2 or len(grupo_b) < 2:
        return False
    if binario:
        tabla = np.array([[grupo_a.sum(), len(grupo_a) - grupo_a.sum()],
                          [grupo_b.sum(), len(grupo_b) - grupo_b.sum()]])
        if (tabla.sum(axis=0) == 0).any():
            return False
        return float(stats.chi2_contingency(tabla)[1]) < alfa
    return float(stats.mannwhitneyu(grupo_a, grupo_b).pvalue) < alfa


def _sube_y_baja(
    curva: np.ndarray, grupos: list[np.ndarray], binario: bool, escala: float,
    configuracion: ConfiguracionValidacion,
) -> bool:
    """¿Hay un máximo (o mínimo) interior con subida y bajada relevantes y significativas?"""
    amplitud = float(curva.max() - curva.min())
    if amplitud == 0:
        return False
    minimo_tramo = max(
        configuracion.proporcion_minima_inversion * amplitud,
        configuracion.efecto_minimo_no_linealidad * escala,
    )
    for signo in (1, -1):
        valores = signo * curva
        j = int(np.argmax(valores))
        if j == 0 or j == len(curva) - 1:
            continue
        izquierda = int(np.argmin(valores[:j]))
        derecha = j + 1 + int(np.argmin(valores[j + 1:]))
        tramos = (valores[j] - valores[izquierda], valores[j] - valores[derecha])
        if min(tramos) < minimo_tramo:
            continue
        alfa = configuracion.alfa_no_linealidad
        if _diferencia_significativa(grupos[j], grupos[izquierda], binario, alfa) and (
            _diferencia_significativa(grupos[j], grupos[derecha], binario, alfa)
        ):
            return True
    return False


def diagnosticar_variable(
    nombre: str,
    x: pd.Series,
    y: pd.Series,
    tipo_objetivo: str | None,
    configuracion: ConfiguracionValidacion,
) -> DiagnosticoVariable:
    """Forma de la relación entre una variable continua ``x`` y el objetivo ``y``."""
    completas = (x.notna() & y.notna()).to_numpy()
    xv, yv = x.to_numpy(dtype=float)[completas], y.to_numpy(dtype=float)[completas]
    limites = _limites_cuantiles(xv, configuracion.intervalos_no_linealidad)
    if len(limites) + 1 < 4:
        return DiagnosticoVariable(nombre, CONTINUA, motivo="Pocos valores distintos para evaluar la forma.")
    # Intervalos no vacíos, renumerados 0, 1, ...
    presentes, intervalos = np.unique(_intervalo(xv, limites), return_inverse=True)
    if len(presentes) < 4:
        return DiagnosticoVariable(nombre, CONTINUA, motivo="Pocos valores distintos para evaluar la forma.")
    binario = tipo_objetivo == TipoObjetivo.BINARIO
    if binario:
        yv = (yv == yv.max()).astype(float)
    grupos = [yv[intervalos == k] for k in range(len(presentes))]
    curva = np.array([g.mean() for g in grupos])
    escala = float(np.std(yv))
    amplitud = float(curva.max() - curva.min())
    if tipo_objetivo in (TipoObjetivo.BINARIO, TipoObjetivo.MULTICLASE):
        p = float(stats.chi2_contingency(pd.crosstab(intervalos, yv).to_numpy())[1])
    else:
        p = float(stats.kruskal(*grupos).pvalue)
    rho = float(stats.spearmanr(xv, yv)[0])
    dependiente = p < configuracion.alfa_no_linealidad and escala > 0
    fuerte = dependiente and amplitud >= configuracion.efecto_minimo_no_linealidad * escala
    motivo = None
    if dependiente and _sube_y_baja(curva, grupos, binario, escala, configuracion):
        motivo = "La relación con el objetivo sube y baja (forma de U o de U invertida)."
    elif fuerte and abs(rho) < configuracion.spearman_debil:
        motivo = (
            f"La dependencia por intervalos es significativa pero la correlación de Spearman "
            f"es débil (ρ = {rho:.3f})."
        )
    return DiagnosticoVariable(
        nombre=nombre,
        tipo_final=CONTINUA,
        spearman=round(rho, 4),
        p_intervalos=p,
        limites_intervalos=[limites[k] for k in presentes[:-1]] if len(limites) else [],
        valores_por_intervalo=[round(float(v), 4) for v in curva],
        filas_por_intervalo=[int(len(g)) for g in grupos],
        medida="tasa de la clase positiva" if binario else "media del objetivo",
        amplitud_en_desviaciones=round(amplitud / escala, 4) if escala > 0 else None,
        monotona=motivo is None,
        motivo=motivo,
    )


# --- Estimación del tiempo ---------------------------------------------------------------------


def discretizar(
    train: pd.DataFrame, columnas: list[str], intervalos: int
) -> tuple[pd.DataFrame, dict[str, list[float]]]:
    """Discretiza columnas en cuantiles de entrenamiento (códigos 0, 1, ...)."""
    resultado = train.copy()
    limites = {}
    for columna in columnas:
        valores = train[columna].to_numpy(dtype=float)
        presentes = valores[~np.isnan(valores)]
        limites[columna] = _limites_cuantiles(presentes, intervalos)
        codigos = _intervalo(valores, limites[columna]).astype(float)
        codigos[np.isnan(valores)] = np.nan
        resultado[columna] = codigos
    return resultado, limites


def _trabajador_pc(
    matriz: np.ndarray, prueba: str, alfa: float, max_k: int | None, cola: Any
) -> None:
    from causallearn.search.ConstraintBased.PC import pc

    inicio = time.perf_counter()
    pc(matriz, alfa, prueba, show_progress=False, verbose=False, max_k=max_k)
    cola.put(time.perf_counter() - inicio)


def _medir_pc(
    matriz: np.ndarray, prueba: str, alfa: float, limite: float, max_k: int | None = None
) -> float | None:
    """Segundos de una ejecución de PC en un subproceso; ``None`` si supera ``limite``."""
    contexto = multiprocessing.get_context("spawn")
    cola = contexto.Queue()
    proceso = contexto.Process(
        target=_trabajador_pc, args=(matriz, prueba, alfa, max_k, cola)
    )
    proceso.start()
    proceso.join(limite)
    if proceso.is_alive():
        proceso.terminate()
        proceso.join()
        return None
    return float(cola.get()) if proceso.exitcode == 0 and not cola.empty() else None


def estimar_tiempo(
    matriz: np.ndarray,
    prueba: str,
    configuracion: ConfiguracionValidacion,
    semilla: int,
    ejecuciones: int | None = None,
    max_k: int | None = None,
) -> tuple[float | None, bool]:
    """Tiempo medio de PC sobre submuestras del entrenamiento y si todas terminaron."""
    rng = np.random.default_rng(semilla)
    tamano = max(2, int(len(matriz) * configuracion.fraccion_submuestra_tiempo))
    tiempos = []
    for _ in range(ejecuciones or configuracion.ejecuciones_estimacion_tiempo):
        filas = np.sort(rng.choice(len(matriz), size=tamano, replace=False))
        segundos = _medir_pc(
            matriz[filas], prueba, configuracion.alfa_pc,
            configuracion.segundos_limite_por_ejecucion, max_k,
        )
        if segundos is None:
            return None, False
        tiempos.append(segundos)
    return float(np.mean(tiempos)), True


def formatear_duracion(segundos: float) -> str:
    """Texto legible para una duración en segundos."""
    if segundos < 10:
        return f"{segundos:.2f} s"
    if segundos < 90:
        return f"{segundos:.0f} s"
    if segundos < 5400:
        return f"{segundos / 60:.0f} min"
    return f"{segundos / 3600:.1f} h"


# --- Recomendación ------------------------------------------------------------------------------


def recomendar_prueba(
    datos: DatosPreparados,
    configuracion: ConfiguracionValidacion | None = None,
    estimar: bool = True,
) -> RecomendacionPrueba:
    """Recomienda la prueba de independencia usando solo el entrenamiento."""
    configuracion = configuracion or ConfiguracionValidacion()
    train = datos.train
    objetivo = datos.objetivo
    tipos = {m.nombre: m.tipo_final for m in datos.columnas}
    variables = [c for c in train.columns if c != objetivo]
    faltantes = {c: int(n) for c, n in train.isna().sum().items() if n}
    categoricas = [v for v in variables if tipos.get(v) in (BINARIA, ORDINAL, ONE_HOT, INDICADOR)]
    proporcion = len(categoricas) / len(variables) if variables else 0.0

    diagnosticos = []
    for variable in variables:
        if tipos.get(variable) == CONTINUA and train[variable].nunique() >= configuracion.intervalos_no_linealidad:
            diagnosticos.append(
                diagnosticar_variable(variable, train[variable], train[objetivo], datos.tipo_objetivo, configuracion)
            )
        else:
            diagnosticos.append(DiagnosticoVariable(variable, tipos.get(variable, CONTINUA)))
    no_monotonas = [d.nombre for d in diagnosticos if d.monotona is False]

    kci_posible = len(train) < configuracion.filas_maximas_kci and len(variables) <= configuracion.variables_maximas_kci
    if faltantes:
        prueba = MV_FISHERZ
        motivo = (
            f"Quedan faltantes después de la preparación en {len(faltantes)} columnas "
            f"({', '.join(faltantes)}); mv_fisherz los maneja sin imputar."
        )
        if no_monotonas:
            motivo += (
                " Atención: estas variables tienen una relación no monótona con el objetivo, que "
                f"mv_fisherz (lineal) puede no detectar: {', '.join(no_monotonas)}."
            )
    elif proporcion > configuracion.proporcion_maxima_categoricas:
        prueba = CHISQ
        motivo = (
            f"El {100 * proporcion:.0f} % de las variables son categóricas o binarias; chi-cuadrado "
            "no supone relaciones lineales (las continuas se discretizan en quintiles)."
        )
    elif no_monotonas:
        prueba = CHISQ
        motivo = (
            "Estas variables tienen una relación no monótona con el objetivo, que una prueba "
            f"lineal como fisherz puede no detectar: {', '.join(no_monotonas)}. Se sugiere "
            "chi-cuadrado con las variables continuas discretizadas en quintiles."
        )
        if kci_posible:
            motivo += " Con pocas filas y variables, KCI es una alternativa más potente pero mucho más lenta."
    else:
        prueba = FISHERZ
        motivo = (
            "No quedan faltantes, predominan las variables continuas y sus relaciones con el "
            "objetivo son monótonas; Fisher-z es rápida y potente en este caso."
        )

    discretizacion, limites = None, {}
    matriz = train[[*variables, objetivo]]
    if prueba == CHISQ:
        continuas = [v for v in variables if tipos.get(v) == CONTINUA]
        if datos.tipo_objetivo == TipoObjetivo.CONTINUO:
            continuas.append(objetivo)
        matriz, limites = discretizar(matriz, continuas, configuracion.intervalos_chisq)
        discretizacion = "quintiles" if configuracion.intervalos_chisq == 5 else f"{configuracion.intervalos_chisq} cuantiles"

    alternativas = [
        AlternativaPrueba(p, *_VENTAJAS_DESVENTAJAS[p])
        for p in (FISHERZ, CHISQ, MV_FISHERZ) if p != prueba
    ]
    if kci_posible:
        alternativas.append(AlternativaPrueba(KCI, *_VENTAJAS_DESVENTAJAS[KCI]))

    tiempo, completa, total, max_k, nota, total_max_k = None, False, None, None, None, None
    semilla = datos.receta.decisiones.separacion.semilla
    if estimar:
        tiempo, completa = estimar_tiempo(
            matriz.to_numpy(dtype=float), prueba, configuracion, semilla
        )
        if tiempo is not None:
            total = tiempo * configuracion.corridas_bootstrap
        else:
            nota = (
                f"Una ejecución de PC superó {configuracion.segundos_limite_por_ejecucion:.0f} s; "
                f"{configuracion.corridas_bootstrap} corridas de bootstrap tardarían horas."
            )
        lento = total is None or total > configuracion.segundos_maximos_chisq
        if prueba == CHISQ and lento:
            max_k = configuracion.max_k_sugerido
            nota = (nota + " " if nota else "") + (
                f"Se sugiere limitar el condicionamiento a max_k = {max_k}: PC solo probará "
                f"independencias con hasta {max_k} variables de condicionamiento, lo que reduce "
                "mucho el tiempo, pero algunas aristas que solo se explican con conjuntos "
                "mayores podrían no eliminarse (el grafo puede tener aristas de más)."
            )
            tiempo_max_k, _ = estimar_tiempo(
                matriz.to_numpy(dtype=float), prueba, configuracion, semilla, 1, max_k
            )
            if tiempo_max_k is not None:
                total_max_k = round(tiempo_max_k * configuracion.corridas_bootstrap, 1)
                nota += (
                    f" Con max_k = {max_k}, {configuracion.corridas_bootstrap} corridas tardarían "
                    f"unos {formatear_duracion(total_max_k)}."
                )
    return RecomendacionPrueba(
        prueba=prueba,
        motivo=motivo,
        discretizacion=discretizacion,
        variables_no_monotonas=no_monotonas,
        faltantes_restantes=faltantes,
        proporcion_categoricas=round(proporcion, 4),
        filas_train=int(len(train)),
        variables=len(variables),
        diagnosticos=diagnosticos,
        alternativas=alternativas,
        limites_discretizacion=limites,
        tiempo_por_ejecucion_s=None if tiempo is None else round(tiempo, 3),
        tiempo_estimado_bootstrap_s=None if total is None else round(total, 1),
        estimacion_completa=completa,
        max_k_sugerido=max_k,
        tiempo_estimado_bootstrap_max_k_s=total_max_k,
        nota_tiempo=nota,
    )

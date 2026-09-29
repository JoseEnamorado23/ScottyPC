"""Construcción, evaluación y persistencia del modelo causal estructural.

Solo entra al modelo el subgrafo del objetivo y sus ancestros. Las raíces conservan su valor
observado; cada variable con padres tiene un mecanismo ajustado solo con train.

``modelo_causal.json`` (``modelo_a_diccionario``) guarda los parámetros ajustados de cada
mecanismo, no un objeto serializado: al cargarlo se reconstruyen las mismas funciones y las
predicciones son idénticas. Una huella (sha256 de las predicciones sobre train) lo comprueba.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import brier_score_loss, r2_score, roc_auc_score

from pcapp_nucleo.causal.aplicabilidad import (
    ADVERTENCIA, MODELO, ProblemaAplicabilidad, es_binaria, evaluar_aplicabilidad, hay_bloqueantes,
)
from pcapp_nucleo.causal.configuracion import ConfiguracionModeloCausal, decimal
from pcapp_nucleo.causal.mecanismos import (
    EXACTITUD, NOMBRES_FAMILIA, Mecanismo, MecanismoLineal, Seleccion, exactitud_balanceada,
    mecanismo_desde_diccionario, nodos_spline, pliegues, seleccionar_mecanismo, umbral_optimo,
)
from pcapp_nucleo.causal.subgrafo import subgrafo_objetivo
from pcapp_nucleo.causal.unidades import NUMERICA, Unidades
from pcapp_nucleo.modelos import TipoObjetivo
from pcapp_nucleo.preparacion import DatosPreparados, MetadatosColumna
from pcapp_nucleo.utilidades import a_diccionario_serializable

VERSION_FORMATO = 1
CONTINUA, BINARIA = "continua", "binaria"
RAIZ, INTERMEDIA, OBJETIVO = "raiz", "intermedia", "objetivo"


class ErrorModeloCausal(Exception):
    """No se puede construir o usar el modelo; ``problemas`` detalla los bloqueantes."""

    def __init__(self, mensaje: str, problemas: list[ProblemaAplicabilidad] | None = None) -> None:
        super().__init__(mensaje)
        self.problemas = problemas or []


class ConstruccionCancelada(Exception):
    pass


# --- Modelo cargado ---------------------------------------------------------------------------


class ModeloCausal:
    """Modelo listo para predecir y calcular contrafactuales (se crea desde su diccionario)."""

    def __init__(self, datos: dict[str, Any]) -> None:
        if datos.get("version_formato") != VERSION_FORMATO:
            raise ErrorModeloCausal("El modelo causal tiene un formato que esta versión no puede leer.")
        self.datos = datos
        self.objetivo: str = datos["objetivo"]
        self.tipo_objetivo: str = datos["tipo_objetivo"]
        self.binario = self.tipo_objetivo == TipoObjetivo.BINARIO
        sub = datos["subgrafo"]
        self.variables: list[str] = list(sub["variables"])
        self.padres: dict[str, list[str]] = {v: list(p) for v, p in sub["padres"].items()}
        self.fuera: list[str] = list(sub["fuera"])
        self.descendientes_objetivo: list[str] = list(sub["descendientes_objetivo"])
        self.info_variables: dict[str, dict[str, Any]] = datos["variables"]
        self.mecanismos: dict[str, Mecanismo] = {
            v: mecanismo_desde_diccionario(m) for v, m in datos["mecanismos"].items()
        }
        self.umbral_decision: float | None = datos.get("umbral_decision")
        self.unidades = Unidades([MetadatosColumna(**c) for c in datos["columnas"]])
        self.semilla: int = datos["semilla"]
        self.muestras_abduccion: int = datos["configuracion"]["muestras_abduccion"]

    @property
    def ancestros(self) -> list[str]:
        return [v for v in self.variables if v != self.objetivo]

    def tipo(self, variable: str) -> str:
        return self.info_variables[variable]["tipo"]

    def matriz(self, variable: str, valores: pd.DataFrame | dict[str, Any]) -> np.ndarray:
        """Padres de ``variable`` como matriz, con los faltantes imputados con la mediana de train."""
        columnas = []
        for padre in self.padres[variable]:
            x = np.asarray(valores[padre], dtype=float).copy()
            x[np.isnan(x)] = self.info_variables[padre]["mediana"]
            columnas.append(np.atleast_1d(x))
        return np.column_stack(columnas)

    def media(self, variable: str, valores: pd.DataFrame | dict[str, Any]) -> np.ndarray:
        return self.mecanismos[variable].media(self.matriz(variable, valores))


def modelo_desde_diccionario(datos: dict[str, Any], train: pd.DataFrame | None = None) -> ModeloCausal:
    """Carga el modelo; con ``train`` comprueba que la huella de las predicciones coincide."""
    modelo = ModeloCausal(datos)
    if train is not None:
        if datos.get("train_sha256") != sha256_train(train):
            raise ErrorModeloCausal("Los datos de entrenamiento no son los usados para construir el modelo.")
        if huella(modelo, train) != datos.get("huella"):
            raise ErrorModeloCausal("Las predicciones del modelo cargado no coinciden con las del modelo guardado.")
    return modelo


def sha256_train(train: pd.DataFrame) -> str:
    valores = pd.util.hash_pandas_object(train, index=True).to_numpy()
    return hashlib.sha256(valores.tobytes() + ",".join(map(str, train.columns)).encode("utf-8")).hexdigest()


def huella(modelo: ModeloCausal, train: pd.DataFrame) -> str:
    """sha256 de las predicciones de todos los mecanismos sobre las filas de train."""
    resumen = hashlib.sha256()
    for variable in modelo.variables:
        if variable in modelo.mecanismos:
            resumen.update(variable.encode("utf-8"))
            resumen.update(np.ascontiguousarray(modelo.mecanismos[variable].eta(modelo.matriz(variable, train))).tobytes())
    return resumen.hexdigest()


# --- Construcción -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextoResultado:
    """Versión del resultado de PC usada (el modelo queda ligado a ella)."""

    version: int | None = None
    sha256: str | None = None


def _monotonia(
    padres: list[str], X: np.ndarray, diagnosticos: list[dict[str, Any]], configuracion: ConfiguracionModeloCausal
) -> list[dict[str, Any]]:
    por_nombre = {d.get("nombre"): d for d in diagnosticos or []}
    decisiones = []
    for i, padre in enumerate(padres):
        if nodos_spline(X[:, i], configuracion) is None:
            decisiones.append({
                "padre": padre, "restriccion": None, "origen": "no_aplica",
                "motivo": "Padre discreto: entra de forma lineal (monótono por construcción).",
            })
            continue
        if padre in configuracion.monotonia:
            valor = configuracion.monotonia[padre]
            decisiones.append({
                "padre": padre, "restriccion": None if valor == "ninguna" else valor, "origen": "manual",
                "motivo": "Elegida por el usuario.",
            })
            continue
        diagnostico = por_nombre.get(padre)
        if diagnostico is None or diagnostico.get("monotona") is None:
            decisiones.append({
                "padre": padre, "restriccion": None, "origen": "automatico",
                "motivo": "Sin diagnóstico de forma en la recomendación de prueba: sin restricción.",
            })
        elif diagnostico["monotona"] is False:
            decisiones.append({
                "padre": padre, "restriccion": None, "origen": "automatico",
                "motivo": f"Relación no monótona con el objetivo: {diagnostico.get('motivo') or 'sube y baja'}",
            })
        else:
            rho = diagnostico.get("spearman") or 0.0
            if rho == 0:
                decisiones.append({
                    "padre": padre, "restriccion": None, "origen": "automatico",
                    "motivo": "Correlación de Spearman nula: no se sabe la dirección; sin restricción.",
                })
            else:
                decisiones.append({
                    "padre": padre, "restriccion": "creciente" if rho > 0 else "decreciente",
                    "origen": "automatico",
                    "motivo": f"Relación monótona según la recomendación de prueba (Spearman ρ = {decimal(rho, '+.3f')}).",
                })
    return decisiones


def _metricas_binarias(y: np.ndarray, p: np.ndarray, umbral: float) -> dict[str, float | None]:
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None
    return {
        "exactitud_balanceada": exactitud_balanceada(y, p, umbral),
        "auc": auc,
        "brier": float(brier_score_loss(y, p)),
    }


def _metricas_continuas(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {"r2": float(r2_score(y, p)), "rmse": float(np.sqrt(np.mean((y - p) ** 2)))}


def _calibracion(y: np.ndarray, p: np.ndarray, intervalos: int) -> list[dict[str, float]]:
    limites = np.unique(np.quantile(p, np.linspace(0, 1, intervalos + 1)))
    grupo = np.clip(np.searchsorted(limites, p, side="right") - 1, 0, max(len(limites) - 2, 0))
    puntos = []
    for g in np.unique(grupo):
        mascara = grupo == g
        puntos.append({
            "probabilidad_media": float(p[mascara].mean()),
            "frecuencia_observada": float(y[mascara].mean()),
            "filas": int(mascara.sum()),
        })
    return puntos


def _histograma(valores: np.ndarray, intervalos: int) -> dict[str, Any]:
    valores = valores[~np.isnan(valores)]
    distintos = np.unique(valores)
    if len(distintos) <= intervalos:
        return {
            "tipo": "valores", "valores": distintos.tolist(),
            "conteos": [int((valores == v).sum()) for v in distintos],
        }
    conteos, limites = np.histogram(valores, bins=intervalos)
    return {"tipo": "histograma", "limites": limites.tolist(), "conteos": conteos.tolist()}


def _signo(y: np.ndarray) -> int:
    diferencias = np.diff(y)
    escala = max(float(np.ptp(y)), 1e-12)
    if np.all(diferencias >= -1e-9 * escala):
        return 1 if diferencias.sum() > 0 else 0
    if np.all(diferencias <= 1e-9 * escala):
        return -1
    return 0  # sube y baja


def _efectos(
    modelo: ModeloCausal, variable: str, train: pd.DataFrame, puntos: int, intervalos_histograma: int | None
) -> list[dict[str, Any]]:
    """Efecto parcial (dependencia parcial sobre las filas de train) de cada padre."""
    mecanismo = modelo.mecanismos[variable]
    X = modelo.matriz(variable, train)
    efectos = []
    for i, padre in enumerate(modelo.padres[variable]):
        info = modelo.info_variables[padre]
        if info["tipo"] == BINARIA:
            rejilla = np.array([info["minimo"], info["maximo"]])
        else:
            rejilla = np.linspace(info["minimo"], info["maximo"], puntos)
        curva = []
        for valor in rejilla:
            Xc = X.copy()
            Xc[:, i] = valor
            curva.append(float(mecanismo.media(Xc).mean()))
        coeficiente = mecanismo.coeficientes[i] if isinstance(mecanismo, MecanismoLineal) else None
        signo = int(np.sign(coeficiente)) if coeficiente is not None else _signo(np.asarray(curva))
        efecto = {
            "padre": padre,
            "coeficiente": coeficiente,
            "signo": signo,
            "x": [modelo.unidades.a_original_numerico(padre, v) for v in rejilla],
            "y": curva,
        }
        if intervalos_histograma:
            originales = np.array([
                modelo.unidades.a_original_numerico(padre, v) if not np.isnan(v) else np.nan
                for v in train[padre].to_numpy(dtype=float)
            ])
            efecto["histograma"] = _histograma(originales, intervalos_histograma)
        efectos.append(efecto)
    return efectos


def _referencia(
    datos: DatosPreparados, binario: bool, configuracion: ConfiguracionModeloCausal
) -> dict[str, Any]:
    """Regresión logística o lineal con todas las variables preparadas (mediana para faltantes)."""
    objetivo = datos.objetivo
    columnas = [c for c in datos.train.columns if c != objetivo]
    medianas = datos.train[columnas].median()

    def matriz(df):
        return df[columnas].fillna(medianas).fillna(0.0).to_numpy(dtype=float)

    X, y = matriz(datos.train), datos.train[objetivo].to_numpy(dtype=float)
    Xt, yt = matriz(datos.test), datos.test[objetivo].to_numpy(dtype=float)

    def ajustar(Xa, ya):
        if binario:
            return LogisticRegression(C=1e6, max_iter=5000).fit(Xa, ya)
        return LinearRegression().fit(Xa, ya)

    def predecir(modelo, Xa):
        return modelo.predict_proba(Xa)[:, 1] if binario else modelo.predict(Xa)

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        oof = np.full(len(y), np.nan)
        for entrenamiento, prueba in pliegues(y, binario, configuracion):
            oof[prueba] = predecir(ajustar(X[entrenamiento], y[entrenamiento]), X[prueba])
        final = ajustar(X, y)
        prediccion_test = predecir(final, Xt)
    if binario:
        umbral, _ = umbral_optimo(y, oof)
        return {
            "familia": "Regresión logística", "variables": columnas, "umbral": umbral,
            "cv": _metricas_binarias(y, oof, umbral), "test": _metricas_binarias(yt, prediccion_test, umbral),
        }
    return {
        "familia": "Regresión lineal", "variables": columnas, "umbral": None,
        "cv": _metricas_continuas(y, oof), "test": _metricas_continuas(yt, prediccion_test),
    }


def _clase_positiva(columnas: list[MetadatosColumna], objetivo: str) -> list[Any] | None:
    for c in columnas:
        if c.nombre == objetivo and c.parametros.get("mapeo"):
            return [o for o, codigo in c.parametros["mapeo"] if codigo == 1]
    return None


def _versiones() -> dict[str, str]:
    versiones = {}
    for paquete in ("pygam", "scikit-learn", "numpy", "scipy"):
        try:
            versiones[paquete] = importlib.metadata.version(paquete)
        except importlib.metadata.PackageNotFoundError:
            versiones[paquete] = "desconocida"
    return versiones


def construir_modelo(
    resultado_pc: dict[str, Any],
    datos: DatosPreparados,
    diagnosticos: list[dict[str, Any]] | None = None,
    configuracion: ConfiguracionModeloCausal | None = None,
    contexto: ContextoResultado | None = None,
    progreso: Callable[[int, int, str], None] | None = None,
    cancelacion: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Construye el modelo y su evaluación: ``(modelo_causal.json, evaluacion.json)``.

    ``diagnosticos`` son los de la recomendación de prueba (monotonía por defecto).

    Raises:
        ErrorModeloCausal: si hay problemas bloqueantes (en ``problemas``).
        ConstruccionCancelada: si ``cancelacion.is_set()`` se activa entre mecanismos.
    """
    configuracion = configuracion or ConfiguracionModeloCausal()
    contexto = contexto or ContextoResultado()
    problemas = evaluar_aplicabilidad(resultado_pc, datos, configuracion)
    if hay_bloqueantes(problemas):
        raise ErrorModeloCausal("El resultado de PC no permite construir el modelo causal.", problemas)

    objetivo, train, test = datos.objetivo, datos.train, datos.test
    binario = datos.tipo_objetivo == TipoObjetivo.BINARIO
    sub = subgrafo_objetivo(list(resultado_pc["variables"]), list(resultado_pc["aristas"]), objetivo)
    con_mecanismo = [v for v in sub.variables if sub.padres[v]]
    total = len(con_mecanismo) + 1
    avisar = progreso or (lambda *_: None)

    info_variables: dict[str, dict[str, Any]] = {}
    for v in sub.variables:
        valores = train[v].to_numpy(dtype=float)
        binaria = binario if v == objetivo else es_binaria(valores)
        info_variables[v] = {
            "tipo": BINARIA if binaria else CONTINUA,
            "rol": OBJETIVO if v == objetivo else (INTERMEDIA if sub.padres[v] else RAIZ),
            "mediana": float(np.nanmedian(valores)),
            "minimo": float(np.nanmin(valores)),
            "maximo": float(np.nanmax(valores)),
            "faltantes_train": int(np.isnan(valores).sum()),
        }
    imputadas = [v for v in sub.variables if info_variables[v]["faltantes_train"] and v != objetivo]

    grupos = {c.parametros.get("columna_original") for c in datos.columnas if c.nombre in sub.variables and c.tipo_final == "one_hot"}
    columnas = [
        c for c in datos.columnas
        if c.nombre in sub.variables or (c.tipo_final == "one_hot" and c.parametros.get("columna_original") in grupos)
    ]

    def matriz(variable: str, df: pd.DataFrame) -> np.ndarray:
        return np.column_stack([
            df[p].fillna(info_variables[p]["mediana"]).to_numpy(dtype=float) for p in sub.padres[variable]
        ])

    selecciones: dict[str, Seleccion] = {}
    monotonia: list[dict[str, Any]] = []
    for paso, variable in enumerate(con_mecanismo):
        if cancelacion is not None and cancelacion.is_set():
            raise ConstruccionCancelada()
        avisar(paso, total, variable)
        observadas = train[variable].notna().to_numpy()
        X = matriz(variable, train)[observadas]
        y = train[variable].to_numpy(dtype=float)[observadas]
        es_objetivo = variable == objetivo
        restricciones = None
        if es_objetivo:
            monotonia = _monotonia(sub.padres[variable], X, diagnosticos or [], configuracion)
            restricciones = [d["restriccion"] for d in monotonia]
        selecciones[variable] = seleccionar_mecanismo(
            variable, sub.padres[variable], X, y, info_variables[variable]["tipo"] == BINARIA, es_objetivo,
            configuracion, restricciones, pesos=configuracion.pesos_clase and es_objetivo and binario,
            eleccion=configuracion.mecanismos.get(variable),
        )
    avisar(len(con_mecanismo), total, "evaluacion")

    seleccion_objetivo = selecciones[objetivo]
    advertencias = [p for p in problemas if p.severidad == ADVERTENCIA]
    for variable in con_mecanismo:
        seleccion = selecciones[variable]
        if variable == objetivo:
            continue
        minimo = configuracion.exactitud_minima_intermedia if seleccion.metrica == EXACTITUD else configuracion.r2_minimo_intermedia
        if seleccion.puntuacion_cv < minimo:
            nombre = "exactitud balanceada" if seleccion.metrica == EXACTITUD else "R²"
            advertencias.append(ProblemaAplicabilidad(
                "INTERMEDIA_MAL_EXPLICADA", ADVERTENCIA,
                f"'{variable}' se explica mal con sus padres ({nombre} en validación cruzada = "
                f"{decimal(seleccion.puntuacion_cv)} < {decimal(minimo, 'g')}): los efectos que pasan por ella son inciertos.",
                "Interprete con cuidado los escenarios que la atraviesan.", MODELO, [variable],
            ))
    if seleccion_objetivo.pesos_clase:
        advertencias.append(ProblemaAplicabilidad(
            "PROBABILIDADES_NO_CALIBRADAS", ADVERTENCIA,
            "El objetivo se ajustó con pesos de clase: las probabilidades dejan de estar calibradas "
            "(sobrestiman la clase minoritaria).",
            "Desactive los pesos de clase si va a usar umbrales de probabilidad.", MODELO, [objetivo],
        ))
    for variable, seleccion in selecciones.items():
        if seleccion.rescate:
            advertencias.append(ProblemaAplicabilidad(
                "RESCATE_GAM", ADVERTENCIA,
                f"El GAM de '{variable}' necesitó ajustes para converger: {' '.join(seleccion.rescate)}",
                "No requiere acción.", MODELO, [variable],
            ))

    mecanismos_json = {}
    for variable, seleccion in selecciones.items():
        mecanismos_json[variable] = {
            **seleccion.mecanismo.a_diccionario(),
            "seleccion": {
                "metrica": seleccion.metrica,
                "elegido": seleccion.elegido,
                "origen": seleccion.origen,
                "motivo": seleccion.motivo,
                "puntuacion_cv": seleccion.puntuacion_cv,
                "umbral_cv": seleccion.umbral,
                "candidatos": [asdict(c) for c in seleccion.candidatos],
                "rescate": seleccion.rescate,
                "pesos_clase": seleccion.pesos_clase,
            },
        }

    modelo_json: dict[str, Any] = {
        "version_formato": VERSION_FORMATO,
        "objetivo": objetivo,
        "tipo_objetivo": datos.tipo_objetivo,
        "clase_positiva": _clase_positiva(datos.columnas, objetivo),
        "resultado_pc": {"version": contexto.version, "sha256": contexto.sha256},
        "train_sha256": sha256_train(train),
        "semilla": configuracion.semilla,
        "configuracion": a_diccionario_serializable(configuracion),
        "subgrafo": {
            "variables": sub.variables,
            "padres": sub.padres,
            "aristas": [list(a) for a in sub.aristas],
            "fuera": sub.fuera,
            "descendientes_objetivo": sub.descendientes_objetivo,
        },
        "variables": info_variables,
        "columnas": a_diccionario_serializable(columnas),
        "mecanismos": mecanismos_json,
        "monotonia": monotonia,
        "umbral_decision": seleccion_objetivo.umbral if binario else None,
        "pesos_clase": seleccion_objetivo.pesos_clase,
        "imputadas_en_modelo": imputadas,
        "advertencias": a_diccionario_serializable(advertencias),
        "versiones": _versiones(),
    }
    modelo = ModeloCausal(modelo_json)
    modelo_json["huella"] = huella(modelo, train)

    evaluacion = _evaluar(modelo, datos, selecciones, configuracion)
    if evaluacion["referencia"].get("advertencia"):
        aviso = ProblemaAplicabilidad(
            "COSTO_PARSIMONIA", ADVERTENCIA, evaluacion["referencia"]["advertencia"],
            "No invalida el modelo causal: interprete las probabilidades con cuidado.", MODELO, [objetivo],
        )
        modelo_json["advertencias"].append(a_diccionario_serializable(aviso))
    avisar(total, total, "listo")
    return a_diccionario_serializable(modelo_json), a_diccionario_serializable(evaluacion)


def _evaluar(
    modelo: ModeloCausal, datos: DatosPreparados, selecciones: dict[str, Seleccion],
    configuracion: ConfiguracionModeloCausal,
) -> dict[str, Any]:
    train, test, objetivo = datos.train, datos.test, modelo.objetivo
    mecanismos = []
    for variable, seleccion in selecciones.items():
        es_objetivo = variable == objetivo
        observadas = test[variable].notna().to_numpy()
        y_test = test[variable].to_numpy(dtype=float)[observadas]
        p_test = modelo.media(variable, test)[observadas]
        binaria = modelo.tipo(variable) == BINARIA
        if binaria:
            umbral = seleccion.umbral if seleccion.umbral is not None else 0.5
            puntuacion_test = exactitud_balanceada(y_test, p_test, umbral) if len(y_test) else None
        else:
            puntuacion_test = float(r2_score(y_test, p_test)) if len(y_test) > 1 else None
        entrada = {
            "variable": variable,
            "rol": OBJETIVO if es_objetivo else INTERMEDIA,
            "tipo": modelo.tipo(variable),
            "padres": modelo.padres[variable],
            "familia": seleccion.mecanismo.familia,
            "nombre_familia": NOMBRES_FAMILIA[seleccion.mecanismo.familia],
            "elegido": seleccion.elegido,
            "origen": seleccion.origen,
            "motivo": seleccion.motivo,
            "metrica": seleccion.metrica,
            "candidatos": [
                {**asdict(c), "nombre_familia": NOMBRES_FAMILIA[c.familia]} for c in seleccion.candidatos
            ],
            "puntuacion_cv": seleccion.puntuacion_cv,
            "puntuacion_test": puntuacion_test,
            "filas_train": int(train[variable].notna().sum()),
            "filas_test": int(observadas.sum()),
            "rescate": seleccion.rescate,
            "efectos": _efectos(
                modelo, variable, train, configuracion.puntos_curva,
                configuracion.intervalos_histograma if es_objetivo else None,
            ),
        }
        mecanismos.append(entrada)

    seleccion = selecciones[objetivo]
    y = train[objetivo].to_numpy(dtype=float)
    y_test = test[objetivo].to_numpy(dtype=float)
    p_test = modelo.media(objetivo, test)
    oof = seleccion.prediccion_cv
    if modelo.binario:
        umbral = modelo.umbral_decision
        evaluacion_objetivo = {
            "umbral_decision": umbral,
            "pesos_clase": seleccion.pesos_clase,
            "cv": _metricas_binarias(y, oof, umbral),
            "test": _metricas_binarias(y_test, p_test, umbral),
            "calibracion": {
                "cv": _calibracion(y, oof, configuracion.intervalos_calibracion),
                "test": _calibracion(y_test, p_test, configuracion.intervalos_calibracion),
            },
            "prevalencia_train": float(y.mean()),
        }
        principal = "auc"
    else:
        evaluacion_objetivo = {
            "umbral_decision": None, "pesos_clase": False,
            "cv": _metricas_continuas(y, oof), "test": _metricas_continuas(y_test, p_test),
            "calibracion": None, "prevalencia_train": None,
        }
        principal = "r2"

    referencia = _referencia(datos, modelo.binario, configuracion)
    comparaciones = []
    metricas = ("exactitud_balanceada", "auc") if modelo.binario else ("r2",)
    for metrica in metricas:
        propio, ref = evaluacion_objetivo["cv"].get(metrica), referencia["cv"].get(metrica)
        if propio is not None and ref is not None:
            comparaciones.append({"metrica": metrica, "modelo_causal": propio, "referencia": ref, "diferencia": propio - ref})
    peores = [c for c in comparaciones if c["diferencia"] < -configuracion.umbral_referencia]
    referencia["comparacion"] = comparaciones
    referencia["principal"] = principal
    if peores:
        detalle = ", ".join(
            f"{'AUC' if c['metrica'] == 'auc' else 'R²' if c['metrica'] == 'r2' else 'exactitud balanceada'} "
            f"{decimal(c['modelo_causal'])} frente a {decimal(c['referencia'])}"
            for c in peores
        )
        referencia["advertencia"] = (
            f"El mecanismo del objetivo predice claramente peor que un modelo con todas las variables "
            f"({detalle}, en validación cruzada): las causas directas de PC no capturan toda la información "
            "predictiva (costo de la parsimonia). Esto no invalida el modelo causal, pero obliga a interpretar "
            "sus probabilidades con cuidado: otras variables no causales (o causas no detectadas) también "
            "aportan información."
        )
    else:
        referencia["advertencia"] = None

    return {
        "objetivo": objetivo,
        "mecanismos": mecanismos,
        "evaluacion_objetivo": evaluacion_objetivo,
        "referencia": referencia,
    }


def descripcion_variables(modelo: ModeloCausal) -> list[dict[str, Any]]:
    """Controles de los escenarios: ancestros (las dummies agrupadas por categoría)."""
    vistos, controles = set(), []
    for variable in modelo.ancestros:
        grupo = modelo.unidades.grupo_de.get(variable)
        nombre = grupo or variable
        if nombre in vistos:
            continue
        vistos.add(nombre)
        info = modelo.info_variables[variable]
        descripcion = modelo.unidades.describir(nombre, info["minimo"], info["maximo"])
        entrada = asdict(descripcion)
        entrada["rol"] = info["rol"]
        entrada["columnas_en_modelo"] = [c for c in descripcion.columnas if c in modelo.info_variables]
        if descripcion.control != NUMERICA and grupo is None:
            entrada["minimo"] = entrada["maximo"] = None
        controles.append(entrada)
    return a_diccionario_serializable(controles)

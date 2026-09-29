"""Mecanismos estructurales: candidatos, validación cruzada, parsimonia y serialización.

Cada mecanismo predice una variable a partir de sus padres (unidades preparadas, sin
faltantes). Para una variable binaria, ``eta`` es el logit de P(X = 1 | padres).

Candidatos (simple frente a complejo):
- continua: regresión lineal frente a splines cúbicos restringidos + Ridge (intermedias)
  o GAM lineal de pyGAM (objetivo);
- binaria: regresión logística frente a GAM logístico de pyGAM.

Se elige el complejo solo si mejora la validación cruzada en al menos
``umbral_parsimonia`` (R² o exactitud balanceada). Todos los parámetros se guardan en JSON
(sin pickle); al cargarlos, las predicciones son idénticas a las del modelo ajustado.
"""

from __future__ import annotations

import contextlib
import io
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LinearRegression, LogisticRegression, RidgeCV
from sklearn.metrics import balanced_accuracy_score, r2_score
from sklearn.model_selection import KFold, StratifiedKFold

from pcapp_nucleo.causal.configuracion import ConfiguracionModeloCausal, decimal

LINEAL, LOGISTICA, SPLINES, GAM_LOGISTICO, GAM_LINEAL = (
    "lineal", "logistica", "splines_ridge", "gam_logistico", "gam_lineal",
)
NOMBRES_FAMILIA = {
    LINEAL: "Regresión lineal",
    LOGISTICA: "Regresión logística",
    SPLINES: "Splines + Ridge",
    GAM_LOGISTICO: "GAM logístico",
    GAM_LINEAL: "GAM lineal",
}
R2, EXACTITUD = "r2", "exactitud_balanceada"
_CONSTRAINTS = {"creciente": "monotonic_inc", "decreciente": "monotonic_dec"}
# Regularización casi nula: coeficientes interpretables y probabilidades calibradas.
_C_LOGISTICA = 1e6
_ALPHAS_RIDGE = tuple(np.logspace(-4, 3, 15))
_PERCENTILES_NODOS = {3: (10, 50, 90), 4: (5, 35, 65, 95), 5: (5, 27.5, 50, 72.5, 95)}


class ErrorAjuste(RuntimeError):
    """Un candidato no se pudo ajustar (p. ej. pyGAM no converge ni con el rescate)."""


# --- Mecanismos --------------------------------------------------------------------------------


class Mecanismo:
    familia = ""

    def __init__(self, variable: str, padres: list[str], binaria: bool) -> None:
        self.variable, self.padres, self.binaria = variable, list(padres), binaria

    def eta(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def media(self, X: np.ndarray) -> np.ndarray:
        """Valor esperado: probabilidad de 1 si es binaria."""
        eta = self.eta(X)
        return expit(eta) if self.binaria else eta

    def parametros(self) -> dict[str, Any]:
        raise NotImplementedError

    def a_diccionario(self) -> dict[str, Any]:
        return {
            "familia": self.familia, "variable": self.variable, "padres": self.padres,
            "binaria": self.binaria, "parametros": self.parametros(),
        }


class MecanismoLineal(Mecanismo):
    """Regresión lineal o logística."""

    def __init__(self, variable, padres, binaria, intercepto: float, coeficientes: list[float]) -> None:
        super().__init__(variable, padres, binaria)
        self.familia = LOGISTICA if binaria else LINEAL
        self.intercepto, self.coeficientes = float(intercepto), [float(c) for c in coeficientes]

    def eta(self, X):
        return np.asarray(X, dtype=float) @ np.asarray(self.coeficientes) + self.intercepto

    def parametros(self):
        return {"intercepto": self.intercepto, "coeficientes": self.coeficientes}


def base_splines(x: np.ndarray, nodos: list[float]) -> np.ndarray:
    """x y los términos de un spline cúbico restringido (lineal fuera de los nodos extremos)."""
    t = np.asarray(nodos, dtype=float)
    k = len(t)
    columnas = [x]
    escala = (t[-1] - t[0]) ** 2
    for j in range(k - 2):
        termino = (
            np.maximum(x - t[j], 0) ** 3
            - np.maximum(x - t[k - 2], 0) ** 3 * (t[k - 1] - t[j]) / (t[k - 1] - t[k - 2])
            + np.maximum(x - t[k - 1], 0) ** 3 * (t[k - 2] - t[j]) / (t[k - 1] - t[k - 2])
        )
        columnas.append(termino / escala)
    return np.column_stack(columnas)


class MecanismoSplines(Mecanismo):
    """Splines cúbicos restringidos por padre (los discretos entran lineales) + Ridge."""

    familia = SPLINES

    def __init__(self, variable, padres, nodos: list[list[float] | None], medias, desviaciones,
                 alpha: float, intercepto: float, coeficientes) -> None:
        super().__init__(variable, padres, False)
        self.nodos = [list(map(float, n)) if n else None for n in nodos]
        self.medias, self.desviaciones = [float(v) for v in medias], [float(v) for v in desviaciones]
        self.alpha, self.intercepto = float(alpha), float(intercepto)
        self.coeficientes = [float(c) for c in coeficientes]

    @staticmethod
    def expandir(X: np.ndarray, nodos: list[list[float] | None]) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        bloques = [base_splines(X[:, i], n) if n else X[:, [i]] for i, n in enumerate(nodos)]
        return np.column_stack(bloques)

    def eta(self, X):
        Z = (self.expandir(X, self.nodos) - np.asarray(self.medias)) / np.asarray(self.desviaciones)
        return Z @ np.asarray(self.coeficientes) + self.intercepto

    def parametros(self):
        return {
            "nodos": self.nodos, "medias": self.medias, "desviaciones": self.desviaciones,
            "alpha": self.alpha, "intercepto": self.intercepto, "coeficientes": self.coeficientes,
        }


class MecanismoGam(Mecanismo):
    """GAM de pyGAM guardado por sus parámetros ajustados (términos, nudos y coeficientes)."""

    def __init__(self, variable, padres, binaria, terminos: list[dict], nudos: list, coeficientes, lam: float) -> None:
        super().__init__(variable, padres, binaria)
        self.familia = GAM_LOGISTICO if binaria else GAM_LINEAL
        self.terminos, self.nudos = terminos, nudos
        self.coeficientes, self.lam = [float(c) for c in coeficientes], float(lam)
        self._gam = None

    @classmethod
    def desde_gam(cls, variable, padres, binaria, gam) -> MecanismoGam:
        terminos = [_nativo(t.info) for t in gam.terms]
        nudos = [np.asarray(t.edge_knots_).tolist() if hasattr(t, "edge_knots_") else None for t in gam.terms]
        lam = float(np.ravel(gam.terms[0].lam)[0]) if gam.terms[0].lam is not None else 0.0
        mecanismo = cls(variable, padres, binaria, terminos, nudos, gam.coef_.tolist(), lam)
        mecanismo._gam = None  # se reconstruye desde los parámetros, igual que al cargar
        return mecanismo

    def _modelo(self):
        if self._gam is None:
            from pygam import LinearGAM, LogisticGAM
            from pygam.terms import Term, TermList

            terminos = TermList(*[Term.build_from_info(dict(info)) for info in self.terminos])
            for termino, nudos in zip(terminos, self.nudos):
                if nudos is not None:
                    termino.edge_knots_ = np.asarray(nudos, dtype=float)
            gam = (LogisticGAM if self.binaria else LinearGAM)(terminos)
            gam._validate_params()
            gam.coef_ = np.asarray(self.coeficientes, dtype=float)
            gam.statistics_ = {"m_features": len(self.padres)}
            self._gam = gam
        return self._gam

    def eta(self, X):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return np.asarray(self._modelo()._linear_predictor(np.asarray(X, dtype=float)), dtype=float)

    def parametros(self):
        return {"terminos": self.terminos, "nudos": self.nudos, "coeficientes": self.coeficientes, "lam": self.lam}


def mecanismo_desde_diccionario(datos: dict[str, Any]) -> Mecanismo:
    familia, p = datos["familia"], datos["parametros"]
    variable, padres, binaria = datos["variable"], datos["padres"], datos["binaria"]
    if familia in (LINEAL, LOGISTICA):
        return MecanismoLineal(variable, padres, binaria, p["intercepto"], p["coeficientes"])
    if familia == SPLINES:
        return MecanismoSplines(
            variable, padres, p["nodos"], p["medias"], p["desviaciones"], p["alpha"],
            p["intercepto"], p["coeficientes"],
        )
    if familia in (GAM_LOGISTICO, GAM_LINEAL):
        return MecanismoGam(variable, padres, binaria, p["terminos"], p["nudos"], p["coeficientes"], p["lam"])
    raise ValueError(f"Familia de mecanismo desconocida: {familia}.")


def _nativo(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: _nativo(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_nativo(v) for v in valor]
    if isinstance(valor, np.ndarray):
        return _nativo(valor.tolist())
    if isinstance(valor, np.generic):
        return valor.item()
    return valor


# --- Ajuste ------------------------------------------------------------------------------------


def _pesos_balanceados(y: np.ndarray) -> np.ndarray:
    positivos = max(float(y.sum()), 1.0)
    negativos = max(float(len(y) - y.sum()), 1.0)
    return np.where(y == 1, len(y) / (2 * positivos), len(y) / (2 * negativos))


def ajustar_lineal(variable, padres, X, y, binaria: bool, pesos: bool = False) -> MecanismoLineal:
    if binaria:
        modelo = LogisticRegression(
            C=_C_LOGISTICA, max_iter=5000, class_weight="balanced" if pesos else None
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            modelo.fit(X, y)
        return MecanismoLineal(variable, padres, True, modelo.intercept_[0], modelo.coef_[0])
    modelo = LinearRegression().fit(X, y)
    return MecanismoLineal(variable, padres, False, modelo.intercept_, modelo.coef_)


def nodos_spline(x: np.ndarray, configuracion: ConfiguracionModeloCausal) -> list[float] | None:
    """Nodos en percentiles (Harrell); ``None`` si la variable es discreta."""
    if len(np.unique(x)) < configuracion.valores_minimos_spline:
        return None
    k = min(max(configuracion.nodos_splines, 3), 5)
    nodos = np.unique(np.percentile(x, _PERCENTILES_NODOS[k]))
    return nodos.tolist() if len(nodos) >= 3 else None


def ajustar_splines(variable, padres, X, y, configuracion: ConfiguracionModeloCausal) -> MecanismoSplines:
    nodos = [nodos_spline(X[:, i], configuracion) for i in range(X.shape[1])]
    Z = MecanismoSplines.expandir(X, nodos)
    medias = Z.mean(axis=0)
    desviaciones = Z.std(axis=0)
    desviaciones[desviaciones == 0] = 1.0
    modelo = RidgeCV(alphas=_ALPHAS_RIDGE).fit((Z - medias) / desviaciones, y)
    return MecanismoSplines(variable, padres, nodos, medias, desviaciones, modelo.alpha_, modelo.intercept_, modelo.coef_)


def _terminos_gam(splines: list[bool], restricciones: list[str | None], lam: float, configuracion):
    from pygam import l, s

    terminos = None
    for i, (es_spline, restriccion) in enumerate(zip(splines, restricciones)):
        if es_spline:
            termino = s(i, n_splines=configuracion.splines_gam, lam=lam, constraints=_CONSTRAINTS.get(restriccion))
        else:
            termino = l(i, lam=lam)
        terminos = termino if terminos is None else terminos + termino
    return terminos


def _ajuste_pygam(binaria, terminos, X, y, pesos):
    """Ajusta y dice si convergió (pyGAM solo imprime «did not converge»)."""
    from pygam import LinearGAM, LogisticGAM

    salida = io.StringIO()
    try:
        with contextlib.redirect_stdout(salida), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gam = (LogisticGAM if binaria else LinearGAM)(terminos).fit(X, y, weights=pesos)
    except (np.linalg.LinAlgError, ValueError, FloatingPointError, ZeroDivisionError) as error:
        return None, f"error numérico ({error})"
    if "did not converge" in salida.getvalue():
        return gam, "no convergió"
    if not np.all(np.isfinite(gam.coef_)):
        return None, "coeficientes no finitos"
    return gam, None


def _lam_por_busqueda(binaria, splines, restricciones, X, y, pesos, configuracion) -> float:
    from pygam import LinearGAM, LogisticGAM

    terminos = _terminos_gam(splines, restricciones, 1.0, configuracion)
    try:
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gam = (LogisticGAM if binaria else LinearGAM)(terminos).gridsearch(
                X, y, weights=pesos, lam=np.asarray(configuracion.lams_gam), progress=False
            )
        return float(np.ravel(gam.terms[0].lam)[0])
    except (np.linalg.LinAlgError, ValueError, FloatingPointError, ZeroDivisionError):
        return float(max(configuracion.lams_gam))


def ajustar_gam(
    variable, padres, X, y, binaria: bool, splines: list[bool], restricciones: list[str | None],
    configuracion: ConfiguracionModeloCausal, pesos: bool = False,
) -> tuple[MecanismoGam, list[str], bool]:
    """GAM con ``lam`` elegido por UBRE/GCV (búsqueda de pyGAM).

    Si no converge: ``lam`` × 10 y × 100; si se usaban pesos de clase, después sin pesos (el
    desbalance se compensa con el umbral de decisión). Devuelve el mecanismo, lo que se hizo
    y si se terminaron usando pesos. ``ErrorAjuste`` si nada converge.
    """
    rescate: list[str] = []
    intentos_pesos = [True, False] if pesos else [False]
    for usar_pesos in intentos_pesos:
        vector = _pesos_balanceados(y) if (usar_pesos and binaria) else None
        lam = _lam_por_busqueda(binaria, splines, restricciones, X, y, vector, configuracion)
        for factor in (1, 10, 100):
            gam, problema = _ajuste_pygam(
                binaria, _terminos_gam(splines, restricciones, lam * factor, configuracion), X, y, vector
            )
            if problema is None:
                if factor > 1:
                    rescate.append(f"Se aumentó la regularización a lam = {decimal(lam * factor, 'g')} para que converja.")
                return MecanismoGam.desde_gam(variable, padres, binaria, gam), rescate, usar_pesos
            rescate.append(f"Con lam = {decimal(lam * factor, 'g')}{' y pesos de clase' if usar_pesos else ''}: {problema}.")
        if usar_pesos:
            rescate.append(
                "Se ajustó sin pesos de clase; el desbalance se compensa con el umbral de decisión."
            )
    raise ErrorAjuste("El GAM no convergió ni aumentando la regularización.")


# --- Validación cruzada y selección -------------------------------------------------------------


def umbral_optimo(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """Umbral de probabilidad que maximiza la exactitud balanceada, y esa exactitud."""
    candidatos = np.unique(np.concatenate([np.quantile(p, np.linspace(0.01, 0.99, 99)), [0.5]]))
    mejor, mejor_exactitud = 0.5, -1.0
    for umbral in candidatos:
        exactitud = exactitud_balanceada(y, p, float(umbral))
        if exactitud > mejor_exactitud + 1e-12:
            mejor, mejor_exactitud = float(umbral), exactitud
    return mejor, mejor_exactitud


def exactitud_balanceada(y: np.ndarray, p: np.ndarray, umbral: float) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(balanced_accuracy_score(y.astype(int), (p >= umbral).astype(int)))


def pliegues(y: np.ndarray, binaria: bool, configuracion: ConfiguracionModeloCausal):
    if binaria:
        minimo = int(min(y.sum(), len(y) - y.sum()))
        n = max(2, min(configuracion.pliegues, minimo))
        return list(StratifiedKFold(n, shuffle=True, random_state=configuracion.semilla).split(y, y.astype(int)))
    return list(KFold(configuracion.pliegues, shuffle=True, random_state=configuracion.semilla).split(y))


def predicciones_fuera_de_pliegue(ajustar, X, y, binaria, configuracion) -> np.ndarray:
    oof = np.full(len(y), np.nan)
    for entrenamiento, prueba in pliegues(y, binaria, configuracion):
        mecanismo = ajustar(X[entrenamiento], y[entrenamiento])
        oof[prueba] = mecanismo.media(X[prueba])
    return oof


def puntuar(y: np.ndarray, prediccion: np.ndarray, binaria: bool) -> tuple[float, float | None]:
    """(puntuación, umbral): exactitud balanceada con su umbral óptimo, o R²."""
    if binaria:
        umbral, exactitud = umbral_optimo(y, prediccion)
        return exactitud, umbral
    return float(r2_score(y, prediccion)), None


@dataclass
class Candidato:
    tipo: str  # "simple" | "complejo"
    familia: str
    puntuacion_cv: float | None = None
    umbral_cv: float | None = None
    error: str | None = None
    rescate: list[str] = field(default_factory=list)


@dataclass
class Seleccion:
    mecanismo: Mecanismo
    metrica: str
    candidatos: list[Candidato]
    elegido: str
    origen: str
    motivo: str
    prediccion_cv: np.ndarray
    puntuacion_cv: float
    umbral: float | None = None
    rescate: list[str] = field(default_factory=list)
    pesos_clase: bool = False


def seleccionar_mecanismo(
    variable: str,
    padres: list[str],
    X: np.ndarray,
    y: np.ndarray,
    binaria: bool,
    es_objetivo: bool,
    configuracion: ConfiguracionModeloCausal,
    restricciones: list[str | None] | None = None,
    pesos: bool = False,
    eleccion: str | None = None,
) -> Seleccion:
    """Ajusta los dos candidatos, los compara en validación cruzada y reajusta el elegido con
    todas las filas. ``eleccion`` (``simple``/``complejo``) es el override del usuario."""
    restricciones = restricciones or [None] * len(padres)
    splines = [nodos_spline(X[:, i], configuracion) is not None for i in range(X.shape[1])]
    metrica = EXACTITUD if binaria else R2

    def simple(Xa, ya):
        return ajustar_lineal(variable, padres, Xa, ya, binaria, pesos)

    if binaria or es_objetivo:
        familia_compleja = GAM_LOGISTICO if binaria else GAM_LINEAL

        def complejo(Xa, ya):
            return ajustar_gam(variable, padres, Xa, ya, binaria, splines, restricciones, configuracion, pesos)[0]
    else:
        familia_compleja = SPLINES

        def complejo(Xa, ya):
            return ajustar_splines(variable, padres, Xa, ya, configuracion)

    candidatos = [Candidato("simple", LOGISTICA if binaria else LINEAL), Candidato("complejo", familia_compleja)]
    predicciones: dict[str, np.ndarray] = {}
    for candidato, ajustar in zip(candidatos, (simple, complejo)):
        if candidato.tipo == "complejo" and not any(splines):
            candidato.error = "Todos los padres son discretos: el modelo complejo coincidiría con el simple."
            continue
        try:
            prediccion = predicciones_fuera_de_pliegue(ajustar, X, y, binaria, configuracion)
        except ErrorAjuste as error:
            candidato.error = str(error)
            continue
        candidato.puntuacion_cv, candidato.umbral_cv = puntuar(y, prediccion, binaria)
        predicciones[candidato.tipo] = prediccion

    simple_c, complejo_c = candidatos
    if complejo_c.puntuacion_cv is None:
        elegido, motivo = "simple", f"Se usa el modelo simple: {complejo_c.error}"
    elif eleccion in ("simple", "complejo"):
        elegido, motivo = eleccion, "Elegido por el usuario."
    else:
        mejora = complejo_c.puntuacion_cv - simple_c.puntuacion_cv
        if mejora >= configuracion.umbral_parsimonia:
            elegido = "complejo"
            motivo = (
                f"El modelo complejo mejora la validación cruzada en {decimal(mejora, '+.3f')} "
                f"(umbral de parsimonia {decimal(configuracion.umbral_parsimonia, 'g')})."
            )
        else:
            elegido = "simple"
            motivo = (
                f"El modelo complejo solo cambia la validación cruzada en {decimal(mejora, '+.3f')} "
                f"(< {decimal(configuracion.umbral_parsimonia, 'g')}): se prefiere el simple."
            )
    origen = "manual" if eleccion in ("simple", "complejo") and complejo_c.puntuacion_cv is not None else "automatico"

    rescate: list[str] = []
    pesos_usados = pesos
    if elegido == "complejo":
        if binaria or es_objetivo:
            mecanismo, rescate, pesos_usados = ajustar_gam(
                variable, padres, X, y, binaria, splines, restricciones, configuracion, pesos
            )
        else:
            mecanismo = ajustar_splines(variable, padres, X, y, configuracion)
        complejo_c.rescate = rescate
    else:
        mecanismo = simple(X, y)
    elegido_c = simple_c if elegido == "simple" else complejo_c
    return Seleccion(
        mecanismo=mecanismo, metrica=metrica, candidatos=candidatos, elegido=elegido, origen=origen,
        motivo=motivo, prediccion_cv=predicciones[elegido], puntuacion_cv=float(elegido_c.puntuacion_cv),
        umbral=elegido_c.umbral_cv, rescate=rescate, pesos_clase=pesos_usados and binaria,
    )

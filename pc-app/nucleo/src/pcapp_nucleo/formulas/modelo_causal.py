"""Explicación del modelo causal: qué variables entran, cómo se elige cada mecanismo y qué calcula.

Parte de ``modelo_causal.json`` y ``evaluacion.json`` ya guardados. Las decisiones con umbral
(parsimonia, calidad de las intermedias, costo frente a la referencia) se reevalúan sobre las
puntuaciones de validación cruzada guardadas, sin reajustar nada: si con otro umbral cambiaría
el mecanismo elegido, se avisa de que habría que reconstruir el modelo.

Además, cada mecanismo se evalúa en un caso (valores de sus padres, por defecto las medianas
de entrenamiento) y se descompone término a término: ``η = β₀ + Σ c_j``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Any

import numpy as np
from scipy.special import expit

from pcapp_nucleo.causal.configuracion import ConfiguracionModeloCausal
from pcapp_nucleo.causal.mecanismos import (
    EXACTITUD,
    NOMBRES_FAMILIA,
    Mecanismo,
    MecanismoGam,
    MecanismoLineal,
    MecanismoSplines,
    base_splines,
)
from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.formulas.traza import (
    ORIGEN_CALCULADO,
    ORIGEN_DATASET,
    ORIGEN_UMBRAL,
    PasoFormula,
    Termino,
    Umbral,
    num,
    texto,
)

_GE = r"\ge"

# nombre -> (símbolo, descripción, mínimo, máximo, paso)
_UMBRALES = {
    "umbral_parsimonia": (r"\delta", "Mejora mínima en CV para preferir el mecanismo complejo", 0.0, 0.5, 0.005),
    "r2_minimo_intermedia": (r"R^2_{\min}", "R² mínimo de una intermedia continua", 0.0, 1.0, 0.01),
    "exactitud_minima_intermedia": (r"EB_{\min}", "Exactitud balanceada mínima de una intermedia binaria", 0.5, 1.0, 0.01),
    "umbral_referencia": (r"\delta_{\mathrm{ref}}", "Pérdida tolerada frente al modelo de referencia", 0.0, 0.2, 0.005),
}


@dataclass(frozen=True)
class ControlCaso:
    """Valor de un padre en el caso evaluado."""

    variable: str
    valor: float
    minimo: float
    maximo: float
    mediana: float
    original: str | None  # en unidades originales (o su etiqueta)


@dataclass(frozen=True)
class CandidatoExplicado:
    tipo: str  # "simple" | "complejo"
    familia: str
    nombre_familia: str
    puntuacion_cv: float | None
    error: str | None


@dataclass(frozen=True)
class MecanismoExplicado:
    variable: str
    rol: str
    tipo: str
    padres: list[str]
    metrica: str
    familia: str
    nombre_familia: str
    candidatos: list[CandidatoExplicado]
    mejora: float | None
    elegido: str
    elegido_guardado: str
    origen: str
    cambiaria: bool
    puntuacion_cv: float | None
    puntuacion_test: float | None
    calidad_suficiente: bool | None  # None para el objetivo
    resumen: str
    pasos: list[PasoFormula] = field(default_factory=list)


@dataclass(frozen=True)
class EntradaModelo:
    nombre: str
    valor: str
    usada: bool
    nota: str


@dataclass(frozen=True)
class TrazaModeloCausal:
    objetivo: str
    resumen: str
    fundamentos: list[PasoFormula]
    entradas: list[EntradaModelo]
    mecanismos: list[MecanismoExplicado]
    monotonia: list[PasoFormula]
    referencia: list[PasoFormula]
    controles: list[ControlCaso]
    umbrales: list[Umbral]
    avisos: list[str]


def configuracion_con_umbrales(base: dict[str, Any], umbrales: dict[str, float] | None) -> ConfiguracionModeloCausal:
    """Configuración guardada del modelo con los umbrales indicados; ``ValueError`` si no son válidos."""
    conocidos = {f.name for f in fields(ConfiguracionModeloCausal)}
    datos = {k: v for k, v in base.items() if k in conocidos}
    if "lams_gam" in datos:
        datos["lams_gam"] = tuple(datos["lams_gam"])
    configuracion = ConfiguracionModeloCausal(**datos)
    cambios = {}
    for nombre, valor in (umbrales or {}).items():
        if nombre not in _UMBRALES:
            raise ValueError(f"Umbral desconocido: {nombre}.")
        _, _, minimo, maximo, _ = _UMBRALES[nombre]
        if not minimo <= valor <= maximo:
            raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}.")
        cambios[nombre] = float(valor)
    return replace(configuracion, **cambios)


def _t(nombre: str) -> str:
    return r"\text{" + nombre.replace("_", r"\_") + "}"


def _metrica(metrica: str) -> str:
    return "exactitud balanceada" if metrica == EXACTITUD else "R²"


def _signo(valor: float, decimales: int = 3) -> str:
    return ("+" if valor >= 0 else "-") + r"\," + num(abs(valor), decimales)


# --- Descomposición de un mecanismo en un caso --------------------------------------------------------------


def contribuciones(mecanismo: Mecanismo, x: np.ndarray) -> tuple[float, list[float]]:
    """(término constante, contribución de cada padre) con ``η = constante + Σ contribuciones``."""
    x = np.asarray(x, dtype=float).reshape(1, -1)
    if isinstance(mecanismo, MecanismoLineal):
        return mecanismo.intercepto, [float(c * v) for c, v in zip(mecanismo.coeficientes, x[0])]
    if isinstance(mecanismo, MecanismoSplines):
        z = (mecanismo.expandir(x, mecanismo.nodos)[0] - np.asarray(mecanismo.medias)) / np.asarray(mecanismo.desviaciones)
        aportes, inicio = [], 0
        for i, nodos in enumerate(mecanismo.nodos):
            ancho = base_splines(x[:, i], nodos).shape[1] if nodos else 1
            bloque = slice(inicio, inicio + ancho)
            aportes.append(float(np.dot(z[bloque], mecanismo.coeficientes[bloque])))
            inicio += ancho
        return mecanismo.intercepto, aportes
    if isinstance(mecanismo, MecanismoGam):
        gam = mecanismo._modelo()
        coef = np.asarray(mecanismo.coeficientes)
        constante, aportes = 0.0, [0.0] * len(mecanismo.padres)
        for i, termino in enumerate(gam.terms):
            valor = float((gam._modelmat(x, term=i) @ coef[gam.terms.get_coef_indices(i)])[0])
            if termino.isintercept:
                constante += valor
            else:
                aportes[int(termino.feature)] += valor
        return constante, aportes
    raise TypeError(f"Mecanismo sin descomposición: {type(mecanismo).__name__}.")


def _ecuacion(mecanismo: Mecanismo, padres: list[str], variable: str) -> PasoFormula:
    binaria = mecanismo.binaria
    salida = rf"P({_t(variable)}=1)=\sigma(\eta)," if binaria else rf"\hat{{{_t(variable)}}}=\eta,"
    if isinstance(mecanismo, MecanismoLineal):
        sustituida = rf"\eta={num(mecanismo.intercepto)}" + "".join(
            rf"{_signo(c)}\,{_t(p)}" for c, p in zip(mecanismo.coeficientes, padres)
        )
        return PasoFormula(
            "ecuacion", "Ecuación ajustada",
            salida + r"\quad \eta=\beta_0+\sum_j\beta_j x_j",
            sustituida,
            "Coeficientes ajustados con todas las filas de entrenamiento (unidades preparadas).",
            terminos=[
                Termino(rf"\beta_{{{j + 1}}}", f"coeficiente de {p}", texto(c, 4), ORIGEN_CALCULADO)
                for j, (c, p) in enumerate(zip(mecanismo.coeficientes, padres))
            ],
        )
    if isinstance(mecanismo, MecanismoSplines):
        nodos = [
            rf"{_t(p)}:\ ({', '.join(num(t) for t in n)})" if n else rf"{_t(p)}:\ \text{{lineal}}"
            for p, n in zip(padres, mecanismo.nodos)
        ]
        return PasoFormula(
            "ecuacion", "Ecuación ajustada (splines cúbicos restringidos + Ridge)",
            salida + r"\quad \eta=\beta_0+\sum_j\Big[\beta_{j0}\tilde x_j+\sum_{k}\beta_{jk}\,\tilde s_k(x_j)\Big]",
            r"\text{nodos}\ \Big\{" + r";\ ".join(nodos) + r"\Big\},\quad \alpha_{\mathrm{Ridge}}=" + num(mecanismo.alpha, 4),
            f"{len(mecanismo.coeficientes)} coeficientes; cada término se estandariza (media y desviación de entrenamiento).",
            terminos=[Termino(r"\alpha", "regularización Ridge elegida por CV", texto(mecanismo.alpha, 4), ORIGEN_CALCULADO)],
            nota="Lineal fuera de los nodos extremos: no extrapola con curvas.",
        )
    if isinstance(mecanismo, MecanismoGam):
        enlace = r"\operatorname{logit}P" if binaria else r"\mathbb{E}"
        return PasoFormula(
            "ecuacion", f"Ecuación ajustada ({NOMBRES_FAMILIA[mecanismo.familia]})",
            rf"{enlace}[{_t(variable)}]=\beta_0+\sum_j f_j(x_j),\qquad f_j=\sum_k \beta_{{jk}}B_k(x_j)",
            rf"\lambda={num(mecanismo.lam, 4)},\quad {len(mecanismo.coeficientes)}\ \text{{coeficientes}}",
            "Cada f_j es una suma de B-splines penalizada por λ (elegido por búsqueda en CV).",
            terminos=[Termino(r"\lambda", "penalización de suavidad", texto(mecanismo.lam, 4), ORIGEN_CALCULADO)],
        )
    raise TypeError(type(mecanismo).__name__)


def _caso(
    modelo: ModeloCausal, variable: str, valores: dict[str, float], umbral: float | None
) -> PasoFormula:
    mecanismo = modelo.mecanismos[variable]
    padres = modelo.padres[variable]
    x = np.array([valores[p] for p in padres], dtype=float)
    constante, aportes = contribuciones(mecanismo, x)
    eta = constante + sum(aportes)
    terminos_latex = "".join(rf"\underbrace{{{_signo(a)}}}_{{{_t(p)}}}" for a, p in zip(aportes, padres))
    sustituida = rf"\eta={num(constante)}{terminos_latex}={num(eta)}"
    if mecanismo.binaria:
        p = float(expit(eta))
        sustituida += rf",\quad p=\sigma({num(eta)})={num(p)}"
        resultado = f"Probabilidad de 1: {texto(p)}."
        if umbral is not None:
            clase = int(p >= umbral)
            sustituida += rf"\ {_GE if clase else '<'}\ t^*={num(umbral)}"
            resultado += f" Con el umbral {texto(umbral)} se predice la clase {clase}."
    else:
        resultado = f"Valor esperado: {texto(eta)} (unidades preparadas)."
        original = modelo.unidades.a_original(variable, eta)
        if isinstance(original, (int, float)) and abs(float(original) - eta) > 1e-9:
            resultado += f" En unidades originales ≈ {texto(float(original), 4)}."
    return PasoFormula(
        "caso", "Evaluado en el caso",
        r"\eta=c_0+\sum_j c_j(x_j)",
        sustituida, resultado,
        terminos=[Termino(rf"x_{{{j + 1}}}", p, texto(valores[p], 4), ORIGEN_DATASET) for j, p in enumerate(padres)]
        + [Termino(rf"c_{{{j + 1}}}", f"aporte de {p} a η", texto(a, 4), ORIGEN_CALCULADO) for j, (a, p) in enumerate(zip(aportes, padres))],
        nota="Cada mecanismo se evalúa por separado con estos valores de sus padres (no es un escenario: "
             "no propaga cambios por el grafo).",
    )


# --- Selección de cada mecanismo ----------------------------------------------------------------------------


def _mecanismo(
    modelo: ModeloCausal, modelo_json: dict[str, Any], variable: str, evaluacion: dict[str, Any] | None,
    cfg: ConfiguracionModeloCausal, valores: dict[str, float],
) -> MecanismoExplicado:
    guardado = modelo_json["mecanismos"][variable]
    sel = guardado["seleccion"]
    info = modelo.info_variables[variable]
    es_objetivo = variable == modelo.objetivo
    candidatos = [
        CandidatoExplicado(c["tipo"], c["familia"], NOMBRES_FAMILIA[c["familia"]], c.get("puntuacion_cv"), c.get("error"))
        for c in sel["candidatos"]
    ]
    simple = next(c for c in candidatos if c.tipo == "simple")
    complejo = next(c for c in candidatos if c.tipo == "complejo")
    metrica = sel["metrica"]
    nombre_m = _metrica(metrica)
    mejora = None
    if complejo.puntuacion_cv is None:
        elegido = "simple"
        decision = f"El complejo no está disponible: {complejo.error}"
        cumple_parsimonia = False
    elif sel["origen"] == "manual":
        elegido = sel["elegido"]
        mejora = complejo.puntuacion_cv - simple.puntuacion_cv
        decision = f"Elegido por el usuario ({elegido}); la regla de parsimonia no se aplica."
        cumple_parsimonia = mejora >= cfg.umbral_parsimonia
    else:
        mejora = complejo.puntuacion_cv - simple.puntuacion_cv
        cumple_parsimonia = mejora >= cfg.umbral_parsimonia
        elegido = "complejo" if cumple_parsimonia else "simple"
        decision = "Gana el complejo." if cumple_parsimonia else "Se prefiere el simple (parsimonia)."
    cambiaria = elegido != sel["elegido"]
    puntuacion = (complejo if elegido == "complejo" else simple).puntuacion_cv

    pasos = [PasoFormula(
        "cv", f"Validación cruzada ({cfg.pliegues} pliegues): {nombre_m}",
        r"EB=\tfrac12\left(\frac{TP}{TP+FN}+\frac{TN}{TN+FP}\right)\ \text{con}\ t^*=\arg\max_t EB(t)"
        if metrica == EXACTITUD else r"R^2=1-\frac{\sum_i(y_i-\hat y_i^{(-k)})^2}{\sum_i(y_i-\bar y)^2}",
        rf"\text{{simple ({simple.nombre_familia})}}={num(simple.puntuacion_cv)},\quad "
        rf"\text{{complejo ({complejo.nombre_familia})}}="
        + (num(complejo.puntuacion_cv) if complejo.puntuacion_cv is not None else r"\text{no disponible}"),
        "Predicciones fuera de pliegue: cada fila se predice con un modelo que no la vio.",
        terminos=[
            Termino("K", "pliegues", str(cfg.pliegues), ORIGEN_UMBRAL),
            Termino("n", "filas de entrenamiento con valor", None, ORIGEN_DATASET),
        ],
    )]
    if mejora is not None:
        pasos.append(PasoFormula(
            "parsimonia", "Regla de parsimonia",
            r"\Delta=CV_{\text{complejo}}-CV_{\text{simple}}\ \ge\ \delta\ \Rightarrow\ \text{complejo}",
            rf"\Delta={num(complejo.puntuacion_cv)}-{num(simple.puntuacion_cv)}={num(mejora)}\ "
            rf"{_GE if cumple_parsimonia else '<'}\ \delta={num(cfg.umbral_parsimonia)}",
            decision + (f" Con estos umbrales cambiaría a «{elegido}» (habría que reconstruir el modelo)." if cambiaria else ""),
            cumple=cumple_parsimonia,
            terminos=[Termino(r"\delta", "umbral de parsimonia", texto(cfg.umbral_parsimonia), ORIGEN_UMBRAL)],
        ))
    else:
        pasos.append(PasoFormula(
            "parsimonia", "Regla de parsimonia", r"\Delta=CV_{\text{complejo}}-CV_{\text{simple}}", None, decision,
        ))

    calidad = None
    if not es_objetivo and puntuacion is not None:
        minimo = cfg.exactitud_minima_intermedia if metrica == EXACTITUD else cfg.r2_minimo_intermedia
        calidad = puntuacion >= minimo
        simbolo = r"EB_{\min}" if metrica == EXACTITUD else r"R^2_{\min}"
        pasos.append(PasoFormula(
            "calidad", "Calidad de la intermedia",
            rf"CV\ \ge\ {simbolo}",
            rf"{num(puntuacion)}\ {_GE if calidad else '<'}\ {simbolo}={num(minimo)}",
            "Se explica bien con sus padres." if calidad else
            "Se explica mal con sus padres: los efectos que pasan por ella son inciertos.",
            cumple=calidad,
        ))

    mecanismo = modelo.mecanismos[variable]
    pasos.append(_ecuacion(mecanismo, modelo.padres[variable], variable))
    pasos.append(_caso(modelo, variable, valores, modelo.umbral_decision if es_objetivo else sel.get("umbral_cv")))

    test = None
    for m in (evaluacion or {}).get("mecanismos", []):
        if m["variable"] == variable:
            test = m.get("puntuacion_test")
    if test is not None and puntuacion is not None:
        pasos.append(PasoFormula(
            "test", "Comprobación en test",
            r"CV\ \text{(entrenamiento)}\ \text{vs}\ \text{test}",
            rf"{num(sel['puntuacion_cv'])}\ \text{{vs}}\ {num(test)}",
            "El test no interviene en la elección: solo comprueba que el mecanismo generaliza.",
        ))

    resumen = (
        f"{NOMBRES_FAMILIA[mecanismo.familia]} ({sel['elegido']}"
        + (", elegido por el usuario" if sel["origen"] == "manual" else "") + ")."
    )
    if cambiaria:
        resumen += f" Con estos umbrales sería «{elegido}»."
    if calidad is False:
        resumen += f" {nombre_m} en CV por debajo del mínimo."
    return MecanismoExplicado(
        variable, info["rol"], info["tipo"], modelo.padres[variable], metrica, mecanismo.familia,
        NOMBRES_FAMILIA[mecanismo.familia], candidatos, None if mejora is None else round(mejora, 4),
        elegido, sel["elegido"], sel["origen"], cambiaria, puntuacion, test, calidad, resumen, pasos,
    )


def _fundamentos(modelo: ModeloCausal, modelo_json: dict[str, Any], cfg: ConfiguracionModeloCausal) -> list[PasoFormula]:
    sub = modelo_json["subgrafo"]
    raices = [v for v in modelo.variables if not modelo.padres[v]]
    return [
        PasoFormula(
            "subgrafo", "1. Variables del modelo",
            r"\mathcal{V}=\{Y\}\cup\operatorname{an}(Y)",
            rf"|\mathcal{{V}}|={len(sub['variables'])},\quad \text{{raíces}}={len(raices)},\quad "
            rf"\text{{con mecanismo}}={len(modelo.mecanismos)}",
            f"Solo entran el objetivo ({modelo.objetivo}) y sus ancestros en el grafo de PC. Las raíces conservan su "
            "valor observado.",
        ),
        PasoFormula(
            "estructural", "2. Mecanismo estructural de cada variable con padres",
            r"X_j=f_j\big(\mathrm{pa}(X_j)\big)+\varepsilon_j\qquad P(X_j=1)=\sigma\big(f_j(\mathrm{pa}(X_j))\big)",
            None,
            "Continua: valor esperado más ruido. Binaria: probabilidad con enlace logístico. Se ajusta solo con train; "
            "los faltantes de los padres se rellenan con la mediana de train.",
        ),
        PasoFormula(
            "candidatos", "3. Dos candidatos por variable",
            r"\text{simple}:\ \text{lineal/logística}\qquad \text{complejo}:\ \text{splines + Ridge (intermedia continua) o GAM (binaria u objetivo)}",
            None,
            "Si todos los padres son discretos, el complejo coincidiría con el simple y no se ajusta.",
        ),
        PasoFormula(
            "parsimonia", "4. Parsimonia",
            r"\text{complejo}\iff CV_{\text{complejo}}-CV_{\text{simple}}\ge\delta",
            rf"\delta={num(cfg.umbral_parsimonia)}",
            "Ante una mejora pequeña se prefiere el modelo simple, más estable e interpretable.",
            terminos=[Termino(r"\delta", "umbral de parsimonia", texto(cfg.umbral_parsimonia), ORIGEN_UMBRAL)],
        ),
    ]


def _referencia(evaluacion: dict[str, Any] | None, cfg: ConfiguracionModeloCausal) -> list[PasoFormula]:
    referencia = (evaluacion or {}).get("referencia") or {}
    pasos = []
    for c in referencia.get("comparacion", []):
        nombre = {"auc": "AUC", "r2": "R²"}.get(c["metrica"], "exactitud balanceada")
        diferencia = c["diferencia"]
        peor = diferencia < -cfg.umbral_referencia
        pasos.append(PasoFormula(
            f"referencia_{c['metrica']}", f"Costo de la parsimonia ({nombre})",
            r"CV_{\text{causal}}-CV_{\text{ref}}<-\delta_{\mathrm{ref}}\ \Rightarrow\ \text{advertencia}",
            rf"{num(c['modelo_causal'])}-{num(c['referencia'])}={num(diferencia)}\ "
            rf"{'<' if peor else _GE}\ -{num(cfg.umbral_referencia)}",
            "El objetivo predice claramente peor que un modelo con todas las variables." if peor
            else "Sin pérdida relevante frente al modelo de referencia.",
            cumple=not peor,
            nota="La referencia usa todas las variables (no solo las causas): mide información predictiva, no causalidad.",
        ))
    return pasos


def _monotonia(modelo_json: dict[str, Any]) -> list[PasoFormula]:
    pasos = []
    for d in modelo_json.get("monotonia", []):
        restriccion = d.get("restriccion")
        pasos.append(PasoFormula(
            f"monotonia_{d['padre']}", d["padre"],
            r"f_j\ \text{creciente}\iff\rho_s>0,\qquad f_j\ \text{decreciente}\iff\rho_s<0",
            rf"\text{{restricción}}=\text{{{restriccion or 'ninguna'}}}",
            d["motivo"],
            nota="Origen: " + {"automatico": "diagnóstico de la recomendación de prueba", "manual": "elegida por el usuario",
                               "no_aplica": "no aplica"}.get(d.get("origen"), d.get("origen") or ""),
        ))
    return pasos


def explicar_modelo_causal(
    modelo_json: dict[str, Any],
    evaluacion: dict[str, Any] | None = None,
    umbrales: dict[str, float] | None = None,
    valores: dict[str, float] | None = None,
    modelo: ModeloCausal | None = None,
) -> TrazaModeloCausal:
    """Traza del modelo causal guardado.

    ``valores``: valores de los ancestros (unidades preparadas) para evaluar cada mecanismo; los
    que falten toman la mediana de entrenamiento. ``modelo``: el ya cargado, para no reconstruirlo.

    Raises:
        ValueError: si un umbral o un valor no es válido.
    """
    cfg = configuracion_con_umbrales(modelo_json["configuracion"], umbrales)
    base = configuracion_con_umbrales(modelo_json["configuracion"], None)
    modelo = modelo or ModeloCausal(modelo_json)
    valores = dict(valores or {})
    desconocidas = sorted(set(valores) - set(modelo.variables))
    if desconocidas:
        raise ValueError(f"Variable desconocida en el caso: {desconocidas[0]}.")
    controles, caso = [], {}
    for v in modelo.variables:
        info = modelo.info_variables[v]
        valor = float(valores.get(v, info["mediana"]))
        if not np.isfinite(valor):
            raise ValueError(f"El valor de {v} no es un número.")
        caso[v] = valor
        if v != modelo.objetivo and any(v in modelo.padres[m] for m in modelo.mecanismos):
            original = modelo.unidades.a_original(v, valor)
            controles.append(ControlCaso(
                v, valor, info["minimo"], info["maximo"], info["mediana"],
                None if original is None else (texto(float(original), 4) if isinstance(original, (int, float)) else str(original)),
            ))

    orden = [v for v in modelo.variables if v in modelo.mecanismos]
    mecanismos = [_mecanismo(modelo, modelo_json, v, evaluacion, cfg, caso) for v in orden]
    sub = modelo_json["subgrafo"]
    raices = [v for v in modelo.variables if not modelo.padres[v]]
    entradas = [
        EntradaModelo("Objetivo y sus ancestros", str(len(sub["variables"])), True, "Las únicas variables del modelo."),
        EntradaModelo("Aristas del resultado de PC", f"versión {modelo_json['resultado_pc']['version']}", True,
                      "Definen los padres de cada variable."),
        EntradaModelo("Conjunto de entrenamiento", "train", True, "Ajusta y compara los candidatos (validación cruzada)."),
        EntradaModelo("Diagnóstico de forma (recomendación)", str(len(modelo_json.get("monotonia", []))), True,
                      "Decide las restricciones de monotonía de los padres del objetivo."),
        EntradaModelo("Variables fuera del subgrafo", ", ".join(sub["fuera"]) or "ninguna", False,
                      "No son ancestros del objetivo en el grafo: no entran al modelo."),
        EntradaModelo("Descendientes del objetivo", ", ".join(sub["descendientes_objetivo"]) or "ninguno", False,
                      "Son consecuencias: usarlas para predecir el objetivo invertiría la causalidad."),
        EntradaModelo("Raíces", ", ".join(raices) or "ninguna", False,
                      "No tienen mecanismo: conservan su valor observado."),
        EntradaModelo("Conjunto de prueba", "test", False,
                      "No interviene en la elección; solo en la comprobación final."),
    ]
    avisos = [a["mensaje"] for a in modelo_json.get("advertencias", [])]
    cambian = [m.variable for m in mecanismos if m.cambiaria]
    if cambian:
        avisos.insert(0, f"Con estos umbrales cambiaría el mecanismo de: {', '.join(cambian)}. "
                         "El modelo guardado no cambia; para aplicarlo hay que reconstruirlo.")
    complejos = sum(m.elegido_guardado == "complejo" for m in mecanismos)
    resumen = (
        f"{len(mecanismos)} mecanismos ({complejos} complejos, {len(mecanismos) - complejos} simples) para "
        f"{modelo.objetivo} y sus ancestros."
    )
    editables = [
        Umbral(n, s, d, float(getattr(cfg, n)), float(getattr(base, n)), mi, ma, p)
        for n, (s, d, mi, ma, p) in _UMBRALES.items()
    ]
    return TrazaModeloCausal(
        modelo.objetivo, resumen, _fundamentos(modelo, modelo_json, cfg), entradas, mecanismos,
        _monotonia(modelo_json), _referencia(evaluacion, cfg), controles, editables, avisos,
    )

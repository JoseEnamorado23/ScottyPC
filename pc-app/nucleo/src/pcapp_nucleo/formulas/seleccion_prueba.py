"""Explicación de la selección de la prueba de independencia (etapa «recomendación»).

Parte de la ``RecomendacionPrueba`` ya calculada (su evidencia por variable es la que
realmente se usó) y reconstruye, regla por regla, qué fórmulas se aplicaron y con qué valores.
No vuelve a leer el dataset ni duplica las reglas de ``seleccion_prueba``: solo reevalúa las
comparaciones con umbral sobre la evidencia guardada, para poder probar otros umbrales
(``umbrales``) y ver cómo cambiaría la decisión.

Lo que no se puede reevaluar desde la evidencia guardada es el criterio de la curva que sube y
baja (usa los grupos de filas de cada intervalo): se conserva el resultado original y se avisa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from scipy import stats

from pcapp_nucleo.configuracion import ConfiguracionValidacion
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
from pcapp_nucleo.preparacion import CONTINUA
from pcapp_nucleo.seleccion_prueba import (
    CHISQ,
    FISHERZ,
    KCI,
    MOTIVO_FORMA_U,
    MV_FISHERZ,
    DiagnosticoVariable,
    RecomendacionPrueba,
)

_GE, _LE = r"\ge", r"\le"


# nombre -> (símbolo LaTeX, descripción, mínimo, máximo, paso, entero)
_UMBRALES = {
    "alfa_no_linealidad": (r"\alpha", "Significación de la dependencia por intervalos", 0.0001, 0.2, 0.0001, False),
    "efecto_minimo_no_linealidad": (r"e_{\min}", "Amplitud mínima de la curva (en desviaciones del objetivo)", 0.0, 2.0, 0.05, False),
    "spearman_debil": (r"\rho_0", "|ρ de Spearman| por debajo del cual la correlación es débil", 0.0, 1.0, 0.01, False),
    "proporcion_maxima_categoricas": (r"c_{\max}", "Proporción de categóricas que activa chi-cuadrado", 0.0, 1.0, 0.05, False),
    "alfa_pc": (r"\alpha_{PC}", "Nivel de significación de las pruebas de independencia de PC", 0.001, 0.2, 0.001, False),
    "intervalos_chisq": (r"L", "Intervalos al discretizar para chi-cuadrado", 2, 10, 1, True),
}
UMBRALES_EDITABLES = tuple(_UMBRALES)


def configuracion_con_umbrales(umbrales: dict[str, float] | None) -> ConfiguracionValidacion:
    """Configuración por defecto con los umbrales indicados; ``ValueError`` si alguno no es válido."""
    cambios: dict[str, float] = {}
    for nombre, valor in (umbrales or {}).items():
        if nombre not in _UMBRALES:
            raise ValueError(f"Umbral desconocido: {nombre}.")
        _, _, minimo, maximo, _, entero = _UMBRALES[nombre]
        if not minimo <= valor <= maximo:
            raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}.")
        cambios[nombre] = int(valor) if entero else float(valor)
    return replace(ConfiguracionValidacion(), **cambios)


@dataclass(frozen=True)
class ReglaDecision:
    orden: int
    titulo: str
    condicion: str  # LaTeX
    sustituida: str  # LaTeX
    cumple: bool
    # "decide": primera regla que se cumple; "sin_efecto": se cumple pero una anterior ya decidió;
    # "no_cumple": no se cumple.
    estado: str
    consecuencia: str
    detalle: str | None = None


@dataclass(frozen=True)
class VariableExplicada:
    nombre: str
    tipo_final: str
    evaluada: bool
    no_monotona: bool | None
    criterio: str | None  # "forma_u" | "spearman_debil" | None
    resumen: str
    pasos: list[PasoFormula] = field(default_factory=list)


@dataclass(frozen=True)
class EntradaDecision:
    nombre: str
    valor: str
    usada: bool
    nota: str


@dataclass(frozen=True)
class TrazaSeleccionPrueba:
    prueba: str
    prueba_original: str
    cambia: bool
    resumen: str
    entradas: list[EntradaDecision]
    reglas: list[ReglaDecision]
    variables: list[VariableExplicada]
    formulas_prueba: list[PasoFormula]
    umbrales: list[Umbral]
    k: int
    avisos: list[str]


# --- Variables -------------------------------------------------------------------------------------------


def _explicar_variable(d: DiagnosticoVariable, cfg: ConfiguracionValidacion) -> VariableExplicada:
    if d.tipo_final != CONTINUA:
        return VariableExplicada(
            d.nombre, d.tipo_final, False, None, None,
            "Ignorada en este diagnóstico: no es continua (la forma de la relación se mide dividiendo "
            "una variable continua en intervalos).",
        )
    if d.spearman is None:
        razon = d.motivo or (
            f"Tiene menos de {cfg.intervalos_no_linealidad} valores distintos, no se puede dividir en "
            f"{cfg.intervalos_no_linealidad} intervalos."
        )
        return VariableExplicada(d.nombre, d.tipo_final, False, None, None, f"Ignorada: {razon}")

    n_int = len(d.valores_por_intervalo)
    amp = d.amplitud_en_desviaciones
    rho = d.spearman
    p = d.p_intervalos
    forma_u = d.motivo == MOTIVO_FORMA_U
    dependiente = p is not None and p < cfg.alfa_no_linealidad
    fuerte = dependiente and amp is not None and amp >= cfg.efecto_minimo_no_linealidad
    spearman_debil = fuerte and abs(rho) < cfg.spearman_debil
    no_monotona = forma_u or spearman_debil
    criterio = "forma_u" if forma_u else ("spearman_debil" if spearman_debil else None)
    barras = d.valores_por_intervalo
    pasos = [
        PasoFormula(
            "intervalos", "1. Dividir en intervalos",
            r"Q_j=\operatorname{cuantil}_{j/m}(x),\quad j=1,\dots,m-1",
            r"Q=\left(" + ",\\ ".join(num(q) for q in d.limites_intervalos) + r"\right)",
            f"{n_int} intervalos con {', '.join(str(f) for f in d.filas_por_intervalo)} filas.",
            terminos=[
                Termino("m", "intervalos pedidos", str(cfg.intervalos_no_linealidad), ORIGEN_UMBRAL),
                Termino("Q_j", "límites (cuantiles de entrenamiento)", None, ORIGEN_DATASET),
            ],
            nota="Un valor igual a un límite va al intervalo inferior; los intervalos vacíos se descartan.",
        ),
        PasoFormula(
            "curva", "2. Curva del objetivo por intervalo",
            r"\bar y_j=\frac{1}{n_j}\sum_{i\in I_j} y_i",
            r"\bar y=\left(" + ",\\ ".join(num(v, 4) for v in barras) + r"\right)",
            f"{d.medida or 'media del objetivo'} en cada intervalo.",
            terminos=[Termino(r"\bar y_j", d.medida or "media del objetivo", None, ORIGEN_DATASET)],
        ),
        PasoFormula(
            "dependencia", "3. ¿Hay dependencia por intervalos?",
            r"p=P\!\left(\chi^2_{(m-1)(c-1)}\ge\sum\frac{(O-E)^2}{E}\right)\ \text{(o Kruskal–Wallis si el objetivo es continuo)}",
            rf"p={num(p)}\ {'<' if dependiente else _GE}\ \alpha={num(cfg.alfa_no_linealidad)}",
            "Hay dependencia." if dependiente else "No hay dependencia significativa.",
            cumple=dependiente,
            terminos=[
                Termino("p", "valor p de la tabla intervalos × objetivo", texto(p), ORIGEN_CALCULADO),
                Termino(r"\alpha", "significación", texto(cfg.alfa_no_linealidad), ORIGEN_UMBRAL),
            ],
        ),
        PasoFormula(
            "amplitud", "4. Amplitud de la curva",
            r"A=\frac{\max_j\bar y_j-\min_j\bar y_j}{s_y}\ \ge\ e_{\min}",
            rf"A={num(amp)}\ {_GE if (amp or 0) >= cfg.efecto_minimo_no_linealidad else '<'}\ e_{{\min}}={num(cfg.efecto_minimo_no_linealidad)}",
            "Efecto grande." if fuerte else "Efecto pequeño (o sin dependencia).",
            cumple=fuerte,
            terminos=[
                Termino("A", "amplitud en desviaciones estándar del objetivo", texto(amp), ORIGEN_CALCULADO),
                Termino(r"e_{\min}", "efecto mínimo", texto(cfg.efecto_minimo_no_linealidad), ORIGEN_UMBRAL),
            ],
            nota="El tamaño de efecto evita que, con miles de filas, ondulaciones pequeñas cuenten como no linealidad.",
        ),
        PasoFormula(
            "spearman", "5. Correlación de Spearman",
            r"\rho_s=\operatorname{corr}\big(\operatorname{rango}(x),\operatorname{rango}(y)\big)",
            rf"|\rho_s|={num(abs(rho))}\ {'<' if abs(rho) < cfg.spearman_debil else _GE}\ \rho_0={num(cfg.spearman_debil)}",
            "Correlación débil." if abs(rho) < cfg.spearman_debil else "Correlación apreciable.",
            cumple=abs(rho) < cfg.spearman_debil,
            terminos=[
                Termino(r"\rho_s", "Spearman con el objetivo", texto(rho), ORIGEN_CALCULADO),
                Termino(r"\rho_0", "umbral de correlación débil", texto(cfg.spearman_debil), ORIGEN_UMBRAL),
            ],
            nota="Asociación monótona, no causalidad.",
        ),
        PasoFormula(
            "veredicto", "6. Veredicto",
            r"\text{no monótona}\iff U\ \lor\ \big(p<\alpha\ \land\ A\ge e_{\min}\ \land\ |\rho_s|<\rho_0\big)",
            rf"U={'1' if forma_u else '0'}\ \lor\ \big({int(dependiente)}\land{int(fuerte)}\land{int(abs(rho) < cfg.spearman_debil)}\big)={int(no_monotona)}",
            "No monótona." if no_monotona else "Monótona.",
            cumple=no_monotona,
            terminos=[Termino("U", "la curva sube y baja (calculado al preparar la recomendación)", "sí" if forma_u else "no", ORIGEN_CALCULADO)],
            nota=(
                "U (forma de U) usa los grupos de filas de cada intervalo y no se recalcula al mover "
                "umbrales: se conserva el resultado original."
            ),
        ),
    ]
    resumen = (
        "No monótona (la curva sube y baja)." if forma_u
        else "No monótona (dependencia fuerte con Spearman débil)." if spearman_debil
        else "Monótona."
    )
    return VariableExplicada(d.nombre, d.tipo_final, True, no_monotona, criterio, resumen, pasos)


# --- Reglas de decisión ------------------------------------------------------------------------------------


def _reglas(
    rec: RecomendacionPrueba, no_monotonas: list[str], cfg: ConfiguracionValidacion
) -> tuple[list[ReglaDecision], str]:
    n_falt = len(rec.faltantes_restantes)
    prop = rec.proporcion_categoricas
    condiciones = [
        (
            "Faltantes", r"F>0", rf"F={n_falt}", n_falt > 0, MV_FISHERZ,
            "F = columnas con faltantes tras la preparación." + (
                f" Columnas: {', '.join(rec.faltantes_restantes)}." if n_falt else ""
            ),
        ),
        (
            "Mayoría de categóricas", r"c=\frac{\#\text{categóricas o binarias}}{\#\text{variables}}>c_{\max}",
            rf"c={num(prop)}\ {'>' if prop > cfg.proporcion_maxima_categoricas else _LE}\ c_{{\max}}={num(cfg.proporcion_maxima_categoricas)}",
            prop > cfg.proporcion_maxima_categoricas, CHISQ,
            "Las continuas se discretizan en cuantiles para chi-cuadrado.",
        ),
        (
            "Relaciones no monótonas", r"\exists\, x:\ \text{no monótona}(x)",
            rf"\#\text{{no monótonas}}={len(no_monotonas)}", bool(no_monotonas), CHISQ,
            f"Variables: {', '.join(no_monotonas)}." if no_monotonas else None,
        ),
        ("Ninguna anterior", r"\text{en otro caso}", r"\text{ninguna se cumplió}", True, FISHERZ, None),
    ]
    reglas, decidida = [], None
    for orden, (titulo, cond, sust, cumple, consecuencia, detalle) in enumerate(condiciones, 1):
        if cumple and decidida is None:
            estado, decidida = "decide", consecuencia
        else:
            estado = "sin_efecto" if cumple else "no_cumple"
        reglas.append(ReglaDecision(orden, titulo, cond, sust, cumple, estado, consecuencia, detalle))
    return reglas, decidida or FISHERZ


# --- Fórmulas de la prueba elegida ------------------------------------------------------------------------------


def _formulas_prueba(
    prueba: str, rec: RecomendacionPrueba, cfg: ConfiguracionValidacion, k: int
) -> list[PasoFormula]:
    n = rec.filas_train
    if prueba in (FISHERZ, MV_FISHERZ):
        gl = n - k - 3
        if gl <= 0:
            return [PasoFormula(
                "fisherz_umbral", "Umbral de Fisher-z",
                r"|z|=\tfrac12\ln\frac{1+r}{1-r}\sqrt{n-|S|-3}",
                rf"n-|S|-3={gl}\le 0",
                "No hay filas suficientes para ese conjunto de condicionamiento.", False,
            )]
        z_crit = float(stats.norm.ppf(1 - cfg.alfa_pc / 2))
        r_crit = math.tanh(z_crit / math.sqrt(gl))
        return [PasoFormula(
            "fisherz_umbral", "Umbral de Fisher-z",
            r"|z|=\tfrac12\ln\frac{1+r}{1-r}\sqrt{n-|S|-3}\ \ge\ z_{1-\alpha/2}"
            r"\ \Longrightarrow\ |r|\ge r_{\text{crít}}=\tanh\!\left(\frac{z_{1-\alpha/2}}{\sqrt{n-|S|-3}}\right)",
            rf"r_{{\text{{crít}}}}=\tanh\!\left(\frac{{{num(z_crit)}}}{{\sqrt{{{n}-{k}-3}}}}\right)={num(r_crit, 4)}",
            f"Con {k} variables de condicionamiento, PC conserva la dependencia solo si |r parcial| ≥ "
            f"{texto(r_crit, 3)}; si no, declara independencia y quita la arista.",
            terminos=[
                Termino("n", "filas de entrenamiento", str(n), ORIGEN_DATASET),
                Termino(r"|S|", "variables de condicionamiento", str(k), ORIGEN_UMBRAL),
                Termino(r"\alpha_{PC}", "significación de PC", texto(cfg.alfa_pc), ORIGEN_UMBRAL),
            ],
            nota="Supone relaciones lineales y datos aproximadamente normales."
            + (" mv_fisherz usa en cada prueba solo las filas completas." if prueba == MV_FISHERZ else ""),
        )]
    if prueba == CHISQ:
        niveles = cfg.intervalos_chisq
        gl = (niveles - 1) ** 2 * niveles ** k
        celdas = niveles ** (k + 2)
        return [PasoFormula(
            "chisq_gl", "Tamaño de la prueba chi-cuadrado",
            r"\mathrm{gl}=(L-1)^2L^{|S|},\qquad \text{filas por celda}\approx\frac{n}{L^{|S|+2}}",
            rf"\mathrm{{gl}}=({niveles}-1)^2\cdot{niveles}^{{{k}}}={gl},\qquad \frac{{{n}}}{{{niveles}^{{{k + 2}}}}}={num(n / celdas, 2)}",
            f"Con |S| = {k}: {gl} grados de libertad y ≈ {texto(n / celdas, 3)} filas por celda."
            + (" Muy pocas filas por celda: la prueba pierde potencia." if n / celdas < 5 else ""),
            cumple=n / celdas >= 5,
            terminos=[
                Termino("L", "intervalos por variable", str(niveles), ORIGEN_UMBRAL),
                Termino("n", "filas de entrenamiento", str(n), ORIGEN_DATASET),
                Termino(r"|S|", "variables de condicionamiento", str(k), ORIGEN_UMBRAL),
            ],
            nota="Crece exponencialmente con |S|: por eso la recomendación puede sugerir limitar max_k.",
        )]
    if prueba == KCI:
        return [PasoFormula(
            "kci", "KCI", r"\mathrm{HSIC}(X,Y\mid S)\ \text{con núcleos}", None,
            "Prueba basada en núcleos; sin fórmula cerrada simple para sustituir.",
        )]
    return []


# --- Entrada principal ---------------------------------------------------------------------------------------------


def explicar_seleccion_prueba(
    rec: RecomendacionPrueba, umbrales: dict[str, float] | None = None, k: int = 0
) -> TrazaSeleccionPrueba:
    """Traza de cómo se elige la prueba con la evidencia de ``rec`` y los ``umbrales`` indicados."""
    if k < 0:
        raise ValueError("k no puede ser negativo.")
    cfg = configuracion_con_umbrales(umbrales)
    base = ConfiguracionValidacion()
    variables = [_explicar_variable(d, cfg) for d in rec.diagnosticos]
    no_monotonas = [v.nombre for v in variables if v.no_monotona]
    reglas, prueba = _reglas(rec, no_monotonas, cfg)

    avisos = []
    if any(v.criterio == "forma_u" for v in variables) and umbrales:
        avisos.append(
            "El criterio de curva en U conserva su resultado original: no puede reevaluarse con "
            "otros umbrales sin volver a leer los datos."
        )
    cambia = prueba != rec.prueba
    entradas = [
        EntradaDecision("Columnas con faltantes", str(len(rec.faltantes_restantes)), True, "Regla 1."),
        EntradaDecision("Proporción de categóricas", texto(rec.proporcion_categoricas, 3) or "", True, "Regla 2."),
        EntradaDecision(
            "Variables no monótonas", ", ".join(no_monotonas) or "ninguna", True, "Regla 3.",
        ),
        EntradaDecision("Filas y variables", f"{rec.filas_train} × {rec.variables}", False,
                        "Solo se usan para las fórmulas de la prueba (y para KCI como alternativa)."),
        EntradaDecision("Tiempo estimado de PC",
                        texto(rec.tiempo_estimado_bootstrap_s) or "no estimado", False,
                        "No influye en qué prueba se elige; solo en la sugerencia de max_k."),
    ]
    resumen = (
        f"Con estos umbrales se elegiría {prueba} (la recomendación guardada es {rec.prueba})."
        if cambia else f"Se elige {prueba}."
    )
    editables = [
        Umbral(
            nombre, simbolo, descripcion, float(getattr(cfg, nombre)), float(getattr(base, nombre)),
            float(minimo), float(maximo), float(paso), entero,
        )
        for nombre, (simbolo, descripcion, minimo, maximo, paso, entero) in _UMBRALES.items()
    ]
    return TrazaSeleccionPrueba(
        prueba, rec.prueba, cambia, resumen, entradas, reglas, variables,
        _formulas_prueba(prueba, rec, cfg, k), editables, k, avisos,
    )

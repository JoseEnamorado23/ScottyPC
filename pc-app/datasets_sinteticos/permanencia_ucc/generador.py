"""Generador del dataset sintético de permanencia estudiantil (estudiantes universitarios colombianos).

Datos sintéticos generados con fines de validación y demostración. No representan estudiantes
reales de ninguna institución.

Uso:
    python generador.py                      # semilla 2026, n = 3000
    python generador.py --semilla 7 --n 5000

El modelo causal verdadero está definido aquí (COEF, ARISTAS y `simular`). Las salidas
(CSV, grafo, ecuaciones, efectos verdaderos) se derivan de esas mismas tablas, de modo que la
documentación nunca se desfasa del código.

`simular(ruido, intervenciones)` implementa el operador do: fija una variable a un valor y vuelve a
generar sus descendientes con el MISMO ruido, de modo que la comparación contrafactual es exacta.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson

CARPETA = Path(__file__).resolve().parent
SALIDAS = CARPETA / "salidas"

# ---------------------------------------------------------------------------------------------
# Coeficientes del modelo causal verdadero
# ---------------------------------------------------------------------------------------------
COEF: dict[str, float] = {
    # --- Nivel 0 ---
    "estrato_probs": [0.35, 0.35, 0.18, 0.07, 0.03, 0.02],
    "p_mujer": 0.52,
    "edad_min": 16.0, "edad_forma": 2.2, "edad_escala": 1.1,
    "pg_b0": 0.50, "pg_estrato": -0.44,
    "vive_b0": 1.60, "vive_edad": -0.30,
    "saber_b0": 232.0, "saber_estrato": 12.0, "saber_pg": -14.0, "saber_sd": 41.0,
    "trab_b0": -0.20, "trab_estrato": -0.30, "trab_edad": 0.22,
    "trab_mu": 2.60, "trab_mu_estrato": -0.10, "trab_mu_edad": 0.04, "trab_sd": 0.45, "trab_min": 4.0,
    # --- Nivel 1 ---
    "asist_b0": 1.50, "asist_trab": -0.022, "asist_mot": 0.40, "asist_sd": 0.55,
    "estud_b0": 1.85, "estud_trab": -0.010, "estud_mot": 0.28, "estud_pg": -0.20, "estud_sd": 0.45,
    "tut_b0": -0.15, "tut_pg": 0.30, "tut_mot": 0.18,
    "cred_b0": 16.2, "cred_trab": -0.07, "cred_sd": 2.2,
    "bien_b0": -1.70, "bien_pg": 0.75,
    "fin_b0": -0.55, "fin_estrato": -0.40, "fin_saber": 0.012,
    # --- Nivel 2 ---
    "prom_b0": 3.80, "prom_saber": 0.0085,
    "prom_asist": 1.80, "asist_escala": 30.0,
    "prom_estud": 0.30, "prom_tut": 0.05,
    "prom_cred": -0.012, "cred_optimo": 15.5,
    "prom_trab": -0.008, "prom_mot": 0.18, "prom_sd": 0.34,
    "rep_b0": -1.10, "rep_prom": -0.85, "rep_cred": 0.07,
    # --- Nivel 3 ---
    "perm_b0": 1.70, "perm_prom": 1.60, "perm_prom_bajo": -0.70,
    "perm_rep": -0.30, "perm_rep2": -0.04,
    "perm_fin": 0.55, "perm_bien": 0.40, "perm_estrato": 0.28,
    "perm_trab": -0.010, "perm_trab2": -0.0004, "perm_sd": 0.30,
}

# Faltantes
FALT = {"saber_mcar": 0.05, "trab_b0": -3.6, "trab_edad": 0.15, "trab_asist": -0.04}

# ---------------------------------------------------------------------------------------------
# Grafo verdadero: (origen, destino, signo, forma)
# ---------------------------------------------------------------------------------------------
ARISTAS: list[tuple[str, str, str, str]] = [
    ("estrato", "primera_generacion", "-", "logistica"),
    ("estrato", "puntaje_saber11", "+", "lineal"),
    ("primera_generacion", "puntaje_saber11", "-", "lineal"),
    ("estrato", "horas_trabajo_semana", "-", "logistica (trabaja o no) y lognormal (cuántas horas)"),
    ("edad_ingreso", "horas_trabajo_semana", "+", "logistica (trabaja o no) y lognormal (cuántas horas)"),
    ("edad_ingreso", "vive_con_familia", "-", "logistica"),
    ("horas_trabajo_semana", "asistencia_pct", "-", "saturante (sigmoide)"),
    ("horas_trabajo_semana", "horas_estudio_semana", "-", "lognormal"),
    ("primera_generacion", "horas_estudio_semana", "-", "lognormal"),
    ("primera_generacion", "tutorias_asistidas", "+", "poisson (log-lineal)"),
    ("horas_trabajo_semana", "creditos_matriculados", "-", "lineal"),
    ("primera_generacion", "apoyo_bienestar", "+", "logistica"),
    ("estrato", "apoyo_financiero", "-", "logistica"),
    ("puntaje_saber11", "apoyo_financiero", "+", "logistica"),
    ("puntaje_saber11", "promedio_semestre", "+", "lineal"),
    ("asistencia_pct", "promedio_semestre", "+", "saturante"),
    ("horas_estudio_semana", "promedio_semestre", "+", "rendimientos decrecientes (log)"),
    ("tutorias_asistidas", "promedio_semestre", "+", "lineal"),
    ("creditos_matriculados", "promedio_semestre", "+/-", "U invertida (óptimo ~15-16)"),
    ("horas_trabajo_semana", "promedio_semestre", "-", "lineal"),
    ("promedio_semestre", "materias_reprobadas", "-", "poisson (log-lineal), ruidoso"),
    ("creditos_matriculados", "materias_reprobadas", "+", "poisson (log-lineal)"),
    ("promedio_semestre", "permanece", "+", "logistica con quiebre (más pendiente bajo 3,0)"),
    ("materias_reprobadas", "permanece", "-", "logistica, cuadrática"),
    ("apoyo_financiero", "permanece", "+", "logistica"),
    ("apoyo_bienestar", "permanece", "+", "logistica"),
    ("estrato", "permanece", "+", "logistica, logarítmica (situación económica)"),
    ("horas_trabajo_semana", "permanece", "-", "logistica, cuadrática"),
]
ARISTAS_LATENTE: list[tuple[str, str, str, str]] = [
    ("motivacion", "asistencia_pct", "+", "sigmoide (entra al índice)"),
    ("motivacion", "horas_estudio_semana", "+", "lognormal"),
    ("motivacion", "tutorias_asistidas", "+", "poisson (log-lineal)"),
    ("motivacion", "promedio_semestre", "+", "lineal"),
]

NIVELES: dict[int, list[str]] = {
    0: ["estrato", "genero", "edad_ingreso", "primera_generacion", "vive_con_familia",
        "puntaje_saber11", "horas_trabajo_semana"],
    1: ["asistencia_pct", "horas_estudio_semana", "tutorias_asistidas", "creditos_matriculados",
        "apoyo_bienestar", "apoyo_financiero"],
    2: ["promedio_semestre", "materias_reprobadas"],
    3: ["permanece"],
}
COLUMNAS = [c for n in sorted(NIVELES) for c in NIVELES[n]]
MODIFICABLES = ["asistencia_pct", "horas_estudio_semana", "tutorias_asistidas", "creditos_matriculados",
                "apoyo_bienestar", "apoyo_financiero", "horas_trabajo_semana"]


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def _suave_prom(x):
    """Compresión suave cerca de 0 y 5 para que no haya acumulación en los límites."""
    x = np.asarray(x, dtype=float)
    alto = np.where(x > 4.3, 4.3 + 0.7 * np.tanh((x - 4.3) / 0.7), x)
    return np.where(alto < 0.8, 0.8 - 0.8 * np.tanh((0.8 - alto) / 0.8), alto)


# ---------------------------------------------------------------------------------------------
# Ruido exógeno (se genera UNA vez y se reutiliza en las intervenciones)
# ---------------------------------------------------------------------------------------------
def generar_ruido(n: int, semilla: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(semilla)
    c = COEF
    return {
        "u_estrato": rng.random(n), "u_genero": rng.random(n),
        "e_edad": rng.gamma(c["edad_forma"], c["edad_escala"], n),
        "u_pg": rng.random(n), "u_vive": rng.random(n), "e_saber": rng.normal(0, 1, n),
        "u_trab": rng.random(n), "z_trab": rng.normal(0, 1, n),
        "mot": rng.normal(0, 1, n),
        "e_asist": rng.normal(0, 1, n), "e_estud": rng.normal(0, 1, n), "u_tut": rng.random(n),
        "e_cred": rng.normal(0, 1, n), "u_bien": rng.random(n), "u_fin": rng.random(n),
        "e_prom": rng.normal(0, 1, n), "u_rep": rng.random(n),
        "e_perm": rng.normal(0, 1, n), "u_perm": rng.random(n),
    }


def simular(R: dict[str, np.ndarray], do: dict | None = None, base: dict | None = None) -> dict[str, np.ndarray]:
    """Evalúa las ecuaciones estructurales con el ruido R.

    do: {variable: función(valor_base) -> valor_nuevo}. La variable intervenida deja de depender de
    sus padres y todos sus descendientes se vuelven a calcular con el mismo ruido. `base` es el mundo
    sin intervenir (se calcula si no se pasa).
    """
    c = COEF
    do = do or {}
    if do and base is None:
        base = simular(R)

    def fija(nombre, valor):
        return do[nombre](base[nombre]) if nombre in do else valor

    n = len(R["mot"])
    d: dict[str, np.ndarray] = {}

    # ---- Nivel 0
    cortes = np.cumsum(c["estrato_probs"])[:-1]
    d["estrato"] = fija("estrato", 1 + np.searchsorted(cortes, R["u_estrato"]))
    d["genero"] = fija("genero", (R["u_genero"] < c["p_mujer"]).astype(int))
    d["edad_ingreso"] = fija("edad_ingreso", np.round(c["edad_min"] + R["e_edad"], 1).clip(16, 30))
    e, edad = d["estrato"], d["edad_ingreso"]
    d["primera_generacion"] = fija(
        "primera_generacion", (R["u_pg"] < sig(c["pg_b0"] + c["pg_estrato"] * (e - 1))).astype(int))
    d["vive_con_familia"] = fija(
        "vive_con_familia", (R["u_vive"] < sig(c["vive_b0"] + c["vive_edad"] * (edad - 18))).astype(int))
    pg = d["primera_generacion"]
    d["puntaje_saber11"] = fija(
        "puntaje_saber11",
        np.clip(np.round(c["saber_b0"] + c["saber_estrato"] * e + c["saber_pg"] * pg
                         + c["saber_sd"] * R["e_saber"]), 0, 500).astype(int))
    p_trab = sig(c["trab_b0"] + c["trab_estrato"] * (e - 2) + c["trab_edad"] * (edad - 18.4))
    horas = c["trab_min"] + np.exp(c["trab_mu"] + c["trab_mu_estrato"] * (e - 2)
                                   + c["trab_mu_edad"] * (edad - 18.4) + c["trab_sd"] * R["z_trab"])
    d["horas_trabajo_semana"] = fija(
        "horas_trabajo_semana",
        np.where(R["u_trab"] < p_trab, np.clip(np.round(horas), 0, 48), 0).astype(int))
    saber, ht = d["puntaje_saber11"], d["horas_trabajo_semana"]
    mot = R["mot"]

    # ---- Nivel 1
    z = c["asist_b0"] + c["asist_trab"] * ht + c["asist_mot"] * mot + c["asist_sd"] * R["e_asist"]
    d["asistencia_pct"] = fija("asistencia_pct", np.clip(np.round(30 + 70 * sig(z)), 30, 100).astype(int))
    lh = c["estud_b0"] + c["estud_trab"] * ht + c["estud_mot"] * mot + c["estud_pg"] * pg \
        + c["estud_sd"] * R["e_estud"]
    d["horas_estudio_semana"] = fija(
        "horas_estudio_semana", np.clip(np.round(2 * np.exp(lh)) / 2, 0, 30))
    lam = np.exp(c["tut_b0"] + c["tut_pg"] * pg + c["tut_mot"] * mot)
    d["tutorias_asistidas"] = fija(
        "tutorias_asistidas", np.clip(poisson.ppf(R["u_tut"], lam), 0, 8).astype(int))
    d["creditos_matriculados"] = fija(
        "creditos_matriculados",
        np.clip(np.round(c["cred_b0"] + c["cred_trab"] * ht + c["cred_sd"] * R["e_cred"]), 8, 22).astype(int))
    d["apoyo_bienestar"] = fija(
        "apoyo_bienestar", (R["u_bien"] < sig(c["bien_b0"] + c["bien_pg"] * pg)).astype(int))
    d["apoyo_financiero"] = fija(
        "apoyo_financiero",
        (R["u_fin"] < sig(c["fin_b0"] + c["fin_estrato"] * (e - 2) + c["fin_saber"] * (saber - 250))).astype(int))
    asist, est = d["asistencia_pct"], d["horas_estudio_semana"]
    tut, cred = d["tutorias_asistidas"], d["creditos_matriculados"]

    # ---- Nivel 2
    g = lambda a: 1 - np.exp(-(a - 30.0) / c["asist_escala"])
    prom_raw = (c["prom_b0"] + c["prom_saber"] * (saber - 250)
                + c["prom_asist"] * (g(asist) - g(85.0))
                + c["prom_estud"] * (np.log1p(est) - np.log1p(7.0))
                + c["prom_tut"] * (tut - 1)
                + c["prom_cred"] * (cred - c["cred_optimo"]) ** 2
                + c["prom_trab"] * ht + c["prom_mot"] * mot + c["prom_sd"] * R["e_prom"])
    d["promedio_semestre"] = fija(
        "promedio_semestre", np.clip(np.round(_suave_prom(prom_raw), 2), 0, 5))
    prom = d["promedio_semestre"]
    lam_r = np.exp(c["rep_b0"] + c["rep_prom"] * (prom - 3.5) + c["rep_cred"] * (cred - 15.5))
    d["materias_reprobadas"] = fija(
        "materias_reprobadas", np.clip(poisson.ppf(R["u_rep"], lam_r), 0, 6).astype(int))
    rep = d["materias_reprobadas"]

    # ---- Nivel 3
    logit = (c["perm_b0"] + c["perm_prom"] * (prom - 3.5) + c["perm_prom_bajo"] * np.maximum(0, 3.0 - prom)
             + c["perm_rep"] * rep + c["perm_rep2"] * rep ** 2
             + c["perm_fin"] * d["apoyo_financiero"] + c["perm_bien"] * d["apoyo_bienestar"]
             + c["perm_estrato"] * np.log(e) + c["perm_trab"] * ht + c["perm_trab2"] * ht ** 2
             + c["perm_sd"] * R["e_perm"])
    d["p_permanece"] = sig(logit)          # probabilidad estructural (no va en el CSV)
    d["permanece"] = fija("permanece", (R["u_perm"] < d["p_permanece"]).astype(int))
    d["motivacion"] = mot
    return d


def aplicar_faltantes(df: pd.DataFrame, semilla: int) -> pd.DataFrame:
    """Faltantes: saber11 MCAR 5 %; horas de trabajo ~3 % (MAR: depende de edad y asistencia, observadas)."""
    rng = np.random.default_rng(semilla + 1)
    df = df.copy()
    n = len(df)
    df["puntaje_saber11"] = df["puntaje_saber11"].astype("Int64")
    df["horas_trabajo_semana"] = df["horas_trabajo_semana"].astype("Int64")
    df.loc[rng.random(n) < FALT["saber_mcar"], "puntaje_saber11"] = pd.NA
    p = sig(FALT["trab_b0"] + FALT["trab_edad"] * (df["edad_ingreso"] - 18.4)
            + FALT["trab_asist"] * (df["asistencia_pct"] - 85))
    df.loc[rng.random(n) < p.values, "horas_trabajo_semana"] = pd.NA
    return df


def generar_dataset(n: int = 3000, semilla: int = 2026) -> tuple[pd.DataFrame, dict, dict]:
    """Devuelve (CSV con faltantes, mundo completo sin faltantes, ruido)."""
    R = generar_ruido(n, semilla)
    mundo = simular(R)
    df = pd.DataFrame({k: mundo[k] for k in COLUMNAS})
    return aplicar_faltantes(df, semilla), mundo, R


# ---------------------------------------------------------------------------------------------
# Efectos verdaderos (do-operator)
# ---------------------------------------------------------------------------------------------
INTERVENCIONES = {
    "asistencia_pct_mas_10_puntos": ("asistencia_pct", lambda a: np.minimum(a + 10, 100)),
    "horas_estudio_semana_mas_5_h": ("horas_estudio_semana", lambda h: np.minimum(h + 5, 30)),
    "tutorias_asistidas_mas_2": ("tutorias_asistidas", lambda t: np.minimum(t + 2, 8)),
    "creditos_matriculados_de_21_a_16": ("creditos_matriculados", lambda x: np.where(x >= 21, 16, x)),
    "creditos_matriculados_bajar_a_16_los_que_tienen_mas": ("creditos_matriculados", lambda x: np.minimum(x, 16)),
    "apoyo_bienestar_0_a_1": ("apoyo_bienestar", lambda x: np.ones_like(x)),
    "apoyo_financiero_0_a_1": ("apoyo_financiero", lambda x: np.ones_like(x)),
    "horas_trabajo_semana_menos_10_h": ("horas_trabajo_semana",
                                        lambda h: np.where(h > 0, np.maximum(h - 10, 0), 0)),
}


def efecto(R, base, nombre) -> dict:
    var, f = INTERVENCIONES[nombre]
    nuevo = simular(R, {var: f}, base)
    delta = nuevo["p_permanece"] - base["p_permanece"]
    cambia = nuevo[var] != base[var]
    riesgo = base["p_permanece"] < 0.5

    def media(mask):
        return float(delta[mask].mean()) if mask.sum() else None

    todos = np.ones_like(riesgo)
    return {
        "variable": var,
        "efecto_poblacion": media(todos),
        "efecto_subgrupo_riesgo": media(riesgo),
        "afectados_poblacion": int(cambia.sum()),
        "afectados_subgrupo_riesgo": int((cambia & riesgo).sum()),
        "efecto_en_afectados_poblacion": media(cambia),
        "efecto_en_afectados_subgrupo_riesgo": media(cambia & riesgo),
    }


def hash_modelo() -> str:
    """Huella de la versión del modelo: coeficientes, faltantes, aristas e intervenciones."""
    carga = {"COEF": COEF, "FALT": FALT, "ARISTAS": ARISTAS, "LATENTE": ARISTAS_LATENTE,
             "INTERVENCIONES": sorted(INTERVENCIONES)}
    return hashlib.sha256(json.dumps(carga, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def efectos_verdaderos(R, base, semilla: int | None = None) -> dict:
    riesgo = base["p_permanece"] < 0.5
    out = {
        "descripcion": ("Cambio medio en P(permanece) (puntos de probabilidad, 0.05 = +5 pp) al intervenir "
                        "con el operador do y regenerar los descendientes con el mismo ruido. "
                        "'subgrupo_riesgo' = estudiantes con P(permanece) < 0.5 en el mundo sin intervenir. "
                        "'efecto_en_afectados' promedia solo sobre quienes cambian de valor."),
        "hash_modelo": hash_modelo(),
        "semilla": semilla,
        "n": int(len(base["motivacion"])),
        "p_permanece_media": float(base["p_permanece"].mean()),
        "n_subgrupo_riesgo": int(riesgo.sum()),
        "efectos": {k: efecto(R, base, k) for k in INTERVENCIONES},
    }
    return out


# ---------------------------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------------------------
def escribir_grafos(salidas: Path):
    cols = ["origen", "destino", "signo", "forma"]
    pd.DataFrame(ARISTAS, columns=cols).to_csv(salidas / "grafo_verdadero.csv", index=False, encoding="utf-8")
    pd.DataFrame(ARISTAS + ARISTAS_LATENTE, columns=cols).to_csv(
        salidas / "grafo_verdadero_con_latente.csv", index=False, encoding="utf-8")


def dibujar_grafo(salidas: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    pos = {}
    x = {0: 0.0, 1: 4.2, 2: 8.2, 3: 11.2}
    for nivel, vars_ in NIVELES.items():
        k = len(vars_)
        ys = np.linspace(8, 0, k) if nivel != 3 else [4.0]
        if nivel == 2:
            ys = [5.6, 2.4]
        for v, y in zip(vars_, ys):
            pos[v] = (x[nivel], y)
    pos["motivacion"] = (2.1, -1.8)
    fig, ax = plt.subplots(figsize=(17, 10))
    ax.set_xlim(-2.4, 13.6); ax.set_ylim(-3.2, 9.6); ax.axis("off")
    titulos = {0: "Nivel 0: características al ingresar\n(no modificables)",
               1: "Nivel 1: comportamientos y apoyos\n(modificables)",
               2: "Nivel 2: resultados académicos", 3: "Nivel 3: objetivo"}
    for n_, t in titulos.items():
        ax.text(x[n_], 9.3, t, ha="center", va="center", fontsize=11, fontweight="bold")
    colores = {0: "#dbe7f5", 1: "#fde9c8", 2: "#e1f0d8", 3: "#f6d4d4"}
    cajas = {}
    for nivel, vars_ in NIVELES.items():
        for v in vars_:
            cajas[v] = ax.text(*pos[v], v, ha="center", va="center", fontsize=9, zorder=5,
                               bbox=dict(boxstyle="round,pad=0.35", fc=colores[nivel], ec="#444"))
    cajas["motivacion"] = ax.text(*pos["motivacion"], "motivacion (latente, no observada)", ha="center",
                                  va="center", fontsize=9, zorder=5,
                                  bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#444", ls="--"))
    fig.canvas.draw()
    for o, dst, s, _ in ARISTAS + ARISTAS_LATENTE:
        lat = o == "motivacion"
        mismo = (o in NIVELES[0] and dst in NIVELES[0])
        a = FancyArrowPatch(pos[o], pos[dst], arrowstyle="-|>", mutation_scale=12, shrinkA=2, shrinkB=2, patchA=cajas[o].get_bbox_patch(), patchB=cajas[dst].get_bbox_patch(),
                            lw=1.0, color="#c0392b" if s == "-" else ("#7f8c8d" if s == "+/-" else "#2c6e49"),
                            ls="--" if lat else "-", alpha=0.75,
                            connectionstyle="arc3,rad=0.28" if mismo else "arc3,rad=0.06", zorder=1)
        ax.add_patch(a)
    ax.text(-2.3, -3.0, "Verde: efecto positivo   Rojo: efecto negativo   Gris: U invertida   "
            "Punteado: variable latente", fontsize=9)
    fig.tight_layout()
    fig.savefig(salidas / "grafo_verdadero.png", dpi=130)
    plt.close(fig)


def escribir_ecuaciones(salidas: Path, n: int, semilla: int):
    c = COEF
    pr = c["estrato_probs"]
    texto = f"""# Ecuaciones estructurales del generador (verdad conocida)

> Datos sintéticos generados con fines de validación y demostración. No representan estudiantes reales de ninguna institución.

Generado con `generador.py` (n = {n}, semilla = {semilla}). Cada variable se calcula a partir de sus padres más un ruido
propio e independiente. `σ(x) = 1/(1+e^-x)`. «Bernoulli(p)» significa que la variable vale 1 con probabilidad p (se
sortea con un uniforme propio). `ε ~ N(0,1)` es un ruido normal estándar distinto en cada ecuación.
`motivacion ~ N(0,1)` es la variable **latente**: afecta a varias variables y **no** está en el CSV.

## Nivel 0 — características al ingresar (no modificables)

- **estrato**: categórica con probabilidades {pr[0]:.2f}, {pr[1]:.2f}, {pr[2]:.2f}, {pr[3]:.2f}, {pr[4]:.2f}, {pr[5]:.2f} para los estratos 1 a 6. Sin padres.
- **genero**: Bernoulli({c['p_mujer']}) (1 = mujer). Sin padres y **sin efecto sobre nada**: variable de control para falsos positivos.
- **edad_ingreso**: {c['edad_min']:.0f} + Gamma(forma={c['edad_forma']}, escala={c['edad_escala']}), redondeada a 0,1 y limitada a 16–30. Sesgada a 17–19. Sin padres.
- **primera_generacion** ~ Bernoulli(σ({c['pg_b0']} {c['pg_estrato']:+}·(estrato−1))). A mayor estrato, menos probable ser primera generación.
- **vive_con_familia** ~ Bernoulli(σ({c['vive_b0']} {c['vive_edad']:+}·(edad_ingreso−18))). **Sin efecto sobre el objetivo**: control.
- **puntaje_saber11** = redondeo({c['saber_b0']:.0f} {c['saber_estrato']:+.0f}·estrato {c['saber_pg']:+.0f}·primera_generacion + {c['saber_sd']:.0f}·ε), limitado a 0–500. Ruido normal.
- **horas_trabajo_semana**: primero «¿trabaja?» ~ Bernoulli(σ({c['trab_b0']} {c['trab_estrato']:+}·(estrato−2) {c['trab_edad']:+}·(edad_ingreso−18,4))).
  Si trabaja: horas = redondeo({c['trab_min']:.0f} + exp({c['trab_mu']} {c['trab_mu_estrato']:+}·(estrato−2) {c['trab_mu_edad']:+}·(edad_ingreso−18,4) + {c['trab_sd']}·ε)), tope 48. Si no, 0. Ruido lognormal.

## Variable latente (no va en el CSV)

- **motivacion** ~ N(0, 1). Es un confusor no observado a propósito: afecta a asistencia, horas de estudio, tutorías y promedio.

## Nivel 1 — comportamientos y apoyos del semestre (modificables)

- **asistencia_pct** = redondeo(30 + 70·σ(z)), con z = {c['asist_b0']} {c['asist_trab']:+}·horas_trabajo {c['asist_mot']:+}·motivacion + {c['asist_sd']}·ε. Forma sigmoide: rango 30–100 sin cortes bruscos. Ruido normal en el índice.
- **horas_estudio_semana** = redondeo a 0,5 de exp({c['estud_b0']} {c['estud_trab']:+}·horas_trabajo {c['estud_mot']:+}·motivacion {c['estud_pg']:+}·primera_generacion + {c['estud_sd']}·ε), tope 30. Ruido lognormal.
- **tutorias_asistidas** ~ Poisson(λ), λ = exp({c['tut_b0']} {c['tut_pg']:+}·primera_generacion {c['tut_mot']:+}·motivacion), tope 8. Efectos pequeños.
- **creditos_matriculados** = redondeo({c['cred_b0']} {c['cred_trab']:+}·horas_trabajo + {c['cred_sd']}·ε), limitado a 8–22. Ruido normal.
- **apoyo_bienestar** ~ Bernoulli(σ({c['bien_b0']} {c['bien_pg']:+}·primera_generacion)).
- **apoyo_financiero** ~ Bernoulli(σ({c['fin_b0']} {c['fin_estrato']:+}·(estrato−2) {c['fin_saber']:+}·(puntaje_saber11−250))).

## Nivel 2 — resultados académicos

- **promedio_semestre** = suavizado(bruto), con
  bruto = {c['prom_b0']} {c['prom_saber']:+}·(saber11−250) {c['prom_asist']:+}·[g(asistencia)−g(85)] {c['prom_estud']:+}·[ln(1+horas_estudio)−ln(8)] {c['prom_tut']:+}·(tutorias−1) {c['prom_cred']:+}·(creditos−{c['cred_optimo']})² {c['prom_trab']:+}·horas_trabajo {c['prom_mot']:+}·motivacion + {c['prom_sd']}·ε.
  - `g(a) = 1 − exp(−(a−30)/{c['asist_escala']:.0f})`: **saturante**, sube rápido con asistencia baja y casi nada por encima de ~85 %.
  - `ln(1+horas_estudio)`: **rendimientos decrecientes**.
  - `(creditos−{c['cred_optimo']})²` con coeficiente negativo: **U invertida**, óptimo ≈ 15–16 créditos.
  - «suavizado» comprime con tanh por encima de 4,3 y por debajo de 0,8, para que no se acumulen notas en 0 ni en 5. Se redondea a 2 decimales (rango 0–5).
- **materias_reprobadas** ~ Poisson(λ), λ = exp({c['rep_b0']} {c['rep_prom']:+}·(promedio−3,5) {c['rep_cred']:+}·(creditos−15,5)), tope 6. Es un conteo ruidoso, no una función determinista del promedio.

## Nivel 3 — objetivo

- **permanece** ~ Bernoulli(σ(η)), con
  η = {c['perm_b0']} {c['perm_prom']:+}·(promedio−3,5) {c['perm_prom_bajo']:+}·máx(0, 3,0−promedio) {c['perm_rep']:+}·reprobadas {c['perm_rep2']:+}·reprobadas² {c['perm_fin']:+}·apoyo_financiero {c['perm_bien']:+}·apoyo_bienestar {c['perm_estrato']:+}·ln(estrato) {c['perm_trab']:+}·horas_trabajo {c['perm_trab2']:+}·horas_trabajo² + {c['perm_sd']}·ε.
  Términos no lineales: quiebre en el promedio (más pendiente bajo 3,0), reprobadas y horas de trabajo cuadráticas, estrato logarítmico, más un ruido normal en el logit. No hay umbral exacto.

## Faltantes (se aplican después de generar, solo en el CSV)

- **puntaje_saber11**: {FALT['saber_mcar']:.0%} al azar (MCAR).
- **horas_trabajo_semana**: ≈3 %, con probabilidad σ({FALT['trab_b0']} {FALT['trab_edad']:+}·(edad_ingreso−18,4) {FALT['trab_asist']:+}·(asistencia_pct−85)).
  Es **MAR**: depende de columnas observadas (edad y asistencia), que son las que se asocian con trabajar muchas horas; no depende del propio valor faltante.
- Ninguna otra columna tiene faltantes.

## Efectos verdaderos

Ver `efectos_verdaderos.json`: se calculan con el operador do sobre estas mismas ecuaciones (mismo ruido, descendientes regenerados), sin faltantes.
"""
    (salidas / "ecuaciones.md").write_text(texto, encoding="utf-8")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--semilla", type=int, default=2026)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--salida", type=Path, default=SALIDAS)
    a = ap.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)

    df, mundo, R = generar_dataset(a.n, a.semilla)
    df.to_csv(a.salida / "permanencia_ucc.csv", index=False, encoding="utf-8")
    escribir_grafos(a.salida)
    dibujar_grafo(a.salida)
    escribir_ecuaciones(a.salida, a.n, a.semilla)
    ef = efectos_verdaderos(R, mundo, a.semilla)
    (a.salida / "efectos_verdaderos.json").write_text(
        json.dumps(ef, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CSV: {len(df)} filas x {df.shape[1]} columnas -> {a.salida / 'permanencia_ucc.csv'}")
    print(f"Permanencia: {df['permanece'].mean():.1%}")
    return df, mundo, R, ef


if __name__ == "__main__":
    main()

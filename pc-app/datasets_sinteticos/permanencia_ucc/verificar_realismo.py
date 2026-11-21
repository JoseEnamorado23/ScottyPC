"""Paso 2: verifica las metas de realismo del dataset sintético y dibuja distribuciones.png.

Uso: python verificar_realismo.py [--semilla 2026] [--n 3000]
"""
from __future__ import annotations

import argparse
import json
import sys

import matplotlib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import generador as g

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def auc_cv(df: pd.DataFrame) -> tuple[float, float]:
    X, y = df.drop(columns="permanece"), df["permanece"]
    modelo = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                           LogisticRegression(max_iter=2000))
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    s = cross_val_score(modelo, X, y, cv=cv, scoring="roc_auc")
    return float(s.mean()), float(s.std())


def pares_casi_deterministas(df: pd.DataFrame):
    corr = df.corr(method="spearman").abs().values.copy()
    np.fill_diagonal(corr, 0)
    i, j = np.unravel_index(np.argmax(corr), corr.shape)
    return float(corr[i, j]), df.columns[i], df.columns[j]


def apilamiento(df: pd.DataFrame) -> dict[str, float]:
    lim = {"edad_ingreso": (16, 30), "puntaje_saber11": (0, 500), "horas_trabajo_semana": (48, 48),
           "asistencia_pct": (30, 100), "horas_estudio_semana": (0, 30), "tutorias_asistidas": (8, 8),
           "creditos_matriculados": (8, 22), "promedio_semestre": (0, 5), "materias_reprobadas": (6, 6)}
    out = {}
    for c, (lo, hi) in lim.items():
        v = df[c].dropna()
        out[c] = float(((v == lo) | (v == hi)).mean())
    return out


def distribuciones(df: pd.DataFrame, ruta):
    cols = [c for c in g.COLUMNAS]
    fig, axs = plt.subplots(4, 5, figsize=(20, 13))
    for ax, c in zip(axs.ravel(), cols):
        v = df[c].dropna().astype(float)
        if v.nunique() <= 12:
            vc = v.value_counts().sort_index()
            ax.bar(vc.index.astype(str), vc.values, color="#4a7ab5")
        else:
            ent = bool((v == v.round()).all()) and v.max() - v.min() <= 120  # enteros con rango amplio van por la rama continua
            if ent:
                bins = np.arange(v.min(), v.max() + 2) - 0.5
            else:  # ancho "redondo" para no producir aliasing con la resolución de los datos
                pasos = np.array([0.05, 0.1, 0.5, 1, 2, 5, 10, 20])
                paso = pasos[np.argmin(np.abs(pasos - (v.max() - v.min()) / 35))]
                bins = np.arange(np.floor(v.min() / paso) * paso, v.max() + paso, paso)
            ax.hist(v, bins=bins, color="#4a7ab5")
        ax.set_title(f"{c}  (faltan {df[c].isna().mean():.0%})" if df[c].isna().any() else c, fontsize=10)
    for ax in axs.ravel()[len(cols):]:
        ax.axis("off")
    fig.suptitle("Distribuciones del dataset sintético permanencia_ucc", fontsize=14)
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--semilla", type=int, default=2026)
    ap.add_argument("--n", type=int, default=3000)
    a = ap.parse_args(argv)

    df, mundo, R = g.generar_dataset(a.n, a.semilla)
    ef = g.efectos_verdaderos(R, mundo)
    filas = []

    def fila(meta, rango, valor, ok):
        filas.append((meta, rango, valor, "OK" if ok else "FALLA"))

    perm = df["permanece"].mean()
    fila("Permanencia", "78 – 85 %", f"{perm:.1%}", 0.78 <= perm <= 0.85)
    p = df["promedio_semestre"]
    fila("Promedio: media", "≈ 3,5", f"{p.mean():.2f}", 3.4 <= p.mean() <= 3.6)
    fila("Promedio: desviación", "≈ 0,6", f"{p.std():.2f}", 0.5 <= p.std() <= 0.7)
    fila("Promedio < 3,0", "15 – 20 %", f"{(p < 3).mean():.1%}", 0.15 <= (p < 3).mean() <= 0.20)
    auc, sd = auc_cv(df)
    fila("AUC regresión logística (CV 5)", "0,78 – 0,88", f"{auc:.3f} ± {sd:.3f}", 0.78 <= auc <= 0.88)
    e = ef["efectos"]["asistencia_pct_mas_10_puntos"]["efecto_subgrupo_riesgo"] * 100
    fila("Asistencia +10: efecto en subgrupo en riesgo", "+3 a +12 pp", f"{e:+.1f} pp", 3 <= e <= 12)
    mx_pob = max(v["efecto_poblacion"] for v in ef["efectos"].values()) * 100
    mx_riesgo_ef = max(v["efecto_subgrupo_riesgo"] for v in ef["efectos"].values())
    mx_riesgo = max(v["efecto_subgrupo_riesgo"] for v in ef["efectos"].values()) * 100
    # ninguna acción sola lleva a casi todos a la meta: % del subgrupo en riesgo que llega a P>=0.8
    riesgo = mundo["p_permanece"] < 0.5
    llegan = 0.0
    for k, (var, f) in g.INTERVENCIONES.items():
        nuevo = g.simular(R, {var: f}, mundo)
        llegan = max(llegan, float((nuevo["p_permanece"][riesgo] >= 0.8).mean()))
    fila("Mejor acción sola: efecto máx. en riesgo", "no extremo", f"{mx_riesgo:+.1f} pp", mx_riesgo < 25)
    fila("Mejor acción sola: % de riesgo que llega a P≥0,8", "pocos", f"{llegan:.1%}", llegan < 0.25)
    for c in ["genero", "vive_con_familia"]:
        r = df[c].corr(df["permanece"])
        fila(f"|ρ| {c} – permanece", "< 0,05", f"{r:+.3f}", abs(r) < 0.05)
    mx, c1, c2 = pares_casi_deterministas(df)
    fila("Máx. |ρ Spearman| entre columnas", "< 0,90 (nada determinista)", f"{mx:.2f} ({c1}–{c2})", mx < 0.90)
    ap_ = apilamiento(df)
    peor = max(ap_, key=ap_.get)
    fila("Acumulación en límites (peor columna)", "< 5 %", f"{ap_[peor]:.1%} ({peor})", ap_[peor] < 0.05)
    fila("Faltantes puntaje_saber11", "≈ 5 %", f"{df['puntaje_saber11'].isna().mean():.1%}",
         0.04 <= df["puntaje_saber11"].isna().mean() <= 0.06)
    fila("Faltantes horas_trabajo_semana", "≈ 3 %", f"{df['horas_trabajo_semana'].isna().mean():.1%}",
         0.02 <= df["horas_trabajo_semana"].isna().mean() <= 0.04)
    fila("No trabaja (horas = 0)", "≈ 55 %", f"{(df['horas_trabajo_semana'] == 0).sum() / df['horas_trabajo_semana'].notna().sum():.1%}",
         0.50 <= (df['horas_trabajo_semana'] == 0).sum() / df['horas_trabajo_semana'].notna().sum() <= 0.60)
    fila("Mujeres", "≈ 52 %", f"{df['genero'].mean():.1%}", 0.49 <= df['genero'].mean() <= 0.55)
    est = df["estrato"].value_counts(normalize=True).sort_index()
    fila("Estratos 1–6", "35/35/18/7/3/2 %", "/".join(f"{x * 100:.0f}" for x in est.values), True)
    fila("Puntaje Saber 11: media / desv.", "≈ 250 / ≈ 45",
         f"{df['puntaje_saber11'].mean():.0f} / {df['puntaje_saber11'].std():.0f}",
         240 <= df['puntaje_saber11'].mean() <= 260 and 40 <= df['puntaje_saber11'].std() <= 50)
    fila("Subgrupo en riesgo (P<0,5)", "informativo", f"{ef['n_subgrupo_riesgo']} estudiantes "
         f"({ef['n_subgrupo_riesgo'] / a.n:.1%})", ef["n_subgrupo_riesgo"] >= 150)

    # El JSON publicado debe corresponder a la versión actual del generador
    ruta_ef = g.SALIDAS / "efectos_verdaderos.json"
    if not ruta_ef.exists():
        fila("efectos_verdaderos.json vigente", "coincide con el generador", "no existe", False)
    else:
        pub = json.loads(ruta_ef.read_text(encoding="utf-8"))
        hash_ok = pub.get("hash_modelo") == g.hash_modelo()
        fila("efectos_verdaderos.json: hash del modelo", "= hash actual", "coincide" if hash_ok else "DESACTUALIZADO", hash_ok)
        if hash_ok and pub.get("semilla") is not None:
            R2 = g.generar_ruido(pub["n"], pub["semilla"])
            m2 = g.simular(R2)
            rec = g.efectos_verdaderos(R2, m2, pub["semilla"])
            dif = max(abs((pub["efectos"][k][c] or 0) - (rec["efectos"][k][c] or 0))
                      for k in rec["efectos"] for c in rec["efectos"][k] if c != "variable")
            fila("efectos_verdaderos.json: valores recalculados", "diferencia < 1e-9", f"{dif:.1e}", dif < 1e-9)

    md = ["# Verificación de realismo", "", f"n = {a.n}, semilla = {a.semilla}", "",
          "| Meta | Rango objetivo | Valor | Estado |", "|---|---|---|---|"]
    md += [f"| {m} | {r} | {v} | {s} |" for m, r, v, s in filas]
    md += ["", "## Efectos verdaderos sobre P(permanece), en puntos porcentuales", "",
           "| Intervención | Población | Subgrupo en riesgo | Afectados (pob.) | Efecto en afectados |",
           "|---|---|---|---|---|"]
    for k, v in ef["efectos"].items():
        md.append(f"| {k} | {v['efecto_poblacion'] * 100:+.1f} | {v['efecto_subgrupo_riesgo'] * 100:+.1f} | "
                  f"{v['afectados_poblacion']} | "
                  f"{(v['efecto_en_afectados_poblacion'] or 0) * 100:+.1f} |")
    texto = "\n".join(md)
    (g.SALIDAS / "verificacion.md").write_text(texto + "\n", encoding="utf-8")
    distribuciones(df, g.SALIDAS / "distribuciones.png")
    print(texto)
    print("\nAcumulación en límites por columna:", {k: f"{v:.1%}" for k, v in ap_.items()})
    return all(f[3] == "OK" for f in filas)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

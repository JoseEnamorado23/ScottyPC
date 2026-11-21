"""Paso 5: compara una corrida de Scotty PC con la verdad conocida del dataset sintético.

Uso:
    python comparar_con_verdad.py CARPETA_EXPORT_PC [--dataset CSV] [--umbral 0.6] [--salida comparacion.md]

CARPETA_EXPORT_PC debe tener aristas.csv y resultado.json (y, si hay, prescripciones.csv).
Solo lee: no modifica ni importa la app ni el núcleo.

Qué mide
  1. Esqueleto (ignora dirección): precisión, exhaustividad (recall) y F1.
  2. Orientación: de las aristas verdaderas encontradas, cuántas quedaron en el sentido correcto.
  3. SHD (distancia de Hamming estructural): aristas faltantes + sobrantes + mal orientadas
     (una arista sin orientar donde la verdad está orientada cuenta como 1).
  4. Faltantes / sobrantes / invertidas, marcando las que explica la variable latente `motivacion`
     (o un camino verdadero indirecto).
  5. Variables de control (genero, vive_con_familia): no deberían tocar al objetivo.
  6. Prescripciones (si hay prescripciones.csv): se aplican en el generador verdadero con el
     operador do y se compara la P(permanece) prometida con la verdadera.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import generador as g

OBJETIVO = "permanece"
CONTROLES = ["genero", "vive_con_familia"]
HIJOS_LATENTE = sorted({d for _, d, _, _ in g.ARISTAS_LATENTE})

# valores válidos de cada variable intervenible: (mínimo, máximo, paso)
VALIDOS = {
    "asistencia_pct": (30, 100, 1), "horas_estudio_semana": (0, 30, 0.5), "tutorias_asistidas": (0, 8, 1),
    "creditos_matriculados": (8, 22, 1), "apoyo_bienestar": (0, 1, 1), "apoyo_financiero": (0, 1, 1),
    "horas_trabajo_semana": (0, 48, 1),
}


# ---------------------------------------------------------------------------------------------
# Grafo
# ---------------------------------------------------------------------------------------------
def aristas_verdaderas() -> set[tuple[str, str]]:
    return {(o, d) for o, d, _, _ in g.ARISTAS}


def caminos_verdaderos(dirigidas: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Cierre transitivo del grafo verdadero (¿hay camino dirigido a→b?)."""
    alcanza = set(dirigidas)
    cambio = True
    while cambio:
        cambio = False
        for (a, b), (c, d) in itertools.product(list(alcanza), repeat=2):
            if b == c and (a, d) not in alcanza:
                alcanza.add((a, d))
                cambio = True
    return alcanza


def leer_aristas_pc(carpeta: Path, umbral: float | None):
    """Devuelve (dirigidas, sin_orientar, filas) con pares ordenados / frozensets."""
    a = pd.read_csv(carpeta / "aristas.csv")
    if umbral is not None:
        a = a[a["frecuencia_total"] >= umbral]
    dirigidas, sin = set(), set()
    for r in a.itertuples():
        if str(r.tipo) == "sin_orientar":
            sin.add(frozenset((r.origen, r.destino)))
        else:  # "dirigida" y "manual"
            dirigidas.add((r.origen, r.destino))
    return dirigidas, sin, a


def comparar_grafo(pc_dir: set, pc_sin: set) -> dict:
    ver = aristas_verdaderas()
    ver_esq = {frozenset(e) for e in ver}
    pc_esq = {frozenset(e) for e in pc_dir} | pc_sin
    tp = ver_esq & pc_esq
    faltan = ver_esq - pc_esq
    sobran = pc_esq - ver_esq
    prec = len(tp) / len(pc_esq) if pc_esq else 0.0
    rec = len(tp) / len(ver_esq) if ver_esq else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    correctas, invertidas, sin_orientar = [], [], []
    for par in tp:
        a, b = sorted(par)
        v = (a, b) if (a, b) in ver else (b, a)
        if par in pc_sin:
            sin_orientar.append(v)
        elif v in pc_dir:
            correctas.append(v)
        else:
            invertidas.append(v)
    orientadas = len(correctas) + len(invertidas)
    acc = len(correctas) / orientadas if orientadas else float("nan")
    shd = len(faltan) + len(sobran) + len(invertidas) + len(sin_orientar)
    return {"ver_esq": ver_esq, "pc_esq": pc_esq, "tp": tp, "faltan": faltan, "sobran": sobran,
            "precision": prec, "recall": rec, "f1": f1, "correctas": correctas, "invertidas": invertidas,
            "sin_orientar": sin_orientar, "acc_orientacion": acc, "shd": shd}


def explicacion_latente(par: frozenset) -> str | None:
    if par <= set(HIJOS_LATENTE):
        return "explicada por la variable latente `motivacion` (ambas son hijas suyas)"
    return None


def explicacion_sobrante(par: frozenset, caminos: set) -> str:
    e = explicacion_latente(par)
    if e:
        return e
    a, b = sorted(par)
    if (a, b) in caminos or (b, a) in caminos:
        return "indirecta: hay un camino causal verdadero entre las dos (efecto mediado)"
    return "sin explicación estructural (posible falso positivo)"


# ---------------------------------------------------------------------------------------------
# Prescripciones
# ---------------------------------------------------------------------------------------------
def _num(x) -> float | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).strip().replace(",", ".")
    pct = s.endswith("%")
    s = s.rstrip("%").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return v / 100 if pct else v


def redondear_valido(var: str, valor: float) -> float:
    lo, hi, paso = VALIDOS[var]
    return float(np.clip(np.round(valor / paso) * paso, lo, hi))


def _indices_originales(dataset: Path | None, n: int) -> dict | None:
    """Si el usuario entrenó con otro CSV (p. ej. un train), mapea su fila i a la fila del original."""
    if dataset is None:
        return None
    orig = pd.read_csv(g.SALIDAS / "permanencia_ucc.csv")
    otro = pd.read_csv(dataset)
    clave = lambda df: df[g.COLUMNAS].astype(str).agg("|".join, axis=1)
    pos = {k: i for i, k in enumerate(clave(orig))}
    return {i: pos.get(k) for i, k in enumerate(clave(otro))}


def evaluar_prescripciones(ruta: Path, n: int, semilla: int, dataset: Path | None) -> dict | None:
    p = pd.read_csv(ruta)
    if p.empty:
        return None
    R = g.generar_ruido(n, semilla)
    base = g.simular(R)
    mapa = _indices_originales(dataset, n)
    columnas = {c[:-6]: c for c in p.columns if c.endswith(" antes") and c[:-6] in g.COLUMNAS}
    filas, ignoradas = [], []
    for _, r in p.iterrows():
        idx = int(r["caso"])
        if mapa is not None:
            idx = mapa.get(idx)
        if idx is None or not 0 <= idx < n:
            ignoradas.append(r["caso"])
            continue
        acciones = {}
        for var, col in columnas.items():
            a, d_ = _num(r[col]), _num(r.get(f"{var} despues"))
            if d_ is not None and a is not None and d_ != a:
                acciones[var] = d_
        sub = lambda dic: {k: (np.asarray(v)[[idx]] if np.ndim(v) else v) for k, v in dic.items()}
        Ri, bi = sub(R), sub(base)

        def p_verdadera(vals):
            if not vals:
                return float(bi["p_permanece"][0])
            do = {v: (lambda b, x=x: np.full_like(b, x, dtype=float)) for v, x in vals.items()}
            return float(g.simular(Ri, do, bi)["p_permanece"][0])

        crudas = {v: float(np.clip(x, VALIDOS[v][0], VALIDOS[v][1])) for v, x in acciones.items() if v in VALIDOS}
        redond = {v: redondear_valido(v, x) for v, x in crudas.items()}
        invalidas = [v for v, x in acciones.items() if v in VALIDOS and abs(redondear_valido(v, x) - x) > 1e-9]
        filas.append({
            "caso": int(r["caso"]), "fila": idx, "acciones": acciones, "valores_no_validos": invalidas,
            "no_modificables": [v for v in acciones if v not in VALIDOS],
            "antes_modelo": _num(r.get("antes")), "prometida": _num(r.get("despues")),
            "deseado": _num(r.get("deseado")), "dice_alcanzado": str(r.get("alcanzado")).lower() in ("true", "sí", "si", "1"),
            "antes_verdadera": p_verdadera({}), "verdadera": p_verdadera(crudas),
            "verdadera_redondeada": p_verdadera(redond),
        })
    if not filas:
        return {"n": 0, "ignoradas": ignoradas}
    df = pd.DataFrame(filas)
    con = df.dropna(subset=["prometida"])
    meta = df["deseado"].dropna()
    out = {"n": len(df), "ignoradas": ignoradas, "tabla": df, "con_valores_no_validos": int((df["valores_no_validos"].str.len() > 0).sum())}
    if len(con):
        out["error_medio"] = float((con["prometida"] - con["verdadera"]).mean())
        out["error_abs_medio"] = float((con["prometida"] - con["verdadera"]).abs().mean())
        out["error_medio_redondeada"] = float((con["prometida"] - con["verdadera_redondeada"]).mean())
        out["error_abs_medio_redondeada"] = float((con["prometida"] - con["verdadera_redondeada"]).abs().mean())
    if len(meta):
        m = df["deseado"].fillna(meta.iloc[0])
        out["meta"] = float(m.iloc[0])
        out["pct_promete_meta"] = float((df["prometida"] >= m).mean())
        out["pct_llega_verdadera"] = float((df["verdadera"] >= m).mean())
        out["pct_llega_redondeada"] = float((df["verdadera_redondeada"] >= m).mean())
    out["mejora_prometida"] = float((df["prometida"] - df["antes_modelo"]).mean()) if df["antes_modelo"].notna().any() else None
    out["mejora_verdadera"] = float((df["verdadera"] - df["antes_verdadera"]).mean())
    return out


# ---------------------------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------------------------
def _arista(v):
    return f"{v[0]} → {v[1]}"


def _par(p):
    a, b = sorted(p)
    return f"{a} — {b}"


def construir_informe(carpeta: Path, umbral, dataset: Path | None) -> tuple[str, dict]:
    ef = json.loads((g.SALIDAS / "efectos_verdaderos.json").read_text(encoding="utf-8"))
    pc_dir, pc_sin, filas = leer_aristas_pc(carpeta, umbral)
    r = comparar_grafo(pc_dir, pc_sin)
    caminos = caminos_verdaderos(aristas_verdaderas())
    md = [f"# Comparación de Scotty PC con la verdad (`{carpeta.name}`)", ""]
    if ef.get("hash_modelo") != g.hash_modelo():
        md += ["> ⚠️ `efectos_verdaderos.json` no corresponde a la versión actual del generador.", ""]
    md += ["## 1. Esqueleto (sin dirección)", "",
           "| Métrica | Valor |", "|---|---|",
           f"| Aristas verdaderas | {len(r['ver_esq'])} |",
           f"| Aristas encontradas por PC | {len(r['pc_esq'])} |",
           f"| Acertadas | {len(r['tp'])} |",
           f"| Precisión | {r['precision']:.2f} |",
           f"| Exhaustividad (recall) | {r['recall']:.2f} |",
           f"| F1 | {r['f1']:.2f} |", "",
           "## 2. Orientación y SHD", "",
           "| Métrica | Valor |", "|---|---|",
           f"| Orientadas correctamente | {len(r['correctas'])} |",
           f"| Invertidas | {len(r['invertidas'])} |",
           f"| Encontradas sin orientar | {len(r['sin_orientar'])} |",
           f"| Exactitud de orientación (sobre las orientadas) | "
           + ("—" if np.isnan(r["acc_orientacion"]) else f"{r['acc_orientacion']:.2f}") + " |",
           f"| **SHD** (faltantes + sobrantes + invertidas + sin orientar) | **{r['shd']}** |", ""]

    md += ["## 3. Diferencias", ""]
    md += [f"### Faltantes ({len(r['faltan'])})", ""]
    md += [f"- {_par(p)}" for p in sorted(r["faltan"], key=_par)] or ["- ninguna"]
    md += ["", f"### Sobrantes ({len(r['sobran'])})", ""]
    md += [f"- {_par(p)} — {explicacion_sobrante(p, caminos)}" for p in sorted(r["sobran"], key=_par)] or ["- ninguna"]
    md += ["", f"### Invertidas ({len(r['invertidas'])})", ""]
    md += [f"- PC dice {v[1]} → {v[0]}; la verdad es {_arista(v)}" + (f" — {e}" if (e := explicacion_latente(frozenset(v))) else "")
           for v in sorted(r["invertidas"])] or ["- ninguna"]
    if r["sin_orientar"]:
        md += ["", f"### Encontradas sin orientar ({len(r['sin_orientar'])})", ""]
        md += [f"- {_par(frozenset(v))} (verdad: {_arista(v)})" for v in sorted(r["sin_orientar"])]

    md += ["", "## 4. Variables de control", "",
           "No deben afectar a `permanece` (son ruido por construcción).", "",
           "| Variable | Aristas con cualquier variable | ¿Conectada al objetivo? |", "|---|---|---|"]
    controles_mal = 0
    for c in CONTROLES:
        vec = sorted({next(iter(p - {c})) for p in r["pc_esq"] if c in p})
        con_obj = OBJETIVO in vec
        controles_mal += con_obj
        verdad = sorted({next(iter(frozenset(e) - {c})) for e in aristas_verdaderas() if c in e})
        md.append(f"| {c} | {', '.join(vec) or '—'} (verdad: {', '.join(verdad) or '—'}) | "
                  + ("**SÍ — falso positivo**" if con_obj else "no") + " |")

    pres = carpeta / "prescripciones.csv"
    res = None
    md += ["", "## 5. Prescripciones", ""]
    if not pres.exists():
        md += ["No hay `prescripciones.csv` en la carpeta; se omite esta sección."]
    else:
        res = evaluar_prescripciones(pres, ef["n"], ef["semilla"], dataset)
        if not res or res["n"] == 0:
            md += ["`prescripciones.csv` no tiene casos evaluables" + (f" (casos ignorados: {res['ignoradas']})" if res else "") + "."]
        else:
            md += [f"Se evaluaron {res['n']} casos aplicando las acciones en el generador verdadero (operador do, "
                   "mismo ruido de cada estudiante). `caso` se interpreta como fila (desde 0) de "
                   "`permanencia_ucc.csv`" + ("" if dataset is None else f" (mapeada desde `{dataset.name}`)") + ".", ""]
            if res["ignoradas"]:
                md += [f"Casos sin correspondencia (ignorados): {res['ignoradas']}", ""]
            md += ["| Métrica | Valor |", "|---|---|"]
            if "error_medio" in res:
                md += [f"| Error medio (prometida − verdadera), valores tal como los propone el optimizador | {res['error_medio'] * 100:+.1f} pp |",
                       f"| Error absoluto medio | {res['error_abs_medio'] * 100:.1f} pp |",
                       f"| Error medio con valores redondeados a estados válidos | {res['error_medio_redondeada'] * 100:+.1f} pp |",
                       f"| Error absoluto medio con valores redondeados | {res['error_abs_medio_redondeada'] * 100:.1f} pp |"]
            if res.get("mejora_prometida") is not None:
                md += [f"| Mejora media prometida (después − antes) | {res['mejora_prometida'] * 100:+.1f} pp |"]
            md += [f"| Mejora media verdadera | {res['mejora_verdadera'] * 100:+.1f} pp |"]
            if "meta" in res:
                md += [f"| Meta | P ≥ {res['meta']:.2f} |",
                       f"| % que el modelo promete llevar a la meta | {res['pct_promete_meta']:.0%} |",
                       f"| % que realmente llega (valores tal cual) | {res['pct_llega_verdadera']:.0%} |",
                       f"| % que realmente llega (valores redondeados) | {res['pct_llega_redondeada']:.0%} |"]
            md += [f"| Casos con valores fuera de los estados válidos (p. ej. 2,4 tutorías) | {res['con_valores_no_validos']} de {res['n']} |", ""]
            nm = sum(1 for x in res["tabla"]["no_modificables"] if x)
            if nm:
                md += [f"Casos con acciones sobre variables que no son del modelo verdadero: {nm}.", ""]
            # sesgo por tipo de acción
            md += ["Peores 5 casos (mayor sobrepromesa):", "",
                   "| caso | acciones | prometida | verdadera | redondeada |", "|---|---|---|---|---|"]
            t = res["tabla"].assign(sobre=lambda d: d["prometida"] - d["verdadera"]).sort_values("sobre", ascending=False).head(5)
            for x in t.itertuples():
                acc = "; ".join(f"{k}→{v:g}" for k, v in x.acciones.items())
                md.append(f"| {x.caso} | {acc} | {x.prometida:.2f} | {x.verdadera:.2f} | {x.verdadera_redondeada:.2f} |")

    resumen = {"f1": r["f1"], "shd": r["shd"], "controles_conectados": controles_mal, "prescripciones": res}
    return "\n".join(md) + "\n", resumen


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", type=Path, help="carpeta exportada por Scotty PC (aristas.csv, resultado.json, ...)")
    ap.add_argument("--dataset", type=Path, help="CSV con el que se corrió PC si no es permanencia_ucc.csv completo")
    ap.add_argument("--umbral", type=float, help="frecuencia mínima para contar una arista (por defecto, todas las del archivo)")
    ap.add_argument("--salida", type=Path, help="dónde escribir comparacion.md (por defecto, dentro de la carpeta)")
    a = ap.parse_args(argv)
    for f in ("aristas.csv", "resultado.json"):
        if not (a.carpeta / f).exists():
            sys.exit(f"Falta {f} en {a.carpeta}")
    texto, resumen = construir_informe(a.carpeta, a.umbral, a.dataset)
    salida = a.salida or (a.carpeta / "comparacion.md")
    salida.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"(escrito en {salida})")
    return resumen


if __name__ == "__main__":
    main()

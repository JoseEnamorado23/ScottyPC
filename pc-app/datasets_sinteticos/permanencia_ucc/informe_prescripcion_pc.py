"""Informe completo de una exportación de PC + su lote de prescripciones contra la verdad de permanencia_ucc.

Extiende ``comparar_con_verdad.py`` con:
  1. métricas del grafo (y si coincide con otra versión, p. ej. v3 del experimento);
  2. prometida vs verdadera (operador do con el ruido de cada estudiante), error medio/absoluto, % que de verdad llega a la meta;
  3. el mismo resultado separado por tipo de acción (tutorías/horas de estudio vs. el resto, y con asistencia);
  4. planes que bajan créditos a quien tiene 14 o menos;
  5. casos «no alcanzables»: si en la verdad tampoco lo eran con las mismas restricciones (búsqueda exhaustiva
     sobre la rejilla permitida, con las restricciones de ``controles.json`` del artefacto o, si no, las de la guía del README).

Uso: python informe_prescripcion_pc.py CARPETA_PC PRESCRIPCIONES.csv [--artefacto X.scotty] [--comparar-con CARPETA_V3] [--salida DIR]
``CARPETA_PC`` necesita aristas.csv y resultado.json (la carpeta ``pc/versiones/N`` del proyecto sirve).
"""
from __future__ import annotations

import argparse
import itertools
import json
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comparar_con_verdad as cv
import generador as g

OBJ = "permanece"
# Guía del README por si no hay artefacto: (dirección, cambio máx., mínimo, máximo, paso)
GUIA = {
    "asistencia_pct": ("subir", 20, None, 100, 1), "horas_estudio_semana": ("subir", 8, None, 30, 0.5),
    "tutorias_asistidas": ("subir", 4, 0, 7, 1), "creditos_matriculados": ("bajar", 6, 14, 22, 1),
    "apoyo_bienestar": ("subir", None, 0, 1, 1), "apoyo_financiero": ("subir", None, 0, 1, 1),
    "horas_trabajo_semana": ("bajar", 10, 0, 48, 1),
}


def restricciones(artefacto: Path | None) -> dict:
    """{variable: (dirección, cambio_máx, mínimo, máximo, paso, valores_permitidos|None)}"""
    if artefacto is None:
        return {v: (*x, None) for v, x in GUIA.items()}
    with zipfile.ZipFile(artefacto) as z:
        controles = json.loads(z.read("controles.json"))["controles"]
    out = {}
    for c in controles:
        if not c.get("permitida", True):
            continue
        vp = [x["valor"] for x in c["valores_permitidos"]] if c.get("valores_permitidos") else None
        v = c["variable"]
        lo, hi, _ = cv.VALIDOS[v]  # sin límite explícito (p. ej. binarias) vale el rango válido de la variable
        out[v] = (c["direccion"], c["cambio_maximo"], lo if c["minimo"] is None else c["minimo"],
                  hi if c["maximo"] is None else c["maximo"], c["paso"] or 1, vp)
    return out


def candidatos(x: float, regla: tuple) -> np.ndarray:
    """Valores a los que puede pasar una variable desde ``x`` (incluye quedarse en ``x``)."""
    direccion, cambio, minimo, maximo, paso, valores = regla
    lo = x - cambio if direccion == "bajar" and cambio is not None else (minimo if minimo is not None else -np.inf)
    hi = x + cambio if direccion == "subir" and cambio is not None else (maximo if maximo is not None else np.inf)
    if direccion == "bajar":
        lo, hi = max(lo, minimo if minimo is not None else -np.inf), x
    elif direccion == "subir":
        lo, hi = x, min(hi, maximo if maximo is not None else np.inf)
    if valores is not None:
        cand = [v for v in valores if lo - 1e-9 <= v <= hi + 1e-9]
    else:
        k = np.arange(0, int(round((hi - lo) / paso)) + 1)
        cand = list(x + (k * paso if direccion == "subir" else -k * paso)) if direccion in ("subir", "bajar") else [x]
        cand = [v for v in cand if lo - 1e-9 <= v <= hi + 1e-9]
    return np.unique(np.round(np.array(cand + [x], dtype=float), 6))


def valor_dataset(v: str, x: float) -> float:
    """Valor que el estudiante tiene en el CSV: la simulación sin redondear, llevada al paso de la variable."""
    paso = cv.VALIDOS[v][2]
    return float(round(float(x) / paso) * paso)


def mejor_verdadera(idx: int, R: dict, base: dict, reglas: dict) -> tuple[float, dict]:
    """Máxima P verdadera alcanzable desde el estudiante ``idx`` con las restricciones (exhaustivo).

    Solo se interviene (do) en las variables que CAMBIAN: una variable que se deja como está sigue respondiendo
    a sus padres (p. ej. los créditos reaccionan a las horas de trabajo), igual que en ``comparar_con_verdad``.
    Se simula cada subconjunto de variables cambiadas por separado.
    """
    variables = list(reglas)
    x0 = {v: valor_dataset(v, base[v][idx]) for v in variables}
    cands = {v: candidatos(x0[v], reglas[v]) for v in variables}
    cambios = {v: cands[v][np.abs(cands[v] - x0[v]) > 1e-9] for v in variables}
    mejor, plan = -1.0, {}
    for k in range(len(variables) + 1):
        for sub in itertools.combinations(variables, k):
            if any(len(cambios[v]) == 0 for v in sub):
                continue
            if not sub:  # sin intervenir
                if float(base["p_permanece"][idx]) > mejor:
                    mejor, plan = float(base["p_permanece"][idx]), {}
                continue
            malla = np.array(list(itertools.product(*[cambios[v] for v in sub])), dtype=float).reshape(-1, len(sub))
            N = len(malla)
            Ri = {k_: np.repeat(np.asarray(v)[[idx]], N) if np.ndim(v) else v for k_, v in R.items()}
            bi = {k_: np.repeat(np.asarray(v)[[idx]], N) if np.ndim(v) else v for k_, v in base.items()}
            do = {v: (lambda b, col=malla[:, j]: col) for j, v in enumerate(sub)}
            p = g.simular(Ri, do, bi)["p_permanece"] if sub else bi["p_permanece"]
            m = int(np.argmax(p))
            if p[m] > mejor:
                mejor, plan = float(p[m]), {v: float(malla[m, j]) for j, v in enumerate(sub)}
    return mejor, plan


def pp(x: float) -> str:
    return f"{x * 100:+.1f} pp"


def resumen_grupo(t: pd.DataFrame, meta: float) -> dict:
    if not len(t):
        return {"n": 0}
    return {"n": len(t), "error_medio": (t.prometida - t.verdadera).mean(), "error_abs": (t.prometida - t.verdadera).abs().mean(),
            "error_medio_red": (t.prometida - t.verdadera_redondeada).mean(),
            "promete_meta": (t.prometida >= meta).mean(), "llega_meta": (t.verdadera >= meta).mean(),
            "llega_meta_red": (t.verdadera_redondeada >= meta).mean(),
            "mejora_prometida": (t.prometida - t.antes_modelo).mean(), "mejora_verdadera": (t.verdadera - t.antes_verdadera).mean()}


def fila_tabla(nombre: str, s: dict) -> str:
    if not s["n"]:
        return f"| {nombre} | 0 | — | — | — | — | — |"
    return (f"| {nombre} | {s['n']} | {pp(s['error_medio'])} | {s['error_abs'] * 100:.1f} pp | {s['promete_meta']:.0%} | "
            f"{s['llega_meta']:.0%} | {s['llega_meta_red']:.0%} |")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("prescripciones", type=Path)
    ap.add_argument("--artefacto", type=Path)
    ap.add_argument("--comparar-con", type=Path, help="carpeta (con aristas.csv) cuyo grafo debe coincidir")
    ap.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    for f in ("aristas.csv", "resultado.json"):
        shutil.copyfile(a.carpeta / f, a.salida / f)
    shutil.copyfile(a.prescripciones, a.salida / "prescripciones.csv")

    texto, resumen = cv.construir_informe(a.salida, None, None)
    (a.salida / "comparacion.md").write_text(texto, encoding="utf-8")
    res = resumen["prescripciones"]
    t: pd.DataFrame = res["tabla"]
    meta = res["meta"]
    ef = json.loads((g.SALIDAS / "efectos_verdaderos.json").read_text(encoding="utf-8"))
    p = pd.read_csv(a.prescripciones).set_index("caso")
    t = t.assign(
        dice_alcanzado=[str(p.loc[c, "alcanzado"]).lower() == "true" for c in t.caso],
        ya_cumple=[str(p.loc[c, "ya_cumple"]).lower() == "true" for c in t.caso])

    md = [f"# Informe de prescripción de PC contra la verdad (`{a.carpeta.parent.parent.name if a.carpeta.parent.name == 'versiones' else a.carpeta.name}`)", ""]
    # 1. Grafo
    dirigidas, sin, _ = cv.leer_aristas_pc(a.salida, None)
    m = cv.comparar_grafo(dirigidas, sin)
    md += ["## 1. Grafo", "",
           "| Métrica | Valor |", "|---|---|",
           f"| Aristas encontradas (verdad: {len(m['ver_esq'])}) | {len(m['pc_esq'])} |",
           f"| Precisión / recall / F1 | {m['precision']:.2f} / {m['recall']:.2f} / {m['f1']:.2f} |",
           f"| Orientadas bien / invertidas / sin orientar | {len(m['correctas'])} / {len(m['invertidas'])} / {len(m['sin_orientar'])} |",
           f"| SHD | {m['shd']} |",
           f"| Aristas falsas | {len(m['sobran'])}: " + ("; ".join(f"{cv._par(x)} ({cv.explicacion_sobrante(x, cv.caminos_verdaderos(cv.aristas_verdaderas()))})" for x in sorted(m['sobran'], key=cv._par)) or "ninguna") + " |"]
    if a.comparar_con:
        d2, s2, _ = cv.leer_aristas_pc(a.comparar_con, None)
        igual = d2 == dirigidas and s2 == sin
        md += [f"| ¿Mismo grafo que `{a.comparar_con.name}`? | {'**sí, aristas y orientaciones idénticas**' if igual else '**NO**: ' + str(sorted((d2 ^ dirigidas) | {tuple(x) for x in (s2 ^ sin)}))} |"]
    _, _, filas_pc = cv.leer_aristas_pc(a.salida, None)
    manuales = filas_pc[filas_pc.tipo.astype(str) == "manual"]
    if len(manuales):
        md += ["", "Orientaciones manuales aplicadas en la app (el esqueleto y las 100 corridas son las mismas; solo cambia la orientación): "
               + "; ".join(f"{r.origen} → {r.destino}" for r in manuales.itertuples()) + "."]
    md += [""]

    # 2. Prometida vs verdadera
    n = res["n"]
    md += ["## 2. Prometida frente a verdadera", "",
           f"{n} planes del lote (de {len(p)} filas), evaluados en el generador con el do-operator y el ruido de cada estudiante. Meta: P ≥ {meta:.2f}.", "",
           "| Métrica | Valor |", "|---|---|",
           f"| Error medio (prometida − verdadera) | {pp(res['error_medio'])} |",
           f"| Error absoluto medio | {res['error_abs_medio'] * 100:.1f} pp |",
           f"| Error medio / absoluto con valores redondeados | {pp(res['error_medio_redondeada'])} / {res['error_abs_medio_redondeada'] * 100:.1f} pp |",
           f"| Mejora media prometida / verdadera | {pp(res['mejora_prometida'])} / {pp(res['mejora_verdadera'])} |",
           f"| % de planes que el modelo promete llevar a {meta:.2f} | {res['pct_promete_meta']:.0%} |",
           f"| **% de planes que DE VERDAD alcanzan {meta:.2f}** | **{res['pct_llega_verdadera']:.0%}** ({int(round(res['pct_llega_verdadera'] * n))} de {n}) |",
           f"| % que alcanza con valores redondeados | {res['pct_llega_redondeada']:.0%} |",
           f"| Planes con valores fuera de los estados válidos | {res['con_valores_no_validos']} de {n} |",
           f"| Casos sin correspondencia (ignorados) | {len(res['ignoradas'])} |", ""]
    alc = t[t.dice_alcanzado]
    noalc = t[~t.dice_alcanzado]
    md += [f"Planes que el modelo da por alcanzados: {len(alc)}; no alcanzables: {len(noalc)}. "
           f"Entre los alcanzados, de verdad llegan a la meta {(alc.verdadera >= meta).mean():.0%}.", ""]

    # 3. Por tipo de acción
    usa = lambda d, vs: d.acciones.apply(lambda ac: any(v in ac for v in vs))  # noqa: E731
    est = usa(t, ["tutorias_asistidas", "horas_estudio_semana"])
    asist = usa(t, ["asistencia_pct"])
    solo_est = est & ~asist
    cabecera = ["| Grupo | Planes | Error medio | Error abs. | Promete meta | Llega (tal cual) | Llega (redondeada) |", "|---|---|---|---|---|---|---|"]
    md += ["## 3. Por tipo de acción", "",
           "Las aristas falsas de v3 son todas hacia `asistencia_pct` (con `horas_estudio_semana`, `tutorias_asistidas` y `edad_ingreso`), "
           "por eso se separan los planes que usan tutorías u horas de estudio.", ""] + cabecera
    for nombre, mask in (("Usan tutorías u horas de estudio", est), ("No las usan", ~est),
                         ("  · usan además asistencia_pct", est & asist), ("  · tutorías/horas sin asistencia", solo_est),
                         ("Usan asistencia_pct (con o sin lo anterior)", asist), ("Todos", est | ~est)):
        md.append(fila_tabla(nombre, resumen_grupo(t[mask], meta)))
    md += [""]
    cuenta = {v: int(usa(t, [v]).sum()) for v in cv.VALIDOS}
    md += ["Planes que tocan cada variable: " + ", ".join(f"`{v}` {c}" for v, c in cuenta.items() if c) + ".", ""]

    # 4. Créditos
    reglas = restricciones(a.artefacto)
    cre_bajan = t[t.acciones.apply(lambda ac: "creditos_matriculados" in ac)]
    malos = []
    for r in cre_bajan.itertuples():
        antes = p.loc[r.caso, "creditos_matriculados antes"]
        despues = r.acciones["creditos_matriculados"]
        if antes <= 14 or despues < 14 - 1e-9:
            malos.append((r.caso, antes, despues))
    md += ["## 4. Créditos", "",
           f"Planes que cambian `creditos_matriculados`: {len(cre_bajan)}. Planes que bajan créditos a alguien con 14 o menos, "
           f"o que dejan menos de 14: **{len(malos)}**" + (f" → {malos}" if malos else " (esperado: 0).") , ""]

    # 5. No alcanzables
    md += ["## 5. Casos «no alcanzables» frente a la verdad", ""]
    if not len(noalc):
        md += ["Ningún caso fue declarado no alcanzable."]
    else:
        R = g.generar_ruido(ef["n"], ef["semilla"])
        base = g.simular(R)
        distintos = sum(1 for c in p.columns if c.endswith(" antes") and c[:-6] in cv.VALIDOS for caso, v in p[c].dropna().items()
                        if abs(valor_dataset(c[:-6], base[c[:-6]][int(caso)]) - v) > 1e-9)
        md += [f"Comprobación: el valor «antes» de {distintos} acciones del CSV difiere del valor del estudiante en el generador (esperado: 0).", ""]
        fuente = "controles.json del artefacto" if a.artefacto else "la guía del README"
        md += [f"Para cada uno de los {len(noalc)} casos se buscó, de forma exhaustiva sobre la rejilla permitida (restricciones de {fuente}), "
               "la mayor P verdadera posible con el ruido de ese estudiante.", "",
               "| caso | P antes (verdad) | P prometida | P verdadera de su plan | **mejor P verdadera posible** | ¿alcanzable en la verdad? | mejor plan |", "|---|---|---|---|---|---|---|"]
        alcanzables = 0
        for r in noalc.itertuples():
            mejor, plan = mejor_verdadera(r.fila, R, base, reglas)
            ok = mejor >= meta - 1e-9
            alcanzables += ok
            cambios = "; ".join(f"{v} {valor_dataset(v, base[v][r.fila]):g}→{x:g}" for v, x in plan.items()) or "—"
            if mejor < r.verdadera - 1e-9:
                raise SystemExit(f"caso {r.caso}: la mejor P ({mejor:.3f}) es menor que la de su propio plan ({r.verdadera:.3f}); revisar la rejilla")
            md.append(f"| {r.caso} | {r.antes_verdadera:.2f} | {r.prometida:.2f} | {r.verdadera:.2f} | {mejor:.2f} | {'**sí**' if ok else 'no'} | {cambios} |")
        md += ["", f"**{len(noalc) - alcanzables} de {len(noalc)}** no eran alcanzables tampoco en la verdad con las mismas restricciones; "
               f"**{alcanzables}** sí lo eran (el modelo no los encontró)."]
    texto = "\n".join(md) + "\n"
    (a.salida / "informe_prescripcion.md").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())

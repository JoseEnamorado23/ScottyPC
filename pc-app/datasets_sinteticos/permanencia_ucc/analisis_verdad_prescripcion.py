"""Análisis de prescripciones de permanencia_ucc contra la VERDAD (generador, operador do con el ruido de cada estudiante).

No modifica el núcleo; usa el proyecto de la app (solo lectura) para reproducir el modelo, la configuración y los casos.

Subcomandos:
  revision  ¿``requiere_revision`` predice el fracaso real? (usa el prescripciones.csv del lote; ligero)
  margen    vuelve a prescribir los mismos casos con deseado 0,85 y 0,90 (mismas restricciones y μ) y evalúa en la verdad
  metodos   plan de cada método del comparador (prescriptor, sin causalidad, imitar exitosos, aleatoria, sin intervención)
            para los mismos casos, evaluado en la verdad; con una versión a igual costo que el prescriptor

Uso: python analisis_verdad_prescripcion.py {revision|margen|metodos} --proyecto CARPETA --prescripciones prescripciones.csv
         [--n N] [--salida DIR]
``--n`` limita a los N primeros casos (para medir tiempos).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comparar_con_verdad as cv
import generador as g

META = 0.80


# --- La verdad ------------------------------------------------------------------------------------------


class Verdad:
    """P verdadera de permanecer para un estudiante (fila del CSV) con unas acciones, vía do-operator."""

    def __init__(self) -> None:
        ef = json.loads((g.SALIDAS / "efectos_verdaderos.json").read_text(encoding="utf-8"))
        self.R = g.generar_ruido(ef["n"], ef["semilla"])
        self.base = g.simular(self.R)
        self._cache: dict[int, tuple[dict, dict]] = {}

    def _sub(self, idx: int):
        if idx not in self._cache:
            sub = lambda d: {k: (np.asarray(v)[[idx]] if np.ndim(v) else v) for k, v in d.items()}  # noqa: E731
            self._cache[idx] = (sub(self.R), sub(self.base))
        return self._cache[idx]

    def antes(self, idx: int) -> float:
        return float(self._sub(idx)[1]["p_permanece"][0])

    def p(self, idx: int, acciones: dict[str, float]) -> float:
        validas = {v: float(np.clip(x, cv.VALIDOS[v][0], cv.VALIDOS[v][1])) for v, x in acciones.items() if v in cv.VALIDOS}
        if not validas:
            return self.antes(idx)
        Ri, bi = self._sub(idx)
        do = {v: (lambda b, x=x: np.full_like(b, x, dtype=float)) for v, x in validas.items()}
        return float(g.simular(Ri, do, bi)["p_permanece"][0])


# --- Proyecto de la app ---------------------------------------------------------------------------------


def cargar_proyecto(carpeta: Path):
    from pcapp_nucleo.carga import cargar_dataset
    from pcapp_nucleo.causal import modelo_desde_diccionario
    from pcapp_nucleo.preparacion import aplicar_receta, receta_desde_diccionario
    from pcapp_nucleo.prescripcion import completar, configuracion_desde_diccionario, referencia_desde_diccionario
    from pcapp_nucleo.prescripcion.lotes import que_no_cumplen

    leer = lambda n: json.loads((carpeta / n).read_text(encoding="utf-8"))  # noqa: E731
    df = cargar_dataset(carpeta / "original.csv")
    receta = receta_desde_diccionario(leer("receta.json"))
    datos = aplicar_receta(df, receta)
    presc = leer("prescripcion/prescripcion.json")
    modelo = modelo_desde_diccionario(leer("modelo_causal/modelo_causal.json"), datos.train)
    config = completar(modelo, configuracion_desde_diccionario(presc["configuracion"]))
    mu = float(presc["calibracion"]["mu"])
    referencia = referencia_desde_diccionario(presc["referencia"])
    filas = que_no_cumplen(modelo, datos.test.drop(columns=[modelo.objetivo], errors="ignore"), config)
    return modelo, datos, config, mu, referencia, filas


def numero(x) -> float | None:
    return cv._num(x)


def pp(x: float) -> str:
    return f"{x * 100:+.1f} pp"


# --- 1. ¿requiere_revision predice el fracaso real? ------------------------------------------------------


def cmd_revision(a) -> str:
    res = cv.evaluar_prescripciones(a.prescripciones, *_n_y_semilla(), None)
    t: pd.DataFrame = res["tabla"]
    p = pd.read_csv(a.prescripciones).set_index("caso")
    t = t.assign(marca=[str(p.loc[c, "requiere_revision"]).lower() == "true" for c in t.caso],
                 alcanzado_modelo=[str(p.loc[c, "alcanzado"]).lower() == "true" for c in t.caso])
    t["llega"] = t.verdadera >= META
    t["fracasa"] = ~t.llega
    md = ["## ¿`requiere_revision` predice el fracaso real?", "",
          f"{len(t)} planes. «Llega» = P verdadera ≥ {META:.2f} (operador do con el ruido de cada estudiante).", "",
          "| Grupo | Planes | % que de verdad llega | P verdadera media | Error medio (prometida − verdadera) | Error abs. |", "|---|---|---|---|---|---|"]
    for nombre, m in (("Con la marca `requiere_revision`", t.marca), ("Sin la marca", ~t.marca), ("Todos", t.marca | ~t.marca)):
        x = t[m]
        if not len(x):
            md.append(f"| {nombre} | 0 | — | — | — | — |")
            continue
        md.append(f"| {nombre} | {len(x)} | {x.llega.mean():.0%} ({int(x.llega.sum())}/{len(x)}) | {x.verdadera.mean():.2f} | "
                  f"{pp((x.prometida - x.verdadera).mean())} | {(x.prometida - x.verdadera).abs().mean() * 100:.1f} pp |")
    tp = int((t.marca & t.fracasa).sum())
    precision = tp / t.marca.sum() if t.marca.sum() else float("nan")
    recall = tp / t.fracasa.sum() if t.fracasa.sum() else float("nan")
    md += ["", f"Como detector del fracaso real: precisión {precision:.0%} (de los marcados, fracasan {tp} de {int(t.marca.sum())}), "
               f"exhaustividad {recall:.0%} (de los {int(t.fracasa.sum())} que fracasan, la marca detecta {tp}). "
               f"Tasa base de fracaso: {t.fracasa.mean():.0%}.", ""]
    # Solo entre los que el modelo da por alcanzados (los no alcanzables ya van marcados como fallidos)
    x = t[t.alcanzado_modelo]
    md += [f"Solo entre los {len(x)} planes que el modelo da por alcanzados: con marca {int(x.marca.sum())} "
           f"(llegan {x[x.marca].llega.mean():.0%}" + (")" if x.marca.sum() else " — sin casos)") +
           f", sin marca {int((~x.marca).sum())} (llegan {x[~x.marca].llega.mean():.0%})."]
    return "\n".join(md) + "\n"


def _n_y_semilla():
    ef = json.loads((g.SALIDAS / "efectos_verdaderos.json").read_text(encoding="utf-8"))
    return ef["n"], ef["semilla"]


# --- Acciones de un resultado/solución en valores originales ----------------------------------------------


def acciones_de_resultado(r: dict) -> dict[str, float]:
    out = {}
    for ac in r["acciones"]:
        d = numero(ac["despues"])
        if d is not None:
            out[ac["variable"]] = d
    return out


# --- 2. Margen de seguridad -----------------------------------------------------------------------------


def cmd_margen(a) -> str:
    from pcapp_nucleo.prescripcion import ObjetivoDeseado, prescribir_lote

    modelo, datos, config, mu, referencia, filas = cargar_proyecto(a.proyecto)
    if a.n:
        filas = filas.iloc[: a.n]
    V = Verdad()
    filas_md = []
    por_caso = {}
    for deseado in a.deseados:
        c = replace(config, objetivo=ObjetivoDeseado(config.objetivo.direccion, deseado, config.objetivo.clase_positiva))
        t0 = time.time()
        resultados = prescribir_lote(modelo, filas, c, mu, referencia)
        seg = time.time() - t0
        verd, antes, costos, nacc, alc_modelo = [], [], [], [], 0
        for r in resultados:
            idx = int(r["caso"]["indice"])
            acc = acciones_de_resultado(r)
            verd.append(V.p(idx, acc))
            antes.append(V.antes(idx))
            costos.append(r["costo_total"])
            nacc.append(len(r["acciones"]))
            alc_modelo += bool(r["alcanzado"])
            por_caso.setdefault(idx, {})[f"{deseado:.2f}"] = {"verdadera": verd[-1], "acciones": acc, "alcanzado_modelo": bool(r["alcanzado"])}
        verd, antes = np.array(verd), np.array(antes)
        n = len(verd)
        filas_md.append({
            "deseado": deseado, "n": n, "modelo_alcanza": alc_modelo / n, "llega_080": float((verd >= META).mean()),
            "llega_deseado": float((verd >= deseado).mean()), "p_media": float(verd.mean()), "mejora": float((verd - antes).mean()),
            "costo": float(np.mean(costos)), "acciones": float(np.mean(nacc)), "segundos": seg,
        })
        print(f"deseado {deseado:.2f}: {seg:.0f} s", flush=True)
    if a.prescripciones:
        res = cv.evaluar_prescripciones(a.prescripciones, *_n_y_semilla(), None)
        t = res["tabla"]
        p = pd.read_csv(a.prescripciones).set_index("caso")
        filas_md.insert(0, {"deseado": 0.80, "n": len(t), "modelo_alcanza": float(np.mean([str(p.loc[c, "alcanzado"]).lower() == "true" for c in t.caso])),
                            "llega_080": float((t.verdadera >= META).mean()), "llega_deseado": float((t.verdadera >= META).mean()),
                            "p_media": float(t.verdadera.mean()), "mejora": float((t.verdadera - t.antes_verdadera).mean()),
                            "costo": float(p.loc[list(t.caso), "costo_total"].mean()), "acciones": float(t.acciones.apply(len).mean()), "segundos": 0.0})
    md = ["## Margen de seguridad: re-prescribir con un deseado mayor", "",
          f"Mismos {filas_md[0]['n']} casos, mismas restricciones y μ = {mu:g}; solo cambia el deseado. Evaluado en la verdad. "
          "La fila de 0,80 es el lote original (prescripciones.csv).", "",
          "| Deseado | El modelo da por alcanzados | **De verdad llega a 0,80** | De verdad llega al deseado | P verdadera media | Mejora verdadera media | Costo medio | Acciones por plan |",
          "|---|---|---|---|---|---|---|---|"]
    for f in filas_md:
        md.append(f"| {f['deseado']:.2f} | {f['modelo_alcanza']:.0%} | **{f['llega_080']:.0%}** | {f['llega_deseado']:.0%} | {f['p_media']:.3f} | "
                  f"{pp(f['mejora'])} | {f['costo']:.3f} | {f['acciones']:.2f} |")
    (a.salida / "margen_por_caso.json").write_text(json.dumps(por_caso, ensure_ascii=False), encoding="utf-8")
    return "\n".join(md) + "\n"


# --- 3. Métodos del comparador contra la verdad ----------------------------------------------------------


def cmd_metodos(a) -> str:
    from pcapp_nucleo.causal.contrafactuales import caso_desde_test, contrafactual_preparado
    from pcapp_nucleo.causal.unidades import ORDINAL
    from pcapp_nucleo.prescripcion.comparador import (
        ALEATORIA, IMITAR, NOMBRES_METODOS, PRESCRIPTOR, SIN_CAUSALIDAD, SIN_INTERVENCION, ProblemaSinCausalidad,
        _aleatoria, _imitar, _sin_intervencion, medias_exitosos,
    )
    from pcapp_nucleo.prescripcion.evidencia import construir_indice
    from pcapp_nucleo.prescripcion.optimizadores import Solucion, crear_optimizador
    from pcapp_nucleo.prescripcion.prescriptor import _fijadas, prescribir_con_solucion, resolver, semilla_de_caso
    from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion

    modelo, datos, config, mu, referencia, filas = cargar_proyecto(a.proyecto)
    if a.n:
        filas = filas.iloc[: a.n]
    vecinos = construir_indice(modelo, datos.train, config)
    medias = medias_exitosos(vecinos) if vecinos is not None else None
    optimizador = crear_optimizador(config.optimizador, config)
    V = Verdad()

    def acciones(problema, caso, s: Solucion) -> dict[str, float]:
        fijadas, nombres = _fijadas(problema, s)
        valores = {v.variable: v for v in contrafactual_preparado(modelo, caso, fijadas, nombres, problema.abduccion).valores} if fijadas else {}
        out = {}
        for i, ac in enumerate(problema.continuas):
            if s.d[i] != 0:
                num = valores[ac.columna].despues_numerico
                if modelo.unidades.control(ac.columna) == ORDINAL:
                    num = modelo.unidades.valor_de_codigo(ac.columna, num)
                out[ac.nombre] = float(num)
        for j, ac in enumerate(problema.discretas):
            if s.estado[j] != ac.actual:
                out[ac.nombre] = float(numero(ac.etiquetas[s.estado[j]]))
        return out

    def costo(problema, s: Solucion) -> float:
        return float(problema.con_mu(1.0).penalizacion(*problema.matrices([s.d], [s.estado]))[0])

    def n_acciones(problema, s: Solucion) -> int:
        return int(np.count_nonzero(s.d)) + sum(1 for j, ac in enumerate(problema.discretas) if s.estado[j] != ac.actual)

    def a_igual_costo(problema, s: Solucion, objetivo: float) -> Solucion:
        """Lleva la solución al costo ``objetivo``: si sus cambios discretos ya lo superan, descarta primero los más caros;
        luego escala la parte continua (sin salirse de los límites)."""
        estado = list(s.estado)
        costo_de = lambda j: problema.discretas[j].costo  # noqa: E731
        while True:
            cambiados = [j for j, ac in enumerate(problema.discretas) if estado[j] != ac.actual]
            costo_disc = costo(problema, Solucion(np.zeros(problema.k), tuple(estado), 0.0, 0.0))
            if costo_disc <= objetivo + 1e-12 or not cambiados:
                break
            peor = max(cambiados, key=costo_de)
            estado[peor] = problema.discretas[peor].actual
        estado = tuple(estado)
        if not problema.k or not np.any(s.d):
            return Solucion(s.d, estado, 0.0, 0.0)
        costo_cont = costo(problema, Solucion(s.d, problema.actual, 0.0, 0.0))
        if costo_cont <= 0:
            return Solucion(s.d, estado, 0.0, 0.0)
        alfa = max(0.0, (objetivo - costo_disc) / costo_cont)
        with np.errstate(divide="ignore", invalid="ignore"):
            tope = np.where(s.d > 0, problema.hi / s.d, np.where(s.d < 0, problema.lo / s.d, np.inf))
        alfa = min(alfa, float(np.min(tope)))
        return Solucion(problema.proyectar(alfa * s.d), estado, 0.0, 0.0)

    METODOS = [PRESCRIPTOR, SIN_CAUSALIDAD, IMITAR, ALEATORIA, SIN_INTERVENCION]
    reg: dict[str, list[dict]] = {m: [] for m in METODOS}
    reg_ic: dict[str, list[dict]] = {m: [] for m in METODOS}
    t0 = time.time()
    for k, indice in enumerate(filas.index):
        caso = caso_desde_test(modelo, filas, int(indice))
        fila = filas.loc[[indice]]
        idx = int(indice)
        problema = ProblemaPrescripcion(modelo, caso, config, mu)
        _, sol_p = prescribir_con_solucion(modelo, caso, config, mu, referencia, fila, optimizador, problema)
        semilla = semilla_de_caso(modelo, caso)
        sol = {PRESCRIPTOR: sol_p, ALEATORIA: _aleatoria(problema, semilla), SIN_INTERVENCION: _sin_intervencion(problema)}
        sol[SIN_CAUSALIDAD] = resolver(
            ProblemaSinCausalidad(modelo, caso, config, mu, referencia, fila, problema.abduccion), optimizador, semilla)[0]
        if medias is not None:
            sol[IMITAR] = _imitar(problema, medias)
        presupuesto = costo(problema, sol_p)
        antes = V.antes(idx)
        for m in METODOS:
            for destino, s in ((reg, sol[m]), (reg_ic, sol[m] if m in (PRESCRIPTOR, SIN_INTERVENCION) else a_igual_costo(problema, sol[m], presupuesto))):
                acc = acciones(problema, caso, s)
                destino[m].append({"caso": idx, "verdadera": V.p(idx, acc), "antes": antes, "costo": costo(problema, s),
                                   "acciones": n_acciones(problema, s), "presupuesto": presupuesto, "plan": acc})
        if (k + 1) % 25 == 0:
            print(f"  {k + 1}/{len(filas)} casos, {time.time() - t0:.0f} s", flush=True)
    seg = time.time() - t0
    print(f"{len(filas)} casos en {seg:.0f} s", flush=True)

    def tabla(r: dict[str, list[dict]], titulo: str) -> list[str]:
        out = [f"### {titulo}", "",
               "| Método | P verdadera media | Mejora verdadera media | **% que de verdad llega a 0,80** | Costo medio | Acciones por plan |", "|---|---|---|---|---|---|"]
        for m in METODOS:
            x = pd.DataFrame(r[m])
            out.append(f"| {NOMBRES_METODOS[m]} | {x.verdadera.mean():.3f} | {pp((x.verdadera - x.antes).mean())} | "
                       f"**{(x.verdadera >= META).mean():.0%}** ({int((x.verdadera >= META).sum())}/{len(x)}) | {x.costo.mean():.3f} | {x.acciones.mean():.2f} |")
        return out

    md = ["## Métodos del comparador evaluados en la verdad", "",
          f"{len(filas)} casos de test que no cumplen el objetivo, μ = {mu:g}, mismas acciones, límites y costos para todos los métodos. "
          "El costo es el del prescriptor (suma de cambios ponderados por su costo, sin μ). La verdad es el do-operator del generador con el ruido de cada estudiante.", ""]
    md += tabla(reg, "Tal como los propone cada método")
    md += ["", "### A igual costo", "",
           "Cada método se lleva, caso a caso, al costo del plan del prescriptor: se escala su cambio continuo (sin salirse de los límites) "
           "hacia arriba o abajo; los cambios discretos (tutorías, créditos, apoyo financiero) no se escalan: si por sí solos ya superan el presupuesto, "
           "se descartan primero los más caros. «Sin intervención» y el prescriptor no cambian.", ""]
    md += tabla(reg_ic, "A igual costo")[2:]
    igualados = {m: pd.DataFrame(reg_ic[m]).pipe(lambda x: float(((x.costo - x.presupuesto).abs() <= 0.05 * x.presupuesto.clip(lower=1e-9)).mean()))
                 for m in (IMITAR, ALEATORIA, SIN_CAUSALIDAD)}
    md += ["", "Casos en que el costo quedó igualado al del prescriptor (±5 %; si no, los límites lo impiden o el método ya costaba menos y no se puede subir más): " +
           ", ".join(f"{NOMBRES_METODOS[m]} {d:.0%}" for m, d in igualados.items()) + "."]
    (a.salida / "metodos_por_caso.json").write_text(json.dumps({"tal_cual": reg, "igual_costo": reg_ic}, ensure_ascii=False), encoding="utf-8")
    return "\n".join(md) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["revision", "margen", "metodos"])
    ap.add_argument("--proyecto", type=Path)
    ap.add_argument("--prescripciones", type=Path)
    ap.add_argument("--n", type=int)
    ap.add_argument("--deseados", type=float, nargs="+", default=[0.85, 0.90])
    ap.add_argument("--salida", type=Path, default=g.SALIDAS / "analisis_verdad")
    a = ap.parse_args(argv)
    a.salida.mkdir(parents=True, exist_ok=True)
    texto = {"revision": cmd_revision, "margen": cmd_margen, "metodos": cmd_metodos}[a.cmd](a)
    sufijo = f"_n{a.n}" if a.n else ""
    (a.salida / f"{a.cmd}{sufijo}.md").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())

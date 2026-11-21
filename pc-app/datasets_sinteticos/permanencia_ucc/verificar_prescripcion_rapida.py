"""Verificación rápida de la prescripción sobre permanencia_ucc con el núcleo (sin la app).

Usa una submuestra de filas del CSV, el grafo VERDADERO como resultado de PC (no corre PC), las ordinales y
las restricciones de la guía del README (límites y cambio máximo en valores originales), prescribe en lote
sobre las filas de test que no cumplen el objetivo y comprueba:

  1. que ningún valor prescrito quede fuera de su rejilla (pasos y niveles de la guía) ni de sus límites;
  2. que ``comparar_con_verdad.py`` lea el ``prescripciones.csv`` que escribe el núcleo (el mismo formato que
     exporta la app) sin «casos ignorados».

Uso: python verificar_prescripcion_rapida.py [--filas 800] [--semilla 7] [--salida CARPETA]
Requiere ``pcapp_nucleo`` instalado o en PYTHONPATH.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import comparar_con_verdad as cv
import generador as g
from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.carga import cargar_dataset
from pcapp_nucleo.causal import ErrorModeloCausal, construir_modelo, modelo_desde_diccionario
from pcapp_nucleo.plantilla import aplicar_elecciones, aplicar_marcas_ordinales
from pcapp_nucleo.preparacion import preparar
from pcapp_nucleo.prescripcion import (
    ObjetivoDeseado, ajustar_referencia, configuracion_por_defecto, confirmar_supuestos, prescribir_lote,
)
from pcapp_nucleo.prescripcion.informe import prescripciones_csv
from pcapp_nucleo.prescripcion.lotes import que_no_cumplen

OBJETIVO = "permanece"
ORDINALES = ["estrato", "tutorias_asistidas", "materias_reprobadas", "creditos_matriculados"]
# Restricciones de la guía (README, sección 4), todas en valores originales: (dirección, cambio máximo, mínimo, máximo, costo)
GUIA = {
    "asistencia_pct": ("subir", 20.0, None, 100.0, 1.0),
    "horas_estudio_semana": ("subir", 8.0, None, 30.0, 1.0),
    "tutorias_asistidas": ("subir", 4.0, None, None, 1.0),
    "creditos_matriculados": ("bajar", 6.0, 14.0, None, 1.0),
    "apoyo_bienestar": ("subir", None, None, None, 1.0),
    "apoyo_financiero": ("subir", None, None, None, 3.0),
    "horas_trabajo_semana": ("bajar", 10.0, 0.0, None, 1.0),
}
# Rejilla esperada de cada variable que se prescribe como número: paso (en unidades originales) y rango válido
REJILLA = {
    "asistencia_pct": (1.0, 30, 100), "horas_estudio_semana": (0.5, 0, 30), "tutorias_asistidas": (1.0, 0, 7),
    "creditos_matriculados": (1.0, 14, 22), "horas_trabajo_semana": (1.0, 0, 48),
    "apoyo_bienestar": (1.0, 0, 1), "apoyo_financiero": (1.0, 0, 1),
}


def configuracion_guia(modelo, mu: float):
    c = configuracion_por_defecto(modelo, list(GUIA))
    c = replace(c, objetivo=ObjetivoDeseado("subir", 0.8), mu=mu)
    acciones = dict(c.acciones)
    for v, (direccion, cambio, minimo, maximo, costo) in GUIA.items():
        if v not in acciones:
            continue
        a = acciones[v]
        cambios = {"direccion": direccion, "costo": costo}
        if a.minimo is not None or a.maximo is not None:  # numéricas y ordinales: límites en valores originales
            cambios.update(cambio_maximo=cambio, minimo=a.minimo if minimo is None else minimo, maximo=a.maximo if maximo is None else maximo)
        if v == "horas_estudio_semana":
            cambios["paso"] = 0.5  # media hora
        acciones[v] = replace(a, **cambios)
    return confirmar_supuestos(replace(c, acciones=acciones), list(acciones))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filas", type=int, default=800)
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--mu", type=float, default=0.005)
    ap.add_argument("--salida", default=str(g.SALIDAS / "verificacion_rapida"))
    a = ap.parse_args(argv)

    completo = cargar_dataset(g.SALIDAS / "permanencia_ucc.csv")
    muestra = completo.sample(a.filas, random_state=a.semilla).sort_index()  # conserva la posición original como índice
    informe = analizar_dataset(muestra, OBJETIVO).informe
    decisiones = aplicar_marcas_ordinales(aplicar_elecciones(informe, {}), muestra, {c: "marcar" for c in ORDINALES})
    datos = preparar(muestra, OBJETIVO, decisiones)
    tipos = {c.nombre: c.tipo_final for c in datos.receta.columnas}
    print(f"train {len(datos.train)}, test {len(datos.test)}; ordinales:", [c for c in ORDINALES if tipos.get(c) == "ordinal"])
    print("índice de test (posición en el CSV original):", list(datos.test.index[:6]), "…")

    resultado_pc = {
        "variables": list(datos.train.columns),
        "aristas": [{"origen": o, "destino": d, "tipo": "dirigida"} for o, d, _, _ in g.ARISTAS],
        "corridas": {"completo": True},
    }
    try:
        modelo_json, _ = construir_modelo(resultado_pc, datos)
    except ErrorModeloCausal as error:
        for p in error.problemas:
            print("PROBLEMA:", p.codigo, "-", p.mensaje)
        return 2
    modelo = modelo_desde_diccionario(modelo_json, datos.train)
    config = configuracion_guia(modelo, a.mu)
    print({v: (x.direccion, x.minimo, x.maximo, x.cambio_maximo, x.paso) for v, x in config.acciones.items()})
    referencia = ajustar_referencia(datos.train, modelo.objetivo, modelo.binario)
    filas = que_no_cumplen(modelo, datos.test, config)
    print(f"casos de test que no cumplen el objetivo: {len(filas)}")
    resultados = prescribir_lote(modelo, filas, config, a.mu, referencia)

    # --- 1. Valores fuera de la rejilla ----------------------------------------------------------------------
    malos, valores = [], 0
    for r in resultados:
        for ac in r["acciones"]:
            v, despues = ac["variable"], ac["despues"]
            paso, lo, hi = REJILLA[v]
            valores += 1
            k = float(despues) / paso
            if abs(k - round(k)) > 1e-6 or not lo - 1e-9 <= float(despues) <= hi + 1e-9:
                malos.append((r["caso"]["indice"], v, despues))
            if v == "creditos_matriculados" and float(despues) < 14 - 1e-9:
                malos.append((r["caso"]["indice"], v, f"{despues} < mínimo 14"))
    alcanzados = sum(r["alcanzado"] for r in resultados)
    print(f"valores prescritos: {valores}; fuera de rejilla o de límites: {len(malos)} {malos[:6]}")
    print(f"alcanzan el objetivo: {alcanzados}/{len(resultados)}; solo con cambios intermedios: "
          f"{sum(bool(r.get('solo_con_cambios_intermedios')) for r in resultados)}")

    # --- 2. El comparador con el CSV que escribe el núcleo ---------------------------------------------------
    carpeta = Path(a.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "prescripciones.csv").write_text(prescripciones_csv(resultados), encoding="utf-8")
    # PC no se corrió: el grafo verdadero, en el formato de aristas.csv de la app, solo para que el comparador funcione
    pd.DataFrame([{"origen": o, "destino": d, "tipo": "dirigida", "frecuencia_total": 1.0} for o, d, _, _ in g.ARISTAS]).to_csv(
        carpeta / "aristas.csv", index=False)
    (carpeta / "resultado.json").write_text(json.dumps({"nota": "grafo verdadero, sin correr PC"}), encoding="utf-8")
    md, resumen = cv.construir_informe(carpeta, None, None)
    (carpeta / "comparacion.md").write_text(md, encoding="utf-8")
    pres = resumen["prescripciones"] or {}
    ignorados = pres.get("ignoradas", [])
    print(f"comparador: {pres.get('n')} casos evaluados, ignorados: {ignorados}, con valores no válidos: {pres.get('con_valores_no_validos')}")
    for k in ("error_medio", "error_abs_medio", "pct_promete_meta", "pct_llega_verdadera", "pct_llega_redondeada"):
        if k in pres:
            print(f"  {k}: {pres[k]:.3f}")
    ok = not malos and not ignorados and pres.get("n") == len(resultados) and not pres.get("con_valores_no_validos")
    print("RESULTADO:", "correcto" if ok else "HAY PROBLEMAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

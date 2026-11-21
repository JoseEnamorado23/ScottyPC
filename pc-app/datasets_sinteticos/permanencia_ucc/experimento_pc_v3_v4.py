"""Experimento v3/v4 sobre permanencia_ucc: corre PC con fisherz (v3), reagrega a otro umbral (v4) y compara v1-v4.

  v1, v2: exportaciones de Scotty PC ya hechas en la app (carpetas con aristas.csv y resultado.json).
  v3: PC con ``fisherz``, umbral 60 %, con los niveles y las variables modificables de v2
      (estrato, edad_ingreso y genero en un nivel anterior a todo). Misma receta y misma separación que v2,
      así que el entrenamiento es idéntico.
  v4: reagregación de las MISMAS corridas de v3 con umbral 50 % (no corre PC otra vez).

Ejecuta PC UNA vez (100 corridas). Por defecto va en secuencial (un solo proceso, poca RAM); ``--procesos N`` las reparte.
Escribe ``<salida>/v3`` y ``<salida>/v4`` con los mismos archivos que la exportación de la app y
``<salida>/comparacion_v1_v4.md`` con la tabla. Con ``--solo-tabla`` no corre PC: compara las carpetas que ya existan.

Uso:
  python experimento_pc_v3_v4.py --v1 <carpeta v1> --v2 <carpeta v2> [--salida CARPETA] [--procesos 1] [--solo-tabla]
Requiere ``pcapp_nucleo`` (con causal-learn) instalado o en PYTHONPATH.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import comparar_con_verdad as cv
import generador as g

OBJETIVO = "permanece"


def _estado(dirigidas: set, sin: set, a: str, b: str) -> str:
    if (a, b) in dirigidas:
        return "sí, bien orientada"
    if (b, a) in dirigidas:
        return "sí, invertida"
    if frozenset((a, b)) in sin:
        return "sí, sin orientar"
    return "no"


def metricas(nombre: str, carpeta: Path) -> dict:
    """Métricas de una carpeta con aristas.csv y resultado.json (formato de la app)."""
    dirigidas, sin, _ = cv.leer_aristas_pc(carpeta, None)
    m = cv.comparar_grafo(dirigidas, sin)
    caminos = cv.caminos_verdaderos(cv.aristas_verdaderas())
    hacia_obj = sorted(next(iter(p - {OBJETIVO})) for p in m["pc_esq"] if OBJETIVO in p)
    verdaderas_obj = sorted(next(iter(p - {OBJETIVO})) for p in m["ver_esq"] if OBJETIVO in p)
    resultado = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
    conf = resultado.get("configuracion", {})
    caract = resultado.get("caracterizacion", {})
    return {
        "nombre": nombre, "prueba": conf.get("prueba"), "umbral": conf.get("umbral_frecuencia"),
        "aristas": len(m["pc_esq"]), "acertadas": len(m["tp"]), "sobrantes": len(m["sobran"]), "faltantes": len(m["faltan"]),
        "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
        "correctas": len(m["correctas"]), "invertidas": len(m["invertidas"]), "sin_orientar": len(m["sin_orientar"]),
        "exactitud_orientacion": m["acc_orientacion"], "shd": m["shd"],
        "hacia_objetivo": hacia_obj, "verdaderas_hacia_objetivo": verdaderas_obj,
        "prescriptivas": caract.get("candidatas_prescriptivas", []),
        "sobrantes_lista": sorted("—".join(sorted(p)) for p in m["sobran"]),
        "sobrantes_latente": sorted("—".join(sorted(p)) for p in m["sobran"] if cv.explicacion_latente(p)),
        "sobrantes_otras": sorted("—".join(sorted(p)) + " (" + cv.explicacion_sobrante(p, caminos) + ")" for p in m["sobran"] if not cv.explicacion_latente(p)),
        "apoyo_financiero→permanece": _estado(dirigidas, sin, "apoyo_financiero", OBJETIVO),
        "promedio_semestre→materias_reprobadas": _estado(dirigidas, sin, "promedio_semestre", "materias_reprobadas"),
    }


def tabla(filas: list[dict]) -> str:
    def f(x, d=2):
        return "—" if x is None or x != x else f"{x:.{d}f}"

    cab = "| Métrica | " + " | ".join(f["nombre"] for f in filas) + " |"
    sep = "|---|" + "---|" * len(filas)
    reglones = [
        ("Prueba / umbral", lambda r: f"{r['prueba']} / {f(r['umbral'], 2)}"),
        ("Aristas encontradas (verdad: 28)", lambda r: str(r["aristas"])),
        ("Precisión", lambda r: f(r["precision"])),
        ("Recall", lambda r: f(r["recall"])),
        ("F1", lambda r: f(r["f1"])),
        ("Orientadas bien / invertidas / sin orientar", lambda r: f"{r['correctas']} / {r['invertidas']} / {r['sin_orientar']}"),
        ("Exactitud de orientación", lambda r: f(r["exactitud_orientacion"])),
        ("SHD", lambda r: str(r["shd"])),
        ("Aristas falsas (sobrantes)", lambda r: str(r["sobrantes"])),
        ("  · explicadas por la latente `motivacion`", lambda r: f"{len(r['sobrantes_latente'])}" + (": " + ", ".join(r["sobrantes_latente"]) if r["sobrantes_latente"] else "")),
        ("  · otras", lambda r: f"{len(r['sobrantes_otras'])}" + (": " + "; ".join(r["sobrantes_otras"]) if r["sobrantes_otras"] else "")),
        ("`apoyo_financiero → permanece`", lambda r: r["apoyo_financiero→permanece"]),
        ("`promedio_semestre → materias_reprobadas`", lambda r: r["promedio_semestre→materias_reprobadas"]),
        ("Aristas hacia `permanece` (verdad: %d)" % len(filas[0]["verdaderas_hacia_objetivo"]),
         lambda r: f"{len(r['hacia_objetivo'])}: " + ", ".join(r["hacia_objetivo"])),
        ("Variables prescriptivas resultantes", lambda r: f"{len(r['prescriptivas'])}: " + (", ".join(r["prescriptivas"]) or "ninguna")),
    ]
    return "\n".join([cab, sep] + [f"| {n} | " + " | ".join(fn(r) for r in filas) + " |" for n, fn in reglones])


def correr_v3_v4(v2: Path, salida: Path, procesos: int) -> None:
    from pcapp_nucleo.caracterizacion import caracterizar
    from pcapp_nucleo.cli_preparacion import cargar_desde_receta
    from pcapp_nucleo.exportacion import exportar
    from pcapp_nucleo.pc_bootstrap import agregar, ejecutar_bootstrap, matriz_spearman
    from pcapp_nucleo.pc_config import configuracion_desde_diccionario

    # La receta de v2 y el CSV original, en una carpeta de trabajo (no se toca la exportación)
    trabajo = salida / "_trabajo"
    trabajo.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(v2 / "receta.json", trabajo / "receta.json")
    receta = json.loads((trabajo / "receta.json").read_text(encoding="utf-8"))
    shutil.copyfile(g.SALIDAS / "permanencia_ucc.csv", trabajo / (receta["origen"]["archivo"] or "original.csv"))
    cargados = cargar_desde_receta(trabajo / "receta.json")  # verifica el hash del CSV
    if cargados is None:
        raise SystemExit("No se pudo reproducir la preparación de v2.")
    original, datos = cargados

    conf_v2 = json.loads((v2 / "resultado.json").read_text(encoding="utf-8"))["configuracion"]
    # Mismos niveles, modificables y semilla que v2; cambian la prueba y (en v4) el umbral
    base = configuracion_desde_diccionario({**conf_v2, "prueba": "fisherz", "umbral_frecuencia": 0.6, "procesos": procesos,
                                            "modo_ejecucion": "secuencial" if procesos <= 1 else "paralelo"})
    print("niveles:", base.niveles)
    print(f"PC con {base.prueba}, {base.corridas_bootstrap} corridas, umbral {base.umbral_frecuencia}, procesos {procesos}", flush=True)
    t = time.time()
    resultado = ejecutar_bootstrap(
        datos, base, progreso=lambda hechas, total, s: print(f"\r  corrida {hechas}/{total}", end="", flush=True))
    print(f"\n  {resultado.corridas_validas} válidas de {resultado.corridas_totales} en {time.time() - t:.0f} s")
    if resultado.corridas_fallidas:
        print("  fallidas:", [(c.corrida, c.motivo) for c in resultado.corridas_fallidas[:5]])

    from pcapp_nucleo.pc_bootstrap import agregar_cuentas

    espeareman = matriz_spearman(datos.train, resultado.variables)
    redundantes = []
    try:
        from pcapp_nucleo.cli_pc import _grupos_redundantes
        redundantes = _grupos_redundantes(original, datos.objetivo)
    except Exception:  # noqa: BLE001 - solo informativo
        pass
    for nombre, umbral in (("v3", 0.6), ("v4", 0.5)):
        conf = replace(base, umbral_frecuencia=umbral)
        grafo = (agregar(resultado, datos, conf, espeareman) if nombre == "v3"
                 else agregar_cuentas(resultado, umbral, conf.orientaciones_manuales, espeareman))
        caract = caracterizar(grafo, resultado, conf.modificables, redundantes)
        carpeta = salida / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(trabajo / "receta.json", carpeta / "receta.json")
        exportar(carpeta, conf, datos.receta, resultado, grafo, caract, espeareman)
        print(f"  {nombre}: umbral {umbral:.0%}, {len(grafo.aristas)} aristas, escrito en {carpeta}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v1", required=True)
    ap.add_argument("--v2", required=True)
    ap.add_argument("--salida", default=str(g.SALIDAS / "experimento_fisherz_v3_v4"))
    ap.add_argument("--procesos", type=int, default=1)
    ap.add_argument("--solo-tabla", action="store_true")
    a = ap.parse_args(argv)
    v1, v2, salida = Path(a.v1), Path(a.v2), Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    if not a.solo_tabla:
        correr_v3_v4(v2, salida, a.procesos)
    carpetas = [("v1", v1), ("v2", v2), ("v3", salida / "v3"), ("v4", salida / "v4")]
    filas = [metricas(n, c) for n, c in carpetas if (c / "aristas.csv").is_file()]
    texto = "# Comparación de corridas de PC contra la verdad (permanencia_ucc)\n\n" + tabla(filas) + "\n"
    (salida / "comparacion_v1_v4.md").write_text(texto, encoding="utf-8")
    print("\n" + texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())

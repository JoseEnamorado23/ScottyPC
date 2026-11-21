"""Prueba del comparador con un «PC falso»: el grafo verdadero menos 3 aristas y con 1 invertida
(más 1 sobrante explicada por la latente), y prescripciones inventadas con sobrepromesa conocida.

Uso: python probar_comparador.py   (escribe salidas/prueba_comparador/)
Falla (exit 1) si el comparador no detecta exactamente lo sembrado.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

import comparar_con_verdad as c
import generador as g

QUITAR = [("estrato", "primera_generacion"), ("tutorias_asistidas", "promedio_semestre"),
          ("apoyo_bienestar", "permanece")]
INVERTIR = ("asistencia_pct", "promedio_semestre")      # PC dice promedio → asistencia (hijas de la latente)
SOBRANTE = ("horas_estudio_semana", "tutorias_asistidas")  # arista espuria que explica la latente
CONTROL = ("genero", "permanece")                       # falso positivo de control


def main() -> bool:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    carpeta = g.SALIDAS / "prueba_comparador"
    carpeta.mkdir(exist_ok=True)
    filas = []
    for o, d, _, _ in g.ARISTAS:
        if (o, d) in QUITAR:
            continue
        if (o, d) == INVERTIR:
            o, d = d, o
        filas.append((o, d, "dirigida", 1.0))
    filas.append((*SOBRANTE, "dirigida", 0.7))
    filas.append((*CONTROL, "sin_orientar", 0.62))
    pd.DataFrame([{"origen": o, "destino": d, "tipo": t, "frecuencia_total": f} for o, d, t, f in filas]).to_csv(
        carpeta / "aristas.csv", index=False)
    (carpeta / "resultado.json").write_text(json.dumps({"nota": "PC falso para probar comparar_con_verdad.py"}), encoding="utf-8")

    # Prescripciones falsas: 6 estudiantes en riesgo; el «modelo» promete la P verdadera tras acciones + 0.10 de sobrepromesa
    ef = json.loads((g.SALIDAS / "efectos_verdaderos.json").read_text(encoding="utf-8"))
    R = g.generar_ruido(ef["n"], ef["semilla"])
    base = g.simular(R)
    riesgo = np.where(base["p_permanece"] < 0.5)[0][:6]
    reg = []
    for k, i in enumerate(riesgo):
        acc = {"asistencia_pct": 100, "tutorias_asistidas": 2.4 if k % 2 else 3, "apoyo_financiero": 1}
        antes = {v: float(base[v][i]) for v in acc}
        sub = {kk: np.asarray(v)[[i]] for kk, v in R.items()}
        bs = {kk: np.asarray(v)[[i]] for kk, v in base.items()}
        do = {v: (lambda b, x=x: np.full_like(b, x, dtype=float)) for v, x in acc.items()}
        p_ver = float(g.simular(sub, do, bs)["p_permanece"][0])
        fila = {"caso": int(i), "antes": float(base["p_permanece"][i]), "despues": min(p_ver + 0.10, 0.99),
                "deseado": 0.8, "alcanzado": p_ver + 0.10 >= 0.8}
        for v, x in acc.items():
            fila[f"{v} antes"], fila[f"{v} despues"] = antes[v], x
        reg.append(fila)
    pd.DataFrame(reg).to_csv(carpeta / "prescripciones.csv", index=False)

    texto, resumen = c.construir_informe(carpeta, None, None)
    (carpeta / "comparacion.md").write_text(texto, encoding="utf-8")
    print(texto)

    r = c.comparar_grafo(*c.leer_aristas_pc(carpeta, None)[:2])
    esperado_shd = 3 + 2 + 1       # 3 faltantes + 2 sobrantes (espuria + control) + 1 invertida
    pr = resumen["prescripciones"]
    chequeos = {
        "3 faltantes": {tuple(sorted(p)) for p in r["faltan"]} == {tuple(sorted(e)) for e in QUITAR},
        "1 invertida": [tuple(v) for v in r["invertidas"]] == [INVERTIR],
        "2 sobrantes": {tuple(sorted(p)) for p in r["sobran"]} == {tuple(sorted(SOBRANTE)), tuple(sorted(CONTROL))},
        f"SHD = {esperado_shd}": r["shd"] == esperado_shd,
        "control genero conectado detectado": resumen["controles_conectados"] == 1,
        "6 casos evaluados": pr is not None and pr["n"] == 6,
        "sobrepromesa ≈ +10 pp (valores sin redondear en casos pares)": pr is not None and pr["error_medio"] > 0.03,
        "detecta valores no válidos (2,4 tutorías)": pr is not None and pr["con_valores_no_validos"] == 3,
    }
    for k, v in chequeos.items():
        print(("OK    " if v else "FALLA ") + k)
    return all(chequeos.values())


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

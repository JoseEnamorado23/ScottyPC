"""Paso 3: carga el CSV con el núcleo de Scotty PC y corre solo la revisión (detectores). No corre PC.

Uso: python revisar_con_nucleo.py   (requiere `pcapp_nucleo` instalado o en PYTHONPATH)
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from pcapp_nucleo.analisis import analizar_dataset, resultado_a_diccionario
from pcapp_nucleo.carga import cargar_dataset

ruta = Path(__file__).resolve().parent / "salidas" / "permanencia_ucc.csv"
df = cargar_dataset(ruta)
res = analizar_dataset(df, "permanece")
d = resultado_a_diccionario(res)
out = Path(__file__).resolve().parent / "salidas" / "revision_nucleo.json"
out.write_text(json.dumps(d, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("filas x columnas:", df.shape, "| válido:", d["valido"])
print("validación:", d["validacion"])
print("resumen:", d.get("resumen"))
print("objetivo:", d.get("objetivo"), d.get("informacion_objetivo"))
print("\n== HALLAZGOS ==")
for h in d.get("hallazgos", []):
    print(json.dumps(h, ensure_ascii=False, default=str))
print("\n== PERFILES ==")
for p in d.get("perfiles_columnas", []):
    print({k: p[k] for k in p if k in ("columna", "tipo_preliminar", "tipo", "faltantes", "valores_unicos", "porcentaje_faltantes", "minimo", "maximo")})

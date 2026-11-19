"""Limpia ``dataset_2022_hash`` (una fila por estudiante y asignatura) para Scotty PC.

Uso: python limpiar_dataset_2022.py <dataset_2022_hash.csv> [salida.csv]

Decisiones (ver docs/dataset_2022.md):
- Unidad de análisis: el estudiante (una fila). ``abandono_hash`` es constante por estudiante
  (A = abandona, 7,3 %).
- Se descartan las columnas redundantes (los indicadores del campus virtual (eventos, minutos, entregas,
  tests, recursos) miden lo mismo: se conserva el número de eventos) y las que son CONSECUENCIA del abandono (baja_fecha, matricula_activa,
  rendimiento del 2.º cuatrimestre y total, créditos superados del curso, actividad del campus
  virtual de enero a julio), los identificadores y los hashes de alta cardinalidad.
- La actividad del campus virtual se suma solo en septiembre-diciembre de 2022 (1.er cuatrimestre).
  Sin registros = sin actividad (0).
"""

import sys
from pathlib import Path

import pandas as pd

PRIMER_CUATRIMESTRE = ["2022_9", "2022_10", "2022_11", "2022_12"]


def numero(serie: pd.Series) -> pd.Series:
    """Número con coma decimal («9,419») a float."""
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def limpiar(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, sep=";", low_memory=False)
    por_estudiante = df.groupby("dni_hash")
    primero = por_estudiante.first()

    def actividad(prefijo: str) -> pd.Series:
        columnas = [f"{prefijo}_{m}" for m in PRIMER_CUATRIMESTRE]
        suma = df[columnas].apply(numero).sum(axis=1, min_count=1)
        return suma.groupby(df["dni_hash"]).sum(min_count=1).fillna(0)

    wifi = df[[f"n_wifi_days_{m}" for m in PRIMER_CUATRIMESTRE]].apply(numero).max(axis=1)
    salida = pd.DataFrame(index=primero.index)
    salida["abandono"] = (primero["abandono_hash"] == "A").astype(int)
    salida["dedicacion_parcial"] = (primero["dedicacion"] == "TP").astype(int)
    salida["desplazado"] = (primero["desplazado_hash"] == "A").astype(int)
    salida["ingreso_pau"] = (primero["tipo_ingreso"] == "NAP").astype(int)
    salida["primera_opcion"] = (numero(primero["preferencia_seleccion"]) == 1).astype(int)
    salida["nota_acceso"] = numero(primero["nota14_hash"])
    # Sin curso previo no hay «rendimiento previo»: ese faltante dependía del objetivo solo por esto.
    salida["primer_anyo"] = (primero["anyo_inicio_estudios"] >= 2022).astype(int)
    salida["asignaturas"] = por_estudiante.size()
    salida["cred_matriculados"] = numero(primero["cred_mat_total"])
    salida["cred_superados_previos"] = numero(primero["cred_sup_tit"])
    salida["rendimiento_cuat_a"] = numero(primero["rendimiento_cuat_a"])
    salida["lms_eventos"] = actividad("pft_events")
    salida["dias_wifi"] = wifi.groupby(df["dni_hash"]).max().fillna(0)
    return salida.reset_index(drop=True)


if __name__ == "__main__":
    origen = Path(sys.argv[1])
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("dataset_2022_estudiantes.csv")
    resultado = limpiar(origen)
    resultado.to_csv(destino, index=False)
    print(f"{destino}: {resultado.shape[0]} estudiantes, {resultado.shape[1]} columnas")

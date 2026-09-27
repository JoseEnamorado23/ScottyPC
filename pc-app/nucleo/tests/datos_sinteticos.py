"""Dataset sintético con problemas conocidos para pruebas de integración.

``construir_dataset_prueba()`` genera los mismos datos en cada ejecución
(semilla fija). El archivo ``datasets_prueba/dataset_prueba.csv`` se generó
con esta función.
"""

import numpy as np
import pandas as pd

FILAS_BASE = 200
FILAS_DUPLICADAS = 3

# Hallazgos que el dataset provoca deliberadamente: (tipo, columnas).
HALLAZGOS_ESPERADOS = {
    ("filas_duplicadas", None),
    ("valores_faltantes", ("peso",)),
    ("valores_faltantes", ("sexo",)),
    ("posible_identificador", ("id",)),
    ("variable_categorica", ("nivel",)),
    ("posible_variable_ordinal", ("nivel",)),
    ("posible_fecha", ("fecha",)),
    ("texto_libre", ("observacion",)),
    ("columna_derivada", ("minimo", "maximo", "ancho")),
    ("correlacion_casi_perfecta", ("altura", "altura_m")),
    ("distribucion_objetivo", ("objetivo",)),
    ("desbalance_clases", ("objetivo",)),
}


def construir_dataset_prueba() -> pd.DataFrame:
    rng = np.random.default_rng(2024)
    n = FILAS_BASE
    temas = ["álgebra", "lectura crítica", "biología", "historia", "programación"]
    altura = rng.normal(168, 9, n).round(1)
    peso = rng.normal(68, 11, n).round(1).astype(object)
    peso[[4, 30, 77, 150]] = np.nan
    sexo = rng.choice(["M", "F"], n).astype(object)
    sexo[[12, 99]] = "?"
    minimo = rng.integers(0, 40, n)
    maximo = minimo + rng.integers(5, 60, n)
    base = pd.DataFrame(
        {
            "id": np.arange(1, n + 1),
            "edad": rng.integers(15, 60, n),
            "peso": peso,
            "altura": altura,
            "altura_m": altura / 100,
            "sexo": sexo,
            "nivel": rng.choice(["bajo", "medio", "alto"], n),
            "fecha": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
            "observacion": [
                f"El participante {i} mostró un desempeño notable en {temas[i % 5]} "
                f"durante la sesión {i % 17 + 1}."
                for i in range(n)
            ],
            "minimo": minimo,
            "maximo": maximo,
            "ancho": maximo - minimo,
            "objetivo": np.where(np.arange(n) % 9 == 0, "si", "no"),
        }
    )
    return pd.concat([base, base.iloc[:FILAS_DUPLICADAS]], ignore_index=True)

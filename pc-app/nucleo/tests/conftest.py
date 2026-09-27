"""Fixtures compartidas para las pruebas del núcleo."""

import numpy as np
import pandas as pd
import pytest

OBJETIVO = "resultado"


def construir_dataset(filas: int = 120, columnas_extra: int = 3) -> pd.DataFrame:
    """Dataset estructuralmente válido: objetivo binario sin faltantes."""
    rng = np.random.default_rng(0)
    datos = {f"x{i}": rng.normal(size=filas) for i in range(columnas_extra)}
    datos[OBJETIVO] = np.arange(filas) % 2
    return pd.DataFrame(datos)


@pytest.fixture
def dataset_valido() -> pd.DataFrame:
    return construir_dataset()

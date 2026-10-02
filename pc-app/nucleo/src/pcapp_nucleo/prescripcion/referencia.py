"""Modelo de referencia (todas las variables preparadas) guardado por sus coeficientes.

Sirve para marcar ``requiere_revision``: si, evaluado sobre el perfil propagado de una
prescripción, no coincide con el modelo causal en si se alcanza el objetivo. Se ajusta solo con
train, igual que la referencia de la evaluación del modelo causal.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.linear_model import LinearRegression, LogisticRegression


@dataclass(frozen=True)
class ModeloReferencia:
    columnas: list[str]
    medianas: list[float]
    coeficientes: list[float]
    intercepto: float
    binario: bool

    def predecir(self, filas: pd.DataFrame) -> np.ndarray:
        """Probabilidad de la clase 1 (o valor esperado, en unidades preparadas)."""
        X = filas.reindex(columns=self.columnas).astype(float).fillna(pd.Series(self.medianas, index=self.columnas)).fillna(0.0)
        eta = X.to_numpy(dtype=float) @ np.asarray(self.coeficientes) + self.intercepto
        return expit(eta) if self.binario else eta


def ajustar_referencia(train: pd.DataFrame, objetivo: str, binario: bool) -> ModeloReferencia:
    columnas = [c for c in train.columns if c != objetivo]
    medianas = train[columnas].median().fillna(0.0)
    X = train[columnas].fillna(medianas).to_numpy(dtype=float)
    y = train[objetivo].to_numpy(dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if binario:
            modelo = LogisticRegression(C=1e6, max_iter=5000).fit(X, y)
            coeficientes, intercepto = modelo.coef_[0], modelo.intercept_[0]
        else:
            modelo = LinearRegression().fit(X, y)
            coeficientes, intercepto = modelo.coef_, modelo.intercept_
    return ModeloReferencia(
        columnas, [float(v) for v in medianas], [float(c) for c in coeficientes], float(intercepto), binario
    )


def referencia_desde_diccionario(datos: dict[str, Any]) -> ModeloReferencia:
    return ModeloReferencia(**datos)

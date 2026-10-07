"""Pruebas del explorador de fórmulas para el modelo causal."""

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from pcapp_nucleo.causal import construir_modelo
from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.formulas import explicar_modelo_causal
from pcapp_nucleo.formulas.modelo_causal import contribuciones

from .test_modelo_causal import N, preparar_df, resultado


@pytest.fixture(scope="module")
def mixto():
    """A → B (no lineal: splines), A → Y, B → Y con Y binaria (GAM o logística), D fuera."""
    rng = np.random.default_rng(5)
    a = rng.uniform(-3, 3, N)
    b = a + 0.6 * np.sin(2 * a) + rng.normal(0, 0.5, N)
    y = (rng.uniform(size=N) < expit(-0.5 + 0.6 * a + 0.8 * b)).astype(int)
    d = rng.normal(size=N)
    datos = preparar_df(pd.DataFrame({"A": a, "B": b, "D": d, "Y": y}), "Y")
    res = resultado(["A", "B", "D", "Y"], [("A", "B"), ("A", "Y"), ("B", "Y")])
    modelo_json, evaluacion = construir_modelo(res, datos)
    return datos, modelo_json, evaluacion


def test_las_contribuciones_suman_eta_en_todas_las_familias(mixto):
    datos, modelo_json, _ = mixto
    modelo = ModeloCausal(modelo_json)
    familias = set()
    for variable, mecanismo in modelo.mecanismos.items():
        familias.add(mecanismo.familia)
        X = modelo.matriz(variable, datos.test.head(20))
        for fila in X:
            constante, aportes = contribuciones(mecanismo, fila)
            assert constante + sum(aportes) == pytest.approx(float(mecanismo.eta(fila[None, :])[0]), abs=1e-8)
    assert "splines_ridge" in familias


def test_con_los_umbrales_guardados_reproduce_las_elecciones(mixto):
    _, modelo_json, evaluacion = mixto
    traza = explicar_modelo_causal(modelo_json, evaluacion)
    assert {m.variable for m in traza.mecanismos} == {"B", "Y"}
    for m in traza.mecanismos:
        assert m.elegido == m.elegido_guardado and not m.cambiaria
        assert m.elegido_guardado == modelo_json["mecanismos"][m.variable]["seleccion"]["elegido"]
        assert [p.id for p in m.pasos][:2] == ["cv", "parsimonia"] and "caso" in [p.id for p in m.pasos]
    b = next(m for m in traza.mecanismos if m.variable == "B")
    assert b.familia == "splines_ridge" and b.calidad_suficiente is True
    fuera = next(e for e in traza.entradas if e.nombre == "Variables fuera del subgrafo")
    assert "D" in fuera.valor and not fuera.usada


def test_un_umbral_de_parsimonia_alto_cambiaria_al_simple(mixto):
    _, modelo_json, evaluacion = mixto
    mejora = next(m for m in explicar_modelo_causal(modelo_json, evaluacion).mecanismos if m.variable == "B").mejora
    assert 0 < mejora < 0.49
    traza = explicar_modelo_causal(modelo_json, evaluacion, {"umbral_parsimonia": round(mejora + 0.01, 3)})
    b = next(m for m in traza.mecanismos if m.variable == "B")
    assert b.elegido == "simple" and b.cambiaria and traza.avisos[0].startswith("Con estos umbrales")
    assert modelo_json["mecanismos"]["B"]["seleccion"]["elegido"] == "complejo"


def test_el_caso_usa_los_valores_dados_y_por_defecto_la_mediana(mixto):
    _, modelo_json, evaluacion = mixto
    modelo = ModeloCausal(modelo_json)
    base = explicar_modelo_causal(modelo_json, evaluacion, modelo=modelo)
    a = next(c for c in base.controles if c.variable == "A")
    assert a.valor == modelo.info_variables["A"]["mediana"]
    otro = explicar_modelo_causal(modelo_json, evaluacion, valores={"A": a.maximo}, modelo=modelo)
    caso = lambda t: next(p for p in next(m for m in t.mecanismos if m.variable == "B").pasos if p.id == "caso")
    assert caso(base).sustituida != caso(otro).sustituida
    y = next(m for m in otro.mecanismos if m.variable == "Y")
    assert "p=" in next(p for p in y.pasos if p.id == "caso").sustituida


def test_valores_y_umbrales_invalidos(mixto):
    _, modelo_json, evaluacion = mixto
    with pytest.raises(ValueError):
        explicar_modelo_causal(modelo_json, evaluacion, {"umbral_parsimonia": 0.9})
    with pytest.raises(ValueError):
        explicar_modelo_causal(modelo_json, evaluacion, {"inventado": 0.1})
    with pytest.raises(ValueError):
        explicar_modelo_causal(modelo_json, evaluacion, valores={"Z": 1.0})

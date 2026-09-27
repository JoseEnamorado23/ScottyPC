"""Pruebas de la selección de la prueba de independencia para PC."""

import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.preparacion import DecisionesUsuario, TratamientoColumna, preparar
from nucleo.seleccion_prueba import (
    CHISQ,
    FISHERZ,
    KCI,
    MV_FISHERZ,
    diagnosticar_variable,
    discretizar,
    recomendar_prueba,
)
from nucleo.utilidades import a_diccionario_serializable


def binario(logito, rng):
    return (rng.random(len(logito)) < 1 / (1 + np.exp(-logito))).astype(int)


def dataset_lineal(n=1000, semilla=0):
    rng = np.random.default_rng(semilla)
    x = rng.normal(size=(n, 3))
    y = binario(1.5 * x[:, 0] - x[:, 1] + 0.5 * x[:, 2], rng)
    return pd.DataFrame({"x1": x[:, 0], "x2": x[:, 1], "x3": x[:, 2], "y": y})


def dataset_en_u(n=1000, semilla=1):
    rng = np.random.default_rng(semilla)
    x = rng.normal(size=n)
    otra = rng.normal(size=n)
    y = binario(2.5 * (x**2 - 1) + 0.8 * otra, rng)
    return pd.DataFrame({"x": x, "otra": otra, "ruido": rng.normal(size=n), "y": y})


def recomendar(dataframe, decisiones=None, **opciones):
    datos = preparar(dataframe, "y", decisiones or DecisionesUsuario())
    return recomendar_prueba(datos, estimar=False, **opciones)


def test_dataset_lineal_recomienda_fisherz():
    recomendacion = recomendar(dataset_lineal())

    assert recomendacion.prueba == FISHERZ
    assert recomendacion.variables_no_monotonas == []
    assert {a.prueba for a in recomendacion.alternativas} == {CHISQ, MV_FISHERZ}


def test_relacion_en_u_recomienda_chisq_y_cita_la_variable():
    recomendacion = recomendar(dataset_en_u())

    assert recomendacion.prueba == CHISQ
    assert recomendacion.variables_no_monotonas == ["x"]
    assert "x" in recomendacion.motivo
    assert recomendacion.discretizacion == "quintiles"
    [diagnostico] = [d for d in recomendacion.diagnosticos if d.nombre == "x"]
    curva = diagnostico.valores_por_intervalo
    assert len(curva) == 6 and curva[0] > curva[2] < curva[5]
    assert diagnostico.p_intervalos < 0.01
    assert sum(diagnostico.filas_por_intervalo) == recomendacion.filas_train


def test_faltantes_recomienda_mv_fisherz():
    dataframe = dataset_lineal()
    dataframe.loc[dataframe.sample(frac=0.15, random_state=3).index, "x2"] = np.nan

    recomendacion = recomendar(dataframe)

    assert recomendacion.prueba == MV_FISHERZ
    assert recomendacion.faltantes_restantes == {"x2": int(recomendacion.faltantes_restantes["x2"])}
    assert "x2" in recomendacion.motivo


def test_faltantes_imputados_recomienda_fisherz():
    dataframe = dataset_lineal()
    dataframe.loc[dataframe.sample(frac=0.15, random_state=3).index, "x2"] = np.nan

    recomendacion = recomendar(dataframe, DecisionesUsuario(
        faltantes={"x2": TratamientoColumna(imputacion="mediana")}
    ))

    assert recomendacion.prueba == FISHERZ


def test_mayoria_categorica_recomienda_chisq():
    rng = np.random.default_rng(4)
    n = 600
    dataframe = pd.DataFrame({f"b{i}": rng.integers(0, 2, n) for i in range(3)})
    dataframe["x"] = rng.normal(size=n)
    dataframe["y"] = binario(dataframe["b0"] * 2 - 1 + dataframe["x"], rng)

    recomendacion = recomendar(dataframe)

    assert recomendacion.prueba == CHISQ
    assert recomendacion.proporcion_categoricas == 0.75
    assert "categóricas o binarias" in recomendacion.motivo


def test_kci_como_alternativa_con_pocas_filas():
    recomendacion = recomendar(dataset_en_u(n=450))

    assert recomendacion.prueba == CHISQ
    assert KCI in {a.prueba for a in recomendacion.alternativas}
    assert "KCI" in recomendacion.motivo


def test_kci_no_se_menciona_con_muchas_filas():
    assert KCI not in {a.prueba for a in recomendar(dataset_en_u()).alternativas}


def test_ondulacion_pequena_no_cuenta_como_no_linealidad():
    rng = np.random.default_rng(5)
    n = 20000
    x = rng.normal(size=n)
    y = binario(1.2 * x + 0.15 * np.sin(4 * x), rng)
    dataframe = pd.DataFrame({"x": x, "z": rng.normal(size=n), "y": y})

    assert recomendar(dataframe).prueba == FISHERZ


def test_objetivo_continuo_usa_kruskal_y_media():
    rng = np.random.default_rng(6)
    x = rng.normal(size=800)
    y = pd.Series(x**2 + rng.normal(0, 0.3, 800))

    diagnostico = diagnosticar_variable("x", pd.Series(x), y, "continuo", ConfiguracionValidacion())

    assert diagnostico.monotona is False
    assert diagnostico.medida == "media del objetivo"


def test_empates_en_limites_no_dejan_intervalos_vacios():
    rng = np.random.default_rng(7)
    x = np.where(rng.random(1000) < 0.4, 0.0, rng.exponential(size=1000))
    y = pd.Series(binario(x - 1, rng))

    diagnostico = diagnosticar_variable("x", pd.Series(x), y, "binario", ConfiguracionValidacion())

    assert all(n > 0 for n in diagnostico.filas_por_intervalo)
    assert not any(np.isnan(diagnostico.valores_por_intervalo))


def test_discretizar_usa_limites_de_entrenamiento():
    train = pd.DataFrame({"a": np.arange(100.0), "b": [0, 1] * 50})

    discretizado, limites = discretizar(train, ["a"], 5)

    assert sorted(discretizado["a"].unique()) == [0, 1, 2, 3, 4]
    assert len(limites["a"]) == 4
    assert discretizado["b"].equals(train["b"])


def test_recomendacion_serializable_a_json():
    texto = json.dumps(a_diccionario_serializable(recomendar(dataset_en_u())), ensure_ascii=False)

    assert json.loads(texto)["prueba"] == CHISQ


def test_estimacion_de_tiempo_con_pc_real():
    datos = preparar(dataset_lineal(n=300), "y", DecisionesUsuario())

    recomendacion = recomendar_prueba(datos)

    assert recomendacion.estimacion_completa is True
    assert recomendacion.tiempo_por_ejecucion_s >= 0
    assert recomendacion.tiempo_estimado_bootstrap_s == pytest.approx(
        recomendacion.tiempo_por_ejecucion_s * 100, abs=1.0
    )
    assert recomendacion.max_k_sugerido is None


def test_chisq_lento_sugiere_max_k():
    configuracion = replace(ConfiguracionValidacion(), segundos_maximos_chisq=0.0)
    datos = preparar(dataset_en_u(n=400), "y", DecisionesUsuario())

    recomendacion = recomendar_prueba(datos, configuracion)

    assert recomendacion.prueba == CHISQ
    assert recomendacion.max_k_sugerido == 3
    assert "max_k = 3" in recomendacion.nota_tiempo
    assert recomendacion.tiempo_estimado_bootstrap_max_k_s is not None

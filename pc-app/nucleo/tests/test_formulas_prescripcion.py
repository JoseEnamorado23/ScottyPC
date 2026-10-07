"""Pruebas del explorador de fórmulas para la prescripción."""

from dataclasses import replace

import numpy as np
import pytest

from pcapp_nucleo.causal import caso_desde_test
from pcapp_nucleo.formulas import explicar_calibracion, explicar_caso
from pcapp_nucleo.prescripcion import calibrar_mu, prescribir_caso
from pcapp_nucleo.utilidades import a_diccionario_serializable

from .test_prescripcion import caso_en_riesgo, configuracion, discreto, logistico, sin_restricciones  # noqa: F401

CALIBRACION = {
    "mu": 0.01, "casos": 100, "alcanzables": 80, "no_alcanzables": 20, "casos_que_ya_cumplen": 50,
    "exito_requerido": 0.95, "advertencia": None, "nota": "Nota.",
    "rejilla": [
        {"mu": 0.001, "tasa_exito": 1.0, "exitos": 80, "evaluados": 80},
        {"mu": 0.01, "tasa_exito": 0.975, "exitos": 78, "evaluados": 80},
        {"mu": 0.1, "tasa_exito": 0.5, "exitos": 40, "evaluados": 80},
    ],
}


def test_calibracion_reproduce_la_eleccion_guardada():
    traza = explicar_calibracion(CALIBRACION)
    assert traza.mu == 0.01 and not traza.cambia
    assert [p.cumple for p in traza.puntos] == [True, True, False]
    assert [p.elegido for p in traza.puntos] == [False, True, False]


def test_calibracion_con_otro_exito():
    assert explicar_calibracion(CALIBRACION, 0.5).mu == 0.1
    exigente = explicar_calibracion(CALIBRACION, 1.0)
    assert exigente.mu == 0.001 and exigente.cambia
    ninguno = explicar_calibracion({**CALIBRACION, "rejilla": [{**p, "exitos": 1} for p in CALIBRACION["rejilla"]]})
    assert ninguno.mu == 0.001 and ninguno.advertencia
    with pytest.raises(ValueError):
        explicar_calibracion(CALIBRACION, 1.5)


def test_calibracion_real_coincide(logistico):  # noqa: F811
    datos, modelo = logistico
    c = replace(configuracion(modelo, ["X1", "X2"], "bajar", 0.3), rejilla_mu=[0.001, 0.01, 0.1])
    r = a_diccionario_serializable(calibrar_mu(modelo, datos.train.iloc[:100], c))
    assert explicar_calibracion(r).mu == r["mu"]


def test_caso_reproduce_la_prescripcion_y_descompone_la_perdida(logistico):  # noqa: F811
    datos, modelo = logistico
    c = sin_restricciones(configuracion(modelo, ["X1", "X2"], "bajar", 0.3), "X1", "X2")
    caso = caso_en_riesgo(datos, modelo)
    original = prescribir_caso(modelo, caso, c, 0.01)
    traza = explicar_caso(modelo, caso, c, 0.01)
    assert traza.despues == original.despues and traza.alcanzado == original.alcanzado
    assert not any("aproximada" in a for a in traza.avisos)
    antes, despues = traza.perdida
    assert antes.cumple is False and despues.cumple is True
    cambian = [a for a in traza.acciones if a.cambia]
    assert {a.variable for a in cambian} == {a.variable for a in original.acciones}
    costo = sum(a.penalizacion for a in traza.acciones)
    assert costo == pytest.approx(0.01 * original.costo_total, rel=1e-6)
    assert all([p.id for p in a.pasos] == ["escala", "limites", "costo"] for a in traza.acciones if a.tipo == "continua")


def test_caso_bloqueado_por_el_cambio_maximo(logistico):  # noqa: F811
    datos, modelo = logistico
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.3)
    traza = explicar_caso(modelo, caso_en_riesgo(datos, modelo), c, 0.01)
    assert not traza.alcanzado and traza.restricciones
    assert traza.perdida[1].cumple is False and "Le falta" in traza.perdida[1].resultado


def test_caso_que_ya_cumple(logistico):  # noqa: F811
    datos, modelo = logistico
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.99)
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[0]))
    traza = explicar_caso(modelo, caso, c, 0.01)
    assert traza.ya_cumple and not any(a.cambia for a in traza.acciones)
    assert all(a.penalizacion == 0 for a in traza.acciones)


def test_caso_con_acciones_discretas(discreto):  # noqa: F811
    datos, modelo = discreto
    c = configuracion(modelo, ["B", "zona", "X"], "subir", 0.8)
    for indice in datos.test.index[:30]:
        caso = caso_desde_test(modelo, datos.test, int(indice))
        original = prescribir_caso(modelo, caso, c, 0.01)
        if any(a.tipo == "discreta" for a in original.acciones):
            break
    traza = explicar_caso(modelo, caso, c, 0.01)
    assert not any("aproximada" in a for a in traza.avisos)
    discretas = {a.variable: a for a in traza.acciones if a.tipo == "discreta"}
    for accion in original.acciones:
        if accion.tipo == "discreta":
            assert discretas[accion.variable].cambia and discretas[accion.variable].despues == str(accion.despues)
    assert sum(a.penalizacion for a in traza.acciones) == pytest.approx(0.01 * original.costo_total, rel=1e-6)


def test_mu_negativo(logistico):  # noqa: F811
    datos, modelo = logistico
    with pytest.raises(ValueError):
        explicar_caso(modelo, caso_en_riesgo(datos, modelo), configuracion(modelo, ["X1"], "bajar", 0.3), -1)

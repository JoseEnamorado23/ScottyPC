"""Pruebas del explorador de fórmulas para el análisis de PC."""

import pytest

from pcapp_nucleo.formulas import explicar_analisis_pc
from pcapp_nucleo.reagregacion import reagregar

from .test_reagregacion import contenido_de, debiles


@pytest.fixture(scope="module")
def contenido():
    return contenido_de(debiles(), "Y", corridas_bootstrap=20)


def test_con_el_umbral_guardado_coincide_con_el_resultado(contenido):
    traza = explicar_analisis_pc(contenido)
    aceptadas = {frozenset((p.a, p.b)) for p in traza.pares if p.estado == "aceptada"}
    assert aceptadas == {frozenset((a["origen"], a["destino"])) for a in contenido["aristas"]}
    assert traza.cambios == [] and traza.candidatas == traza.candidatas_guardadas
    assert traza.umbral == traza.umbral_guardado


def test_las_frecuencias_se_calculan_desde_las_cuentas(contenido):
    validas = contenido["corridas"]["validas"]
    for par in explicar_analisis_pc(contenido).pares:
        i, j = contenido["variables"].index(par.a), contenido["variables"].index(par.b)
        cuentas = contenido["cuentas"]
        total = cuentas["dirigidas"][i][j] + cuentas["dirigidas"][j][i] + cuentas["sin_orientar"][i][j]
        assert par.frecuencia == round(total / validas, 4)
        assert par.pasos[0].id == "frecuencia"
        assert (par.estado == "aceptada") == (len(par.pasos) == 3)


def test_bajar_el_umbral_agrega_aristas_y_subirlo_las_quita(contenido):
    bajo = explicar_analisis_pc(contenido, 0.1)
    alto = explicar_analisis_pc(contenido, 1.0)
    assert all(c.cambio == "nueva" for c in bajo.cambios) and bajo.cambios
    assert all(c.cambio == "quitada" for c in alto.cambios)
    esperado = {frozenset((a["origen"], a["destino"])) for a in reagregar(contenido, 0.1, []).contenido["aristas"]}
    assert {frozenset((p.a, p.b)) for p in bajo.pares if p.estado == "aceptada"} == esperado
    assert bajo.umbrales[0].valor == 0.1 and bajo.umbrales[0].original == contenido["agregacion"]["umbral_frecuencia"]


def test_los_pares_aceptados_explican_orientacion_y_signo(contenido):
    aceptada = next(p for p in explicar_analisis_pc(contenido).pares if p.estado == "aceptada")
    assert [p.id for p in aceptada.pasos] == ["frecuencia", "orientacion", "signo"]
    assert aceptada.tipo in ("dirigida", "sin_orientar", "manual")
    assert aceptada.signo in (-1, 0, 1)


def test_cada_variable_tiene_categoria_y_regla(contenido):
    traza = explicar_analisis_pc(contenido)
    assert {v.nombre for v in traza.variables} == set(contenido["variables"]) - {"Y"}
    assert all(v.regla for v in traza.variables)
    directas = [v for v in traza.variables if v.categoria == "causa_directa"]
    assert all(v.camino and v.camino.endswith(r"\text{Y}") for v in directas)


def test_umbral_invalido(contenido):
    for umbral in (0, 1.5, -1):
        with pytest.raises(ValueError):
            explicar_analisis_pc(contenido, umbral)

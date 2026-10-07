"""Pruebas del explorador de fórmulas para la selección de prueba."""

import pytest

from pcapp_nucleo.formulas import explicar_seleccion_prueba
from pcapp_nucleo.formulas.seleccion_prueba import configuracion_con_umbrales
from pcapp_nucleo.preparacion import BINARIA, CONTINUA
from pcapp_nucleo.seleccion_prueba import (
    CHISQ,
    FISHERZ,
    MOTIVO_FORMA_U,
    MV_FISHERZ,
    DiagnosticoVariable,
    RecomendacionPrueba,
)


def continua(nombre, rho=0.5, p=1e-9, amplitud=1.2, motivo=None):
    return DiagnosticoVariable(
        nombre, CONTINUA, spearman=rho, p_intervalos=p,
        limites_intervalos=[-1.0, 0.0, 1.0], valores_por_intervalo=[0.1, 0.3, 0.6, 0.8],
        filas_por_intervalo=[250, 250, 250, 250], medida="tasa de la clase positiva",
        amplitud_en_desviaciones=amplitud, monotona=motivo is None, motivo=motivo,
    )


def recomendacion(diagnosticos, prueba=FISHERZ, faltantes=None, proporcion=0.0, filas=1000):
    return RecomendacionPrueba(
        prueba=prueba, motivo="", discretizacion=None,
        variables_no_monotonas=[d.nombre for d in diagnosticos if d.monotona is False],
        faltantes_restantes=faltantes or {}, proporcion_categoricas=proporcion,
        filas_train=filas, variables=len(diagnosticos), diagnosticos=diagnosticos, alternativas=[],
    )


def test_caso_lineal_elige_fisherz_y_sustituye_valores():
    traza = explicar_seleccion_prueba(recomendacion([continua("x1"), continua("x2", rho=0.3)]), k=2)
    assert traza.prueba == FISHERZ and not traza.cambia
    assert [r.estado for r in traza.reglas] == ["no_cumple", "no_cumple", "no_cumple", "decide"]
    paso = traza.formulas_prueba[0]
    assert paso.id == "fisherz_umbral" and "1000" in paso.sustituida and "-2-3" in paso.sustituida
    assert all(v.no_monotona is False for v in traza.variables)


def test_faltantes_deciden_primero_y_las_demas_quedan_sin_efecto():
    diag = [continua("x", rho=0.01, amplitud=0.9, p=1e-6)]
    traza = explicar_seleccion_prueba(recomendacion(diag, MV_FISHERZ, faltantes={"x": 3}))
    assert traza.prueba == MV_FISHERZ
    estados = [r.estado for r in traza.reglas]
    assert estados == ["decide", "no_cumple", "sin_efecto", "sin_efecto"]


def test_spearman_debil_con_dependencia_fuerte_es_no_monotona():
    diag = [continua("x", rho=0.02, p=1e-8, amplitud=0.8, motivo="Spearman débil")]
    traza = explicar_seleccion_prueba(recomendacion(diag))
    variable = traza.variables[0]
    assert variable.no_monotona and variable.criterio == "spearman_debil"
    assert traza.prueba == CHISQ


def test_mover_umbral_cambia_la_decision_sin_tocar_la_recomendacion():
    diag = [continua("x", rho=0.05, p=1e-8, amplitud=0.8)]
    rec = recomendacion(diag)
    assert explicar_seleccion_prueba(rec).prueba == CHISQ
    traza = explicar_seleccion_prueba(rec, {"spearman_debil": 0.01})
    assert traza.prueba == FISHERZ and traza.cambia is False
    traza = explicar_seleccion_prueba(rec, {"efecto_minimo_no_linealidad": 1.5})
    assert traza.prueba == FISHERZ


def test_forma_u_se_conserva_y_avisa_al_mover_umbrales():
    diag = [continua("x", rho=0.4, motivo=MOTIVO_FORMA_U)]
    rec = recomendacion(diag, CHISQ)
    traza = explicar_seleccion_prueba(rec, {"alfa_no_linealidad": 0.001})
    assert traza.variables[0].criterio == "forma_u" and traza.prueba == CHISQ
    assert traza.avisos
    assert not explicar_seleccion_prueba(rec).avisos


def test_variables_ignoradas_explican_por_que():
    diag = [DiagnosticoVariable("b", BINARIA), DiagnosticoVariable("c", CONTINUA)]
    traza = explicar_seleccion_prueba(recomendacion(diag))
    assert [v.evaluada for v in traza.variables] == [False, False]
    assert "no es continua" in traza.variables[0].resumen
    assert "menos de 6 valores distintos" in traza.variables[1].resumen


def test_mayoria_de_categoricas_usa_chisq_y_calcula_grados_de_libertad():
    traza = explicar_seleccion_prueba(recomendacion([continua("x")], proporcion=0.8), k=1)
    assert traza.prueba == CHISQ
    assert "100" not in traza.formulas_prueba[0].resultado  # gl = 16 * 5
    assert "80" in traza.formulas_prueba[0].resultado


def test_fisherz_sin_filas_suficientes():
    traza = explicar_seleccion_prueba(recomendacion([continua("x")], filas=4), k=3)
    assert traza.formulas_prueba[0].cumple is False


def test_umbrales_invalidos():
    with pytest.raises(ValueError):
        configuracion_con_umbrales({"inexistente": 1})
    with pytest.raises(ValueError):
        configuracion_con_umbrales({"spearman_debil": 5})
    with pytest.raises(ValueError):
        explicar_seleccion_prueba(recomendacion([]), k=-1)

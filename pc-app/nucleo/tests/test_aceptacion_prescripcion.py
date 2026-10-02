"""Aceptación de la prescripción con datasets reales (PC con 100 corridas + modelo causal +
prescripción). Usan la sección «prescripcion» de ``datasets_prueba/configuraciones/``. Lentas:
``pytest -m lento -s``.
"""

import json
from dataclasses import replace
from functools import lru_cache

import pytest

from pcapp_nucleo.pc_bootstrap import crear_grupo_procesos
from pcapp_nucleo.prescripcion import (
    ConfiguracionAccion,
    ObjetivoDeseado,
    ajustar_referencia,
    calibrar_mu,
    configuracion_por_defecto,
    confirmar_supuestos,
    evaluar_prescribibilidad,
    evaluar_prescriptor,
    prescribir_lote,
    que_no_cumplen,
)
from tests.test_aceptacion_modelo_causal import DATASETS, modelo

pytestmark = pytest.mark.lento


@lru_cache
def preparado(nombre: str):
    """Datos, modelo, configuración de prescripción (supuestos confirmados), μ calibrado y referencia."""
    datos, cargado, _, _ = modelo(nombre)
    ajustes = json.loads((DATASETS / "configuraciones" / f"{nombre}.json").read_text(encoding="utf-8"))["prescripcion"]
    c = configuracion_por_defecto(cargado, ajustes["modificables"])
    if "direccion" in ajustes.get("objetivo", {}):
        direccion = ajustes["objetivo"]["direccion"]
        if direccion != c.objetivo.direccion and cargado.binario:
            umbral = cargado.umbral_decision
            c = replace(c, objetivo=ObjetivoDeseado(direccion, umbral + 0.1 if direccion == "subir" else umbral - 0.1))
    acciones = dict(c.acciones)
    for variable, cambios in ajustes.get("acciones", {}).items():
        acciones[variable] = replace(acciones.get(variable, ConfiguracionAccion(variable)), **cambios)
    c = confirmar_supuestos(replace(c, acciones=acciones), list(acciones))
    referencia = ajustar_referencia(datos.train, cargado.objetivo, cargado.binario)
    with crear_grupo_procesos(4) as ejecutor:
        mu = calibrar_mu(cargado, datos.train, c, ejecutor=ejecutor).mu
    return datos, cargado, c, mu, referencia


@lru_cache
def lote_test(nombre: str):
    datos, cargado, c, mu, referencia = preparado(nombre)
    filas = que_no_cumplen(cargado, datos.test.drop(columns=[cargado.objetivo]), c)
    with crear_grupo_procesos(4) as ejecutor:
        return prescribir_lote(cargado, filas, c, mu, referencia, ejecutor=ejecutor)


def test_diabetes_solo_cambia_bmi_y_glucosa_y_la_mayoria_alcanza():
    _, _, c, mu, _ = preparado("diabetes")
    resultados = lote_test("diabetes")
    usadas = {a["variable"] for r in resultados for a in r["acciones"]}
    tasa = sum(r["alcanzado"] for r in resultados) / len(resultados)
    print(f"\nDiabetes: mu = {mu:g}; {len(resultados)} casos en riesgo; exito {tasa:.1%}; variables usadas {sorted(usadas)}")
    assert usadas <= {"BMI", "Glucose"}
    assert not usadas & {"Age", "Pregnancies", "BloodPressure"}
    assert tasa > 0.5
    for r in resultados:
        for a in r["acciones"]:
            maximo = c.acciones[a["variable"]].cambio_maximo
            assert abs(a["cambio"]) <= maximo + 1e-6


def test_diabetes_los_dos_optimizadores_tienen_exito_similar():
    datos, cargado, c, mu, referencia = preparado("diabetes")
    with crear_grupo_procesos(4) as ejecutor:
        evaluacion = evaluar_prescriptor(cargado, datos.test, c, mu, referencia, ejecutor=ejecutor)
    gradiente, genetico = evaluacion.comparacion_optimizadores
    print(f"\nDiabetes: gradiente {gradiente.tasa_exito:.1%} ({gradiente.segundos_medios:.2f} s), genetico "
          f"{genetico.tasa_exito:.1%} ({genetico.segundos_medios:.2f} s); McNemar p = {evaluacion.mcnemar['p_valor']:.3f}")
    assert abs(gradiente.tasa_exito - genetico.tasa_exito) <= 0.05
    assert evaluacion.mcnemar["p_valor"] > 0.05
    assert "INTERNA" in evaluacion.texto


def test_vino_acidez_fija_sin_camino_y_so2_libre_por_el_total():
    _, cargado, c, _, _ = preparado("vino_tinto")
    advertencia = next(p for p in evaluar_prescribibilidad(cargado, c) if p.codigo == "MODIFICABLES_SIN_CAMINO")
    assert "fixed acidity" in advertencia.variables and "fixed acidity" not in c.acciones
    resultados = lote_test("vino_tinto")
    assert not any(a["variable"] == "fixed acidity" for r in resultados for a in r["acciones"])
    con_so2 = [
        r for r in resultados
        if any(a["variable"] == "free sulfur dioxide" and a["cambio"] < 0 for a in r["acciones"])
    ]
    print(f"\nVino: {len(resultados)} casos; {len(con_so2)} reducen el SO2 libre")
    assert con_so2
    traza = {p["variable"]: p for p in con_so2[0]["traza"]}
    assert "free sulfur dioxide" in {x["padre"] for x in traza["total sulfur dioxide"]["por_padre"]}
    assert "total sulfur dioxide" in {x["padre"] for x in traza["quality"]["por_padre"]}


def test_salud_fetal_solo_bajar_contracciones_no_es_alcanzable():
    _, cargado, c, _, _ = preparado("salud_fetal")
    assert c.acciones["uterine_contractions"].direccion == "bajar"
    resultados = lote_test("salud_fetal")
    print(f"\nSalud fetal: {len(resultados)} casos en riesgo; alcanzados {sum(r['alcanzado'] for r in resultados)}")
    assert resultados and not any(r["alcanzado"] for r in resultados)
    for r in resultados:
        assert all(a["cambio"] <= 0 for a in r["acciones"])  # nunca aumentar las contracciones
        restricciones = {(x["variable"], x["restriccion"]) for x in r["restricciones_activas"]}
        assert ("uterine_contractions", "direccion") in restricciones
        assert "Lo impiden" in r["explicacion"]


def test_sin_variables_prescriptivas_queda_bloqueado():
    _, cargado, _, _, _ = preparado("diabetes")
    problemas = evaluar_prescribibilidad(cargado, configuracion_por_defecto(cargado, []))
    bloqueo = next(p for p in problemas if p.codigo == "SIN_PRESCRIPTIVAS")
    assert bloqueo.severidad == "bloqueante"
    assert bloqueo.mensaje.startswith("Con estos datos no hay variables prescriptivas")

"""Aceptación del modelo causal con datasets reales (PC con 100 corridas + modelo causal).

Usan las configuraciones reproducibles de ``datasets_prueba/configuraciones/`` (decisiones
completas, configuración de PC con niveles y orientaciones manuales justificadas). Son lentas:
se ejecutan con ``pytest -m lento -s``.
"""

import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from pcapp_nucleo.carga import cargar_dataset
from pcapp_nucleo.causal import (
    ErrorModeloCausal,
    Intervencion,
    caso_desde_test,
    construir_modelo,
    contrafactual,
    evaluar_aplicabilidad,
    modelo_desde_diccionario,
)
from pcapp_nucleo.pc_bootstrap import agregar, ejecutar_bootstrap
from pcapp_nucleo.pc_config import configuracion_desde_diccionario
from pcapp_nucleo.preparacion import decisiones_desde_diccionario, preparar
from pcapp_nucleo.seleccion_prueba import recomendar_prueba
from pcapp_nucleo.utilidades import a_diccionario_serializable

pytestmark = pytest.mark.lento

DATASETS = Path(__file__).resolve().parents[2] / "datasets_prueba"


@lru_cache
def analizar(nombre: str):
    """Datos preparados, bootstrap, configuración y diagnósticos de un dataset."""
    ruta = DATASETS / "configuraciones" / f"{nombre}.json"
    configuracion = json.loads(ruta.read_text(encoding="utf-8"))
    archivo = DATASETS / configuracion["dataset"]
    if not archivo.is_file():
        pytest.skip(f"Falta {configuracion['dataset']} en datasets_prueba/.")
    datos = preparar(
        cargar_dataset(archivo, hoja=configuracion["hoja"]), configuracion["objetivo"],
        decisiones_desde_diccionario(configuracion["decisiones"]),
    )
    pc = configuracion_desde_diccionario(configuracion["configuracion_pc"])
    bootstrap = ejecutar_bootstrap(datos, pc)
    diagnosticos = a_diccionario_serializable(recomendar_prueba(datos, estimar=False).diagnosticos)
    return datos, bootstrap, pc, diagnosticos


def contenido(nombre: str, **cambios_pc) -> dict:
    """Resultado como en ``resultado.json`` (variables, aristas y corridas)."""
    datos, bootstrap, pc, _ = analizar(nombre)
    grafo = agregar(bootstrap, datos, replace(pc, **cambios_pc))
    return {
        "variables": grafo.variables,
        "aristas": a_diccionario_serializable(grafo.aristas),
        "corridas": {"completo": bootstrap.completo},
    }


@lru_cache
def modelo(nombre: str):
    datos, _, _, diagnosticos = analizar(nombre)
    modelo_json, evaluacion = construir_modelo(contenido(nombre), datos, diagnosticos)
    return datos, modelo_desde_diccionario(modelo_json, datos.train), modelo_json, evaluacion


def caso(nombre: str):
    datos, cargado, _, _ = modelo(nombre)
    return cargado, caso_desde_test(cargado, datos.test, int(datos.test.index[0]))


# --- Diabetes -------------------------------------------------------------------------------------


def test_diabetes_causas_y_propagacion_de_la_edad():
    _, cargado, _, _ = modelo("diabetes")
    assert set(cargado.padres["Outcome"]) == {"Glucose", "BMI", "Pregnancies"}
    assert "Age" not in cargado.padres["Outcome"]

    modelo_cargado, c = caso("diabetes")
    r = contrafactual(modelo_cargado, c, [Intervencion("Age", "desplazar", 10)])
    traza = {p.variable: p for p in r.traza}
    print(f"\nDiabetes, Age + 10: {r.antes:.4f} -> {r.despues:.4f}; traza: {list(traza)}")
    assert r.cambio != 0.0
    assert {c.padre for c in traza["Glucose"].por_padre} == {"Age"}
    # Age llega al objetivo solo a través de sus hijos (Glucose y, con Age → Pregnancies, Pregnancies).
    padres_del_efecto = {c.padre for c in traza["Outcome"].por_padre}
    assert "Glucose" in padres_del_efecto and "Age" not in padres_del_efecto
    assert padres_del_efecto <= {"Glucose", "Pregnancies"}


def test_diabetes_presion_sin_efecto():
    modelo_cargado, c = caso("diabetes")
    r = contrafactual(modelo_cargado, c, [Intervencion("BloodPressure", "desplazar", -10)])
    assert r.cambio == 0.0 and all(v.cambio == 0.0 for v in r.valores)
    assert "SIN_EFECTO" in {a.codigo for a in r.avisos}


def test_diabetes_sin_orientar_queda_bloqueado_con_un_mensaje_claro():
    datos, _, _, _ = analizar("diabetes")
    sin_orientar = contenido("diabetes", orientaciones_manuales=[])
    problemas = evaluar_aplicabilidad(sin_orientar, datos)
    aristas = [p for p in problemas if p.codigo == "ARISTA_SIN_ORIENTAR"]
    assert aristas and all(p.severidad == "bloqueante" and p.destino == "resultados" for p in aristas)
    assert any("Pregnancies" in p.variables and "Age" in p.variables for p in aristas)
    assert all(p.accion.startswith("Oriente la arista") for p in aristas)
    with pytest.raises(ErrorModeloCausal):
        construir_modelo(sin_orientar, datos)


# --- Vino tinto ------------------------------------------------------------------------------------


def test_vino_tinto_causas_y_dioxido_de_azufre():
    _, cargado, _, _ = modelo("vino_tinto")
    assert set(cargado.padres["quality"]) == {"volatile acidity", "total sulfur dioxide", "sulphates", "alcohol"}
    assert "free sulfur dioxide" in cargado.padres["total sulfur dioxide"]

    modelo_cargado, c = caso("vino_tinto")
    r = contrafactual(modelo_cargado, c, [Intervencion("free sulfur dioxide", "desplazar", -10)])
    valores = {v.variable: v for v in r.valores}
    traza = {p.variable: p for p in r.traza}
    print(f"\nVino, free SO2 - 10: total SO2 {valores['total sulfur dioxide'].cambio:+.2f}; "
          f"P(buena) {r.antes:.4f} -> {r.despues:.4f}")
    assert valores["total sulfur dioxide"].cambio < 0
    assert r.cambio > 0
    assert {c.padre for c in traza["total sulfur dioxide"].por_padre} == {"free sulfur dioxide"}
    assert {c.padre for c in traza["quality"].por_padre} == {"total sulfur dioxide"}


# --- Salud fetal -----------------------------------------------------------------------------------


def test_salud_fetal_monotonia_y_costo_de_la_parsimonia():
    _, _, modelo_json, evaluacion = modelo("salud_fetal")
    monotonia = {d["padre"]: d for d in modelo_json["monotonia"]}
    variabilidad = monotonia["mean_value_of_short_term_variability"]
    print(f"\nSalud fetal: {variabilidad}; referencia: {evaluacion['referencia']['comparacion']}")
    assert variabilidad["restriccion"] is None and variabilidad["origen"] == "automatico"
    assert "no monótona" in variabilidad["motivo"]
    assert evaluacion["referencia"]["advertencia"]
    assert "COSTO_PARSIMONIA" in {a["codigo"] for a in modelo_json["advertencias"]}

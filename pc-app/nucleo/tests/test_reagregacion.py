"""Reagregación sin volver a ejecutar PC, migración de resultados antiguos, advertencias de
interpretación e informe HTML."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo.caracterizacion import caracterizar
from pcapp_nucleo.exportacion import resultado_a_diccionario
from pcapp_nucleo.informe import etiqueta_version, informe_html, resumen_decisiones
from pcapp_nucleo.pc_bootstrap import agregar, ejecutar_bootstrap, matriz_spearman
from pcapp_nucleo.pc_config import ErrorConfiguracionPC, OrientacionManual, configuracion_por_defecto
from pcapp_nucleo.preparacion import DecisionesUsuario, preparar
from pcapp_nucleo.reagregacion import (
    ErrorReagregacion,
    avisos_resultado,
    escribir_reagregacion,
    migrar_resultado,
    reagregar,
)

DATASETS = Path(__file__).resolve().parents[2] / "datasets_prueba"
COMPARADAS = ("aristas", "ciclos", "caracterizacion", "advertencias")


def contenido_de(dataframe, objetivo, **cambios):
    """``resultado.json`` de un análisis completo (sin escribir archivos)."""
    datos = preparar(dataframe, objetivo, DecisionesUsuario(normalizar=False))
    base = configuracion_por_defecto(list(datos.train.columns), datos.objetivo)
    conf = replace(base, **{"corridas_bootstrap": 20, "procesos": 1, **cambios})
    resultado = ejecutar_bootstrap(datos, conf)
    spearman = matriz_spearman(datos.train, resultado.variables)
    grafo = agregar(resultado, datos, conf, spearman)
    caracterizacion = caracterizar(grafo, resultado, conf.modificables, [["A", "B"]])
    contenido = resultado_a_diccionario(conf, datos.receta, resultado, grafo, caracterizacion, spearman)
    return json.loads(json.dumps(contenido))  # como al leerlo de resultado.json


def debiles():
    """Relaciones de distinta fuerza con pocos casos: las frecuencias de las aristas varían."""
    rng = np.random.default_rng(12)
    n = 160
    a = rng.normal(size=n)
    b = 0.5 * a + rng.normal(size=n)
    c = 0.25 * b + rng.normal(size=n)
    d = 0.2 * a + 0.2 * c + rng.normal(size=n)
    y = 0.6 * b + 0.18 * d + rng.normal(size=n)
    return pd.DataFrame({"A": a, "B": b, "C": c, "D": d, "Y": y})


def cadena():
    rng = np.random.default_rng(1)
    a = rng.normal(size=1500)
    b = a + rng.normal(size=1500)
    return pd.DataFrame({"A": a, "B": b, "C": b + rng.normal(size=1500)})


@pytest.fixture(scope="module")
def contenido():
    return contenido_de(debiles(), "Y", modificables=["B", "C"])


def pares(contenido):
    return {frozenset((a["origen"], a["destino"])) for a in contenido["aristas"]}


def test_con_el_umbral_original_reproduce_exactamente_el_resultado(contenido):
    original = contenido["configuracion"]

    nuevo = reagregar(contenido, original["umbral_frecuencia"], original["orientaciones_manuales"]).contenido

    assert nuevo == contenido


def test_subir_el_umbral_nunca_agrega_aristas(contenido):
    umbrales = [round(u, 2) for u in np.arange(0.05, 1.0001, 0.05)]
    esqueletos = [pares(reagregar(contenido, u, []).contenido) for u in umbrales]

    for menor, mayor in zip(esqueletos, esqueletos[1:]):
        assert mayor <= menor
    assert len(esqueletos[0]) > len(esqueletos[-1])  # el umbral sí cambia el grafo


def test_bajar_el_umbral_conserva_frecuencias_y_spearman(contenido):
    bajo = reagregar(contenido, 0.2, []).contenido
    originales = {frozenset((a["origen"], a["destino"])): a for a in contenido["aristas"]}

    for arista in bajo["aristas"]:
        previa = originales.get(frozenset((arista["origen"], arista["destino"])))
        if previa:
            assert arista == previa
        assert arista["spearman"] is not None
    assert bajo["agregacion"]["umbral_frecuencia"] == 0.2
    assert bajo["configuracion"] == contenido["configuracion"]  # la configuración no cambia


def test_orientacion_manual_contraria_a_los_niveles_se_rechaza():
    contenido = contenido_de(cadena(), "C")
    contraria = OrientacionManual("C", "A", "El objetivo causa A")

    with pytest.raises(ErrorConfiguracionPC, match="contradice los niveles") as error:
        reagregar(contenido, 0.6, [contraria])

    assert error.value.problemas[0].campo == "orientaciones_manuales.0"


def test_orientacion_manual_de_una_arista_sin_orientar():
    contenido = contenido_de(cadena(), "C")
    assert ("A", "B", "sin_orientar") in {(a["origen"], a["destino"], a["tipo"]) for a in contenido["aristas"]}

    nuevo = reagregar(contenido, 0.6, [{"origen": "B", "destino": "A", "justificacion": "B se mide antes"}])

    manual = next(a for a in nuevo.contenido["aristas"] if a["tipo"] == "manual")
    assert (manual["origen"], manual["destino"], manual["justificacion"]) == ("B", "A", "B se mide antes")
    assert nuevo.contenido["agregacion"]["orientaciones_manuales"] == [
        {"origen": "B", "destino": "A", "justificacion": "B se mide antes"}
    ]


@pytest.mark.parametrize(
    "umbral, orientaciones, campo",
    [
        (0, [], "umbral_frecuencia"),
        (1.2, [], "umbral_frecuencia"),
        (0.6, [{"origen": "A", "destino": "B", "justificacion": " "}], "orientaciones_manuales.0.justificacion"),
        (0.6, [{"origen": "A", "destino": "X", "justificacion": "x"}], "orientaciones_manuales.0"),
        (0.6, [{"origen": "A", "destino": "B", "justificacion": "x"},
               {"origen": "B", "destino": "A", "justificacion": "y"}], "orientaciones_manuales.1"),
    ],
)
def test_umbral_y_orientaciones_no_validos(umbral, orientaciones, campo):
    contenido = contenido_de(cadena(), "C")

    with pytest.raises(ErrorReagregacion) as error:
        reagregar(contenido, umbral, orientaciones)

    assert [p.campo for p in error.value.problemas] == [campo]


def test_escribe_los_archivos_de_la_version(tmp_path, contenido):
    rutas = escribir_reagregacion(tmp_path, reagregar(contenido, 0.3, []))

    guardado = json.loads(rutas["resultado.json"].read_text(encoding="utf-8"))
    assert guardado["agregacion"]["umbral_frecuencia"] == 0.3
    assert len(pd.read_csv(rutas["aristas.csv"])) == len(guardado["aristas"])
    assert rutas["grafo.png"].stat().st_size > 10_000


# --- Migración -----------------------------------------------------------------------------------


def test_migrar_un_resultado_sin_cuentas_recupera_las_cuentas_exactas(contenido):
    antiguo = {k: v for k, v in contenido.items() if k not in ("cuentas", "spearman", "agregacion")}
    variables = contenido["variables"]
    spearman = [[None] * len(variables) for _ in variables]  # sin datos: solo el ρ de las aristas

    migrado = migrar_resultado(antiguo, spearman)

    assert migrado["cuentas"]["dirigidas"] == contenido["cuentas"]["dirigidas"]
    assert migrado["cuentas"]["sin_orientar"] == contenido["cuentas"]["sin_orientar"]
    assert migrado["agregacion"] == contenido["agregacion"]
    original = contenido["configuracion"]["umbral_frecuencia"]
    assert reagregar(migrado, original, []).contenido["aristas"] == contenido["aristas"]


def test_resultado_migrado_de_la_fase_6_con_su_umbral_reproduce_el_original():
    """``datasets_prueba/diabetes_pc`` (salida de la CLI, excluida de git) se generó antes de
    guardar las cuentas. Sin esos archivos se omite: la migración también la cubren
    ``test_migrar_un_resultado_sin_cuentas_recupera_las_cuentas_exactas`` y el sidecar."""
    ruta, ruta_train = DATASETS / "diabetes_pc" / "resultado.json", DATASETS / "diabetes_train.csv"
    if not ruta.is_file() or not ruta_train.is_file():
        pytest.skip("Faltan datasets_prueba/diabetes_pc/resultado.json o diabetes_train.csv (salidas de la CLI).")
    original = json.loads(ruta.read_text(encoding="utf-8"))
    assert "cuentas" not in original
    train = pd.read_csv(ruta_train)

    migrado = migrar_resultado(original, matriz_spearman(train, original["variables"]))
    nuevo = reagregar(migrado, original["configuracion"]["umbral_frecuencia"], []).contenido

    for clave in COMPARADAS:
        assert nuevo[clave] == original[clave], clave
    directas = {v["variable"] for v in nuevo["caracterizacion"]["variables"] if v["categoria"] == "causa_directa"}
    assert directas == {"Pregnancies", "Glucose", "BMI"}


# --- Advertencias ---------------------------------------------------------------------------------


def test_aristas_debiles_y_aristas_por_bajar_el_umbral(contenido):
    avisos = {a.codigo: a for a in avisos_resultado(contenido)}
    total = {
        frozenset((a["origen"], a["destino"])): a["frecuencia_total"] for a in reagregar(contenido, 0.4, []).contenido["aristas"]
    }
    umbral = contenido["configuracion"]["umbral_frecuencia"]
    esperadas = {par for par, f in total.items() if f < umbral}
    assert esperadas, "el dataset sintético debe tener aristas débiles"
    listadas = [p for codigo in ("ARISTAS_DEBILES", "ARISTAS_DEBILES_OBJETIVO") for p in getattr(avisos.get(codigo), "pares", [])]
    assert {frozenset((p.variable_a, p.variable_b)) for p in listadas} == esperadas
    assert all(p.con_objetivo == ("Y" in (p.variable_a, p.variable_b)) for p in listadas)

    bajo = reagregar(contenido, 0.4, []).contenido
    avisos_bajo = {a.codigo: a for a in avisos_resultado(bajo)}
    anadidas = avisos_bajo["ARISTAS_POR_UMBRAL_BAJO"]
    assert {frozenset((p.variable_a, p.variable_b)) for p in anadidas.pares} == esperadas
    assert "ARISTAS_DEBILES" not in avisos_bajo and "ARISTAS_DEBILES_OBJETIVO" not in avisos_bajo


def test_avisos_de_revision_grupos_y_prueba(contenido):
    hallazgos = [{"tipo": "tamano_efectivo_insuficiente", "columnas_involucradas": ["Y"], "detalle": "Pocos casos."}]

    codigos = [a.codigo for a in avisos_resultado(contenido, hallazgos, "kci")]

    assert {"GRUPO_REDUNDANTE", "TAMANO_EFECTIVO", "PRUEBA_DISTINTA"} <= set(codigos)
    assert "PRUEBA_DISTINTA" not in [a.codigo for a in avisos_resultado(contenido, [], "fisherz")]


# --- Informe ---------------------------------------------------------------------------------------


def test_informe_html_autocontenido(contenido):
    ajustado = reagregar(contenido, 0.3, [{"origen": "A", "destino": "B", "justificacion": "A <antes> de B"}]).contenido
    receta = {
        "origen": {"archivo": "datos.csv", "hoja": None, "sha256": "abc123"},
        "objetivo": "Y", "tipo_objetivo": "continuo",
        "decisiones": {"columnas_excluidas": ["id"], "faltantes": {"C": {"imputacion": "mediana"}}},
        "separacion": {"tipo": "estratificada", "proporcion_test": 0.3, "semilla": 42},
        "separacion_aplicada": {"tipo": "estratificada", "filas_train": 112, "filas_test": 48},
    }
    versiones = [
        {"version": 1, "base": None, "umbral_frecuencia": 0.6, "orientaciones_manuales": [], "creada_en": "2026-09-28T10:00:00"},
        {"version": 2, "base": 1, "umbral_frecuencia": 0.3,
         "orientaciones_manuales": ajustado["agregacion"]["orientaciones_manuales"], "creada_en": "2026-09-28T10:05:00"},
    ]

    texto = informe_html(ajustado, receta, avisos_resultado(ajustado), b"\x89PNG-falso", versiones, 2, "Mi proyecto", "hoy")

    assert "data:image/png;base64," in texto
    assert "http://" not in texto and "https://" not in texto and "<script" not in texto
    for fragmento in ("abc123", "datos.csv", "Historial de versiones", "versión 2", "(exportada)",
                      "Ajustada: umbral 0,3, original 0,6", "Umbral original", "A &lt;antes&gt; de B",
                      "Candidatas prescriptivas", "imputar con la mediana"):
        assert fragmento in texto, fragmento


def test_resumen_de_decisiones():
    lineas = resumen_decisiones({"eliminar_duplicados": True, "logaritmos": ["Insulin"], "normalizar": False})

    assert [(l.concepto, l.detalle) for l in lineas] == [
        ("Filas duplicadas", "se eliminan"), ("Logaritmo", "Insulin"), ("Normalización min–max", "no"),
    ]


def test_etiqueta_de_version():
    assert etiqueta_version(0.6, 0.6, 0) == "Original"
    assert etiqueta_version(0.45, 0.6, 0) == "Ajustada: umbral 0,45, original 0,6"
    assert etiqueta_version(0.45, 0.6, 2) == "Ajustada: umbral 0,45, original 0,6; 2 orientaciones manuales"
    assert etiqueta_version(0.6, 0.6, 1) == "Ajustada: 1 orientación manual; umbral original 0,6"

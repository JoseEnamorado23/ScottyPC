"""Aceptación de PC con bootstrap sobre datasets reales (100 corridas).

Son pruebas lentas: se excluyen de ``pytest`` y se ejecutan con
``pytest -m lento -s`` (``-s`` muestra los tiempos). Usan tolerancia porque
el resultado del bootstrap depende de la semilla.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.caracterizacion import CAUSA_DIRECTA, SIN_CAMINO, caracterizar
from pcapp_nucleo.carga import cargar_dataset
from pcapp_nucleo.pc_bootstrap import agregar, ejecutar_bootstrap
from pcapp_nucleo.pc_config import ConfiguracionPC
from pcapp_nucleo.plantilla import generar_plantilla
from pcapp_nucleo.preparacion import Codificacion, TratamientoColumna, preparar

pytestmark = pytest.mark.lento

DATASETS = Path(__file__).resolve().parents[2] / "datasets_prueba"


def cargar(nombre):
    ruta = DATASETS / nombre
    if not ruta.is_file():
        pytest.skip(f"Falta {nombre} en datasets_prueba/.")
    return cargar_dataset(ruta)


def preparar_con_plantilla(dataframe, objetivo, ajustar):
    decisiones = ajustar(generar_plantilla(analizar_dataset(dataframe, objetivo).informe))
    return preparar(dataframe, objetivo, decisiones)


def analizar(datos, configuracion, nombre):
    resultado = ejecutar_bootstrap(datos, configuracion)
    grafo = agregar(resultado, datos, configuracion)
    categorias = {v.variable: v.categoria for v in caracterizar(grafo, resultado, []).variables}
    directas = {v for v, c in categorias.items() if c == CAUSA_DIRECTA}
    print(
        f"\n{nombre}: {resultado.tiempo_s:.1f} s en modo {resultado.ejecucion.modo_usado} "
        f"({resultado.ejecucion.procesos} proceso(s)); "
        f"{resultado.corridas_validas} corridas válidas; causas directas: {sorted(directas)}"
    )
    return categorias, directas


def test_vino_tinto():
    dataframe = cargar("winequality-red.csv")

    def ajustar(decisiones):
        grupos = {str(q): int(q > 5) for q in range(3, 9)}
        return replace(
            decisiones,
            eliminar_duplicados=True,
            codificaciones={**decisiones.codificaciones, "quality": Codificacion("agrupacion", grupos=grupos)},
        )

    datos = preparar_con_plantilla(dataframe, "quality", ajustar)
    quimica = [c for c in datos.train.columns if c not in ("density", "pH", "quality")]
    configuracion = ConfiguracionPC(prueba="fisherz", niveles=[quimica, ["density", "pH"], ["quality"]])

    _, directas = analizar(datos, configuracion, "Vino tinto")

    esperadas = {"volatile acidity", "total sulfur dioxide", "sulphates", "alcohol"}
    assert len(esperadas & directas) >= 3


CEROS_DIABETES = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


def test_diabetes():
    dataframe = cargar("diabetes.csv")

    def ajustar(decisiones):
        faltantes = dict.fromkeys(CEROS_DIABETES, TratamientoColumna(ceros_como_faltantes=True))
        return replace(decisiones, faltantes={**decisiones.faltantes, **faltantes})

    datos = preparar_con_plantilla(dataframe, "Outcome", ajustar)
    configuracion = ConfiguracionPC(
        prueba="mv_fisherz",
        niveles=[
            ["Age", "Pregnancies", "DiabetesPedigreeFunction"],
            ["BMI", "SkinThickness", "BloodPressure"],
            ["Glucose", "Insulin"],
            ["Outcome"],
        ],
    )

    categorias, directas = analizar(datos, configuracion, "Diabetes")

    assert len({"Glucose", "BMI", "Pregnancies"} & directas) >= 2
    assert categorias["BloodPressure"] == SIN_CAMINO


def test_salud_fetal():
    dataframe = cargar("fetal_health.csv")

    def ajustar(decisiones):
        agrupacion = Codificacion("agrupacion", grupos={"1": 0, "2": 1, "3": 1})
        return replace(decisiones, codificaciones={**decisiones.codificaciones, "fetal_health": agrupacion})

    datos = preparar_con_plantilla(dataframe, "fetal_health", ajustar)
    variables = [c for c in datos.train.columns if c != "fetal_health"]
    configuracion = ConfiguracionPC(prueba="chisq", max_k=3, niveles=[variables, ["fetal_health"]])

    _, directas = analizar(datos, configuracion, "Salud fetal")

    esperadas = {
        "accelerations", "abnormal_short_term_variability", "mean_value_of_short_term_variability",
        "prolongued_decelerations", "histogram_min", "uterine_contractions",
        "percentage_of_time_with_abnormal_long_term_variability",
    }
    assert len(esperadas & directas) >= 5

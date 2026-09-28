"""Criterios de aceptación con los datasets reales de datasets_prueba/.

Cada prueba se omite si su archivo no está disponible.
"""

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.carga import cargar_dataset
from pcapp_nucleo.modelos import Severidad, TipoHallazgo
from pcapp_nucleo.plantilla import generar_plantilla
from pcapp_nucleo.preparacion import ConfiguracionSeparacion, TratamientoColumna, preparar
from pcapp_nucleo.seleccion_prueba import recomendar_prueba

DATASETS = Path(__file__).resolve().parents[2] / "datasets_prueba"
DENGUE = "Dengue Dataset 2023-2025.xlsx"
PEDIATRICO = "MASTER_CHART_F1000Research.xlsx"
OBJETIVO_PEDIATRICO = "GROUPS: DENGUE FEVER OR COMPLICATED DENGUE "


def cargar(nombre):
    ruta = DATASETS / nombre
    if not ruta.is_file():
        pytest.skip(f"Falta {nombre} en datasets_prueba/.")
    return cargar_dataset(ruta)


def revisar(nombre, objetivo):
    dataframe = cargar(nombre)
    resultado = analizar_dataset(dataframe, objetivo)
    assert resultado.valido
    return dataframe, resultado.informe


def hallazgos(informe, tipo):
    return {tuple(h.columnas_involucradas): h for h in informe.hallazgos if h.tipo == tipo}


def recomendar(nombre, objetivo, ajustar=None):
    dataframe, informe = revisar(nombre, objetivo)
    decisiones = generar_plantilla(informe)
    if ajustar:
        decisiones = ajustar(decisiones)
    return recomendar_prueba(preparar(dataframe, objetivo, decisiones), estimar=False)


def test_dengue_fecha_division_temporal_y_unidades():
    dataframe, informe = revisar(DENGUE, "Outcome")

    fecha = hallazgos(informe, TipoHallazgo.POSIBLE_FECHA)[("Date",)]
    assert fecha.evidencia["formato"] == "%d.%m.%y"
    assert ("Temp",) in hallazgos(informe, TipoHallazgo.POSIBLE_MEZCLA_UNIDADES)
    decisiones = generar_plantilla(informe)
    assert "Date" in decisiones.columnas_fecha_disponibles
    datos = preparar(
        dataframe, "Outcome", decisiones,
        separacion=ConfiguracionSeparacion(tipo="temporal", columna_fecha="Date"),
    )
    fechas = pd.to_datetime(dataframe["Date"], format="%d.%m.%y")
    assert fechas[datos.receta.indices_train].max() < fechas[datos.receta.indices_test].min()
    assert "Date" not in datos.train.columns


def test_dengue_pediatrico():
    _, informe = revisar(PEDIATRICO, OBJETIVO_PEDIATRICO)

    ferritina = hallazgos(informe, TipoHallazgo.FALTANTES_DEPENDIENTES_OBJETIVO)[
        ("FERRITIN", OBJETIVO_PEDIATRICO)
    ]
    assert ferritina.severidad == Severidad.ALTA
    assert ferritina.evidencia["diferencia_puntos"] >= 30
    grupos = hallazgos(informe, TipoHallazgo.GRUPO_REDUNDANTE)
    assert any({" HB", "PCV"} <= set(columnas) for columnas in grupos)
    assert hallazgos(informe, TipoHallazgo.TAMANO_EFECTIVO_INSUFICIENTE)


def test_salud_fetal_recomienda_chisq_por_relacion_en_u():
    recomendacion = recomendar("fetal_health.csv", "fetal_health")

    assert recomendacion.prueba == "chisq"
    assert "mean_value_of_short_term_variability" in recomendacion.variables_no_monotonas
    assert "mean_value_of_short_term_variability" in recomendacion.motivo


def test_vino_tinto_recomienda_fisherz():
    assert recomendar("winequality-red.csv", "quality").prueba == "fisherz"


def test_vino_blanco_tiene_relaciones_no_monotonas():
    recomendacion = recomendar("winequality-white.csv", "quality")

    assert recomendacion.prueba == "chisq"
    assert {"citric acid", "residual sugar", "free sulfur dioxide"} <= set(recomendacion.variables_no_monotonas)


CEROS_DIABETES = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


@pytest.mark.parametrize("imputacion, prueba", [(None, "mv_fisherz"), ("mediana", "fisherz")])
def test_diabetes_ceros_como_faltantes(imputacion, prueba):
    def marcar_ceros(decisiones):
        tratamiento = TratamientoColumna(ceros_como_faltantes=True, imputacion=imputacion)
        return replace(decisiones, faltantes={**decisiones.faltantes, **dict.fromkeys(CEROS_DIABETES, tratamiento)})

    _, informe = revisar("diabetes.csv", "Outcome")
    confirmar = generar_plantilla(informe).acciones_hallazgos
    assert all(confirmar[f"ceros_sospechosos:{c}"].requiere_confirmacion for c in CEROS_DIABETES)

    assert recomendar("diabetes.csv", "Outcome", marcar_ceros).prueba == prueba


def test_nsw_objetivo_con_faltantes_no_es_valido():
    dataframe = cargar("NSW_AFDC_CS.csv")

    assert not analizar_dataset(dataframe, "re78").valido


def test_nsw_flujo_completo_con_objetivo_sin_faltantes():
    dataframe, informe = revisar("NSW_AFDC_CS.csv", "nodegree")

    datos = preparar(dataframe, "nodegree", generar_plantilla(informe))
    recomendacion = recomendar_prueba(datos, estimar=False)

    assert len(datos.train) + len(datos.test) <= len(dataframe)
    assert recomendacion.prueba in {"fisherz", "chisq", "mv_fisherz"}

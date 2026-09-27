"""Pruebas de las reglas de validación de DataFrames."""

import json

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.modelos import CodigoValidacion
from pcapp_nucleo.utilidades import a_diccionario_serializable
from pcapp_nucleo.validacion import validar_archivo, validar_dataset

from .conftest import OBJETIVO, construir_dataset


def codigos_error(resultado):
    return [p.codigo for p in resultado.errores]


def test_dataset_valido(dataset_valido):
    resultado = validar_dataset(dataset_valido, OBJETIVO)

    assert resultado.valido is True
    assert resultado.errores == []


def test_filas_insuficientes():
    resultado = validar_dataset(construir_dataset(filas=99), OBJETIVO)

    assert resultado.valido is False
    assert codigos_error(resultado) == [CodigoValidacion.FILAS_INSUFICIENTES]
    assert resultado.errores[0].mensaje == (
        "El dataset contiene 99 filas y se requieren al menos 100."
    )


def test_minimo_filas_usa_configuracion():
    configuracion = ConfiguracionValidacion(minimo_filas=10)

    resultado = validar_dataset(construir_dataset(filas=20), OBJETIVO, configuracion)

    assert resultado.valido is True


def test_columnas_excesivas():
    # 50 columnas extra + objetivo = 51 columnas.
    resultado = validar_dataset(construir_dataset(columnas_extra=50), OBJETIVO)

    assert codigos_error(resultado) == [CodigoValidacion.COLUMNAS_EXCESIVAS]
    assert "51 columnas" in resultado.errores[0].mensaje


def test_cincuenta_columnas_son_aceptadas():
    resultado = validar_dataset(construir_dataset(columnas_extra=49), OBJETIVO)

    assert resultado.valido is True


def test_objetivo_inexistente(dataset_valido):
    resultado = validar_dataset(dataset_valido, "diabetes")

    assert codigos_error(resultado) == [CodigoValidacion.OBJETIVO_INEXISTENTE]
    assert resultado.errores[0].mensaje == (
        "La variable objetivo 'diabetes' no existe en el dataset."
    )


def test_objetivo_con_faltantes():
    dataframe = construir_dataset(filas=150)
    dataframe[OBJETIVO] = dataframe[OBJETIVO].astype(float)
    dataframe.loc[:11, OBJETIVO] = np.nan

    resultado = validar_dataset(dataframe, OBJETIVO)

    assert codigos_error(resultado) == [CodigoValidacion.OBJETIVO_CON_FALTANTES]
    assert resultado.errores[0].mensaje == (
        "La variable objetivo contiene 12 valores faltantes (8.0 %)."
    )
    assert resultado.errores[0].evidencia == {"faltantes": 12, "porcentaje_faltantes": 8.0}


def test_objetivo_constante():
    dataframe = construir_dataset()
    dataframe[OBJETIVO] = 1

    resultado = validar_dataset(dataframe, OBJETIVO)

    assert codigos_error(resultado) == [CodigoValidacion.OBJETIVO_CONSTANTE]


@pytest.mark.parametrize("nombre", ["Unnamed: 1", "", "   ", None, np.nan])
def test_columnas_sin_nombre(nombre):
    dataframe = construir_dataset()
    dataframe.columns = ["x0", nombre, "x2", OBJETIVO]

    resultado = validar_dataset(dataframe, OBJETIVO)

    assert codigos_error(resultado) == [CodigoValidacion.COLUMNAS_SIN_NOMBRE]
    assert resultado.errores[0].evidencia == {"posiciones": [2]}
    assert "posición 2" in resultado.errores[0].mensaje


def test_columnas_repetidas_no_se_renombran():
    dataframe = construir_dataset()
    dataframe.columns = ["edad", "sexo", "edad", OBJETIVO]

    resultado = validar_dataset(dataframe, OBJETIVO)

    assert codigos_error(resultado) == [CodigoValidacion.COLUMNAS_REPETIDAS]
    assert resultado.errores[0].columnas == ["edad"]
    assert list(dataframe.columns) == ["edad", "sexo", "edad", OBJETIVO]


def test_dataset_vacio():
    resultado = validar_dataset(pd.DataFrame(columns=["a", OBJETIVO]), OBJETIVO)

    assert codigos_error(resultado) == [CodigoValidacion.DATASET_VACIO]


def test_advertencias_no_bloquean():
    dataframe = construir_dataset()
    dataframe.columns = ["x0", " x1 ", "x2", OBJETIVO]

    resultado = validar_dataset(dataframe, OBJETIVO)

    assert resultado.valido is True
    assert [p.codigo for p in resultado.advertencias] == [
        CodigoValidacion.NOMBRES_CON_ESPACIOS
    ]


def test_varios_errores_se_informan_juntos():
    dataframe = construir_dataset(filas=50)
    dataframe[OBJETIVO] = 0

    resultado = validar_dataset(dataframe, OBJETIVO)

    assert set(codigos_error(resultado)) == {
        CodigoValidacion.FILAS_INSUFICIENTES,
        CodigoValidacion.OBJETIVO_CONSTANTE,
    }


def test_no_modifica_el_dataframe():
    dataframe = construir_dataset(filas=99)
    dataframe.columns = ["x0", "", "x0", OBJETIVO]
    dataframe[OBJETIVO] = dataframe[OBJETIVO].astype(float)
    dataframe.loc[0, OBJETIVO] = np.nan
    copia = dataframe.copy()

    validar_dataset(dataframe, OBJETIVO)

    pd.testing.assert_frame_equal(dataframe, copia)


def test_resultado_serializable_a_json():
    dataframe = construir_dataset(filas=80)
    dataframe.columns = ["x0", "x0", "Unnamed: 2", OBJETIVO]
    dataframe[OBJETIVO] = dataframe[OBJETIVO].astype(float)
    dataframe.loc[:3, OBJETIVO] = np.nan

    resultado = validar_dataset(dataframe, OBJETIVO)
    texto = json.dumps(a_diccionario_serializable(resultado), ensure_ascii=False)

    datos = json.loads(texto)
    assert datos["valido"] is False
    assert {e["codigo"] for e in datos["errores"]} == {
        "COLUMNAS_SIN_NOMBRE",
        "COLUMNAS_REPETIDAS",
        "FILAS_INSUFICIENTES",
        "OBJETIVO_CON_FALTANTES",
    }


def test_validar_archivo_convierte_errores_de_carga(tmp_path):
    ruta = tmp_path / "datos.json"
    ruta.write_text("{}", encoding="utf-8")

    resultado = validar_archivo(ruta, OBJETIVO)

    assert resultado.valido is False
    assert codigos_error(resultado) == [CodigoValidacion.FORMATO_NO_SOPORTADO]
    json.dumps(a_diccionario_serializable(resultado))


def test_validar_archivo_csv_valido(tmp_path, dataset_valido):
    ruta = tmp_path / "datos.csv"
    dataset_valido.to_csv(ruta, index=False)

    resultado = validar_archivo(ruta, OBJETIVO)

    assert resultado.valido is True

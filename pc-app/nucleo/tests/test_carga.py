"""Pruebas de la carga de archivos CSV y XLSX."""

import pandas as pd
import pytest

from pcapp_nucleo.carga import (
    ErrorCarga,
    cargar_csv,
    cargar_dataset,
    cargar_excel,
    obtener_hojas_excel,
)
from pcapp_nucleo.modelos import CodigoValidacion
from pcapp_nucleo.validacion import validar_dataset

from .conftest import OBJETIVO

CSV_SIMPLE = "edad,sexo,resultado\n30,M,1\n45,F,0\n"


def codigo_de(error: pytest.ExceptionInfo) -> str:
    return error.value.problema.codigo


# --- CSV ---------------------------------------------------------------------


def test_csv_normal(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text(CSV_SIMPLE, encoding="utf-8")

    dataframe = cargar_csv(ruta)

    assert list(dataframe.columns) == ["edad", "sexo", "resultado"]
    assert dataframe["edad"].tolist() == [30, 45]


@pytest.mark.parametrize("separador", [";", "\t", "|"])
def test_csv_detecta_separador(tmp_path, separador):
    ruta = tmp_path / "datos.csv"
    ruta.write_text(CSV_SIMPLE.replace(",", separador), encoding="utf-8")

    dataframe = cargar_csv(ruta)

    assert list(dataframe.columns) == ["edad", "sexo", "resultado"]
    assert dataframe.shape == (2, 3)


def test_csv_punto_y_coma_con_coma_decimal(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("peso;altura\n70,5;1,80\n82,1;1,75\n", encoding="utf-8")

    dataframe = cargar_csv(ruta)

    assert list(dataframe.columns) == ["peso", "altura"]


def test_csv_separador_ambiguo_es_error(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("a,b;c\n1,2;3\n", encoding="utf-8")

    with pytest.raises(ErrorCarga) as error:
        cargar_csv(ruta)

    assert codigo_de(error) == CodigoValidacion.SEPARADOR_NO_DETECTADO


def test_csv_filas_irregulares_es_error(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("a,b,c\n1,2\n1,2,3,4\n", encoding="utf-8")

    with pytest.raises(ErrorCarga) as error:
        cargar_csv(ruta)

    assert codigo_de(error) == CodigoValidacion.SEPARADOR_NO_DETECTADO


def test_csv_utf8_con_bom(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("edad,región\n30,Sur\n", encoding="utf-8-sig")
    assert ruta.read_bytes().startswith(b"\xef\xbb\xbf")

    dataframe = cargar_csv(ruta)

    assert list(dataframe.columns) == ["edad", "región"]


def test_csv_cp1252(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_bytes("año;región\n2020;Sur\n".encode("cp1252"))

    dataframe = cargar_csv(ruta)

    assert list(dataframe.columns) == ["año", "región"]


def test_csv_conserva_encabezados_repetidos_y_vacios(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("edad,,edad\n1,2,3\n", encoding="utf-8")

    dataframe = cargar_csv(ruta)

    assert list(dataframe.columns) == ["edad", "", "edad"]
    codigos = {p.codigo for p in validar_dataset(dataframe, "edad").errores}
    assert {CodigoValidacion.COLUMNAS_SIN_NOMBRE, CodigoValidacion.COLUMNAS_REPETIDAS} <= codigos


def test_csv_vacio(tmp_path):
    ruta = tmp_path / "datos.csv"
    ruta.write_text("", encoding="utf-8")

    with pytest.raises(ErrorCarga) as error:
        cargar_csv(ruta)

    assert codigo_de(error) == CodigoValidacion.ARCHIVO_VACIO


# --- XLSX --------------------------------------------------------------------


def test_excel_una_hoja(tmp_path):
    ruta = tmp_path / "datos.xlsx"
    esperado = pd.DataFrame({"edad": [30, 45], OBJETIVO: [1, 0]})
    esperado.to_excel(ruta, index=False)

    dataframe = cargar_excel(ruta)

    pd.testing.assert_frame_equal(dataframe, esperado)


@pytest.fixture
def excel_varias_hojas(tmp_path):
    ruta = tmp_path / "libro.xlsx"
    estudiantes = pd.DataFrame({"nombre": ["Ana", "Luis"], "edad": [20, 22]})
    resultados = pd.DataFrame({"nota": [8.5, 6.0], OBJETIVO: [1, 0]})
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        estudiantes.to_excel(escritor, sheet_name="estudiantes", index=False)
        resultados.to_excel(escritor, sheet_name="resultados", index=False)
    return ruta, resultados


def test_excel_varias_hojas(excel_varias_hojas):
    ruta, resultados = excel_varias_hojas

    assert obtener_hojas_excel(ruta) == ["estudiantes", "resultados"]
    pd.testing.assert_frame_equal(cargar_excel(ruta, hoja="resultados"), resultados)


def test_excel_varias_hojas_sin_indicar_hoja(excel_varias_hojas):
    ruta, _ = excel_varias_hojas

    with pytest.raises(ErrorCarga) as error:
        cargar_excel(ruta)

    assert codigo_de(error) == CodigoValidacion.HOJA_NO_ESPECIFICADA
    assert error.value.problema.evidencia["hojas_disponibles"] == ["estudiantes", "resultados"]


def test_excel_hoja_inexistente(excel_varias_hojas):
    ruta, _ = excel_varias_hojas

    with pytest.raises(ErrorCarga) as error:
        cargar_excel(ruta, hoja="notas")

    assert codigo_de(error) == CodigoValidacion.HOJA_NO_ENCONTRADA
    assert str(error.value) == (
        "La hoja 'notas' no existe en el archivo. "
        "Hojas disponibles: estudiantes, resultados."
    )


def test_excel_corrupto(tmp_path):
    ruta = tmp_path / "datos.xlsx"
    ruta.write_text("esto no es un xlsx", encoding="utf-8")

    with pytest.raises(ErrorCarga) as error:
        cargar_excel(ruta)

    assert codigo_de(error) == CodigoValidacion.ARCHIVO_ILEGIBLE
    assert error.value.__cause__ is not None


# --- Despacho por formato ----------------------------------------------------


@pytest.mark.parametrize("nombre", ["datos.CSV", "datos.Csv"])
def test_extension_sin_distinguir_mayusculas(tmp_path, nombre):
    ruta = tmp_path / nombre
    ruta.write_text(CSV_SIMPLE, encoding="utf-8")

    assert cargar_dataset(ruta).shape == (2, 3)


@pytest.mark.parametrize("nombre", ["datos.txt", "datos.xls", "datos.json", "datos"])
def test_formato_no_soportado(tmp_path, nombre):
    ruta = tmp_path / nombre
    ruta.write_text(CSV_SIMPLE, encoding="utf-8")

    with pytest.raises(ErrorCarga) as error:
        cargar_dataset(ruta)

    assert codigo_de(error) == CodigoValidacion.FORMATO_NO_SOPORTADO
    assert str(error.value) == (
        "Formato de archivo no soportado. Los formatos aceptados son CSV y XLSX."
    )


def test_archivo_inexistente(tmp_path):
    with pytest.raises(ErrorCarga) as error:
        cargar_dataset(tmp_path / "no_existe.csv")

    assert codigo_de(error) == CodigoValidacion.ARCHIVO_NO_ENCONTRADO


def test_cargar_dataset_selecciona_hoja(excel_varias_hojas):
    ruta, resultados = excel_varias_hojas

    pd.testing.assert_frame_equal(cargar_dataset(ruta, hoja="resultados"), resultados)

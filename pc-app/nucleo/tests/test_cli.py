"""Pruebas de integración del flujo completo y de la CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from nucleo.analisis import analizar_dataset, resultado_a_diccionario
from nucleo.cli import SALIDA_CORRECTA, SALIDA_DATASET_INVALIDO, SALIDA_ERROR, main

from .conftest import OBJETIVO, construir_dataset
from .datos_sinteticos import HALLAZGOS_ESPERADOS, construir_dataset_prueba

RAIZ_PAQUETE = Path(__file__).resolve().parents[1]


def ejecutar(capsys, *argumentos):
    codigo = main([str(a) for a in argumentos])
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def cargar_json(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


@pytest.fixture
def csv_valido(tmp_path):
    ruta = tmp_path / "estudiantes.csv"
    construir_dataset().to_csv(ruta, index=False)
    return ruta


@pytest.fixture
def excel_varias_hojas(tmp_path):
    ruta = tmp_path / "libro.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        construir_dataset(filas=150).to_excel(escritor, sheet_name="estudiantes", index=False)
        pd.DataFrame({"a": [1, 2]}).to_excel(escritor, sheet_name="actividades", index=False)
    return ruta


# --- analizar_dataset ------------------------------------------------------------


def test_analizar_dataset_valido_ejecuta_revision():
    dataframe = construir_dataset()
    copia = dataframe.copy(deep=True)

    resultado = analizar_dataset(dataframe, OBJETIVO)

    assert resultado.valido is True
    assert resultado.informe is not None
    assert dataframe.equals(copia)
    datos = json.loads(json.dumps(resultado_a_diccionario(resultado), ensure_ascii=False, indent=2))
    assert {"valido", "validacion", "resumen", "hallazgos", "perfiles_columnas"} <= set(datos)


def test_analizar_dataset_invalido_no_ejecuta_revision(monkeypatch):
    def revision_prohibida(*_):
        raise AssertionError("la revisión no debe ejecutarse")

    monkeypatch.setattr("nucleo.analisis.revisar_dataset", revision_prohibida)

    resultado = analizar_dataset(construir_dataset(filas=50), OBJETIVO)

    assert resultado.valido is False
    assert resultado.informe is None
    assert resultado.validacion.errores[0].codigo == "FILAS_INSUFICIENTES"
    assert set(resultado_a_diccionario(resultado)) == {"valido", "validacion"}


# --- Argumentos ------------------------------------------------------------------


def test_sin_comando_muestra_ayuda(capsys):
    codigo, salida, _ = ejecutar(capsys)

    assert codigo == SALIDA_ERROR
    assert "revisar" in salida and "uso:" in salida


def test_revisar_sin_archivo(capsys):
    codigo, _, error = ejecutar(capsys, "revisar")

    assert codigo == SALIDA_ERROR
    assert "faltan argumentos obligatorios" in error


def test_revisar_sin_objetivo(capsys, csv_valido):
    codigo, _, error = ejecutar(capsys, "revisar", csv_valido)

    assert codigo == SALIDA_ERROR
    assert "--objetivo" in error
    assert not csv_valido.with_name("estudiantes_revision.json").exists()


def test_comando_desconocido(capsys):
    codigo, _, error = ejecutar(capsys, "borrar", "x.csv")

    assert codigo == SALIDA_ERROR
    assert "opción no válida" in error


def test_ayuda_del_comando(capsys):
    codigo, salida, _ = ejecutar(capsys, "revisar", "--help")

    assert codigo == 0
    assert "--objetivo" in salida and "--hoja" in salida


# --- Casos válidos -----------------------------------------------------------------


def test_csv_valido(capsys, csv_valido):
    codigo, salida, _ = ejecutar(capsys, "revisar", csv_valido, "--objetivo", OBJETIVO)

    assert codigo == SALIDA_CORRECTA
    assert "REVISIÓN DEL DATASET" in salida
    assert "Filas: 120" in salida
    assert "REVISIÓN COMPLETADA" in salida
    informe = cargar_json(csv_valido.with_name("estudiantes_revision.json"))
    assert informe["valido"] is True
    assert informe["origen"] == {"archivo": "estudiantes.csv", "hoja": None}
    assert informe["resumen"]["filas"] == 120
    assert len(informe["perfiles_columnas"]) == 4
    assert isinstance(informe["hallazgos"], list)


def test_json_existente_no_se_sobrescribe(capsys, csv_valido):
    existente = csv_valido.with_name("estudiantes_revision.json")
    existente.write_text("contenido previo", encoding="utf-8")

    codigo, salida, _ = ejecutar(capsys, "revisar", csv_valido, "--objetivo", OBJETIVO)

    assert codigo == SALIDA_CORRECTA
    assert existente.read_text(encoding="utf-8") == "contenido previo"
    nuevo = csv_valido.with_name("estudiantes_revision_2.json")
    assert cargar_json(nuevo)["valido"] is True
    assert str(nuevo) in salida


def test_xlsx_una_hoja(capsys, tmp_path):
    ruta = tmp_path / "datos.xlsx"
    construir_dataset().to_excel(ruta, index=False)

    codigo, _, _ = ejecutar(capsys, "revisar", ruta, "--objetivo", OBJETIVO)

    assert codigo == SALIDA_CORRECTA
    assert cargar_json(tmp_path / "datos_revision.json")["resumen"]["filas"] == 120


def test_xlsx_selecciona_hoja(capsys, excel_varias_hojas):
    codigo, salida, _ = ejecutar(
        capsys, "revisar", excel_varias_hojas, "--objetivo", OBJETIVO, "--hoja", "estudiantes"
    )

    assert codigo == SALIDA_CORRECTA
    assert "(hoja: estudiantes)" in salida
    informe = cargar_json(excel_varias_hojas.with_name("libro_revision.json"))
    assert informe["origen"]["hoja"] == "estudiantes"
    assert informe["resumen"]["filas"] == 150


# --- Errores ---------------------------------------------------------------------


def test_hoja_inexistente(capsys, excel_varias_hojas):
    codigo, _, error = ejecutar(
        capsys, "revisar", excel_varias_hojas, "--objetivo", OBJETIVO, "--hoja", "datos"
    )

    assert codigo == SALIDA_ERROR
    assert 'Error: la hoja "datos" no existe.' in error
    assert "Hojas disponibles:\n- estudiantes\n- actividades" in error


def test_varias_hojas_sin_indicar_hoja(capsys, excel_varias_hojas):
    codigo, _, error = ejecutar(capsys, "revisar", excel_varias_hojas, "--objetivo", OBJETIVO)

    assert codigo == SALIDA_ERROR
    assert "--hoja" in error and "- estudiantes" in error


def test_archivo_inexistente(capsys, tmp_path):
    codigo, _, error = ejecutar(capsys, "revisar", tmp_path / "no.csv", "--objetivo", OBJETIVO)

    assert codigo == SALIDA_ERROR
    assert "Error: el archivo no existe" in error


def test_formato_no_soportado(capsys, tmp_path):
    ruta = tmp_path / "datos.txt"
    ruta.write_text("a,b\n1,2\n", encoding="utf-8")

    codigo, _, error = ejecutar(capsys, "revisar", ruta, "--objetivo", OBJETIVO)

    assert codigo == SALIDA_ERROR
    assert "Error: formato de archivo no soportado.\nFormatos aceptados: CSV y XLSX." in error


def test_dataset_invalido_no_genera_informe(capsys, tmp_path):
    ruta = tmp_path / "pequeno.csv"
    construir_dataset(filas=73).to_csv(ruta, index=False)

    codigo, salida, error = ejecutar(capsys, "revisar", ruta, "--objetivo", OBJETIVO)

    assert codigo == SALIDA_DATASET_INVALIDO
    assert "El dataset contiene 73 filas y se requieren al menos 100." in error
    assert "DATASET NO VÁLIDO" in salida
    assert not list(tmp_path.glob("*.json"))


def test_objetivo_inexistente(capsys, csv_valido):
    codigo, _, error = ejecutar(capsys, "revisar", csv_valido, "--objetivo", "inexistente")

    assert codigo == SALIDA_DATASET_INVALIDO
    assert "La variable objetivo 'inexistente' no existe en el dataset." in error
    assert not list(csv_valido.parent.glob("*.json"))


# --- End-to-end ------------------------------------------------------------------------


def test_end_to_end_dataset_con_problemas(capsys, tmp_path):
    ruta = tmp_path / "dataset_prueba.csv"
    dataframe = construir_dataset_prueba()
    dataframe.to_csv(ruta, index=False)

    codigo, salida, _ = ejecutar(capsys, "revisar", ruta, "--objetivo", "objetivo")

    assert codigo == SALIDA_CORRECTA
    assert "REVISIÓN COMPLETADA" in salida
    informe = cargar_json(tmp_path / "dataset_prueba_revision.json")
    assert [p["nombre"] for p in informe["perfiles_columnas"]] == list(dataframe.columns)
    assert informe["resumen"]["tipo_objetivo"] == "binario"
    encontrados = {
        (h["tipo"], None if h["tipo"] == "filas_duplicadas" else tuple(h["columnas_involucradas"]))
        for h in informe["hallazgos"]
    }
    assert HALLAZGOS_ESPERADOS <= encontrados


def test_python_m_nucleo_en_subproceso(tmp_path):
    ruta = tmp_path / "datos.csv"
    construir_dataset().to_csv(ruta, index=False)
    entorno = {
        **os.environ,
        "PYTHONPATH": str(RAIZ_PAQUETE / "src"),
        "PYTHONIOENCODING": "utf-8",
    }

    proceso = subprocess.run(
        [sys.executable, "-m", "nucleo", "revisar", str(ruta), "--objetivo", OBJETIVO],
        capture_output=True,
        env=entorno,
        check=False,
    )

    assert proceso.returncode == SALIDA_CORRECTA, proceso.stderr.decode("utf-8")
    assert "REVISIÓN COMPLETADA" in proceso.stdout.decode("utf-8")
    assert cargar_json(tmp_path / "datos_revision.json")["valido"] is True

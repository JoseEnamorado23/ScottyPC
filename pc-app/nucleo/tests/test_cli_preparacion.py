"""Pruebas de los comandos plantilla, preparar y sugerir-prueba."""

import json

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo.cli import SALIDA_CORRECTA, SALIDA_DATASET_INVALIDO, SALIDA_ERROR, main

from .datos_sinteticos import construir_dataset_prueba


def ejecutar(capsys, *argumentos):
    codigo = main([str(a) for a in argumentos])
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def cargar_json(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


@pytest.fixture
def dataset(tmp_path):
    ruta = tmp_path / "estudio.csv"
    construir_dataset_prueba().to_csv(ruta, index=False)
    return ruta


@pytest.fixture
def decisiones(capsys, dataset):
    codigo, _, _ = ejecutar(capsys, "plantilla", dataset, "--objetivo", "objetivo")
    assert codigo == SALIDA_CORRECTA
    return dataset.with_name("estudio_decisiones.json")


def test_flujo_completo(capsys, dataset, decisiones):
    plantilla = cargar_json(decisiones)
    assert plantilla["eliminar_duplicados"] is True
    assert all("requiere_confirmacion" in a for a in plantilla["acciones_hallazgos"].values())

    codigo, salida, _ = ejecutar(
        capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", decisiones,
        "--test", "0.25", "--semilla", "7",
    )
    assert codigo == SALIDA_CORRECTA
    assert "DATOS PREPARADOS" in salida
    receta = cargar_json(dataset.with_name("estudio_receta.json"))
    train = pd.read_csv(dataset.with_name("estudio_train.csv"))
    test = pd.read_csv(dataset.with_name("estudio_test.csv"))
    assert receta["separacion"]["proporcion_test"] == 0.25
    assert receta["separacion"]["semilla"] == 7
    assert "separacion" not in receta["decisiones"]
    assert receta["origen"]["archivo"] == "estudio.csv" and len(receta["origen"]["sha256"]) == 64
    assert len(train) == len(receta["indices_train"]) and len(test) == len(receta["indices_test"])
    assert list(train.columns)[-1] == "objetivo"

    codigo, salida, _ = ejecutar(
        capsys, "sugerir-prueba", dataset.with_name("estudio_receta.json"), "--sin-estimacion"
    )
    assert codigo == SALIDA_CORRECTA
    assert "Prueba sugerida:" in salida
    recomendacion = cargar_json(dataset.with_name("estudio_recomendacion.json"))
    assert recomendacion["prueba"] in {"fisherz", "chisq", "mv_fisherz"}
    assert recomendacion["tiempo_por_ejecucion_s"] is None


def test_decisiones_editadas_cambian_la_recomendacion(capsys, dataset, decisiones):
    datos = cargar_json(decisiones)
    datos["faltantes"]["peso"]["imputacion"] = None  # conservar los faltantes
    decisiones.write_text(json.dumps(datos), encoding="utf-8")

    ejecutar(capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", decisiones)
    ejecutar(capsys, "sugerir-prueba", dataset.with_name("estudio_receta.json"), "--sin-estimacion")

    assert cargar_json(dataset.with_name("estudio_recomendacion.json"))["prueba"] == "mv_fisherz"


def test_separacion_temporal_desde_la_linea_de_comandos(capsys, dataset, decisiones):
    codigo, salida, _ = ejecutar(
        capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", decisiones,
        "--fecha", "fecha", "--corte", "2024-05-01",
    )

    assert codigo == SALIDA_CORRECTA
    assert "temporal por 'fecha' (corte 2024-05-01)" in salida
    receta = cargar_json(dataset.with_name("estudio_receta.json"))
    fechas = pd.to_datetime(pd.read_csv(dataset)["fecha"])
    assert (fechas[receta["indices_test"]] >= "2024-05-01").all()
    assert (fechas[receta["indices_train"]] < "2024-05-01").all()


def test_no_sobrescribe_archivos(capsys, dataset, decisiones):
    argumentos = ["preparar", dataset, "--objetivo", "objetivo", "--decisiones", decisiones]
    ejecutar(capsys, *argumentos)
    primera = dataset.with_name("estudio_receta.json").read_text(encoding="utf-8")

    codigo, _, _ = ejecutar(capsys, *argumentos, "--semilla", "99")

    assert codigo == SALIDA_CORRECTA
    assert dataset.with_name("estudio_receta.json").read_text(encoding="utf-8") == primera
    for sufijo in ("receta_2.json", "train_2.csv", "test_2.csv"):
        assert dataset.with_name(f"estudio_{sufijo}").exists()
    ejecutar(capsys, "plantilla", dataset, "--objetivo", "objetivo")
    assert dataset.with_name("estudio_decisiones_2.json").exists()


@pytest.mark.parametrize(
    "extra, mensaje",
    [
        (["--corte", "2024-05-01"], "--corte requiere"),
        (["--test", "1.5"], "proporción de test"),
        (["--fecha", "no_existe"], "no existe en el dataset"),
    ],
)
def test_errores_de_opciones(capsys, dataset, decisiones, extra, mensaje):
    codigo, _, error = ejecutar(
        capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", decisiones, *extra
    )

    assert codigo == SALIDA_ERROR
    assert mensaje in error
    assert not dataset.with_name("estudio_receta.json").exists()


def test_decisiones_inexistentes_o_invalidas(capsys, dataset, tmp_path):
    codigo, _, error = ejecutar(
        capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", tmp_path / "no.json"
    )
    assert codigo == SALIDA_ERROR and "no existe" in error

    malas = tmp_path / "malas.json"
    malas.write_text('{"faltantes": {"peso": {"imputar": "mediana"}}}', encoding="utf-8")
    codigo, _, error = ejecutar(capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", malas)
    assert codigo == SALIDA_ERROR and "campos desconocidos" in error


def test_dataset_invalido(capsys, tmp_path):
    ruta = tmp_path / "pequeno.csv"
    pd.DataFrame({"x": np.arange(50), "y": [0, 1] * 25}).to_csv(ruta, index=False)

    codigo, salida, _ = ejecutar(capsys, "plantilla", ruta, "--objetivo", "y")

    assert codigo == SALIDA_DATASET_INVALIDO
    assert "no se generó la plantilla" in salida
    assert not list(tmp_path.glob("*.json"))


def test_receta_con_archivo_modificado(capsys, dataset, decisiones):
    ejecutar(capsys, "preparar", dataset, "--objetivo", "objetivo", "--decisiones", decisiones)
    dataset.write_text(dataset.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    codigo, _, error = ejecutar(capsys, "sugerir-prueba", dataset.with_name("estudio_receta.json"))

    assert codigo == SALIDA_ERROR
    assert "cambió desde que se creó la receta" in error


def test_receta_inexistente(capsys, tmp_path):
    codigo, _, error = ejecutar(capsys, "sugerir-prueba", tmp_path / "no.json")

    assert codigo == SALIDA_ERROR
    assert "no existe" in error

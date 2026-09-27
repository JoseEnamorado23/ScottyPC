"""Pruebas de los comandos plantilla-pc y pc."""

import json
import threading

import numpy as np
import pandas as pd
import pytest

from nucleo.cli import SALIDA_CORRECTA, SALIDA_ERROR, main
from nucleo.cli_preparacion import cargar_desde_receta
from nucleo.pc_bootstrap import ejecutar_bootstrap
from nucleo.pc_config import configuracion_desde_diccionario


def ejecutar(capsys, *argumentos):
    codigo = main([str(a) for a in argumentos])
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


@pytest.fixture
def receta(capsys, tmp_path):
    """Dataset con un colisionador A → B ← C y B → Y, preparado por la CLI."""
    rng = np.random.default_rng(0)
    n = 600
    a, c = rng.normal(size=n), rng.normal(size=n)
    b = a + c + rng.normal(0, 0.7, n)
    ruta = tmp_path / "estudio.csv"
    pd.DataFrame({"A": a, "B": b, "C": c, "Y": b + rng.normal(size=n)}).to_csv(ruta, index=False)
    decisiones = tmp_path / "decisiones.json"
    decisiones.write_text("{}", encoding="utf-8")
    codigo, _, error = ejecutar(capsys, "preparar", ruta, "--objetivo", "Y", "--decisiones", decisiones)
    assert codigo == SALIDA_CORRECTA, error
    return tmp_path / "estudio_receta.json"


def configurar(capsys, receta, **cambios):
    codigo, salida, _ = ejecutar(capsys, "plantilla-pc", receta)
    assert codigo == SALIDA_CORRECTA
    ruta = receta.with_name("estudio_pc.json")
    configuracion = json.loads(ruta.read_text(encoding="utf-8"))
    configuracion.update({"corridas_bootstrap": 6, "procesos": 1, **cambios})
    ruta.write_text(json.dumps(configuracion), encoding="utf-8")
    return ruta, salida


def test_plantilla_pc(capsys, receta):
    ruta, salida = configurar(capsys, receta)

    configuracion = json.loads(ruta.read_text(encoding="utf-8"))
    assert configuracion["niveles"] == [["A", "B", "C"], ["Y"]]
    assert configuracion["prueba"] == "fisherz"
    assert "CONFIGURACIÓN DE PC" in salida


def test_plantilla_pc_usa_la_recomendacion_guardada(capsys, receta):
    receta.with_name("estudio_recomendacion.json").write_text(
        json.dumps({"prueba": "chisq", "max_k_sugerido": 3}), encoding="utf-8"
    )

    ruta, salida = configurar(capsys, receta)

    configuracion = json.loads(ruta.read_text(encoding="utf-8"))
    assert (configuracion["prueba"], configuracion["max_k"]) == ("chisq", 3)
    assert "estudio_recomendacion.json" in salida


def test_pc_genera_los_resultados(capsys, receta):
    configuracion, _ = configurar(capsys, receta, modificables=["A", "C"])

    codigo, salida, _ = ejecutar(capsys, "pc", receta, "--config", configuracion)

    assert codigo == SALIDA_CORRECTA
    carpeta = receta.with_name("estudio_pc")
    for nombre in ("resultado.json", "aristas.csv", "mascara.csv", "matriz_frecuencias.csv", "grafo.png"):
        assert (carpeta / nombre).exists()
    assert not (carpeta / "punto_control.json").exists()
    assert "Corrida 6/6" in salida
    assert "Causas directas: B" in salida
    assert "Causas indirectas: A (a través de B), C (a través de B)" in salida
    assert "Candidatas prescriptivas: A, C." in salida

    codigo, _, _ = ejecutar(capsys, "pc", receta, "--config", configuracion, "--procesos", "2")
    assert codigo == SALIDA_CORRECTA
    assert receta.with_name("estudio_pc_2").is_dir()
    primero = json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))
    segundo = json.loads((receta.with_name("estudio_pc_2") / "resultado.json").read_text(encoding="utf-8"))
    assert primero["aristas"] == segundo["aristas"]


def test_reanudar_sin_punto_de_control(capsys, receta):
    configuracion, _ = configurar(capsys, receta)

    codigo, _, error = ejecutar(capsys, "pc", receta, "--config", configuracion, "--reanudar")

    assert codigo == SALIDA_ERROR
    assert "no hay un análisis interrumpido" in error


def test_reanudar_continua_en_la_misma_carpeta(capsys, receta):
    configuracion, _ = configurar(capsys, receta)
    carpeta = receta.with_name("estudio_pc")
    carpeta.mkdir()
    # Punto de control válido con 0 corridas: se genera cancelando antes de empezar.
    _, datos = cargar_desde_receta(receta)
    cancelado = threading.Event()
    cancelado.set()
    ejecutar_bootstrap(
        datos, configuracion_desde_diccionario(json.loads(configuracion.read_text(encoding="utf-8"))),
        cancelacion=cancelado, punto_control=carpeta / "punto_control.json",
    )
    capsys.readouterr()

    codigo, salida, _ = ejecutar(capsys, "pc", receta, "--config", configuracion, "--reanudar")

    assert codigo == SALIDA_CORRECTA
    assert "desde el punto de control" in salida
    assert (carpeta / "resultado.json").exists()
    assert not receta.with_name("estudio_pc_2").exists()


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"niveles": [["A", "B"], ["Y"]]}, "faltan: C"),
        ({"prueba": "otra"}, "Prueba no válida"),
        ({"columna": 1}, "campos desconocidos"),
    ],
)
def test_configuracion_invalida(capsys, receta, cambios, mensaje):
    configuracion, _ = configurar(capsys, receta, **cambios)

    codigo, _, error = ejecutar(capsys, "pc", receta, "--config", configuracion)

    assert codigo == SALIDA_ERROR
    assert mensaje in error
    assert not receta.with_name("estudio_pc").exists()

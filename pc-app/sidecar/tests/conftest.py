"""Utilidades compartidas: cliente con token y recorrido del flujo con diabetes."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from servidor.aplicacion import crear_aplicacion
from servidor.configuracion import ConfiguracionServidor

DATASETS = Path(__file__).resolve().parents[2] / "datasets_prueba"
DIABETES = DATASETS / "diabetes.csv"
TOKEN = "token-de-prueba"
NIVELES_DIABETES = [
    ["Age", "Pregnancies", "DiabetesPedigreeFunction"],
    ["BMI", "SkinThickness", "BloodPressure"],
    ["Glucose", "Insulin"],
    ["Outcome"],
]
CEROS = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


def crear_cliente(datos: Path, token: str | None = TOKEN) -> TestClient:
    configuracion = ConfiguracionServidor(datos, token, desarrollo=token is None, procesos=2)
    return TestClient(crear_aplicacion(configuracion), headers={"X-Token": token} if token else {})


@pytest.fixture
def cliente(tmp_path):
    with crear_cliente(tmp_path / "datos") as c:
        yield c


@pytest.fixture
def diabetes():
    if not DIABETES.is_file():
        pytest.skip("Falta datasets_prueba/diabetes.csv.")
    return DIABETES


def esperar_trabajo(cliente: TestClient, trabajo_id: str, limite_s: float = 180) -> dict:
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        trabajo = cliente.get(f"/trabajos/{trabajo_id}").json()
        if trabajo["estado"] not in ("pendiente", "en_curso"):
            return trabajo
        time.sleep(0.1)
    raise AssertionError(f"El trabajo {trabajo_id} no terminó en {limite_s} s")


def ok(respuesta, estado: int = 200):
    assert respuesta.status_code == estado, respuesta.text
    return respuesta.json() if respuesta.content else None


def crear_proyecto(cliente: TestClient, ruta: Path) -> str:
    return ok(cliente.post("/proyectos", json={"ruta_archivo": str(ruta)}), 201)["id"]


def hasta_decisiones(cliente: TestClient, ruta: Path) -> str:
    proyecto = crear_proyecto(cliente, ruta)
    ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "Outcome"}))
    decisiones = ok(cliente.get(f"/proyectos/{proyecto}/decisiones/plantilla"))
    for columna in CEROS:
        decisiones["faltantes"][columna] = {"ceros_como_faltantes": True, "imputacion": "mediana"}
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones))
    return proyecto


def hasta_configuracion(cliente: TestClient, ruta: Path, **cambios) -> str:
    proyecto = hasta_decisiones(cliente, ruta)
    ok(cliente.post(f"/proyectos/{proyecto}/preparar"))
    configuracion = ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc"))["configuracion"]
    configuracion.update(
        {"niveles": NIVELES_DIABETES, "corridas_bootstrap": 10, "procesos": 1,
         "modificables": ["BMI", "Glucose"], **cambios}
    )
    ok(cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json=configuracion))
    return proyecto

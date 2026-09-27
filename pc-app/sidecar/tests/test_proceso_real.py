"""Arranque del proceso real: línea "listo", token, apagado y vigilancia del padre."""

import json
import os
import queue
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"


def lanzar(*argumentos: str) -> subprocess.Popen:
    entorno = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}
    return subprocess.Popen(
        [sys.executable, "-m", "pcapp_servidor", *argumentos],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=entorno,
    )


def primera_linea(proceso: subprocess.Popen, limite_s: float = 60) -> dict:
    lineas: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: lineas.put(proceso.stdout.readline()), daemon=True).start()
    try:
        return json.loads(lineas.get(timeout=limite_s))
    except queue.Empty:
        proceso.kill()
        raise AssertionError("El servidor no imprimió la línea de arranque a tiempo")


def peticion(puerto: int, ruta: str, token: str | None, metodo: str = "GET") -> tuple[int, dict]:
    solicitud = urllib.request.Request(
        f"http://127.0.0.1:{puerto}{ruta}", method=metodo, headers={"X-Token": token} if token else {}
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=10) as respuesta:
            return respuesta.status, json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_linea_de_arranque_token_y_apagado(tmp_path):
    proceso = lanzar("--datos", str(tmp_path / "datos"))
    try:
        listo = primera_linea(proceso)

        assert set(listo) == {"evento", "puerto", "token"}
        assert listo["evento"] == "listo" and isinstance(listo["puerto"], int) and listo["puerto"] > 0
        assert isinstance(listo["token"], str) and len(listo["token"]) >= 32
        assert peticion(listo["puerto"], "/salud", listo["token"])[0] == 200
        assert peticion(listo["puerto"], "/salud", None)[0] == 401

        assert peticion(listo["puerto"], "/apagar", listo["token"], "POST")[0] == 200
        assert proceso.wait(timeout=30) == 0
        assert proceso.stdout.read() == ""  # nada más en stdout
        assert (tmp_path / "datos" / "app.db").exists()
        assert (tmp_path / "datos" / "logs" / "servidor.log").exists()
    finally:
        proceso.kill()


def test_se_cierra_al_terminar_el_proceso_padre(tmp_path):
    padre = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    proceso = lanzar("--datos", str(tmp_path / "datos"), "--pid-padre", str(padre.pid))
    try:
        listo = primera_linea(proceso)
        assert peticion(listo["puerto"], "/salud", listo["token"])[0] == 200

        padre.kill()
        padre.wait()

        assert proceso.wait(timeout=30) == 0
    finally:
        padre.kill()
        proceso.kill()


def test_error_de_arranque_en_formato_json(tmp_path):
    proceso = lanzar("--datos", str(tmp_path / "datos"), "--sin-token")

    evento = primera_linea(proceso)

    assert evento["evento"] == "error" and "--modo-desarrollo" in evento["mensaje"]
    assert proceso.wait(timeout=30) == 1


@pytest.mark.parametrize("ocupar", [True])
def test_puerto_ocupado(tmp_path, ocupar):
    import socket

    ocupado = socket.socket()
    ocupado.bind(("127.0.0.1", 0))
    ocupado.listen()
    puerto = ocupado.getsockname()[1]
    try:
        proceso = lanzar("--datos", str(tmp_path / "datos"), "--puerto", str(puerto))
        evento = primera_linea(proceso)
        assert evento["evento"] == "error" and str(puerto) in evento["mensaje"]
        assert proceso.wait(timeout=30) == 1
    finally:
        ocupado.close()

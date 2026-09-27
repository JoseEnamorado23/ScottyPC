"""Arranque del servidor: argumentos, puerto, token, uvicorn y vigilancia del padre.

Protocolo con Tauri: al estar listo, el servidor imprime en stdout una única
línea JSON ``{"evento": "listo", "puerto": N, "token": "..."}``. Si no puede
arrancar, imprime ``{"evento": "error", "mensaje": "..."}`` y termina con
código 1. Todo lo demás va al registro (``<datos>/logs``).
"""

from __future__ import annotations

import argparse
import importlib
import json
import secrets
import socket
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from pcapp_servidor.configuracion import PUERTO_DESARROLLO, ConfiguracionServidor
from pcapp_servidor.registro import REGISTRO, configurar_registro


def _emitir(evento: dict) -> None:
    sys.stdout.write(json.dumps(evento, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _argumentos(argumentos: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m pcapp_servidor", description="Servidor local de pc-app.")
    parser.add_argument("--datos", required=True, help="Carpeta de datos (app.db, proyectos/, logs/).")
    parser.add_argument("--puerto", type=int, help="Puerto (por defecto, uno libre elegido por el sistema).")
    parser.add_argument("--pid-padre", type=int, help="Cerrar el servidor cuando termine este proceso.")
    parser.add_argument("--procesos", type=int, help="Tamaño del grupo de procesos (por defecto, núcleos − 1).")
    parser.add_argument("--modo-desarrollo", action="store_true", help=f"Puerto fijo {PUERTO_DESARROLLO}.")
    parser.add_argument("--sin-token", action="store_true", help="Desactiva el token (solo con --modo-desarrollo).")
    return parser.parse_args(argumentos)


def vigilar_padre(pid: int, apagar: Callable[[], None], intervalo_s: float = 2.0) -> threading.Thread:
    """Llama a ``apagar`` cuando el proceso ``pid`` deja de existir."""
    import psutil

    try:
        creado = psutil.Process(pid).create_time()
    except psutil.Error:
        creado = None
    detener = threading.Event()

    def vigilar() -> None:
        while not detener.wait(intervalo_s):
            try:
                vivo = creado is not None and psutil.Process(pid).create_time() == creado
            except psutil.Error:
                vivo = False
            if not vivo:
                REGISTRO.info("El proceso padre %d terminó; apagando el servidor", pid)
                apagar()
                return

    if creado is None:
        REGISTRO.info("El proceso padre %d no existe; apagando el servidor", pid)
        apagar()
    hilo = threading.Thread(target=vigilar, name="vigilancia-padre", daemon=True)
    hilo.start()
    return hilo


def main(argumentos: list[str] | None = None) -> int:
    opciones = _argumentos(argumentos)
    if opciones.sin_token and not opciones.modo_desarrollo:
        _emitir({"evento": "error", "mensaje": "--sin-token solo se permite con --modo-desarrollo."})
        return 1
    try:
        importlib.import_module("pcapp_nucleo.pc_bootstrap")  # comprueba que el núcleo instalado es el de pc-app
    except ImportError:
        _emitir({"evento": "error", "mensaje": "No se encontró el núcleo de pc-app (pip install -e ../nucleo)."})
        return 1

    import uvicorn

    from pcapp_servidor.aplicacion import crear_aplicacion

    datos = Path(opciones.datos).expanduser().resolve()
    datos.mkdir(parents=True, exist_ok=True)
    configurar_registro(datos / "logs")
    token = None if opciones.sin_token else secrets.token_urlsafe(32)
    puerto = opciones.puerto if opciones.puerto is not None else (PUERTO_DESARROLLO if opciones.modo_desarrollo else 0)

    enchufe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        enchufe.bind(("127.0.0.1", puerto))
    except OSError as error:
        _emitir({"evento": "error", "mensaje": f"No se pudo usar el puerto {puerto}: {error}."})
        return 1
    enchufe.listen(128)
    puerto_real = enchufe.getsockname()[1]

    class Servidor(uvicorn.Server):
        async def startup(self, sockets=None) -> None:  # noqa: ANN001
            await super().startup(sockets)
            if not self.should_exit:
                REGISTRO.info("Servidor listo en 127.0.0.1:%d", puerto_real)
                _emitir({"evento": "listo", "puerto": puerto_real, "token": token})

    servidor: Servidor | None = None

    def apagar() -> None:
        if servidor is not None:
            servidor.should_exit = True

    aplicacion = crear_aplicacion(
        ConfiguracionServidor(datos, token, opciones.modo_desarrollo, opciones.procesos), apagar
    )
    servidor = Servidor(uvicorn.Config(aplicacion, log_config=None, access_log=False, lifespan="on"))
    if opciones.pid_padre:
        vigilar_padre(opciones.pid_padre, apagar)
    servidor.run(sockets=[enchufe])
    REGISTRO.info("Servidor detenido")
    return 0

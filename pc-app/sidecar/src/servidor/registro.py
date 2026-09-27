"""Registro rotativo en ``<datos>/logs/servidor.log``.

stdout queda reservado para la línea de arranque que lee Tauri; todo lo demás
(incluidos los mensajes de uvicorn) va al archivo de registro.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

REGISTRO = logging.getLogger("servidor")


def configurar_registro(carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    manejador = RotatingFileHandler(
        carpeta / "servidor.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    for nombre in ("servidor", "uvicorn", "uvicorn.error", "uvicorn.access"):
        registro = logging.getLogger(nombre)
        registro.handlers = [manejador]
        registro.setLevel(logging.INFO)
        registro.propagate = False

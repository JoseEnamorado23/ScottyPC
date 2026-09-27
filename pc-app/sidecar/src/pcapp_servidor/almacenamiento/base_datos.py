"""Conexión a SQLite y migraciones del esquema.

Se abre una conexión por operación (seguro entre hilos) en modo WAL, con
espera ante bloqueos y claves foráneas activadas.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

VERSION_ESQUEMA = 1


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BaseDatos:
    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        self._migrar()

    @contextmanager
    def conexion(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.ruta, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def _migrar(self) -> None:
        with self.conexion() as con:
            con.execute("PRAGMA journal_mode = WAL")
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                esquema = resources.files("pcapp_servidor.almacenamiento").joinpath("esquema.sql").read_text("utf-8")
                con.executescript(esquema)
                con.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")
            elif version > VERSION_ESQUEMA:
                raise RuntimeError(
                    f"app.db tiene la versión de esquema {version}, más nueva que la que admite este "
                    f"servidor ({VERSION_ESQUEMA})."
                )

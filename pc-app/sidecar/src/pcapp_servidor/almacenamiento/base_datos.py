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

VERSION_ESQUEMA = 2

# Migraciones: versión de origen → script que la lleva a la siguiente.
_MIGRACIONES = {
    # 1 → 2: nuevo tipo de trabajo «modelo_causal» (SQLite no permite cambiar un CHECK: se
    # recrea la tabla conservando las filas).
    1: """
        CREATE TABLE trabajos_nueva (
            id TEXT PRIMARY KEY,
            proyecto_id TEXT NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL CHECK (tipo IN ('recomendacion', 'pc', 'modelo_causal')),
            estado TEXT NOT NULL CHECK (
                estado IN ('pendiente', 'en_curso', 'completado', 'cancelado', 'fallido', 'interrumpido')
            ),
            completadas INTEGER NOT NULL DEFAULT 0,
            total INTEGER,
            fallidas INTEGER NOT NULL DEFAULT 0,
            segundos REAL NOT NULL DEFAULT 0,
            mensaje TEXT,
            parametros TEXT NOT NULL DEFAULT '{}',
            inicio TEXT,
            fin TEXT,
            error TEXT,
            actualizado_en TEXT NOT NULL
        );
        INSERT INTO trabajos_nueva SELECT
            id, proyecto_id, tipo, estado, completadas, total, fallidas, segundos, mensaje,
            parametros, inicio, fin, error, actualizado_en
        FROM trabajos;
        DROP TABLE trabajos;
        ALTER TABLE trabajos_nueva RENAME TO trabajos;
        CREATE UNIQUE INDEX un_trabajo_activo ON trabajos(proyecto_id)
            WHERE estado IN ('pendiente', 'en_curso');
        CREATE INDEX trabajos_por_proyecto ON trabajos(proyecto_id, inicio);
    """,
}


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
                return
            if version > VERSION_ESQUEMA:
                raise RuntimeError(
                    f"app.db tiene la versión de esquema {version}, más nueva que la que admite este "
                    f"servidor ({VERSION_ESQUEMA})."
                )
            while version < VERSION_ESQUEMA:
                con.executescript(_MIGRACIONES[version])
                version += 1
                con.execute(f"PRAGMA user_version = {version}")

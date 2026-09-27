"""Repositorios sencillos sobre las tablas de app.db."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, fields
from typing import Any

from pcapp_servidor.almacenamiento.base_datos import BaseDatos, ahora
from pcapp_servidor.errores import conflicto

ESTADOS_ACTIVOS = ("pendiente", "en_curso")


@dataclass
class Proyecto:
    id: str
    nombre: str
    archivo_original: str
    archivo: str
    hoja: str | None
    sha256: str
    objetivo: str | None
    etapa_actual: str | None
    creado_en: str
    actualizado_en: str


@dataclass
class Trabajo:
    id: str
    proyecto_id: str
    tipo: str
    estado: str
    completadas: int
    total: int | None
    fallidas: int
    segundos: float
    mensaje: str | None
    parametros: dict[str, Any]
    inicio: str | None
    fin: str | None
    error: str | None
    actualizado_en: str


def _fila(clase: type, fila: sqlite3.Row | None) -> Any:
    if fila is None:
        return None
    valores = {f.name: fila[f.name] for f in fields(clase)}
    if clase is Trabajo:
        valores["parametros"] = json.loads(valores["parametros"] or "{}")
    return clase(**valores)


class RepositorioProyectos:
    def __init__(self, base: BaseDatos) -> None:
        self.base = base

    def crear(self, proyecto: Proyecto) -> None:
        valores = {f.name: getattr(proyecto, f.name) for f in fields(Proyecto)}
        with self.base.conexion() as con:
            con.execute(
                f"INSERT INTO proyectos ({', '.join(valores)}) VALUES ({', '.join('?' * len(valores))})",
                list(valores.values()),
            )

    def obtener(self, proyecto_id: str) -> Proyecto | None:
        with self.base.conexion() as con:
            return _fila(Proyecto, con.execute("SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone())

    def listar(self) -> list[Proyecto]:
        with self.base.conexion() as con:
            filas = con.execute("SELECT * FROM proyectos ORDER BY creado_en DESC").fetchall()
        return [_fila(Proyecto, f) for f in filas]

    def actualizar(self, proyecto_id: str, **campos: Any) -> None:
        campos["actualizado_en"] = ahora()
        with self.base.conexion() as con:
            con.execute(
                f"UPDATE proyectos SET {', '.join(f'{c} = ?' for c in campos)} WHERE id = ?",
                [*campos.values(), proyecto_id],
            )

    def eliminar(self, proyecto_id: str) -> None:
        with self.base.conexion() as con:
            con.execute("DELETE FROM proyectos WHERE id = ?", (proyecto_id,))


class RepositorioEtapas:
    def __init__(self, base: BaseDatos) -> None:
        self.base = base

    def estados(self, proyecto_id: str) -> dict[str, str]:
        with self.base.conexion() as con:
            filas = con.execute("SELECT etapa, estado FROM etapas WHERE proyecto_id = ?", (proyecto_id,)).fetchall()
        return {f["etapa"]: f["estado"] for f in filas}

    def marcar(self, proyecto_id: str, etapas: dict[str, str]) -> None:
        momento = ahora()
        with self.base.conexion() as con:
            con.executemany(
                "INSERT INTO etapas (proyecto_id, etapa, estado, actualizada_en) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (proyecto_id, etapa) DO UPDATE SET estado = excluded.estado, "
                "actualizada_en = excluded.actualizada_en",
                [(proyecto_id, etapa, estado, momento) for etapa, estado in etapas.items()],
            )


class RepositorioTrabajos:
    def __init__(self, base: BaseDatos) -> None:
        self.base = base

    def crear(self, trabajo: Trabajo) -> None:
        valores = {f.name: getattr(trabajo, f.name) for f in fields(Trabajo)}
        valores["parametros"] = json.dumps(valores["parametros"])
        try:
            with self.base.conexion() as con:
                con.execute(
                    f"INSERT INTO trabajos ({', '.join(valores)}) VALUES ({', '.join('?' * len(valores))})",
                    list(valores.values()),
                )
        except sqlite3.IntegrityError as error:
            raise conflicto(
                "TRABAJO_ACTIVO", "El proyecto ya tiene un trabajo en curso; espere a que termine o cancélelo."
            ) from error

    def obtener(self, trabajo_id: str) -> Trabajo | None:
        with self.base.conexion() as con:
            return _fila(Trabajo, con.execute("SELECT * FROM trabajos WHERE id = ?", (trabajo_id,)).fetchone())

    def activo_de(self, proyecto_id: str) -> Trabajo | None:
        with self.base.conexion() as con:
            fila = con.execute(
                "SELECT * FROM trabajos WHERE proyecto_id = ? AND estado IN ('pendiente', 'en_curso')",
                (proyecto_id,),
            ).fetchone()
        return _fila(Trabajo, fila)

    def actualizar(self, trabajo_id: str, **campos: Any) -> None:
        if "parametros" in campos:
            campos["parametros"] = json.dumps(campos["parametros"])
        campos["actualizado_en"] = ahora()
        try:
            with self.base.conexion() as con:
                con.execute(
                    f"UPDATE trabajos SET {', '.join(f'{c} = ?' for c in campos)} WHERE id = ?",
                    [*campos.values(), trabajo_id],
                )
        except sqlite3.IntegrityError as error:
            raise conflicto(
                "TRABAJO_ACTIVO", "El proyecto ya tiene un trabajo en curso; espere a que termine o cancélelo."
            ) from error

    def marcar_interrumpidos(self) -> int:
        """Los trabajos que quedaron activos (el servidor se cerró sin terminarlos)."""
        with self.base.conexion() as con:
            cursor = con.execute(
                "UPDATE trabajos SET estado = 'interrumpido', fin = ?, actualizado_en = ?, "
                "mensaje = 'El servidor se cerró mientras el trabajo estaba en curso.' "
                "WHERE estado IN ('pendiente', 'en_curso')",
                (ahora(), ahora()),
            )
            return cursor.rowcount

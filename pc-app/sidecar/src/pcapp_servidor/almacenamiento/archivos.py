"""Carpetas de proyecto y operaciones de archivos seguras.

Toda ruta que se borra, se sirve o se mueve se comprueba con ``resolve()``
para garantizar que queda dentro de la carpeta esperada.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from pcapp_servidor.errores import no_encontrado

_ID_VALIDO = re.compile(r"[0-9a-f]{32}")
ANTERIORES = "anteriores"


def dentro_de(ruta: Path, base: Path) -> bool:
    return ruta.resolve().is_relative_to(base.resolve())


class Archivos:
    def __init__(self, datos: Path) -> None:
        self.datos = datos
        self.proyectos = datos / "proyectos"
        self.proyectos.mkdir(parents=True, exist_ok=True)

    def carpeta(self, proyecto_id: str) -> Path:
        """Carpeta del proyecto; el id debe tener el formato generado por el servidor."""
        if not _ID_VALIDO.fullmatch(proyecto_id):
            raise no_encontrado("El proyecto no existe.", "PROYECTO_NO_ENCONTRADO")
        carpeta = self.proyectos / proyecto_id
        if not dentro_de(carpeta, self.proyectos):
            raise no_encontrado("El proyecto no existe.", "PROYECTO_NO_ENCONTRADO")
        return carpeta

    def borrar_carpeta(self, proyecto_id: str) -> None:
        carpeta = self.carpeta(proyecto_id)
        if carpeta.exists():
            if not dentro_de(carpeta, self.datos) or carpeta.resolve() == self.datos.resolve():
                raise RuntimeError(f"Ruta de proyecto fuera de la carpeta de datos: {carpeta}")
            shutil.rmtree(carpeta)

    def archivar(self, proyecto_id: str, nombres: list[str]) -> Path | None:
        """Mueve los archivos existentes a ``anteriores/<fecha-hora>/``; devuelve esa carpeta."""
        carpeta = self.carpeta(proyecto_id)
        existentes = [carpeta / n for n in nombres if (carpeta / n).exists()]
        if not existentes:
            return None
        marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destino = carpeta / ANTERIORES / marca
        destino.mkdir(parents=True)
        for ruta in existentes:
            shutil.move(str(ruta), str(destino / ruta.name))
        return destino

    @staticmethod
    def escribir_json(ruta: Path, datos: Any) -> None:
        temporal = ruta.with_name(ruta.name + ".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(ruta)

    @staticmethod
    def leer_json(ruta: Path) -> Any:
        return json.loads(ruta.read_text(encoding="utf-8"))

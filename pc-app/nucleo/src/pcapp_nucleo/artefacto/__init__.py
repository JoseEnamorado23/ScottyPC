"""Artefacto ``.scotty``: empaqueta un proyecto con prescripción vigente para servirlo sin reentrenar.

- ``formato``: esquemas y validación de los JSON del artefacto.
- ``exportar``: ``exportar_artefacto`` (a partir de un proyecto de Scotty PC).
- ``cargar``: ``cargar_artefacto`` y la API ``Artefacto`` (predecir, prescribir, contrafactual, lote).
- ``golden``: casos de verificación y ``verificar_golden``.

Solo ``formato`` se importa al importar el paquete: ``exportar`` y ``cargar`` arrastran el modelo y el
optimizador, y sus nombres públicos se resuelven la primera vez que se piden (``__getattr__``).
"""

from importlib import import_module
from typing import Any

from pcapp_nucleo.artefacto.formato import (
    EXTENSION,
    FORMATO,
    VERSION_FORMATO,
    ErrorFormatoArtefacto,
    Manifest,
    controles_desde_diccionario,
    esquema_entrada_desde_diccionario,
    manifest_desde_diccionario,
)

__all__ = [
    "EXTENSION",
    "FORMATO",
    "VERSION_FORMATO",
    "ErrorFormatoArtefacto",
    "Manifest",
    "controles_desde_diccionario",
    "esquema_entrada_desde_diccionario",
    "manifest_desde_diccionario",
]

_PEREZOSOS = {
    "Artefacto": "cargar", "ErrorArtefacto": "cargar", "ErrorSolicitud": "cargar", "cargar_artefacto": "cargar",
    "ErrorExportacion": "exportar", "exportar_artefacto": "exportar", "exportar_artefacto_completo": "exportar",
    "verificar_golden": "golden",
}
__all__ += sorted(_PEREZOSOS)


def __getattr__(nombre: str) -> Any:
    if nombre in _PEREZOSOS:
        return getattr(import_module(f"pcapp_nucleo.artefacto.{_PEREZOSOS[nombre]}"), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")

"""Configuración del servidor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PUERTO_DESARROLLO = 8765

# Orígenes de la aplicación Tauri (macOS/Linux y Windows) y del servidor de desarrollo de Vite.
ORIGENES_PERMITIDOS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True)
class ConfiguracionServidor:
    """``token=None`` desactiva la autenticación (solo en modo desarrollo)."""

    datos: Path
    token: str | None
    desarrollo: bool = False
    procesos: int | None = None  # tamaño del grupo de procesos; None = núcleos − 1

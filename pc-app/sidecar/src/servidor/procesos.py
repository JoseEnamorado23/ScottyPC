"""Grupo de procesos reutilizable entre análisis.

Arrancar los procesos de trabajo cuesta varios segundos en Windows (cada uno
importa causal-learn). El grupo se crea solo cuando un análisis decide ir en
paralelo (``EjecutorPerezoso``) y se reutiliza después.

Tras una cancelación hay que reciclarlo (sus procesos siguen ocupados con
corridas descartadas), pero puede estar en uso por el análisis de otro
proyecto. Por eso cada análisis lo usa dentro de ``uso()`` y la cancelación
solo lo marca con ``reciclar_al_liberar()``: se recicla cuando lo suelta el
último análisis que lo usaba.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from concurrent.futures import Executor, Future, ProcessPoolExecutor
from contextlib import contextmanager
from typing import Any

from nucleo.pc_bootstrap import crear_grupo_procesos

from servidor.registro import REGISTRO


def _terminar(grupo: ProcessPoolExecutor) -> None:
    if hasattr(grupo, "terminate_workers"):  # Python >= 3.14
        grupo.terminate_workers()
        return
    for proceso in list(getattr(grupo, "_processes", {}).values()):
        proceso.terminate()
    grupo.shutdown(wait=False, cancel_futures=True)


class GrupoProcesos:
    def __init__(self, procesos: int | None = None) -> None:
        self.procesos = procesos or max(1, (os.cpu_count() or 2) - 1)
        self._grupo: ProcessPoolExecutor | None = None
        self._cerrado = False
        self._usuarios = 0
        self._reciclar_pendiente = False
        self._candado = threading.Lock()

    @property
    def creado(self) -> bool:
        return self._grupo is not None

    @contextmanager
    def uso(self) -> Iterator[Executor]:
        """Ejecutor perezoso para un análisis; registra que el grupo está en uso."""
        with self._candado:
            self._usuarios += 1
        try:
            yield EjecutorPerezoso(self)
        finally:
            with self._candado:
                self._usuarios -= 1
                reciclar = self._reciclar_pendiente and self._usuarios == 0
                if reciclar:
                    self._reciclar_pendiente = False
            if reciclar:
                self.reciclar()

    def reciclar_al_liberar(self) -> None:
        with self._candado:
            if self._grupo is not None:
                self._reciclar_pendiente = True

    def obtener(self) -> ProcessPoolExecutor:
        with self._candado:
            if self._cerrado:
                raise RuntimeError("El grupo de procesos está cerrado.")
            if self._grupo is None:
                REGISTRO.info("Creando el grupo de %d procesos", self.procesos)
                self._grupo = crear_grupo_procesos(self.procesos)
            return self._grupo

    def reciclar(self) -> None:
        with self._candado:
            if self._grupo is not None:
                REGISTRO.info("Reciclando el grupo de procesos")
                _terminar(self._grupo)
                self._grupo = None

    def cerrar(self) -> None:
        with self._candado:
            self._cerrado = True
            if self._grupo is not None:
                _terminar(self._grupo)
                self._grupo = None

class EjecutorPerezoso(Executor):
    """Crea el grupo real en el primer ``submit`` (solo si el análisis va en paralelo)."""

    def __init__(self, grupo: GrupoProcesos) -> None:
        self._grupo = grupo

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future:
        return self._grupo.obtener().submit(fn, *args, **kwargs)

"""Trabajos en segundo plano (recomendación de prueba y análisis PC).

Cada trabajo corre en un hilo propio con un evento de cancelación. El
progreso se guarda en memoria en cada corrida y en SQLite como mucho una vez
por segundo (y siempre al terminar). Si el servidor se reinicia, los trabajos
que estaban activos quedan como "interrumpidos" y pueden reanudarse.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from pcapp_servidor.almacenamiento.base_datos import ahora
from pcapp_servidor.almacenamiento.repositorio import RepositorioTrabajos, Trabajo
from pcapp_servidor.errores import ErrorApi, conflicto, no_encontrado
from pcapp_servidor.registro import REGISTRO

REANUDABLES = ("cancelado", "interrumpido", "fallido")
_INTERVALO_GUARDADO_S = 1.0


@dataclass
class Contexto:
    """Lo que recibe la función de un trabajo."""

    trabajo_id: str
    cancelacion: threading.Event
    reanudar: bool
    reportar: Callable[..., None]
    parametros: dict[str, Any] = field(default_factory=dict)
    # Detalles del trabajo en curso (p. ej. el modo de ejecución); solo en memoria.
    detallar: Callable[..., None] = lambda **_: None


@dataclass
class _Activo:
    trabajo: Trabajo
    hilo: threading.Thread
    cancelacion: threading.Event
    restantes_s: float | None = None
    detalles: dict[str, Any] | None = None
    guardado_en: float = 0.0
    inicio_monotono: float = field(default_factory=time.monotonic)

    def segundos(self) -> float:
        """El mayor entre lo reportado (incluye sesiones previas) y lo medido aquí."""
        return round(max(self.trabajo.segundos, time.monotonic() - self.inicio_monotono), 2)


FuncionTrabajo = Callable[[Contexto], str | None]
"""Ejecuta el trabajo; devuelve un mensaje final opcional. Lanza ErrorApi ante
errores del usuario; cualquier otra excepción se registra como error técnico."""


class GestorTrabajos:
    def __init__(self, repositorio: RepositorioTrabajos) -> None:
        self.repositorio = repositorio
        self._activos: dict[str, _Activo] = {}
        self._candado = threading.Lock()
        self._apagando = False

    # --- Consulta -------------------------------------------------------------------------

    def obtener(self, trabajo_id: str) -> tuple[Trabajo, float | None]:
        """Trabajo (con el progreso en memoria si está activo) y segundos restantes estimados."""
        with self._candado:
            activo = self._activos.get(trabajo_id)
            if activo is not None:
                return replace(activo.trabajo, segundos=activo.segundos()), activo.restantes_s
        trabajo = self.repositorio.obtener(trabajo_id)
        if trabajo is None:
            raise no_encontrado("El trabajo no existe.", "TRABAJO_NO_ENCONTRADO")
        return trabajo, None

    def detalles(self, trabajo_id: str) -> dict[str, Any] | None:
        with self._candado:
            activo = self._activos.get(trabajo_id)
            return dict(activo.detalles) if activo is not None and activo.detalles else None

    def hay_activo(self, proyecto_id: str) -> bool:
        return self.repositorio.activo_de(proyecto_id) is not None

    def exigir_sin_activo(self, proyecto_id: str) -> None:
        if self.hay_activo(proyecto_id):
            raise conflicto(
                "TRABAJO_ACTIVO",
                "El proyecto tiene un trabajo en curso; espere a que termine o cancélelo antes de "
                "modificarlo.",
            )

    # --- Ciclo de vida ------------------------------------------------------------------

    def iniciar(
        self, proyecto_id: str, tipo: str, funcion: FuncionTrabajo, parametros: dict[str, Any]
    ) -> Trabajo:
        if self._apagando:
            raise conflicto("SERVIDOR_APAGANDOSE", "El servidor se está apagando.")
        momento = ahora()
        trabajo = Trabajo(
            id=uuid.uuid4().hex, proyecto_id=proyecto_id, tipo=tipo, estado="en_curso",
            completadas=0, total=None, fallidas=0, segundos=0.0, mensaje=None,
            parametros=parametros, inicio=momento, fin=None, error=None, actualizado_en=momento,
        )
        self.repositorio.crear(trabajo)
        self._lanzar(trabajo, funcion, reanudar=False)
        return trabajo

    def reanudar(self, trabajo_id: str, funcion: FuncionTrabajo) -> Trabajo:
        trabajo, _ = self.obtener(trabajo_id)
        if trabajo.estado not in REANUDABLES:
            raise conflicto(
                "TRABAJO_NO_REANUDABLE",
                f"Solo se pueden reanudar trabajos cancelados, interrumpidos o fallidos (estado: {trabajo.estado}).",
            )
        self.repositorio.actualizar(trabajo_id, estado="en_curso", fin=None, error=None, mensaje=None)
        trabajo = replace(trabajo, estado="en_curso", fin=None, error=None, mensaje=None)
        self._lanzar(trabajo, funcion, reanudar=True)
        return trabajo

    def cancelar(self, trabajo_id: str) -> Trabajo:
        with self._candado:
            activo = self._activos.get(trabajo_id)
        if activo is None:
            trabajo, _ = self.obtener(trabajo_id)
            raise conflicto("TRABAJO_NO_ACTIVO", f"El trabajo no está en curso (estado: {trabajo.estado}).")
        activo.cancelacion.set()
        activo.trabajo.mensaje = "Cancelación solicitada."
        return replace(activo.trabajo)

    def esperar(self, trabajo_id: str, segundos: float | None = None) -> None:
        with self._candado:
            activo = self._activos.get(trabajo_id)
        if activo is not None:
            activo.hilo.join(segundos)

    def detener_todos(self, espera_s: float = 10.0) -> None:
        """Al apagar: cancela los trabajos activos y espera a que guarden su estado."""
        self._apagando = True
        with self._candado:
            activos = list(self._activos.values())
        for activo in activos:
            activo.cancelacion.set()
        limite = time.monotonic() + espera_s
        for activo in activos:
            activo.hilo.join(max(0.0, limite - time.monotonic()))

    # --- Ejecución -------------------------------------------------------------------------

    def _lanzar(self, trabajo: Trabajo, funcion: FuncionTrabajo, reanudar: bool) -> None:
        cancelacion = threading.Event()
        activo = _Activo(trabajo, threading.Thread(), cancelacion)
        contexto = Contexto(
            trabajo.id, cancelacion, reanudar,
            lambda **avance: self._reportar(activo, **avance), trabajo.parametros,
            lambda **detalles: self._detallar(activo, detalles),
        )
        activo.hilo = threading.Thread(
            target=self._ejecutar, args=(activo, funcion, contexto), name=f"trabajo-{trabajo.id[:8]}", daemon=True
        )
        with self._candado:
            self._activos[trabajo.id] = activo
        activo.hilo.start()

    def _reportar(
        self, activo: _Activo, completadas: int, total: int, fallidas: int = 0,
        segundos: float = 0.0, restantes_s: float | None = None,
    ) -> None:
        with self._candado:
            activo.trabajo.completadas, activo.trabajo.total = completadas, total
            activo.trabajo.fallidas, activo.trabajo.segundos = fallidas, round(segundos, 2)
            activo.restantes_s = None if restantes_s is None else round(restantes_s, 1)
            guardar = time.monotonic() - activo.guardado_en >= _INTERVALO_GUARDADO_S
            if guardar:
                activo.guardado_en = time.monotonic()
        if guardar:
            self._guardar_progreso(activo.trabajo)

    def _detallar(self, activo: _Activo, detalles: dict[str, Any]) -> None:
        with self._candado:
            activo.detalles = {**(activo.detalles or {}), **detalles}

    def _guardar_progreso(self, trabajo: Trabajo) -> None:
        self.repositorio.actualizar(
            trabajo.id, completadas=trabajo.completadas, total=trabajo.total,
            fallidas=trabajo.fallidas, segundos=trabajo.segundos, mensaje=trabajo.mensaje,
        )

    def _ejecutar(self, activo: _Activo, funcion: FuncionTrabajo, contexto: Contexto) -> None:
        trabajo = activo.trabajo
        estado, mensaje, error = "completado", None, None
        try:
            mensaje = funcion(contexto)
            if contexto.cancelacion.is_set():
                estado = "interrumpido" if self._apagando else "cancelado"
                mensaje = (
                    "El servidor se apagó durante el trabajo; puede reanudarlo."
                    if self._apagando else "Trabajo cancelado; puede reanudarlo."
                )
        except ErrorApi as problema:
            estado, error = "fallido", problema.mensaje
        except Exception:  # noqa: BLE001 - el detalle técnico va al registro, nunca al cliente
            referencia = uuid.uuid4().hex[:12]
            REGISTRO.exception("Error en el trabajo %s (referencia %s)", trabajo.id, referencia)
            estado, error = "fallido", f"Error interno; consulte el registro del servidor (referencia {referencia})."
        with self._candado:
            trabajo.estado, trabajo.mensaje, trabajo.error, trabajo.fin = estado, mensaje, error, ahora()
            trabajo.segundos = activo.segundos()
            self._activos.pop(trabajo.id, None)
        self.repositorio.actualizar(
            trabajo.id, estado=estado, mensaje=mensaje, error=error, fin=trabajo.fin,
            completadas=trabajo.completadas, total=trabajo.total, fallidas=trabajo.fallidas,
            segundos=trabajo.segundos,
        )
        REGISTRO.info("Trabajo %s (%s) terminado: %s", trabajo.id, trabajo.tipo, estado)

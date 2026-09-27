"""Trabajos en segundo plano."""

from fastapi import APIRouter, Depends

from pcapp_servidor.esquemas import RESPUESTAS_ERROR, Trabajo
from pcapp_servidor.flujo import Servicios
from pcapp_servidor.rutas import servicios

router = APIRouter(prefix="/trabajos", tags=["trabajos"], responses=RESPUESTAS_ERROR)


@router.get("/{trabajo_id}", response_model=Trabajo, summary="Estado y progreso de un trabajo")
def estado(trabajo_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.estado_trabajo(trabajo_id)


@router.post("/{trabajo_id}/cancelar", response_model=Trabajo, summary="Cancela un trabajo en curso")
def cancelar(trabajo_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.vista_trabajo(s.trabajos.cancelar(trabajo_id))


@router.post("/{trabajo_id}/reanudar", response_model=Trabajo, status_code=202, summary="Reanuda un trabajo")
def reanudar(trabajo_id: str, s: Servicios = Depends(servicios)) -> dict:
    """Un análisis PC continúa desde su punto de control; una recomendación se repite."""
    return s.vista_trabajo(s.reanudar_trabajo(trabajo_id))

"""Salud y apagado del servidor."""

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Depends, Request

from pcapp_servidor import __version__
from pcapp_servidor.esquemas import Apagado, Salud
from pcapp_servidor.flujo import Servicios
from pcapp_servidor.rutas import servicios

router = APIRouter(tags=["sistema"])


def _version_nucleo() -> str:
    try:
        return version("pcapp_nucleo")
    except PackageNotFoundError:
        return "desconocida"


@router.get("/salud", response_model=Salud, summary="Estado del servidor")
def salud(s: Servicios = Depends(servicios)) -> dict:
    return {
        "estado": "ok",
        "version_servidor": __version__,
        "version_nucleo": _version_nucleo(),
        "grupo_procesos_creado": s.grupo.creado,
    }


@router.post("/apagar", response_model=Apagado, summary="Apaga el servidor")
def apagar(peticion: Request) -> dict:
    peticion.app.state.apagar()
    return {"mensaje": "Apagando el servidor; los trabajos en curso quedarán interrumpidos y podrán reanudarse."}

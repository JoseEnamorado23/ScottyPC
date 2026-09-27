"""Rutas HTTP de la API."""

from fastapi import Request

from pcapp_servidor.flujo import Servicios


def servicios(peticion: Request) -> Servicios:
    return peticion.app.state.servicios

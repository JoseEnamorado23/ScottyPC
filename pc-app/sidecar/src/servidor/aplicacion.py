"""Construcción de la aplicación FastAPI."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from servidor import __version__
from servidor.almacenamiento.base_datos import BaseDatos
from servidor.configuracion import ORIGENES_PERMITIDOS, ConfiguracionServidor
from servidor.errores import cuerpo_error, registrar_manejadores
from servidor.flujo import Servicios
from servidor.registro import REGISTRO
from servidor.rutas import proyectos, sistema, trabajos


def crear_aplicacion(
    configuracion: ConfiguracionServidor, apagar: Callable[[], None] | None = None
) -> FastAPI:
    """Crea la aplicación. ``apagar`` detiene el servidor (lo usa POST /apagar)."""
    configuracion.datos.mkdir(parents=True, exist_ok=True)
    servicios = Servicios(configuracion, BaseDatos(configuracion.datos / "app.db"))

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        interrumpidos = servicios.trabajos.repositorio.marcar_interrumpidos()
        if interrumpidos:
            REGISTRO.info("%d trabajo(s) quedaron interrumpidos por un cierre anterior", interrumpidos)
        yield
        servicios.apagar()

    aplicacion = FastAPI(
        title="pc-app: servidor local",
        version=__version__,
        description="API local que expone el núcleo de pc-app. Todas las peticiones requieren el "
        "encabezado X-Token con el token que el servidor imprime al arrancar.",
        lifespan=ciclo_de_vida,
    )
    aplicacion.state.servicios = servicios
    aplicacion.state.apagar = apagar or (lambda: None)
    registrar_manejadores(aplicacion)

    token = configuracion.token

    @aplicacion.middleware("http")
    async def exigir_token(peticion: Request, siguiente):  # noqa: ANN001
        if token is not None and peticion.method != "OPTIONS":
            recibido = peticion.headers.get("x-token", "")
            if not hmac.compare_digest(recibido.encode(), token.encode()):
                return JSONResponse(
                    cuerpo_error("NO_AUTORIZADO", "Falta el encabezado X-Token o no es válido."), status_code=401
                )
        return await siguiente(peticion)

    # Se añade después del token para envolverlo: las respuestas 401 también llevan CORS.
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=list(ORIGENES_PERMITIDOS),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-Token", "Content-Type"],
    )
    for modulo in (sistema, proyectos, trabajos):
        aplicacion.include_router(modulo.router)
    return aplicacion

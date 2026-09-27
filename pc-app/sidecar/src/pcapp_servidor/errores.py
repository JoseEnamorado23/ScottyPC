"""Errores de la API con un formato uniforme.

Todas las respuestas de error tienen la forma
``{"error": {"codigo": ..., "mensaje": ..., "detalles": ...}}``. Los errores
técnicos inesperados se registran en el log con una referencia y el cliente
solo recibe esa referencia.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pcapp_servidor.registro import REGISTRO


class ErrorApi(Exception):
    def __init__(self, estado: int, codigo: str, mensaje: str, detalles: Any = None) -> None:
        super().__init__(mensaje)
        self.estado, self.codigo, self.mensaje, self.detalles = estado, codigo, mensaje, detalles


def no_encontrado(mensaje: str, codigo: str = "NO_ENCONTRADO") -> ErrorApi:
    return ErrorApi(404, codigo, mensaje)


def conflicto(codigo: str, mensaje: str, detalles: Any = None) -> ErrorApi:
    return ErrorApi(409, codigo, mensaje, detalles)


def invalido(codigo: str, mensaje: str, detalles: Any = None) -> ErrorApi:
    return ErrorApi(422, codigo, mensaje, detalles)


def cuerpo_error(codigo: str, mensaje: str, detalles: Any = None) -> dict[str, Any]:
    return {"error": {"codigo": codigo, "mensaje": mensaje, "detalles": detalles}}


_MENSAJES_VALIDACION = {
    "missing": "Campo obligatorio.",
    "extra_forbidden": "Campo desconocido.",
    "literal_error": "Valor no permitido.",
    "string_type": "Debe ser un texto.",
    "int_type": "Debe ser un número entero.",
    "int_parsing": "Debe ser un número entero.",
    "float_type": "Debe ser un número.",
    "float_parsing": "Debe ser un número.",
    "bool_type": "Debe ser verdadero o falso.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "list_type": "Debe ser una lista.",
    "dict_type": "Debe ser un objeto.",
    "model_type": "Debe ser un objeto.",
    "greater_than": "Valor demasiado pequeño.",
    "greater_than_equal": "Valor demasiado pequeño.",
    "less_than": "Valor demasiado grande.",
    "less_than_equal": "Valor demasiado grande.",
    "json_invalid": "El cuerpo de la petición no es JSON válido.",
}


def errores_por_campo(error: RequestValidationError) -> list[dict[str, str]]:
    """Errores de Pydantic como ``[{"campo": "a.b.0", "mensaje": ...}]`` en español."""
    detalles = []
    for problema in error.errors():
        ubicacion = [str(p) for p in problema.get("loc", ()) if p not in ("body", "query", "path")]
        mensaje = _MENSAJES_VALIDACION.get(problema.get("type", ""), "Valor no válido.")
        opciones = (problema.get("ctx") or {}).get("expected")
        if problema.get("type") == "literal_error" and opciones:
            mensaje = f"Valor no permitido; opciones: {opciones}."
        limite = (problema.get("ctx") or {})
        for clave in ("gt", "ge", "lt", "le"):
            if clave in limite:
                simbolo = {"gt": ">", "ge": ">=", "lt": "<", "le": "<="}[clave]
                mensaje = f"Debe ser {simbolo} {limite[clave]}."
        detalles.append({"campo": ".".join(ubicacion), "mensaje": mensaje})
    return detalles


def registrar_manejadores(aplicacion: FastAPI) -> None:
    @aplicacion.exception_handler(ErrorApi)
    async def _error_api(_: Request, error: ErrorApi) -> JSONResponse:
        return JSONResponse(cuerpo_error(error.codigo, error.mensaje, error.detalles), status_code=error.estado)

    @aplicacion.exception_handler(RequestValidationError)
    async def _validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            cuerpo_error("DATOS_NO_VALIDOS", "Hay datos no válidos en la petición.", errores_por_campo(error)),
            status_code=422,
        )

    @aplicacion.exception_handler(StarletteHTTPException)
    async def _http(_: Request, error: StarletteHTTPException) -> JSONResponse:
        mensajes = {404: ("NO_ENCONTRADO", "Recurso no encontrado."),
                    405: ("METODO_NO_PERMITIDO", "Método no permitido para este recurso.")}
        codigo, mensaje = mensajes.get(error.status_code, ("ERROR_HTTP", str(error.detail)))
        return JSONResponse(cuerpo_error(codigo, mensaje), status_code=error.status_code)

    @aplicacion.exception_handler(Exception)
    async def _inesperado(peticion: Request, error: Exception) -> JSONResponse:
        referencia = uuid.uuid4().hex[:12]
        REGISTRO.exception("Error interno %s en %s %s", referencia, peticion.method, peticion.url.path)
        return JSONResponse(
            cuerpo_error(
                "ERROR_INTERNO",
                f"Ocurrió un error interno. Consulte el registro del servidor (referencia {referencia}).",
                {"referencia": referencia},
            ),
            status_code=500,
        )

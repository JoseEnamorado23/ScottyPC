"""Configuración del análisis PC con bootstrap.

``ConfiguracionPC`` es serializable a JSON y se guarda junto a la receta.
Los ``niveles`` expresan el conocimiento mínimo del usuario: nada de un nivel
posterior puede causar algo de un nivel anterior.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Any

PRUEBAS_PC = ("fisherz", "mv_fisherz", "chisq", "kci")


class ErrorConfiguracionPC(Exception):
    """Configuración no válida para los datos, con un mensaje para el usuario."""


def _procesos_por_defecto() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


@dataclass(frozen=True)
class OrientacionManual:
    """Orientación impuesta por el usuario a una arista que PC deja sin orientar."""

    origen: str
    destino: str
    justificacion: str = ""


@dataclass(frozen=True)
class ConfiguracionPC:
    """Parámetros de PC con bootstrap.

    - ``umbral_frecuencia``: fracción mínima de corridas válidas en que debe
      aparecer una arista (en cualquier orientación) para aceptarla.
    - ``procesos``: procesos en paralelo; no cambia el resultado.
    - ``punto_control_cada``: cada cuántas corridas se guarda un punto de
      control (si se indicó un archivo).
    """

    prueba: str = "fisherz"
    alpha: float = 0.05
    corridas_bootstrap: int = 100
    fraccion_submuestra: float = 0.8
    umbral_frecuencia: float = 0.6
    max_k: int | None = None
    semilla: int = 42
    procesos: int = field(default_factory=_procesos_por_defecto)
    niveles: list[list[str]] = field(default_factory=list)
    modificables: list[str] = field(default_factory=list)
    orientaciones_manuales: list[OrientacionManual] = field(default_factory=list)
    punto_control_cada: int = 10


def nivel_por_variable(configuracion: ConfiguracionPC) -> dict[str, int]:
    return {v: i for i, nivel in enumerate(configuracion.niveles) for v in nivel}


def configuracion_por_defecto(
    variables: list[str], objetivo: str, prueba: str = "fisherz", max_k: int | None = None
) -> ConfiguracionPC:
    """Todas las variables en un nivel y el objetivo en un nivel posterior."""
    return ConfiguracionPC(
        prueba=prueba,
        max_k=max_k,
        niveles=[[v for v in variables if v != objetivo], [objetivo]],
    )


def configuracion_desde_diccionario(datos: Any) -> ConfiguracionPC:
    """Construye ``ConfiguracionPC`` desde un diccionario (p. ej. leído de JSON)."""
    if not isinstance(datos, dict):
        raise ErrorConfiguracionPC("La configuración de PC debe ser un objeto JSON.")
    nombres = {f.name for f in fields(ConfiguracionPC)}
    desconocidos = sorted(set(datos) - nombres)
    if desconocidos:
        raise ErrorConfiguracionPC(
            f"La configuración de PC contiene campos desconocidos: {', '.join(desconocidos)}."
        )
    orientaciones = []
    for i, valor in enumerate(datos.get("orientaciones_manuales", [])):
        try:
            orientaciones.append(OrientacionManual(**valor))
        except TypeError as error:
            raise ErrorConfiguracionPC(f"La orientación manual {i + 1} no es válida: {error}.") from error
    try:
        return ConfiguracionPC(**{**datos, "orientaciones_manuales": orientaciones})
    except TypeError as error:
        raise ErrorConfiguracionPC(f"La configuración de PC no es válida: {error}.") from error


def validar_configuracion(
    configuracion: ConfiguracionPC, variables: list[str], objetivo: str
) -> None:
    """Comprueba la configuración frente a las variables del conjunto de entrenamiento.

    Raises:
        ErrorConfiguracionPC: con un mensaje en español si algo no es válido.
    """
    c = configuracion
    if c.prueba not in PRUEBAS_PC:
        raise ErrorConfiguracionPC(
            f"Prueba no válida: {c.prueba!r}. Opciones: {', '.join(PRUEBAS_PC)}."
        )
    comprobaciones = [
        (0 < c.alpha < 1, "alpha debe estar entre 0 y 1."),
        (c.corridas_bootstrap >= 1, "corridas_bootstrap debe ser al menos 1."),
        (0 < c.fraccion_submuestra <= 1, "fraccion_submuestra debe estar entre 0 y 1."),
        (0 < c.umbral_frecuencia <= 1, "umbral_frecuencia debe estar entre 0 y 1."),
        (c.max_k is None or c.max_k >= 0, "max_k debe ser null o un entero no negativo."),
        (c.procesos >= 1, "procesos debe ser al menos 1."),
        (c.punto_control_cada >= 1, "punto_control_cada debe ser al menos 1."),
    ]
    for valido, mensaje in comprobaciones:
        if not valido:
            raise ErrorConfiguracionPC(mensaje)

    en_niveles = [v for nivel in c.niveles for v in nivel]
    repetidas = sorted({v for v in en_niveles if en_niveles.count(v) > 1})
    if repetidas:
        raise ErrorConfiguracionPC(
            f"Estas variables aparecen en más de un nivel: {', '.join(repetidas)}."
        )
    desconocidas = sorted(set(en_niveles) - set(variables))
    if desconocidas:
        raise ErrorConfiguracionPC(
            f"Los niveles mencionan variables que no están en los datos preparados: "
            f"{', '.join(desconocidas)}."
        )
    ausentes = [v for v in variables if v not in en_niveles]
    if objetivo in ausentes:
        raise ErrorConfiguracionPC(f"El objetivo '{objetivo}' debe estar en algún nivel.")
    if ausentes:
        raise ErrorConfiguracionPC(
            f"Cada variable debe estar en exactamente un nivel; faltan: {', '.join(ausentes)}."
        )

    candidatas = set(variables) - {objetivo}
    fuera = sorted(set(c.modificables) - candidatas)
    if fuera:
        raise ErrorConfiguracionPC(
            f"Las variables modificables deben ser variables de los datos distintas del "
            f"objetivo: {', '.join(fuera)}."
        )

    nivel = nivel_por_variable(c)
    for orientacion in c.orientaciones_manuales:
        for extremo in (orientacion.origen, orientacion.destino):
            if extremo not in nivel:
                raise ErrorConfiguracionPC(
                    f"La orientación manual menciona una variable desconocida: '{extremo}'."
                )
        if nivel[orientacion.origen] > nivel[orientacion.destino]:
            raise ErrorConfiguracionPC(
                f"La orientación manual {orientacion.origen} → {orientacion.destino} contradice "
                "los niveles: una variable de un nivel posterior no puede causar una de un nivel "
                "anterior."
            )

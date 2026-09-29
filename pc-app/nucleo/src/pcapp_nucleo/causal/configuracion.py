"""Configuración del modelo causal (umbrales y overrides del usuario)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

MONOTONIAS = ("creciente", "decreciente", "ninguna")
ELECCIONES_MECANISMO = ("simple", "complejo")


def decimal(valor: float, formato: str = ".3f") -> str:
    """Número con coma decimal para los mensajes."""
    return format(valor, formato).replace(".", ",")


@dataclass(frozen=True)
class ConfiguracionModeloCausal:
    """Parámetros de construcción. Los valores por defecto sirven para cualquier dataset.

    - ``umbral_parsimonia``: mejora mínima en validación cruzada (R² o exactitud
      balanceada) para preferir el mecanismo complejo al simple.
    - ``umbral_referencia``: diferencia a partir de la cual el mecanismo del objetivo se
      considera claramente peor que el modelo de referencia (todas las variables).
    - ``pesos_clase``: ajusta el objetivo binario con pesos de clase; las probabilidades
      dejan de estar calibradas (por defecto no, y el desbalance se compensa con el umbral).
    - ``monotonia``: override por padre del objetivo (``creciente``, ``decreciente`` o
      ``ninguna``); los que no aparecen se deciden con la recomendación de prueba.
    - ``mecanismos``: override por variable (``simple`` o ``complejo``).
    """

    semilla: int = 42
    pliegues: int = 5
    umbral_parsimonia: float = 0.02
    umbral_referencia: float = 0.02
    filas_por_padre: int = 10
    minoritaria_por_padre: int = 10
    r2_minimo_intermedia: float = 0.10
    exactitud_minima_intermedia: float = 0.60
    muestras_abduccion: int = 200
    nodos_splines: int = 5
    splines_gam: int = 10
    lams_gam: tuple[float, ...] = (1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0, 1000.0)
    valores_minimos_spline: int = 10
    pesos_clase: bool = False
    monotonia: dict[str, str] = field(default_factory=dict)
    mecanismos: dict[str, str] = field(default_factory=dict)
    puntos_curva: int = 50
    intervalos_calibracion: int = 10
    intervalos_histograma: int = 20


class ErrorConfiguracionCausal(ValueError):
    """La configuración no es válida; ``campo`` indica dónde."""

    def __init__(self, mensaje: str, campo: str) -> None:
        super().__init__(mensaje)
        self.campo = campo


def configuracion_desde_diccionario(datos: dict[str, Any] | None) -> ConfiguracionModeloCausal:
    datos = dict(datos or {})
    conocidos = {f.name for f in fields(ConfiguracionModeloCausal)}
    desconocidos = sorted(set(datos) - conocidos)
    if desconocidos:
        raise ErrorConfiguracionCausal(f"Campo desconocido: {desconocidos[0]}.", desconocidos[0])
    if "lams_gam" in datos:
        datos["lams_gam"] = tuple(float(v) for v in datos["lams_gam"])
    for padre, valor in (datos.get("monotonia") or {}).items():
        if valor not in MONOTONIAS:
            raise ErrorConfiguracionCausal(
                f"La monotonía de '{padre}' debe ser una de: {', '.join(MONOTONIAS)}.", f"monotonia.{padre}"
            )
    for variable, valor in (datos.get("mecanismos") or {}).items():
        if valor not in ELECCIONES_MECANISMO:
            raise ErrorConfiguracionCausal(
                f"El mecanismo de '{variable}' debe ser 'simple' o 'complejo'.", f"mecanismos.{variable}"
            )
    configuracion = ConfiguracionModeloCausal(**datos)
    if configuracion.pliegues < 2:
        raise ErrorConfiguracionCausal("Se necesitan al menos 2 pliegues.", "pliegues")
    if configuracion.muestras_abduccion < 1:
        raise ErrorConfiguracionCausal("Se necesita al menos una muestra de abducción.", "muestras_abduccion")
    return configuracion

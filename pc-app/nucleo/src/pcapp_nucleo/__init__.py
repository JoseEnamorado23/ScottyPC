"""Núcleo de análisis para la aplicación de investigación sobre modelos prescriptivos."""

from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.modelos import (
    CodigoValidacion,
    Hallazgo,
    InformeRevision,
    NivelProblema,
    PerfilColumna,
    ProblemaValidacion,
    ResultadoAnalisis,
    ResultadoValidacion,
    Severidad,
)

__version__ = "0.1.0"

__all__ = [
    "CodigoValidacion",
    "ConfiguracionValidacion",
    "Hallazgo",
    "InformeRevision",
    "NivelProblema",
    "PerfilColumna",
    "ProblemaValidacion",
    "ResultadoAnalisis",
    "ResultadoValidacion",
    "Severidad",
]

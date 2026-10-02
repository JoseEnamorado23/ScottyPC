"""Optimizador de prescripciones sobre el motor de contrafactuales del modelo causal."""

from pcapp_nucleo.prescripcion.calibracion import CalibracionCancelada, CalibracionMu, calibrar_mu
from pcapp_nucleo.prescripcion.condiciones import MENSAJE_SIN_PRESCRIPTIVAS, evaluar_prescribibilidad
from pcapp_nucleo.prescripcion.configuracion import (
    AUTOMATICO,
    ConfiguracionAccion,
    ConfiguracionPrescripcion,
    ErrorConfiguracionPrescripcion,
    ObjetivoDeseado,
    Supuestos,
    completar,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    confirmar_supuestos,
    problemas_configuracion,
    variables_prescriptivas,
)
from pcapp_nucleo.prescripcion.informe import AVISO_PERMANENTE, informe_prescripcion_html, prescripciones_csv
from pcapp_nucleo.prescripcion.lotes import (
    TEXTO_EVALUACION_INTERNA,
    EvaluacionPrescriptor,
    LoteCancelado,
    evaluar_prescriptor,
    prescribir_lote,
    que_no_cumplen,
)
from pcapp_nucleo.prescripcion.optimizadores import Genetico, GradienteProximal, crear_optimizador
from pcapp_nucleo.prescripcion.prescriptor import ResultadoPrescripcion, prescribir_caso
from pcapp_nucleo.prescripcion.referencia import ModeloReferencia, ajustar_referencia, referencia_desde_diccionario

__all__ = [
    "AUTOMATICO",
    "AVISO_PERMANENTE",
    "CalibracionCancelada",
    "CalibracionMu",
    "ConfiguracionAccion",
    "ConfiguracionPrescripcion",
    "ErrorConfiguracionPrescripcion",
    "EvaluacionPrescriptor",
    "Genetico",
    "GradienteProximal",
    "LoteCancelado",
    "MENSAJE_SIN_PRESCRIPTIVAS",
    "ModeloReferencia",
    "ObjetivoDeseado",
    "ResultadoPrescripcion",
    "Supuestos",
    "TEXTO_EVALUACION_INTERNA",
    "ajustar_referencia",
    "calibrar_mu",
    "completar",
    "configuracion_desde_diccionario",
    "configuracion_por_defecto",
    "confirmar_supuestos",
    "crear_optimizador",
    "evaluar_prescribibilidad",
    "evaluar_prescriptor",
    "informe_prescripcion_html",
    "prescribir_caso",
    "prescribir_lote",
    "prescripciones_csv",
    "problemas_configuracion",
    "que_no_cumplen",
    "referencia_desde_diccionario",
    "variables_prescriptivas",
]

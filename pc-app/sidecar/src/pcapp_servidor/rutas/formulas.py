"""Explorador de fórmulas: fórmula general y valores reales de las decisiones de cada etapa."""

from fastapi import APIRouter, Depends

from pcapp_servidor.esquemas import (
    RESPUESTAS_ERROR,
    SolicitudFormulasAnalisisPC,
    SolicitudFormulasCalibracion,
    SolicitudFormulasCaso,
    SolicitudFormulasModeloCausal,
    SolicitudFormulasSeleccionPrueba,
    TrazaAnalisisPC,
    TrazaCalibracion,
    TrazaCaso,
    TrazaModeloCausal,
    TrazaSeleccionPrueba,
)
from pcapp_servidor.flujo import Servicios
from pcapp_servidor.rutas import servicios

router = APIRouter(prefix="/proyectos/{proyecto_id}/formulas", tags=["fórmulas"], responses=RESPUESTAS_ERROR)


@router.post(
    "/seleccion-prueba", response_model=TrazaSeleccionPrueba,
    summary="Cómo se elige la prueba de independencia de PC",
)
def seleccion_prueba(
    proyecto_id: str, solicitud: SolicitudFormulasSeleccionPrueba | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """Solo lectura. 409 si la recomendación no está vigente; 422 ``UMBRAL_INVALIDO`` si un umbral
    está fuera de rango. Los umbrales enviados solo cambian lo que se muestra, no la recomendación."""
    solicitud = solicitud or SolicitudFormulasSeleccionPrueba()
    return s.formulas_seleccion_prueba(proyecto_id, solicitud.umbrales, solicitud.k)


@router.post("/analisis-pc", response_model=TrazaAnalisisPC, summary="Cómo las cuentas del bootstrap forman el grafo")
def analisis_pc(
    proyecto_id: str, solicitud: SolicitudFormulasAnalisisPC | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """Solo lectura. 409 si el análisis no está vigente; 404 si la versión no existe; 422
    ``UMBRAL_INVALIDO`` si el umbral no es válido. No guarda nada ni vuelve a ejecutar PC."""
    solicitud = solicitud or SolicitudFormulasAnalisisPC()
    return s.formulas_analisis_pc(proyecto_id, solicitud.umbral, solicitud.version)


@router.post("/modelo-causal", response_model=TrazaModeloCausal, summary="Cómo se elige y qué calcula cada mecanismo")
def modelo_causal(
    proyecto_id: str, solicitud: SolicitudFormulasModeloCausal | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """Solo lectura. 409 si el modelo causal no está vigente; 422 ``UMBRAL_INVALIDO`` si un umbral o un
    valor no es válido. No reajusta ni guarda nada."""
    solicitud = solicitud or SolicitudFormulasModeloCausal()
    return s.formulas_modelo_causal(proyecto_id, solicitud.umbrales, solicitud.valores)


@router.post("/prescripcion/calibracion", response_model=TrazaCalibracion, summary="Cómo se elige μ")
def calibracion(
    proyecto_id: str, solicitud: SolicitudFormulasCalibracion | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """Solo lectura, sobre la rejilla guardada. 409 si la prescripción no está vigente o μ no se calibró."""
    solicitud = solicitud or SolicitudFormulasCalibracion()
    return s.formulas_calibracion(proyecto_id, solicitud.exito)


@router.post("/prescripcion/caso", response_model=TrazaCaso, summary="Función objetivo de la prescripción de un caso")
def caso_prescripcion(proyecto_id: str, solicitud: SolicitudFormulasCaso, s: Servicios = Depends(servicios)) -> dict:
    """Prescribe el caso igual que ``/prescripcion/caso`` (con otro μ si se indica) y descompone la pérdida.
    No guarda nada. Mismos errores que la prescripción de un caso."""
    return s.formulas_caso_prescripcion(proyecto_id, solicitud.caso.model_dump(), solicitud.mu)

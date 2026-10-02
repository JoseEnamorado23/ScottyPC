"""Prescripción: configuración, condiciones, calibración de μ, caso, lotes, evaluación y exportación."""

from fastapi import APIRouter, Depends, Query

from pcapp_servidor.esquemas import (
    RESPUESTAS_ERROR,
    CondicionesPrescripcion,
    ConfiguracionPrescripcion,
    InformeEvaluacion,
    MetaEvaluacion,
    MetaLote,
    PaginaLote,
    ResultadoExportarPrescripcion,
    ResultadoPrescripcion,
    SolicitudCasoPrescripcion,
    SolicitudExportarPrescripcion,
    SolicitudLote,
    Trabajo,
    ValidacionPrescripcion,
    VistaConfiguracionPrescripcion,
)
from pcapp_servidor.flujo import Servicios
from pcapp_servidor.rutas import servicios

router = APIRouter(prefix="/proyectos/{proyecto_id}/prescripcion", tags=["prescripción"], responses=RESPUESTAS_ERROR)


@router.post("/condiciones", response_model=CondicionesPrescripcion, summary="Condiciones para prescribir")
def condiciones(
    proyecto_id: str, configuracion: ConfiguracionPrescripcion | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """Con la configuración enviada o, si no se envía, con la guardada (o la sugerida)."""
    return s.condiciones_prescripcion(proyecto_id, configuracion.model_dump() if configuracion else None)


@router.get("/configuracion", response_model=VistaConfiguracionPrescripcion, summary="Configuración de la prescripción")
def configuracion(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    """La guardada o, si no hay, la sugerida (``guardada: false``) con las modificables de pc.json."""
    return s.configuracion_prescripcion(proyecto_id)


@router.put("/configuracion", response_model=VistaConfiguracionPrescripcion, summary="Guarda la configuración")
def guardar(proyecto_id: str, configuracion: ConfiguracionPrescripcion, s: Servicios = Depends(servicios)) -> dict:
    """Solo desactualiza la etapa de prescripción (sus lotes y evaluaciones se archivan)."""
    return s.guardar_configuracion_prescripcion(proyecto_id, configuracion.model_dump())


@router.post("/configuracion/validar", response_model=ValidacionPrescripcion, summary="Valida sin guardar")
def validar(proyecto_id: str, configuracion: ConfiguracionPrescripcion, s: Servicios = Depends(servicios)) -> dict:
    return s.validar_configuracion_prescripcion(proyecto_id, configuracion.model_dump())


@router.post("/calibrar-mu", response_model=Trabajo, status_code=202, summary="Calibra μ con train (trabajo)")
def calibrar(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.vista_trabajo(s.lanzar_calibracion_mu(proyecto_id))


@router.post("/caso", response_model=ResultadoPrescripcion, summary="Prescripción de un caso")
def caso(proyecto_id: str, solicitud: SolicitudCasoPrescripcion, s: Servicios = Depends(servicios)) -> dict:
    """409 ``MU_SIN_CALIBRAR`` si μ es automático y no se calibró; 409 ``PRESCRIPCION_BLOQUEADA`` con
    los problemas si hay bloqueantes."""
    return s.prescribir_caso_api(proyecto_id, solicitud.caso.model_dump())


@router.post("/lote", response_model=Trabajo, status_code=202, summary="Prescripción por lote (trabajo)")
def lote(proyecto_id: str, solicitud: SolicitudLote, s: Servicios = Depends(servicios)) -> dict:
    """«test»: los casos de test que no cumplen el objetivo. «csv»: un archivo con las columnas
    originales, preparado con la receta (las filas que no se pueden preparar se informan)."""
    return s.vista_trabajo(s.lanzar_lote(proyecto_id, solicitud.origen, solicitud.ruta_csv))


@router.get("/lotes", response_model=list[MetaLote], summary="Lotes guardados")
def lotes(proyecto_id: str, s: Servicios = Depends(servicios)) -> list:
    return s.lotes(proyecto_id)


@router.get("/lotes/{numero}", response_model=PaginaLote, summary="Resultados de un lote (paginados)")
def resultados_lote(
    proyecto_id: str,
    numero: int,
    pagina: int = Query(1, ge=1),
    filtro: str | None = Query(None, description="alcanzado, no_alcanzable, requiere_revision o ya_cumple."),
    s: Servicios = Depends(servicios),
) -> dict:
    return s.lote(proyecto_id, numero, pagina, filtro)


@router.post("/evaluacion", response_model=Trabajo, status_code=202, summary="Evalúa el prescriptor sobre test (trabajo)")
def evaluacion(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.vista_trabajo(s.lanzar_evaluacion(proyecto_id))


@router.get("/evaluaciones", response_model=list[MetaEvaluacion], summary="Evaluaciones guardadas")
def evaluaciones(proyecto_id: str, s: Servicios = Depends(servicios)) -> list:
    return s.evaluaciones(proyecto_id)


@router.get("/evaluaciones/{numero}", response_model=InformeEvaluacion, summary="Informe de una evaluación")
def informe_evaluacion(proyecto_id: str, numero: int, s: Servicios = Depends(servicios)) -> dict:
    return s.evaluacion(proyecto_id, numero)


@router.post("/exportar", response_model=ResultadoExportarPrescripcion, summary="CSV de prescripciones e informe HTML")
def exportar(proyecto_id: str, solicitud: SolicitudExportarPrescripcion, s: Servicios = Depends(servicios)) -> dict:
    return s.exportar_prescripcion(proyecto_id, solicitud.carpeta_destino, solicitud.lote, solicitud.evaluacion)

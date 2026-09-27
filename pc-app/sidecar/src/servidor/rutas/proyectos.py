"""Proyectos y etapas del flujo."""

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse

from servidor.esquemas import (
    RESPUESTAS_ERROR,
    ConfiguracionPC,
    DecisionesUsuario,
    Proyecto,
    ProyectoCreado,
    RecomendacionPrueba,
    RespuestaConfiguracionPC,
    ResultadoExportar,
    ResultadoPC,
    ResumenPreparacion,
    Revision,
    SolicitudExportar,
    SolicitudProyecto,
    SolicitudRevision,
    Trabajo,
)
from servidor.flujo import Servicios
from servidor.rutas import servicios

router = APIRouter(prefix="/proyectos", tags=["proyectos"], responses=RESPUESTAS_ERROR)


@router.post("", response_model=ProyectoCreado, status_code=201, summary="Crea un proyecto a partir de un archivo")
def crear(solicitud: SolicitudProyecto, s: Servicios = Depends(servicios)) -> dict:
    """Copia el archivo (el original no se modifica) y devuelve hojas, columnas y vista previa."""
    return s.crear_proyecto(solicitud.ruta_archivo, solicitud.nombre)


@router.get("", response_model=list[Proyecto], summary="Lista los proyectos")
def listar(s: Servicios = Depends(servicios)) -> list[dict]:
    return s.listar()


@router.get("/{proyecto_id}", response_model=Proyecto, summary="Obtiene un proyecto")
def obtener(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.vista(s.proyecto(proyecto_id))


@router.delete("/{proyecto_id}", status_code=204, summary="Elimina un proyecto y su carpeta")
def eliminar(proyecto_id: str, s: Servicios = Depends(servicios)) -> Response:
    s.eliminar(proyecto_id)
    return Response(status_code=204)


@router.post("/{proyecto_id}/revision", response_model=Revision, summary="Valida y revisa el dataset")
def revision(proyecto_id: str, solicitud: SolicitudRevision, s: Servicios = Depends(servicios)) -> dict:
    return s.revisar(proyecto_id, solicitud.objetivo, solicitud.hoja)


@router.get("/{proyecto_id}/decisiones/plantilla", response_model=DecisionesUsuario, summary="Decisiones sugeridas")
def plantilla_decisiones(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.plantilla_decisiones(proyecto_id)


@router.get("/{proyecto_id}/decisiones", response_model=DecisionesUsuario, summary="Decisiones guardadas")
def obtener_decisiones(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.decisiones(proyecto_id)


@router.put("/{proyecto_id}/decisiones", response_model=DecisionesUsuario, summary="Valida y guarda las decisiones")
def guardar_decisiones(proyecto_id: str, decisiones: DecisionesUsuario, s: Servicios = Depends(servicios)) -> dict:
    """Invalida la preparación y las etapas posteriores. Los errores (422) indican el campo."""
    return s.guardar_decisiones(proyecto_id, decisiones.model_dump())


@router.post("/{proyecto_id}/preparar", response_model=ResumenPreparacion, summary="Prepara los datos")
def preparar(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.preparar(proyecto_id)


@router.post(
    "/{proyecto_id}/recomendacion", response_model=Trabajo, status_code=202,
    summary="Lanza la recomendación de prueba (trabajo)",
)
def recomendacion(
    proyecto_id: str,
    estimar_tiempo: bool = Query(True, description="Estimar el tiempo de PC (puede tardar minutos)."),
    s: Servicios = Depends(servicios),
) -> dict:
    return s.vista_trabajo(s.lanzar_recomendacion(proyecto_id, estimar_tiempo))


@router.get(
    "/{proyecto_id}/recomendacion", response_model=RecomendacionPrueba, summary="Recomendación guardada"
)
def obtener_recomendacion(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    proyecto = s.proyecto(proyecto_id)
    s.etapas.exigir_vigente(proyecto_id, "recomendacion")
    return s.archivos.leer_json(s.archivos.carpeta(proyecto.id) / "recomendacion.json")


@router.get(
    "/{proyecto_id}/configuracion-pc", response_model=RespuestaConfiguracionPC,
    summary="Configuración de PC (o la plantilla si aún no existe)",
)
def configuracion_pc(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.configuracion_pc(proyecto_id)


@router.put(
    "/{proyecto_id}/configuracion-pc", response_model=RespuestaConfiguracionPC,
    summary="Valida y guarda la configuración de PC",
)
def guardar_configuracion_pc(
    proyecto_id: str, configuracion: ConfiguracionPC, s: Servicios = Depends(servicios)
) -> dict:
    return s.guardar_configuracion_pc(proyecto_id, configuracion.model_dump())


@router.post("/{proyecto_id}/pc", response_model=Trabajo, status_code=202, summary="Lanza el análisis PC (trabajo)")
def pc(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.vista_trabajo(s.lanzar_pc(proyecto_id))


@router.get("/{proyecto_id}/resultado", response_model=ResultadoPC, summary="Resultado del análisis")
def resultado(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.resultado(proyecto_id)


@router.get(
    "/{proyecto_id}/archivos/{nombre}",
    summary="Descarga un archivo de resultados",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}, "text/csv": {}, "application/json": {}}}},
)
def archivo(proyecto_id: str, nombre: str, s: Servicios = Depends(servicios)) -> FileResponse:
    """Solo grafo.png, aristas.csv, mascara.csv, matriz_frecuencias.csv y resultado.json.

    Requiere el encabezado X-Token: desde el navegador, descárguelo con fetch y
    muéstrelo con URL.createObjectURL (una etiqueta <img> no envía el encabezado).
    """
    ruta, tipo = s.archivo_resultado(proyecto_id, nombre)
    return FileResponse(ruta, media_type=tipo, filename=nombre)


@router.post("/{proyecto_id}/exportar", response_model=ResultadoExportar, summary="Exporta los resultados")
def exportar(proyecto_id: str, solicitud: SolicitudExportar, s: Servicios = Depends(servicios)) -> dict:
    return s.exportar(proyecto_id, solicitud.carpeta_destino)

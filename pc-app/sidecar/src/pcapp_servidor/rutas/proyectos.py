"""Proyectos y etapas del flujo."""

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse

from pcapp_servidor.esquemas import (
    Aplicabilidad,
    CasosModelo,
    ModeloCausal,
    ResultadoContrafactual,
    SolicitudContrafactual,
    SolicitudModeloCausal,
    ConfiguracionPC,
    DatosHoja,
    DecisionesUsuario,
    Distribucion,
    EstadoPreparacion,
    EvaluacionEleccion,
    Procedencia,
    Proyecto,
    ProyectoCreado,
    RESPUESTAS_ERROR,
    RecomendacionPrueba,
    RespuestaConfiguracionPC,
    ResultadoExportar,
    ResultadoPC,
    ResumenPreparacion,
    Revision,
    SolicitudEvaluarPrueba,
    SolicitudExportar,
    SolicitudPreparar,
    SolicitudPrevisualizar,
    SolicitudProyecto,
    SolicitudReagregar,
    SolicitudRevision,
    SolicitudVersion,
    SolicitudVersionActual,
    Trabajo,
    ValidacionConfiguracionPC,
    VersionesResultado,
)
from pcapp_servidor.flujo import Servicios
from pcapp_servidor.rutas import servicios

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


@router.get("/{proyecto_id}/datos", response_model=DatosHoja, summary="Vista previa de una hoja")
def datos(
    proyecto_id: str,
    hoja: str | None = Query(None, description="Hoja (XLSX); por defecto, la del proyecto o la primera."),
    s: Servicios = Depends(servicios),
) -> dict:
    return s.datos_hoja(proyecto_id, hoja)


@router.get("/{proyecto_id}/distribucion", response_model=Distribucion, summary="Distribución de una columna")
def distribucion(
    proyecto_id: str,
    columna: str = Query(..., description="Nombre de la columna."),
    hoja: str | None = Query(None, description="Hoja (XLSX); por defecto, la del proyecto."),
    s: Servicios = Depends(servicios),
) -> dict:
    """Sobre todas las filas: conteos por valor o histograma si es numérica con muchos valores."""
    return s.distribucion(proyecto_id, columna, hoja)


@router.get("/{proyecto_id}/revision", response_model=Revision, summary="Revisión guardada")
def obtener_revision(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.revision(proyecto_id)


@router.post(
    "/{proyecto_id}/decisiones/previsualizar", response_model=DecisionesUsuario,
    summary="Decisiones que resultan de las acciones elegidas",
)
def previsualizar_decisiones(
    proyecto_id: str, solicitud: SolicitudPrevisualizar, s: Servicios = Depends(servicios)
) -> dict:
    """Las calcula el núcleo; no guarda nada. Los hallazgos sin elección usan la acción sugerida."""
    return s.previsualizar_decisiones(proyecto_id, solicitud.elecciones)


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
def preparar(
    proyecto_id: str, solicitud: SolicitudPreparar | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """La separación elegida se guarda en la receta (su única fuente). Rehacer la
    preparación deja desactualizadas la recomendación, la configuración de PC y el
    análisis, pero no las decisiones."""
    separacion = solicitud.separacion.model_dump() if solicitud and solicitud.separacion else None
    return s.preparar(proyecto_id, separacion)


@router.get(
    "/{proyecto_id}/preparacion", response_model=EstadoPreparacion,
    summary="Resumen de la preparación vigente y separación inicial del formulario",
)
def estado_preparacion(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.estado_preparacion(proyecto_id)


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


@router.post(
    "/{proyecto_id}/recomendacion/evaluar", response_model=EvaluacionEleccion,
    summary="Advertencias sobre la prueba y el max_k elegidos",
)
def evaluar_prueba(
    proyecto_id: str, solicitud: SolicitudEvaluarPrueba, s: Servicios = Depends(servicios)
) -> dict:
    """Compara la elección con la recomendación guardada; no guarda nada."""
    return s.evaluar_prueba(proyecto_id, solicitud.prueba, solicitud.max_k)


@router.get(
    "/{proyecto_id}/configuracion-pc/plantilla", response_model=ConfiguracionPC,
    summary="Plantilla de la configuración de PC (para restablecer)",
)
def plantilla_configuracion_pc(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.plantilla_configuracion_pc(proyecto_id)


@router.post(
    "/{proyecto_id}/configuracion-pc/validar", response_model=ValidacionConfiguracionPC,
    summary="Valida la configuración de PC sin guardarla",
)
def validar_configuracion_pc(
    proyecto_id: str, configuracion: ConfiguracionPC, s: Servicios = Depends(servicios)
) -> dict:
    """Todos los errores (con su campo) y las advertencias, p. ej. si el objetivo no está al final."""
    return s.validar_configuracion_pc(proyecto_id, configuracion.model_dump())


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
def resultado(
    proyecto_id: str,
    version: int | None = Query(None, description="Versión (por defecto, la actual)."),
    s: Servicios = Depends(servicios),
) -> dict:
    return s.resultado(proyecto_id, version)


@router.get(
    "/{proyecto_id}/resultado/versiones", response_model=VersionesResultado,
    summary="Versiones del resultado (original y ajustadas)",
)
def versiones(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    """La primera consulta de un resultado anterior a las versiones lo migra (``migrada``)."""
    return s.versiones(proyecto_id)


@router.post(
    "/{proyecto_id}/resultado/reagregar", response_model=ResultadoPC,
    summary="Previsualiza el resultado con otro umbral u otras orientaciones (no guarda nada)",
)
def reagregar(proyecto_id: str, solicitud: SolicitudReagregar, s: Servicios = Depends(servicios)) -> dict:
    """Sin volver a ejecutar PC: parte de las cuentas del bootstrap. 422 con el campo de cada
    problema (p. ej. ``orientaciones_manuales.0`` si contradice los niveles)."""
    return s.previsualizar_reagregacion(
        proyecto_id, solicitud.umbral_frecuencia, [o.model_dump() for o in solicitud.orientaciones_manuales]
    )


@router.post(
    "/{proyecto_id}/resultado/versiones", response_model=VersionesResultado, status_code=201,
    summary="Guarda el ajuste como una versión nueva y la hace actual",
)
def guardar_version(proyecto_id: str, solicitud: SolicitudVersion, s: Servicios = Depends(servicios)) -> dict:
    """Las versiones anteriores (y pc.json) no se modifican."""
    return s.guardar_version(
        proyecto_id, solicitud.umbral_frecuencia,
        [o.model_dump() for o in solicitud.orientaciones_manuales], solicitud.version_base,
    )


@router.put(
    "/{proyecto_id}/resultado/version-actual", response_model=VersionesResultado,
    summary="Cambia la versión actual del resultado",
)
def cambiar_version_actual(
    proyecto_id: str, solicitud: SolicitudVersionActual, s: Servicios = Depends(servicios)
) -> dict:
    return s.cambiar_version_actual(proyecto_id, solicitud.version)


@router.get(
    "/{proyecto_id}/resultado/procedencia", response_model=Procedencia,
    summary="Datos, decisiones, separación y configuración que produjeron el resultado",
)
def procedencia(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.procedencia(proyecto_id)


@router.get(
    "/{proyecto_id}/archivos/{nombre}",
    summary="Descarga un archivo de resultados",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}, "text/csv": {}, "application/json": {}}}},
)
def archivo(
    proyecto_id: str,
    nombre: str,
    version: int | None = Query(None, description="Versión (por defecto, la actual)."),
    s: Servicios = Depends(servicios),
) -> FileResponse:
    """Solo grafo.png, aristas.csv, mascara.csv, matriz_frecuencias.csv y resultado.json.

    Requiere el encabezado X-Token: desde el navegador, descárguelo con fetch y
    muéstrelo con URL.createObjectURL (una etiqueta <img> no envía el encabezado).
    """
    ruta, tipo = s.archivo_resultado(proyecto_id, nombre, version)
    return FileResponse(ruta, media_type=tipo, filename=nombre)


@router.post("/{proyecto_id}/exportar", response_model=ResultadoExportar, summary="Exporta los resultados")
def exportar(proyecto_id: str, solicitud: SolicitudExportar, s: Servicios = Depends(servicios)) -> dict:
    """Archivos de una versión, la receta e ``informe.html`` (autocontenido, se abre sin conexión)."""
    return s.exportar(proyecto_id, solicitud.carpeta_destino, solicitud.version)


# --- Modelo causal ------------------------------------------------------------------------------


@router.post(
    "/{proyecto_id}/modelo-causal/aplicabilidad", response_model=Aplicabilidad,
    summary="Comprueba si se puede construir el modelo causal (no construye nada)",
)
def aplicabilidad_modelo(
    proyecto_id: str, solicitud: SolicitudModeloCausal | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """Bloqueantes y advertencias, cada uno con la acción que lo resuelve y la pantalla donde se hace."""
    return s.aplicabilidad_modelo(proyecto_id, solicitud.a_configuracion() if solicitud else None)


@router.post(
    "/{proyecto_id}/modelo-causal", response_model=Trabajo, status_code=202,
    summary="Construye el modelo causal (trabajo)",
)
def construir_modelo_causal(
    proyecto_id: str, solicitud: SolicitudModeloCausal | None = None, s: Servicios = Depends(servicios)
) -> dict:
    """409 con ``detalles.problemas`` si hay bloqueantes. Usa la versión actual del resultado de PC."""
    return s.vista_trabajo(s.lanzar_modelo_causal(proyecto_id, solicitud.a_configuracion() if solicitud else None))


@router.get("/{proyecto_id}/modelo-causal", response_model=ModeloCausal, summary="Modelo causal y su evaluación")
def modelo_causal(proyecto_id: str, s: Servicios = Depends(servicios)) -> dict:
    return s.modelo_causal(proyecto_id)


@router.get(
    "/{proyecto_id}/modelo-causal/casos", response_model=CasosModelo,
    summary="Filas de test en unidades originales (para elegir un caso)",
)
def casos_modelo(
    proyecto_id: str,
    pagina: int = Query(1, ge=1, description="Página (50 filas por página)."),
    s: Servicios = Depends(servicios),
) -> dict:
    return s.casos_modelo(proyecto_id, pagina)


@router.post(
    "/{proyecto_id}/modelo-causal/contrafactual", response_model=ResultadoContrafactual,
    summary="Escenario «¿qué pasa si…?» sobre un caso",
)
def contrafactual_modelo(proyecto_id: str, solicitud: SolicitudContrafactual, s: Servicios = Depends(servicios)) -> dict:
    """El caso es una fila de test (``indice_test``) o valores propios (``valores``, unidades originales).
    422 si una intervención no es válida (p. ej. sobre el objetivo o una consecuencia suya)."""
    return s.contrafactual_modelo(
        proyecto_id, solicitud.caso.model_dump(), [i.model_dump() for i in solicitud.intervenciones]
    )

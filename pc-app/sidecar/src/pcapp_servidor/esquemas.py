"""Modelos Pydantic de la API: reflejan las dataclasses del núcleo.

Una prueba comprueba que los campos de cada modelo coinciden con los de su
dataclass, para que un cambio en el núcleo no desincronice la API (y los
tipos de TypeScript que se generan desde /openapi.json).
"""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Entrada(BaseModel):
    """Modelos que se reciben: los campos desconocidos son un error."""

    model_config = ConfigDict(extra="forbid")


# --- Errores -------------------------------------------------------------------------------


class DetalleCampo(BaseModel):
    campo: str = Field(description="Ruta del campo, p. ej. 'faltantes.Glucose.imputacion'.")
    mensaje: str


class CuerpoError(BaseModel):
    codigo: str
    mensaje: str
    detalles: Any = None


class RespuestaError(BaseModel):
    error: CuerpoError


RESPUESTAS_ERROR: dict[int | str, dict[str, Any]] = {
    404: {"model": RespuestaError, "description": "No encontrado."},
    409: {"model": RespuestaError, "description": "Falta una etapa previa o hay un trabajo en curso."},
    422: {"model": RespuestaError, "description": "Datos no válidos (detalles por campo)."},
}


# --- Salud y proyectos ----------------------------------------------------------------------


class Salud(BaseModel):
    estado: Literal["ok"]
    version_servidor: str
    version_nucleo: str
    grupo_procesos_creado: bool


class SolicitudProyecto(_Entrada):
    ruta_archivo: str = Field(description="Ruta del CSV o XLSX del usuario (no se modifica: se copia).")
    nombre: str | None = None


EstadoEtapa = Literal["vigente", "desactualizada"]


class Proyecto(BaseModel):
    id: str
    nombre: str
    archivo_original: str
    hoja: str | None
    sha256: str
    objetivo: str | None
    etapa_actual: str | None
    etapas: dict[str, EstadoEtapa] = Field(description="Estado de cada etapa realizada.")
    trabajo_activo: str | None = Field(description="Id del trabajo en curso, si hay uno.")
    ultimo_trabajo: ResumenTrabajo | None = Field(
        None, description="Último trabajo del proyecto (para marcar los interrumpidos y reanudarlos)."
    )
    creado_en: str
    actualizado_en: str


class ProyectoCreado(Proyecto):
    hojas: list[str] | None = Field(description="Hojas del libro (solo XLSX).")
    hoja_vista: str | None = Field(description="Hoja usada para la vista previa.")
    filas: int
    columnas: list[str]
    vista_previa: list[dict[str, Any]] = Field(description="Primeras 20 filas.")


class DatosHoja(BaseModel):
    hoja: str | None
    hojas: list[str] | None
    filas: int
    columnas: list[str]
    vista_previa: list[dict[str, Any]] = Field(description="Primeras 20 filas.")


class Categoria(BaseModel):
    valor: Any
    conteo: int
    porcentaje: float


class Histograma(BaseModel):
    limites: list[float] = Field(description="Bordes de los intervalos (uno más que los conteos).")
    conteos: list[int]


class Distribucion(BaseModel):
    columna: str
    tipo: Literal["categorias", "histograma"]
    total: int
    faltantes: int
    valores_distintos: int
    categorias: list[Categoria] = Field(description="Valores más frecuentes (hasta 20) y 'otros'.")
    histograma: Histograma | None = None


# --- Revisión -------------------------------------------------------------------------------


class SolicitudRevision(_Entrada):
    objetivo: str
    hoja: str | None = None


class ProblemaValidacion(BaseModel):
    nivel: Literal["error", "advertencia"]
    codigo: str
    mensaje: str
    columnas: list[str]
    evidencia: dict[str, Any]


class ResultadoValidacion(BaseModel):
    valido: bool
    errores: list[ProblemaValidacion]
    advertencias: list[ProblemaValidacion]


class Hallazgo(BaseModel):
    tipo: str
    columnas_involucradas: list[str]
    severidad: Literal["alta", "media", "baja"]
    detalle: str
    evidencia: dict[str, Any]
    acciones_posibles: list[str]
    accion_sugerida: str | None
    identificador: str


class PerfilColumna(BaseModel):
    nombre: str
    tipo_detectado: str
    faltantes: int
    porcentaje_faltantes: float
    valores_unicos: int
    minimo: float | None
    maximo: float | None


class Revision(BaseModel):
    valido: bool
    validacion: ResultadoValidacion
    resumen: dict[str, Any]
    hallazgos: list[Hallazgo]
    perfiles_columnas: list[PerfilColumna]
    objetivo: str | None
    informacion_objetivo: dict[str, Any]


# --- Decisiones -----------------------------------------------------------------------------


class TratamientoColumna(_Entrada):
    ceros_como_faltantes: bool = False
    indicador_medido: bool = False
    imputacion: Literal["eliminar_filas", "mediana", "multivariada"] | None = None


class Codificacion(_Entrada):
    tipo: Literal["binaria", "ordinal", "one_hot", "agrupacion"]
    orden: list[Any] | None = None
    valor_positivo: Any = None
    grupos: dict[str, Any] | None = None


class ConversionUnidades(_Entrada):
    columna: str
    condicion: Literal[">", ">=", "<", "<="]
    umbral: float
    restar: float = 0.0
    multiplicar: float = 1.0
    descripcion: str = ""


class ConfiguracionSeparacion(_Entrada):
    tipo: Literal["estratificada", "temporal"] = "estratificada"
    proporcion_test: float = Field(0.3, gt=0, lt=1)
    semilla: int = 42
    columna_fecha: str | None = None
    corte: str | None = Field(None, description="Fecha de corte AAAA-MM-DD (separación temporal).")


class AccionHallazgo(_Entrada):
    accion: str
    opciones: list[str] = []
    descripcion: str = ""
    requiere_confirmacion: bool = False


class DecisionesUsuario(_Entrada):
    eliminar_duplicados: bool = False
    acciones_hallazgos: dict[str, AccionHallazgo] = {}
    columnas_excluidas: list[str] = []
    faltantes: dict[str, TratamientoColumna] = {}
    codificaciones: dict[str, Codificacion] = {}
    conversiones: list[ConversionUnidades] = []
    logaritmos: list[str] = []
    normalizar: bool = True
    columnas_fecha_disponibles: list[str] = []
    notas: list[str] = []


class SolicitudPrevisualizar(_Entrada):
    elecciones: dict[str, str] = Field(
        default_factory=dict, description="Acción elegida por hallazgo: {identificador: acción}."
    )


# --- Preparación y recomendación ---------------------------------------------------------------


class MetadatosColumna(BaseModel):
    nombre: str
    tipo_final: str
    transformaciones: list[str]
    parametros: dict[str, Any]


class SolicitudPreparar(_Entrada):
    separacion: ConfiguracionSeparacion | None = Field(
        None, description="Separación en train y test; si falta, la de la receta anterior o la sugerida."
    )


class LimiteColumnas(BaseModel):
    estado: Literal["ok", "lento", "bloqueado"]
    columnas: int
    mensaje: str | None
    columnas_one_hot: dict[str, int] = Field(description="Columnas que aporta cada codificación one-hot.")


class ClaseObjetivo(BaseModel):
    valor: Any
    conteo: int
    porcentaje: float


class DistribucionObjetivo(BaseModel):
    tipo: Literal["clases", "continuo"]
    filas: int
    clases: list[ClaseObjetivo] = []
    media: float | None = None
    mediana: float | None = None
    minimo: float | None = None
    maximo: float | None = None


class DistribucionesObjetivo(BaseModel):
    train: DistribucionObjetivo
    test: DistribucionObjetivo


class ResumenPreparacion(BaseModel):
    filas_train: int
    filas_test: int
    tipo_objetivo: str | None
    columnas: list[MetadatosColumna]
    faltantes_restantes: dict[str, int] = Field(description="Faltantes por columna en train.")
    separacion: dict[str, Any] = Field(description="Separación aplicada (corte real, filas de cada conjunto).")
    separacion_configurada: ConfiguracionSeparacion
    distribucion_objetivo: DistribucionesObjetivo
    limite_columnas: LimiteColumnas
    advertencias: list[str]


class EstadoPreparacion(BaseModel):
    vigente: bool = Field(description="Si hay una preparación vigente (entonces 'resumen' es el suyo).")
    resumen: ResumenPreparacion | None
    separacion: ConfiguracionSeparacion = Field(
        description="La de la receta vigente o, si no la hay, la sugerida (valor inicial del formulario)."
    )
    columnas_fecha_disponibles: list[str] = Field(description="Fechas detectadas para la separación temporal.")


class DiagnosticoVariable(BaseModel):
    nombre: str
    tipo_final: str
    spearman: float | None
    p_intervalos: float | None
    limites_intervalos: list[float]
    valores_por_intervalo: list[float]
    filas_por_intervalo: list[int]
    medida: str | None
    amplitud_en_desviaciones: float | None
    monotona: bool | None
    motivo: str | None


class AlternativaPrueba(BaseModel):
    prueba: str
    ventajas: str
    desventajas: str


class RecomendacionPrueba(BaseModel):
    prueba: str
    motivo: str
    discretizacion: str | None
    variables_no_monotonas: list[str]
    faltantes_restantes: dict[str, int]
    proporcion_categoricas: float
    filas_train: int
    variables: int
    diagnosticos: list[DiagnosticoVariable]
    alternativas: list[AlternativaPrueba]
    limites_discretizacion: dict[str, list[float]]
    tiempo_por_ejecucion_s: float | None
    tiempo_estimado_bootstrap_s: float | None
    estimacion_completa: bool
    max_k_sugerido: int | None
    tiempo_estimado_bootstrap_max_k_s: float | None
    nota_tiempo: str | None


class SolicitudEvaluarPrueba(_Entrada):
    prueba: Literal["fisherz", "mv_fisherz", "chisq", "kci"]
    max_k: int | None = Field(None, ge=0)


class AdvertenciaEleccion(BaseModel):
    codigo: str
    campo: str
    mensaje: str
    nivel: Literal["advertencia", "info"]


class EvaluacionEleccion(BaseModel):
    prueba: str
    max_k: int | None
    advertencias: list[AdvertenciaEleccion]
    tiempo_estimado_s: float | None = Field(description="Tiempo del bootstrap con esta elección, si se estimó.")


# --- Configuración de PC ---------------------------------------------------------------------


def _procesos_por_defecto() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


class OrientacionManual(_Entrada):
    origen: str
    destino: str
    justificacion: str = ""


class ConfiguracionPC(_Entrada):
    prueba: Literal["fisherz", "mv_fisherz", "chisq", "kci"] = "fisherz"
    alpha: float = Field(0.05, gt=0, lt=1)
    corridas_bootstrap: int = Field(100, ge=1)
    fraccion_submuestra: float = Field(0.8, gt=0, le=1)
    umbral_frecuencia: float = Field(0.6, gt=0, le=1)
    max_k: int | None = Field(None, ge=0)
    semilla: int = 42
    procesos: int = Field(default_factory=_procesos_por_defecto, ge=1)
    niveles: list[list[str]] = Field(description="Grupos ordenados; nada de un nivel posterior causa uno anterior.")
    modificables: list[str] = []
    orientaciones_manuales: list[OrientacionManual] = []
    punto_control_cada: int = Field(10, ge=1)
    modo_ejecucion: Literal["adaptativo", "secuencial", "paralelo"] = "adaptativo"
    umbral_paralelo_s: float = Field(30.0, ge=0)
    nombres_niveles: list[str] | None = Field(None, description="Títulos de los niveles (opcionales).")


class ProblemaConfiguracion(BaseModel):
    campo: str
    mensaje: str


class ValidacionConfiguracionPC(BaseModel):
    valida: bool
    errores: list[ProblemaConfiguracion]
    advertencias: list[ProblemaConfiguracion]


class RespuestaConfiguracionPC(BaseModel):
    configuracion: ConfiguracionPC
    guardada: bool = Field(description="False si es la plantilla sugerida (aún no guardada).")


# --- Trabajos -----------------------------------------------------------------------------------

EstadoTrabajo = Literal["pendiente", "en_curso", "completado", "cancelado", "fallido", "interrumpido"]


class Trabajo(BaseModel):
    id: str
    proyecto_id: str
    tipo: Literal["recomendacion", "pc"]
    estado: EstadoTrabajo
    completadas: int
    total: int | None
    fallidas: int
    segundos_transcurridos: float
    segundos_restantes_estimados: float | None
    mensaje: str | None
    error: str | None
    parametros: dict[str, Any]
    inicio: str | None
    fin: str | None
    detalles: DetallesTrabajo | None = Field(None, description="Modo de ejecución del análisis en curso.")


class DetallesTrabajo(BaseModel):
    modo: Literal["midiendo", "secuencial", "paralelo"]
    procesos: int


class ResumenTrabajo(BaseModel):
    id: str
    tipo: Literal["recomendacion", "pc"]
    estado: EstadoTrabajo
    completadas: int
    total: int | None
    mensaje: str | None
    reanudable: bool = Field(description="Si se puede reanudar ahora (estado y etapas lo permiten).")


# --- Resultado de PC ---------------------------------------------------------------------------


class CorridaFallida(BaseModel):
    corrida: int
    motivo: str


class EjecucionBootstrap(BaseModel):
    modo_solicitado: str
    modo_usado: str
    procesos: int
    motivo: str
    segundos_primera_corrida: float | None
    segundos_segunda_corrida: float | None
    segundos_estimados_restantes: float | None


class AristaAgregada(BaseModel):
    origen: str
    destino: str
    tipo: Literal["dirigida", "sin_orientar", "manual"]
    frecuencia_total: float
    frecuencia_origen_destino: float
    frecuencia_destino_origen: float
    frecuencia_sin_orientar: float
    spearman: float | None
    signo: int
    justificacion: str | None


class CaracterizacionVariable(BaseModel):
    variable: str
    categoria: Literal["causa_directa", "causa_indirecta", "consecuencia", "ambigua", "sin_camino"]
    a_traves_de: list[str]
    frecuencia_con_objetivo: float
    grupo_redundante: list[str] | None
    modificable: bool


class Caracterizacion(BaseModel):
    objetivo: str
    variables: list[CaracterizacionVariable]
    candidatas_prescriptivas: list[str]
    mensaje: str


class RecetaOrigen(BaseModel):
    archivo: str | None
    hoja: str | None
    sha256: str | None
    objetivo: str
    tipo_objetivo: str | None


class Corridas(BaseModel):
    totales: int
    completadas: int
    validas: int
    fallidas: list[CorridaFallida]
    completo: bool


class Matrices(BaseModel):
    frecuencia_dirigida: list[list[float]]
    frecuencia_sin_orientar: list[list[float]]


class Agregacion(BaseModel):
    umbral_frecuencia: float
    orientaciones_manuales: list[OrientacionManual]


class ParVariables(BaseModel):
    variable_a: str
    variable_b: str
    frecuencia: float
    con_objetivo: bool


class AvisoResultado(BaseModel):
    codigo: str
    nivel: Literal["advertencia", "info"]
    titulo: str
    mensaje: str
    variables: list[str]
    pares: list[ParVariables]


class ColumnaDisposicion(BaseModel):
    titulo: str
    variables: list[str]


class ResultadoPC(BaseModel):
    configuracion: ConfiguracionPC = Field(description="Configuración de la ejecución (pc.json); no cambia entre versiones.")
    receta: RecetaOrigen
    corridas: Corridas
    tiempo_s: float
    ejecucion: EjecucionBootstrap | None
    limites_discretizacion: dict[str, list[float]]
    variables: list[str]
    aristas: list[AristaAgregada]
    ciclos: list[list[str]]
    caracterizacion: Caracterizacion
    matrices: Matrices
    advertencias: list[str]
    agregacion: Agregacion = Field(description="Umbral y orientaciones manuales con que se agregó esta versión.")
    version: int | None = Field(description="Versión guardada; null en una previsualización.")
    etiqueta: str = Field(description="«Original» o «Ajustada: umbral X, original Y».")
    avisos: list[AvisoResultado] = Field(description="Advertencias de interpretación, calculadas por el núcleo.")
    disposicion: list[ColumnaDisposicion] = Field(
        description="Columnas del grafo: una por nivel, con su título y las variables ordenadas para reducir cruces."
    )


# --- Versiones del resultado -----------------------------------------------------------------


class SolicitudReagregar(_Entrada):
    umbral_frecuencia: float = Field(description="Fracción mínima de corridas (0 < umbral <= 1; lo valida el núcleo).")
    orientaciones_manuales: list[OrientacionManual] = []


class SolicitudVersion(SolicitudReagregar):
    version_base: int | None = Field(None, description="Versión que se estaba viendo al ajustar (informativo).")


class VersionResultado(BaseModel):
    version: int
    base: int | None
    umbral_frecuencia: float
    orientaciones_manuales: list[OrientacionManual]
    creada_en: str
    migrada: bool = Field(description="Resultado anterior a las versiones, completado al abrirlo por primera vez.")
    etiqueta: str


class VersionesResultado(BaseModel):
    version_actual: int
    umbral_original: float
    versiones: list[VersionResultado]


class SolicitudVersionActual(_Entrada):
    version: int


class LineaResumen(BaseModel):
    concepto: str
    detalle: str


class Procedencia(BaseModel):
    archivo: str | None
    hoja: str | None
    sha256: str | None
    objetivo: str
    tipo_objetivo: str | None
    filas_train: int | None
    filas_test: int | None
    decisiones: list[LineaResumen]
    separacion: list[LineaResumen]
    configuracion: ConfiguracionPC = Field(description="Configuración original de PC (pc.json de la ejecución).")
    prueba_recomendada: str | None


# --- Exportación ------------------------------------------------------------------------------


class SolicitudExportar(_Entrada):
    carpeta_destino: str
    version: int | None = Field(None, description="Versión que se exporta (por defecto, la actual).")


class ResultadoExportar(BaseModel):
    carpeta: str
    archivos: list[str]
    version: int


class Apagado(BaseModel):
    mensaje: str


# Modelos con referencias a clases definidas más abajo.
for _modelo in (Proyecto, ProyectoCreado, Trabajo):
    _modelo.model_rebuild()

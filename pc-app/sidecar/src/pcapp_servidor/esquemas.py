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

TipoTrabajo = Literal[
    "recomendacion", "pc", "modelo_causal", "calibracion_mu", "lote_prescripcion", "evaluacion_prescripcion"
]
EstadoTrabajo = Literal["pendiente", "en_curso", "completado", "cancelado", "fallido", "interrumpido"]


class Trabajo(BaseModel):
    id: str
    proyecto_id: str
    tipo: TipoTrabajo
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
    tipo: TipoTrabajo
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
    origen_candidatas: Literal["configuracion_pc", "prescripcion"] = Field(
        description="De qué lista de modificables salen las candidatas prescriptivas."
    )
    nota_candidatas: str


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


# --- Modelo causal ------------------------------------------------------------------------------


class ProblemaAplicabilidad(BaseModel):
    codigo: str
    severidad: Literal["bloqueante", "advertencia"]
    mensaje: str
    accion: str = Field(description="Qué hacer para resolverlo.")
    destino: Literal["resultados", "decisiones", "preparacion", "analisis", "modelo_causal", "prescripcion"] | None = Field(
        description="Pantalla donde se resuelve (la interfaz lleva a ella)."
    )
    variables: list[str]


class SubgrafoObjetivo(BaseModel):
    objetivo: str
    variables: list[str] = Field(description="Objetivo y ancestros, en orden topológico si no hay ciclos.")
    padres: dict[str, list[str]]
    aristas: list[list[str]]
    sin_orientar: list[list[str]]
    fuera: list[str]


class Aplicabilidad(BaseModel):
    problemas: list[ProblemaAplicabilidad]
    bloqueado: bool
    version_resultado: int | None
    subgrafo: SubgrafoObjetivo | None


class SolicitudModeloCausal(_Entrada):
    monotonia: dict[str, Literal["creciente", "decreciente", "ninguna"]] = Field(
        {}, description="Override por padre del objetivo; los demás se deciden con la recomendación de prueba."
    )
    mecanismos: dict[str, Literal["simple", "complejo"]] = Field({}, description="Override del tipo de mecanismo.")
    pesos_clase: bool = Field(
        False, description="Pesos de clase en el objetivo (las probabilidades dejan de estar calibradas)."
    )
    umbral_parsimonia: float | None = Field(
        None, ge=0, le=1, description="Mejora mínima para preferir el modelo complejo."
    )

    def a_configuracion(self) -> dict[str, Any]:
        datos = self.model_dump()
        if datos["umbral_parsimonia"] is None:
            datos.pop("umbral_parsimonia")
        return datos


class ResultadoLigado(BaseModel):
    version: int | None
    sha256: str | None


class SubgrafoModelo(BaseModel):
    variables: list[str]
    padres: dict[str, list[str]]
    aristas: list[list[str]]
    fuera: list[str]
    descendientes_objetivo: list[str]


class InfoVariableModelo(BaseModel):
    tipo: Literal["continua", "binaria"]
    rol: Literal["raiz", "intermedia", "objetivo"]
    mediana: float | None
    minimo: float | None
    maximo: float | None
    faltantes_train: int


class DecisionMonotonia(BaseModel):
    padre: str
    restriccion: Literal["creciente", "decreciente"] | None
    origen: Literal["automatico", "manual", "no_aplica"]
    motivo: str


class ResumenMecanismo(BaseModel):
    familia: str
    padres: list[str]
    binaria: bool
    seleccion: dict[str, Any]


class ResumenModeloCausal(BaseModel):
    version_formato: int
    objetivo: str
    tipo_objetivo: str | None
    clase_positiva: list[Any] | None = Field(description="Valores originales del objetivo que cuentan como 1.")
    resultado_pc: ResultadoLigado
    train_sha256: str
    semilla: int
    configuracion: dict[str, Any]
    subgrafo: SubgrafoModelo
    variables: dict[str, InfoVariableModelo] = Field(description="Unidades preparadas.")
    monotonia: list[DecisionMonotonia]
    umbral_decision: float | None
    pesos_clase: bool
    imputadas_en_modelo: list[str]
    advertencias: list[ProblemaAplicabilidad]
    versiones: dict[str, str]
    huella: str
    mecanismos: dict[str, ResumenMecanismo]


class CandidatoMecanismo(BaseModel):
    tipo: Literal["simple", "complejo"]
    familia: str
    puntuacion_cv: float | None
    umbral_cv: float | None
    error: str | None
    rescate: list[str]
    nombre_familia: str


class HistogramaEfecto(BaseModel):
    tipo: Literal["valores", "histograma"]
    valores: list[float] | None = None
    limites: list[float] | None = None
    conteos: list[int]


class EfectoParcial(BaseModel):
    padre: str
    coeficiente: float | None = Field(description="Solo en mecanismos lineales (unidades preparadas).")
    signo: int = Field(description="1 creciente, -1 decreciente, 0 sube y baja (o plano).")
    x: list[float] = Field(description="Valores del padre en unidades originales.")
    y: list[float] = Field(description="Efecto parcial (probabilidad o valor esperado).")
    histograma: HistogramaEfecto | None = None


class EvaluacionMecanismo(BaseModel):
    variable: str
    rol: Literal["intermedia", "objetivo"]
    tipo: Literal["continua", "binaria"]
    padres: list[str]
    familia: str
    nombre_familia: str
    elegido: Literal["simple", "complejo"]
    origen: Literal["automatico", "manual"]
    motivo: str
    metrica: Literal["r2", "exactitud_balanceada"]
    candidatos: list[CandidatoMecanismo]
    puntuacion_cv: float
    puntuacion_test: float | None
    filas_train: int
    filas_test: int
    rescate: list[str]
    efectos: list[EfectoParcial]


class PuntoCalibracion(BaseModel):
    probabilidad_media: float
    frecuencia_observada: float
    filas: int


class Calibracion(BaseModel):
    cv: list[PuntoCalibracion]
    test: list[PuntoCalibracion]


class EvaluacionObjetivo(BaseModel):
    umbral_decision: float | None
    pesos_clase: bool
    cv: dict[str, float | None]
    test: dict[str, float | None]
    calibracion: Calibracion | None
    prevalencia_train: float | None


class ComparacionReferencia(BaseModel):
    metrica: str
    modelo_causal: float
    referencia: float
    diferencia: float


class ModeloReferencia(BaseModel):
    familia: str
    variables: list[str]
    umbral: float | None
    cv: dict[str, float | None]
    test: dict[str, float | None]
    comparacion: list[ComparacionReferencia]
    principal: str
    advertencia: str | None


class EvaluacionModeloCausal(BaseModel):
    objetivo: str
    mecanismos: list[EvaluacionMecanismo]
    evaluacion_objetivo: EvaluacionObjetivo
    referencia: ModeloReferencia


class ControlVariable(BaseModel):
    nombre: str
    control: Literal["numerica", "ordinal", "categorica", "grupo_one_hot"]
    columnas: list[str]
    categorias: list[Any]
    minimo: float | None = Field(description="Mínimo de entrenamiento en unidades originales (numéricas).")
    maximo: float | None
    rol: Literal["raiz", "intermedia"]
    columnas_en_modelo: list[str]


class ModeloCausal(BaseModel):
    modelo: ResumenModeloCausal
    evaluacion: EvaluacionModeloCausal
    controles: list[ControlVariable] = Field(description="Ancestros del objetivo intervenibles (dummies agrupadas).")
    vigente: bool = Field(description="False si la versión actual del resultado de PC no es la del modelo.")
    motivo_desactualizado: str | None
    filas_test: int


class CasoTest(BaseModel):
    indice: int = Field(description="Posición de la fila en los datos originales.")
    valores: dict[str, Any] = Field(description="Por control, en unidades originales.")
    objetivo: Any


class CasosModelo(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    filas: list[CasoTest]


class CasoEntrada(_Entrada):
    indice_test: int | None = Field(None, description="Fila de test (índice de «casos»).")
    valores: dict[str, Any] | None = Field(None, description="Valores propios en unidades originales.")


class IntervencionEntrada(_Entrada):
    variable: str = Field(description="Ancestro del objetivo, o el nombre de una categoría one-hot.")
    tipo: Literal["desplazar", "fijar"]
    valor: Any = Field(description="Cantidad a sumar (desplazar) o valor/categoría (fijar), en unidades originales.")


class SolicitudContrafactual(_Entrada):
    caso: CasoEntrada
    intervenciones: list[IntervencionEntrada] = []


class AvisoContrafactual(BaseModel):
    codigo: str
    mensaje: str
    variables: list[str]


class ValorContrafactual(BaseModel):
    variable: str
    rol: Literal["raiz", "intermedia", "objetivo"]
    tipo: Literal["continua", "binaria"]
    grupo: str | None
    antes: Any
    despues: Any
    antes_numerico: float | None
    despues_numerico: float | None
    cambio: float
    intervenida: bool
    extrapolacion: bool
    observado: bool


class ContribucionPadre(BaseModel):
    padre: str
    contribucion: float


class PasoTraza(BaseModel):
    variable: str
    causa: Literal["intervencion", "propagacion"]
    antes: float | None
    despues: float | None
    cambio: float
    por_padre: list[ContribucionPadre]


class ResultadoContrafactual(BaseModel):
    objetivo: str
    medida: Literal["probabilidad", "valor"]
    antes: float
    despues: float
    cambio: float
    umbral_decision: float | None
    clase_antes: int | None
    clase_despues: int | None
    valores: list[ValorContrafactual]
    traza: list[PasoTraza]
    avisos: list[AvisoContrafactual]
    aproximado: bool
    muestras: int
    extrapolacion: bool
    caso: dict[str, Any]


# --- Prescripción ---------------------------------------------------------------------------------


class ObjetivoDeseado(_Entrada):
    direccion: Literal["subir", "bajar"]
    valor: float = Field(description="Probabilidad de la clase 1 (objetivo binario) o valor en unidades originales.")


class ConfiguracionAccion(_Entrada):
    variable: str
    permitida: bool = True
    direccion: Literal["subir", "bajar", "ambas"] = "ambas"
    minimo: float | None = Field(None, description="Límite absoluto (unidades originales).")
    maximo: float | None = None
    cambio_maximo: float | None = Field(None, description="Cambio máximo respecto del valor actual (unidades originales).")
    costo: float = Field(1.0, description="Costo por unidad de la escala normalizada (rango de train).")
    estados_permitidos: list[Any] | None = Field(None, description="Binarias, ordinales y categorías: estados a los que se puede pasar.")


class Supuestos(_Entrada):
    modificable_por_decision: bool = False
    medida_antes_del_resultado: bool = False
    no_define_el_objetivo: bool = False
    confirmado_en: str | None = None


class ConfiguracionPrescripcion(_Entrada):
    modificables: list[str]
    objetivo: ObjetivoDeseado
    acciones: dict[str, ConfiguracionAccion]
    supuestos: dict[str, Supuestos] = {}
    mu: Literal["automatico"] | float = "automatico"
    optimizador: Literal["gradiente_proximal", "genetico"] = "gradiente_proximal"
    rejilla_mu: list[float] = Field(default_factory=lambda: [0.001, 0.001778, 0.003162, 0.005623, 0.01, 0.017783, 0.031623, 0.056234, 0.1])
    exito_calibracion: float = 0.95
    arranques_aleatorios: int = 4
    iteraciones_maximas: int = 300
    tolerancia: float = 1e-8
    tau_suavizado: float = 0.25
    poblacion: int = 40
    generaciones: int = 60
    alfa_blx: float = 0.5
    probabilidad_mutacion: float = 0.2
    elite: int = 2


class PuntoRejilla(BaseModel):
    mu: float
    tasa_exito: float | None
    exitos: int
    evaluados: int


class CalibracionMu(BaseModel):
    mu: float
    rejilla: list[PuntoRejilla]
    casos: int
    alcanzables: int
    no_alcanzables: int
    casos_que_ya_cumplen: int
    exito_requerido: float
    advertencia: str | None
    nota: str
    calibrada_en: str | None = None


class VistaConfiguracionPrescripcion(BaseModel):
    configuracion: ConfiguracionPrescripcion
    guardada: bool = Field(description="False si es la configuración sugerida (aún no guardada).")
    prescriptivas: list[str]
    sin_camino: list[str]
    desconocidas: list[str]
    controles: list[ControlVariable]
    variables_grafo: list[str] = Field(description="Variables del grafo que se pueden marcar como modificables.")
    modificables_pc: list[str] = Field(description="Modificables de la configuración de PC (punto de partida).")
    medida: Literal["probabilidad", "valor"]
    umbral_decision: float | None
    calibracion: CalibracionMu | None
    mu_efectivo: float | None = Field(description="μ que se usará (manual o calibrado); null si falta calibrar.")
    aviso: str


class ValidacionPrescripcion(BaseModel):
    valida: bool
    errores: list[ProblemaConfiguracion]
    condiciones: list[ProblemaAplicabilidad]
    configuracion: ConfiguracionPrescripcion


class CondicionesPrescripcion(BaseModel):
    problemas: list[ProblemaAplicabilidad]
    bloqueado: bool
    aviso: str


class SolicitudCasoPrescripcion(_Entrada):
    caso: CasoEntrada


class AccionPrescrita(BaseModel):
    variable: str
    tipo: Literal["continua", "discreta"]
    antes: Any
    despues: Any
    antes_numerico: float | None
    despues_numerico: float | None
    cambio: float | None
    contribucion: float = Field(description="Cuánto baja el logro si se quita solo esta acción.")
    restriccion_activa: str | None
    extrapolacion: bool
    mantener: bool = Field(description="Intermedia que se mantiene constante (cambio despreciable).")


class RestriccionActiva(BaseModel):
    variable: str
    restriccion: Literal["limite", "cambio_maximo", "direccion", "estados_permitidos"]
    mensaje: str


class ResultadoPrescripcion(BaseModel):
    caso: dict[str, Any]
    objetivo: str
    medida: Literal["probabilidad", "valor"]
    direccion: Literal["subir", "bajar"]
    deseado: float
    antes: float
    despues: float
    alcanzado: bool
    ya_cumple: bool
    falta: float
    acciones: list[AccionPrescrita]
    sin_cambio: list[str]
    restricciones_activas: list[RestriccionActiva]
    extrapolacion: bool
    aproximado: bool
    requiere_revision: bool
    referencia: dict[str, Any]
    explicacion: str
    costo_total: float
    optimizador: str
    mu: float
    segundos: float
    traza: list[PasoTraza]
    valores: list[ValorContrafactual]
    avisos: list[AvisoContrafactual]


class SolicitudLote(_Entrada):
    origen: Literal["test", "csv"]
    ruta_csv: str | None = Field(None, description="CSV o XLSX con las columnas ORIGINALES del dataset (origen «csv»).")


class ProblemaFila(BaseModel):
    fila: int
    mensaje: str


class MetaLote(BaseModel):
    numero: int
    origen: Literal["test", "csv"]
    ruta_csv: str | None
    casos: int
    mu: float
    optimizador: str
    filas_con_problemas: list[ProblemaFila]
    columnas_ignoradas: list[str]
    huella_modelo: str
    creado_en: str
    resumen: dict[str, int]


class PaginaLote(BaseModel):
    meta: MetaLote
    total: int
    pagina: int
    por_pagina: int
    filas: list[ResultadoPrescripcion]


class ComparacionOptimizadores(BaseModel):
    optimizador: str
    tasa_exito: float
    costo_medio: float
    segundos_medios: float


class EvaluacionPrescriptor(BaseModel):
    casos: int
    tasa_exito: float
    no_alcanzables: int
    cambio_medio: dict[str, dict[str, float | None]]
    porcentaje_acciones_en_cero: float
    porcentaje_requiere_revision: float
    porcentaje_extrapolacion: float
    sensibilidad_cambio_maximo: list[dict[str, float]]
    sensibilidad_mu: list[dict[str, float]]
    comparacion_optimizadores: list[ComparacionOptimizadores]
    mcnemar: dict[str, Any]
    mu: float
    texto: str


class MetaEvaluacion(BaseModel):
    numero: int
    casos: int
    mu: float
    optimizador: str
    tasa_exito: float
    huella_modelo: str
    creado_en: str


class InformeEvaluacion(BaseModel):
    meta: MetaEvaluacion
    evaluacion: EvaluacionPrescriptor


class SolicitudExportarPrescripcion(_Entrada):
    carpeta_destino: str
    lote: int | None = Field(None, description="Lote cuyas prescripciones se exportan en CSV.")
    evaluacion: int | None = Field(None, description="Evaluación que se incluye en el informe.")


class ResultadoExportarPrescripcion(BaseModel):
    carpeta: str
    archivos: list[str]


class Apagado(BaseModel):
    mensaje: str


# Modelos con referencias a clases definidas más abajo.
for _modelo in (Proyecto, ProyectoCreado, Trabajo):
    _modelo.model_rebuild()

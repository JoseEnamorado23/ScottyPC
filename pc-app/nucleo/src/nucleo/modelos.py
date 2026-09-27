"""Contratos de datos del núcleo.

Las dataclasses de este módulo representan los resultados que producirán
la validación y la revisión de datasets. No contienen lógica de análisis
ni DataFrames: solo datos simples, serializables a JSON mediante
``nucleo.utilidades.a_diccionario_serializable``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


_MAXIMO_COLUMNAS_IDENTIFICADOR = 5


class NivelProblema(str, Enum):
    """Nivel de un problema detectado durante la validación."""

    ERROR = "error"
    ADVERTENCIA = "advertencia"


class Severidad(str, Enum):
    """Severidad de un hallazgo detectado durante la revisión."""

    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class CodigoValidacion:
    """Códigos internos de los problemas de carga y validación."""

    # Carga de archivos
    FORMATO_NO_SOPORTADO = "FORMATO_NO_SOPORTADO"
    ARCHIVO_NO_ENCONTRADO = "ARCHIVO_NO_ENCONTRADO"
    ARCHIVO_ILEGIBLE = "ARCHIVO_ILEGIBLE"
    ARCHIVO_VACIO = "ARCHIVO_VACIO"
    CODIFICACION_NO_RECONOCIDA = "CODIFICACION_NO_RECONOCIDA"
    SEPARADOR_NO_DETECTADO = "SEPARADOR_NO_DETECTADO"
    HOJA_NO_ENCONTRADA = "HOJA_NO_ENCONTRADA"
    HOJA_NO_ESPECIFICADA = "HOJA_NO_ESPECIFICADA"
    HOJA_NO_APLICABLE = "HOJA_NO_APLICABLE"

    # Estructura del dataset
    DATASET_VACIO = "DATASET_VACIO"
    COLUMNAS_SIN_NOMBRE = "COLUMNAS_SIN_NOMBRE"
    COLUMNAS_REPETIDAS = "COLUMNAS_REPETIDAS"
    NOMBRES_CON_ESPACIOS = "NOMBRES_CON_ESPACIOS"
    FILAS_INSUFICIENTES = "FILAS_INSUFICIENTES"
    COLUMNAS_EXCESIVAS = "COLUMNAS_EXCESIVAS"

    # Variable objetivo
    OBJETIVO_INEXISTENTE = "OBJETIVO_INEXISTENTE"
    OBJETIVO_CON_FALTANTES = "OBJETIVO_CON_FALTANTES"
    OBJETIVO_CONSTANTE = "OBJETIVO_CONSTANTE"


class TipoColumna:
    """Tipos preliminares asignados por el perfilado de columnas."""

    NUMERICA = "numerica"
    CATEGORICA = "categorica"
    TEXTO = "texto"
    FECHA = "fecha"
    BOOLEANA = "booleana"
    VACIA = "vacia"


class TipoObjetivo:
    """Tipos preliminares de la variable objetivo."""

    BINARIO = "binario"
    MULTICLASE = "multiclase"
    CONTINUO = "continuo"


class TipoHallazgo:
    """Tipos de hallazgo producidos por los detectores de revisión."""

    FILAS_DUPLICADAS = "filas_duplicadas"
    VALORES_FALTANTES = "valores_faltantes"
    ALTA_PROPORCION_FALTANTES = "alta_proporcion_faltantes"
    CEROS_SOSPECHOSOS = "ceros_sospechosos"
    CONSTANTE = "constante"
    CASI_CONSTANTE = "casi_constante"
    POSIBLE_IDENTIFICADOR = "posible_identificador"
    TEXTO_LIBRE = "texto_libre"
    POSIBLE_FECHA = "posible_fecha"
    VARIABLE_CATEGORICA = "variable_categorica"
    POSIBLE_VARIABLE_ORDINAL = "posible_variable_ordinal"
    DISTRIBUCION_OBJETIVO = "distribucion_objetivo"
    DESBALANCE_CLASES = "desbalance_clases"
    COLUMNAS_REDUNDANTES = "columnas_redundantes"
    RECODIFICACION_UNO_A_UNO = "recodificacion_uno_a_uno"
    COLUMNA_DERIVADA = "columna_derivada"
    BINARIA_DERIVADA = "binaria_derivada"
    CORRELACION_CASI_PERFECTA = "correlacion_casi_perfecta"
    POSIBLE_MEZCLA_UNIDADES = "posible_mezcla_unidades"
    ASIMETRIA_FUERTE = "asimetria_fuerte"
    FALTANTES_DEPENDIENTES_OBJETIVO = "faltantes_dependientes_objetivo"
    TAMANO_EFECTIVO_INSUFICIENTE = "tamano_efectivo_insuficiente"
    GRUPO_REDUNDANTE = "grupo_redundante"


@dataclass(frozen=True)
class ProblemaValidacion:
    """Error o advertencia detectada durante la validación de un dataset."""

    nivel: NivelProblema
    codigo: str
    mensaje: str
    columnas: list[str] = field(default_factory=list)
    evidencia: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResultadoValidacion:
    """Resultado completo de la validación de un dataset."""

    valido: bool
    errores: list[ProblemaValidacion] = field(default_factory=list)
    advertencias: list[ProblemaValidacion] = field(default_factory=list)


@dataclass(frozen=True)
class Hallazgo:
    """Problema detectado durante la revisión de un dataset.

    Las acciones son descripciones en texto para el usuario; nunca se
    ejecutan automáticamente.

    ``identificador`` permite referirse al hallazgo desde las decisiones del
    usuario. Si no se indica se genera de forma determinista como
    ``tipo:columna1|columna2`` (solo ``tipo`` si involucra más de
    ``_MAXIMO_COLUMNAS_IDENTIFICADOR`` columnas); ``revisar_dataset``
    garantiza que sea único dentro de un informe.
    """

    tipo: str
    columnas_involucradas: list[str]
    severidad: Severidad
    detalle: str
    evidencia: dict[str, Any] = field(default_factory=dict)
    acciones_posibles: list[str] = field(default_factory=list)
    accion_sugerida: str | None = None
    identificador: str = ""

    def __post_init__(self) -> None:
        if not self.identificador:
            columnas = self.columnas_involucradas
            sufijo = "|".join(columnas) if len(columnas) <= _MAXIMO_COLUMNAS_IDENTIFICADOR else ""
            object.__setattr__(self, "identificador", f"{self.tipo}:{sufijo}" if sufijo else self.tipo)


@dataclass(frozen=True)
class PerfilColumna:
    """Perfil básico de una columna.

    ``minimo`` y ``maximo`` son ``None`` para columnas no numéricas. Los
    valores deben almacenarse como tipos nativos de Python, no de NumPy.
    """

    nombre: str
    tipo_detectado: str
    faltantes: int
    porcentaje_faltantes: float
    valores_unicos: int
    minimo: float | None = None
    maximo: float | None = None


@dataclass(frozen=True)
class InformeRevision:
    """Informe completo de revisión de un dataset.

    ``objetivo`` e ``informacion_objetivo`` quedan reservados para que las
    siguientes fases describan la variable objetivo.
    """

    resumen: dict[str, Any] = field(default_factory=dict)
    hallazgos: list[Hallazgo] = field(default_factory=list)
    perfiles_columnas: list[PerfilColumna] = field(default_factory=list)
    objetivo: str | None = None
    informacion_objetivo: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResultadoAnalisis:
    """Resultado del flujo completo: validación y, si es válido, revisión.

    ``informe`` es ``None`` cuando la validación encuentra errores
    bloqueantes: en ese caso la revisión no se ejecuta.
    """

    valido: bool
    validacion: ResultadoValidacion
    informe: InformeRevision | None = None

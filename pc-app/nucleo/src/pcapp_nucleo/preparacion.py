"""Preparación de datos a partir de las decisiones del usuario.

El orden de aplicación evita filtrar información del conjunto de test:

1. Antes de separar (nada aprende de la distribución de los datos):
   eliminar duplicados, excluir columnas, convertir textos centinela en
   faltantes, convertir unidades, marcar ceros como faltantes, crear
   indicadores de "dato medido", aplicar logaritmos, codificar categóricas
   (y el objetivo) y eliminar filas con faltantes.
2. Separar en entrenamiento y test (estratificada o temporal).
3. Después de separar, ajustado SOLO con entrenamiento y aplicado a ambos:
   imputación por mediana, imputación multivariada y normalización min-max.

``preparar`` devuelve ``DatosPreparados`` con una ``Receta`` que registra
todas las decisiones, la separación (índices incluidos) y los parámetros
aprendidos. ``aplicar_receta`` reproduce exactamente el mismo resultado a
partir del DataFrame original sin volver a aprender nada.

Ninguna función modifica el DataFrame recibido.
"""

from __future__ import annotations

import copy
import hashlib
import operator
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.api import types as tipos_pandas
from sklearn.model_selection import train_test_split

from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.fechas import convertir_fechas, interpretar_fechas_texto
from pcapp_nucleo.perfilado import detectar_tipo_columna
from pcapp_nucleo.revision import detectar_tipo_objetivo
from pcapp_nucleo.utilidades import a_diccionario_serializable

VERSION_RECETA = 2
# Versiones de receta que se pueden leer (la 1 guardaba la separación en las decisiones).
VERSIONES_RECETA_LEGIBLES = (1, 2)

IMPUTACIONES = ("eliminar_filas", "mediana", "multivariada")
TIPOS_CODIFICACION = ("binaria", "ordinal", "one_hot", "agrupacion")
TIPOS_SEPARACION = ("estratificada", "temporal")
_CONDICIONES = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}

# Tipos finales de las columnas preparadas.
CONTINUA, BINARIA, ORDINAL, ONE_HOT, INDICADOR, OBJETIVO = (
    "continua", "binaria", "ordinal", "one_hot", "indicador", "objetivo",
)


class ErrorPreparacion(Exception):
    """Error en las decisiones o en los datos, con un mensaje para el usuario."""


# --- Decisiones del usuario ---------------------------------------------------------


@dataclass(frozen=True)
class TratamientoColumna:
    """Tratamiento de faltantes de una columna.

    ``imputacion``: ``"eliminar_filas"``, ``"mediana"``, ``"multivariada"``
    o ``None`` (conservar los faltantes).
    """

    ceros_como_faltantes: bool = False
    indicador_medido: bool = False
    imputacion: str | None = None


@dataclass(frozen=True)
class Codificacion:
    """Codificación de una columna categórica (o del objetivo).

    - ``binaria``: ``valor_positivo`` pasa a 1 y el otro valor a 0 (si no se
      indica, 1 es el segundo valor en orden alfabético).
    - ``ordinal``: ``orden`` de menor a mayor; cada valor pasa a su posición.
    - ``one_hot``: una columna 0/1 por categoría excepto la primera
      (referencia), para no introducir una dependencia exacta entre columnas.
      Aumenta el número de variables de PC.
    - ``agrupacion``: ``grupos`` = {valor_original: nuevo_valor}.
    """

    tipo: str
    orden: list[Any] | None = None
    valor_positivo: Any = None
    grupos: dict[str, Any] | None = None


@dataclass(frozen=True)
class ConversionUnidades:
    """Si ``columna <condicion> umbral``: nuevo = (x - restar) * multiplicar.

    Ejemplo °F → °C: ``condicion=">", umbral=50, restar=32, multiplicar=5/9``.
    """

    columna: str
    condicion: str
    umbral: float
    restar: float = 0.0
    multiplicar: float = 1.0
    descripcion: str = ""


@dataclass(frozen=True)
class ConfiguracionSeparacion:
    """Separación en entrenamiento y test.

    ``temporal``: entrenamiento = fechas anteriores a ``corte`` (texto ISO,
    p. ej. ``"2024-07-01"``); sin corte, el primer ``1 - proporcion_test``
    cronológico. La columna de fecha se elimina después de separar.
    """

    tipo: str = "estratificada"
    proporcion_test: float = 0.3
    semilla: int = 42
    columna_fecha: str | None = None
    corte: str | None = None


@dataclass(frozen=True)
class AccionHallazgo:
    """Acción elegida para un hallazgo, con las opciones disponibles.

    ``requiere_confirmacion`` marca decisiones importantes que el software no
    puede tomar solo; la interfaz exigirá que el usuario las revise.
    """

    accion: str
    opciones: list[str] = field(default_factory=list)
    descripcion: str = ""
    requiere_confirmacion: bool = False


@dataclass(frozen=True)
class DecisionesUsuario:
    """Todas las decisiones de preparación, editables como JSON.

    La separación en entrenamiento y test no forma parte de las decisiones: se
    elige al preparar y queda en la receta (única fuente). Las columnas de
    ``columnas_fecha_disponibles`` nunca son variables de PC; solo pueden usarse
    para una separación temporal.

    Los campos concretos (``columnas_excluidas``, ``faltantes``...) son los
    que se aplican; ``acciones_hallazgos`` registra qué se decidió para cada
    hallazgo del revisor (trazabilidad para la interfaz).
    """

    eliminar_duplicados: bool = False
    acciones_hallazgos: dict[str, AccionHallazgo] = field(default_factory=dict)
    columnas_excluidas: list[str] = field(default_factory=list)
    faltantes: dict[str, TratamientoColumna] = field(default_factory=dict)
    codificaciones: dict[str, Codificacion] = field(default_factory=dict)
    conversiones: list[ConversionUnidades] = field(default_factory=list)
    logaritmos: list[str] = field(default_factory=list)
    normalizar: bool = True
    columnas_fecha_disponibles: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)


# --- Resultado y receta --------------------------------------------------------------


@dataclass(frozen=True)
class MetadatosColumna:
    """Tipo final, transformaciones aplicadas y parámetros de una columna."""

    nombre: str
    tipo_final: str
    transformaciones: list[str] = field(default_factory=list)
    parametros: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrigenDatos:
    archivo: str | None = None
    hoja: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class Receta:
    """Todo lo necesario para reproducir la preparación exactamente."""

    version: int
    origen: OrigenDatos
    objetivo: str
    tipo_objetivo: str | None
    decisiones: DecisionesUsuario
    separacion: ConfiguracionSeparacion
    separacion_aplicada: dict[str, Any]
    indices_train: list[int]
    indices_test: list[int]
    parametros_previos: dict[str, Any]
    parametros_aprendidos: dict[str, Any]
    columnas: list[MetadatosColumna]
    advertencias: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DatosPreparados:
    """Conjuntos preparados. ``train`` y ``test`` son DataFrames (se guardan
    como CSV); el resto es serializable a JSON a través de la receta. El
    índice de ambos conjuntos es la posición de la fila en los datos
    originales."""

    train: pd.DataFrame
    test: pd.DataFrame
    objetivo: str
    tipo_objetivo: str | None
    columnas: list[MetadatosColumna]
    receta: Receta


# --- Serialización -----------------------------------------------------------------------


def calcular_sha256(ruta: str | Path) -> str:
    """Hash SHA-256 del contenido de un archivo."""
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _construir(clase: type, datos: Any, contexto: str, **anidados: Any) -> Any:
    if not isinstance(datos, dict):
        raise ErrorPreparacion(f"{contexto} debe ser un objeto JSON.")
    nombres = {f.name for f in fields(clase)}
    desconocidos = sorted(set(datos) - nombres)
    if desconocidos:
        raise ErrorPreparacion(
            f"{contexto} contiene campos desconocidos: {', '.join(desconocidos)}."
        )
    try:
        return clase(**{**datos, **anidados})
    except TypeError as error:
        raise ErrorPreparacion(f"{contexto} no es válido: {error}.") from error


def decisiones_desde_diccionario(datos: Any) -> DecisionesUsuario:
    """Construye ``DecisionesUsuario`` desde un diccionario (p. ej. leído de JSON)."""
    if not isinstance(datos, dict):
        raise ErrorPreparacion("Las decisiones deben ser un objeto JSON.")
    anidados = {
        "acciones_hallazgos": {
            clave: _construir(AccionHallazgo, valor, f"La acción del hallazgo '{clave}'")
            for clave, valor in datos.get("acciones_hallazgos", {}).items()
        },
        "faltantes": {
            columna: _construir(TratamientoColumna, valor, f"El tratamiento de '{columna}'")
            for columna, valor in datos.get("faltantes", {}).items()
        },
        "codificaciones": {
            columna: _construir(Codificacion, valor, f"La codificación de '{columna}'")
            for columna, valor in datos.get("codificaciones", {}).items()
        },
        "conversiones": [
            _construir(ConversionUnidades, valor, f"La conversión {i + 1}")
            for i, valor in enumerate(datos.get("conversiones", []))
        ],
    }
    # 'separacion' de archivos antiguos se ignora aquí (ver ``separacion_heredada``).
    resto = {
        clave: valor for clave, valor in datos.items()
        if clave not in anidados and clave != "separacion"
    }
    return _construir(DecisionesUsuario, resto, "Las decisiones", **anidados)


def separacion_desde_diccionario(datos: Any) -> ConfiguracionSeparacion:
    return _construir(ConfiguracionSeparacion, datos, "La separación")


def separacion_heredada(datos: Any) -> ConfiguracionSeparacion | None:
    """Separación de un archivo de decisiones antiguo (antes vivía ahí); ``None`` si no la tiene.

    Solo debe usarse como valor inicial cuando todavía no hay receta.
    """
    if isinstance(datos, dict) and isinstance(datos.get("separacion"), dict):
        return separacion_desde_diccionario(datos["separacion"])
    return None


def columnas_fecha_reservadas(decisiones: DecisionesUsuario) -> list[str]:
    """Columnas de fecha que las decisiones no excluyen: se reservaron para separar por tiempo."""
    return [c for c in decisiones.columnas_fecha_disponibles if c not in decisiones.columnas_excluidas]


def separacion_sugerida(
    decisiones: DecisionesUsuario, heredada: ConfiguracionSeparacion | None = None
) -> ConfiguracionSeparacion:
    """Separación inicial cuando todavía no hay receta: la de un archivo antiguo
    si existe; si no, temporal por la fecha reservada en las decisiones; si no,
    estratificada."""
    if heredada is not None:
        return heredada
    reservadas = columnas_fecha_reservadas(decisiones)
    if reservadas:
        return ConfiguracionSeparacion(tipo="temporal", columna_fecha=reservadas[0])
    return ConfiguracionSeparacion()


def receta_desde_diccionario(datos: Any) -> Receta:
    """Construye una ``Receta`` desde un diccionario (p. ej. leído de JSON)."""
    if not isinstance(datos, dict):
        raise ErrorPreparacion("La receta debe ser un objeto JSON.")
    if datos.get("version") not in VERSIONES_RECETA_LEGIBLES:
        raise ErrorPreparacion(
            f"Versión de receta no soportada: {datos.get('version')!r} "
            f"(se esperaba {VERSION_RECETA})."
        )
    if datos["version"] == 1:
        separacion = separacion_heredada(datos.get("decisiones")) or ConfiguracionSeparacion()
        datos = {**datos, "version": VERSION_RECETA}
    else:
        separacion = separacion_desde_diccionario(datos.get("separacion", {}))
    anidados = {
        "origen": _construir(OrigenDatos, datos.get("origen", {}), "El origen de la receta"),
        "decisiones": decisiones_desde_diccionario(datos.get("decisiones", {})),
        "separacion": separacion,
        "columnas": [
            _construir(MetadatosColumna, valor, "Los metadatos de una columna")
            for valor in datos.get("columnas", [])
        ],
    }
    resto = {clave: valor for clave, valor in datos.items() if clave not in anidados}
    return _construir(Receta, resto, "La receta", **anidados)


def receta_a_diccionario(receta: Receta) -> dict[str, Any]:
    return a_diccionario_serializable(receta)


# --- Validación de decisiones ------------------------------------------------------------


def _validar_decisiones(
    decisiones: DecisionesUsuario, columnas: list[str], objetivo: str
) -> None:
    existentes = set(columnas)
    if objetivo not in existentes:
        raise ErrorPreparacion(f"La variable objetivo '{objetivo}' no existe en el dataset.")
    referencias = {
        "columnas_excluidas": decisiones.columnas_excluidas,
        "faltantes": list(decisiones.faltantes),
        "codificaciones": list(decisiones.codificaciones),
        "conversiones": [c.columna for c in decisiones.conversiones],
        "logaritmos": decisiones.logaritmos,
    }
    for seccion, nombres in referencias.items():
        faltan = [n for n in nombres if n not in existentes]
        if faltan:
            raise ErrorPreparacion(
                f"Las decisiones ({seccion}) mencionan columnas que no existen: "
                f"{', '.join(repr(n) for n in faltan)}."
            )
    if objetivo in decisiones.columnas_excluidas:
        raise ErrorPreparacion("La variable objetivo no puede excluirse.")
    if objetivo in decisiones.faltantes:
        raise ErrorPreparacion("La variable objetivo no admite tratamiento de faltantes.")
    for columna, tratamiento in decisiones.faltantes.items():
        if tratamiento.imputacion not in (None, *IMPUTACIONES):
            raise ErrorPreparacion(
                f"Imputación no válida para '{columna}': {tratamiento.imputacion!r}. "
                f"Opciones: {', '.join(IMPUTACIONES)} o null."
            )
    for columna, codificacion in decisiones.codificaciones.items():
        if codificacion.tipo not in TIPOS_CODIFICACION:
            raise ErrorPreparacion(
                f"Codificación no válida para '{columna}': {codificacion.tipo!r}. "
                f"Opciones: {', '.join(TIPOS_CODIFICACION)}."
            )
        if codificacion.tipo == "ordinal" and not codificacion.orden:
            raise ErrorPreparacion(f"La codificación ordinal de '{columna}' necesita 'orden'.")
        if codificacion.tipo == "agrupacion" and not codificacion.grupos:
            raise ErrorPreparacion(f"La agrupación de '{columna}' necesita 'grupos'.")
    for conversion in decisiones.conversiones:
        if conversion.condicion not in _CONDICIONES:
            raise ErrorPreparacion(
                f"Condición no válida en la conversión de '{conversion.columna}': "
                f"{conversion.condicion!r}. Opciones: {', '.join(_CONDICIONES)}."
            )


def validar_separacion(
    separacion: ConfiguracionSeparacion, columnas: list[str], decisiones: DecisionesUsuario
) -> None:
    """Comprueba que la separación sea aplicable.

    Raises:
        ErrorPreparacion: con un mensaje en español.
    """
    if separacion.tipo not in TIPOS_SEPARACION:
        raise ErrorPreparacion(
            f"Tipo de separación no válido: {separacion.tipo!r}. "
            f"Opciones: {', '.join(TIPOS_SEPARACION)}."
        )
    if not 0 < separacion.proporcion_test < 1:
        raise ErrorPreparacion("La proporción de test debe estar entre 0 y 1.")
    if separacion.tipo == "temporal" and separacion.columna_fecha is None:
        raise ErrorPreparacion("La separación temporal necesita 'columna_fecha'.")
    if separacion.tipo == "temporal" and separacion.columna_fecha not in columnas:
        raise ErrorPreparacion(
            f"La columna de fecha '{separacion.columna_fecha}' no existe en el dataset."
        )
    if (
        separacion.tipo == "temporal"
        and decisiones.columnas_fecha_disponibles
        and separacion.columna_fecha not in decisiones.columnas_fecha_disponibles
    ):
        raise ErrorPreparacion(
            f"'{separacion.columna_fecha}' no es una columna de fecha detectada; opciones: "
            f"{', '.join(decisiones.columnas_fecha_disponibles)}."
        )


# --- Auxiliares -------------------------------------------------------------------------------


def _mismo_valor(a: Any, b: Any) -> bool:
    """Compara valores leídos de JSON con valores de los datos (``"1"`` = ``1`` = ``1.0``)."""
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _nativo(valor: Any) -> Any:
    return valor.item() if isinstance(valor, np.generic) else valor


def _mapear(serie: pd.Series, pares: list[list[Any]], columna: str) -> pd.Series:
    """Aplica una correspondencia ``[[original, nuevo], ...]``; error si falta algún valor."""
    correspondencia = {}
    sin_pareja = []
    for valor in serie.dropna().unique():
        nuevo = next((n for original, n in pares if _mismo_valor(original, valor)), None)
        if nuevo is None:
            sin_pareja.append(_nativo(valor))
        else:
            correspondencia[valor] = nuevo
    if sin_pareja:
        raise ErrorPreparacion(
            f"La columna '{columna}' tiene valores sin correspondencia en su codificación: "
            f"{', '.join(repr(v) for v in sin_pareja[:10])}."
        )
    return pd.to_numeric(serie.map(correspondencia))


def _numerica(datos: pd.DataFrame, columna: str, accion: str) -> pd.Series:
    serie = datos[columna]
    if not tipos_pandas.is_numeric_dtype(serie.dtype) or tipos_pandas.is_bool_dtype(serie.dtype):
        raise ErrorPreparacion(f"No se puede {accion} en '{columna}': la columna no es numérica.")
    return serie.astype(float)


class _Registro:
    """Transformaciones y parámetros por columna, acumulados durante la preparación."""

    def __init__(self, columnas: list[str]) -> None:
        self.columnas: dict[str, dict[str, Any]] = {
            c: {"tipo_final": None, "transformaciones": [], "parametros": {}} for c in columnas
        }

    def anotar(self, columna: str, transformacion: str, **parametros: Any) -> None:
        entrada = self.columnas.setdefault(
            columna, {"tipo_final": None, "transformaciones": [], "parametros": {}}
        )
        entrada["transformaciones"].append(transformacion)
        entrada["parametros"].update(parametros)

    def tipo(self, columna: str, tipo_final: str) -> None:
        self.columnas.setdefault(
            columna, {"tipo_final": None, "transformaciones": [], "parametros": {}}
        )["tipo_final"] = tipo_final


# --- 1. Pasos anteriores a la separación ------------------------------------------------------


def _preprocesar(
    dataframe: pd.DataFrame,
    objetivo: str,
    decisiones: DecisionesUsuario,
    fecha: str | None,
    configuracion: ConfiguracionValidacion,
    previos: dict[str, Any] | None,
) -> tuple[pd.DataFrame, dict[str, Any], _Registro]:
    """Pasos que no aprenden de la distribución de los datos.

    ``previos`` son las elecciones dependientes de los valores observados
    (categorías, correspondencias, log o log1p, formato de fecha). En
    ``preparar`` se calculan y se devuelven; en ``aplicar_receta`` se reciben
    de la receta y se reutilizan tal cual.
    """
    reproducir = previos is not None
    previos = copy.deepcopy(previos) if reproducir else {}
    datos = dataframe.reset_index(drop=True).copy()
    registro = _Registro(list(datos.columns))

    if decisiones.eliminar_duplicados:
        antes = len(datos)
        try:
            duplicadas = datos.duplicated()
        except TypeError:
            duplicadas = datos.map(repr).duplicated()
        datos = datos[~duplicadas]
        previos["filas_duplicadas_eliminadas"] = antes - len(datos)

    # Las fechas nunca son variables: se quitan salvo la usada para separar (que se
    # quita después de separar, en ``_ordenar_columnas``).
    excluir = {*decisiones.columnas_excluidas, *decisiones.columnas_fecha_disponibles} - {fecha}
    datos = datos.drop(columns=[c for c in datos.columns if c in excluir])

    for columna in list(datos.columns):
        if columna != fecha:
            datos[columna] = _centinelas_a_faltantes(
                datos[columna], columna, configuracion, registro
            )

    for conversion in decisiones.conversiones:
        valores = _numerica(datos, conversion.columna, "convertir unidades")
        mascara = _CONDICIONES[conversion.condicion](valores, conversion.umbral).fillna(False)
        valores = valores.where(~mascara, (valores - conversion.restar) * conversion.multiplicar)
        datos[conversion.columna] = valores
        registro.anotar(
            conversion.columna,
            f"conversion_unidades({conversion.condicion} {conversion.umbral:g})",
            filas_convertidas=int(mascara.sum()),
        )

    for columna, tratamiento in decisiones.faltantes.items():
        if columna in datos and tratamiento.ceros_como_faltantes:
            valores = _numerica(datos, columna, "marcar ceros como faltantes")
            ceros = valores == 0
            datos[columna] = valores.mask(ceros)
            registro.anotar(columna, "ceros_como_faltantes", ceros_marcados=int(ceros.sum()))

    for columna, tratamiento in decisiones.faltantes.items():
        if columna in datos and tratamiento.indicador_medido:
            nombre = f"{columna}_medido"
            if nombre in datos:
                raise ErrorPreparacion(f"No se puede crear el indicador '{nombre}': ya existe.")
            datos[nombre] = datos[columna].notna().astype(int)
            registro.tipo(nombre, INDICADOR)
            registro.anotar(nombre, "indicador_dato_medido", columna_original=columna)

    for columna in decisiones.logaritmos:
        if columna not in datos:
            continue
        valores = _numerica(datos, columna, "aplicar el logaritmo")
        if reproducir:
            funcion = previos["logaritmos"][columna]
        else:
            minimo = valores.min()
            if minimo < 0:
                raise ErrorPreparacion(
                    f"No se puede aplicar el logaritmo en '{columna}': tiene valores negativos."
                )
            funcion = "log" if minimo > 0 else "log1p"
            previos.setdefault("logaritmos", {})[columna] = funcion
        datos[columna] = np.log(valores) if funcion == "log" else np.log1p(valores)
        registro.anotar(columna, funcion)

    datos = _codificar(datos, objetivo, decisiones, previos, reproducir, registro)

    eliminar = [
        c for c, t in decisiones.faltantes.items() if t.imputacion == "eliminar_filas" and c in datos
    ]
    if eliminar:
        antes = len(datos)
        datos = datos.dropna(subset=eliminar)
        for columna in eliminar:
            registro.anotar(columna, "filas_con_faltantes_eliminadas")
        previos["filas_eliminadas_por_faltantes"] = antes - len(datos)

    no_numericas = [
        c for c in datos.columns
        if c != fecha and not tipos_pandas.is_numeric_dtype(datos[c].dtype)
    ]
    if no_numericas:
        raise ErrorPreparacion(
            "Estas columnas no son numéricas: "
            f"{', '.join(repr(c) for c in no_numericas)}. Codifíquelas o exclúyalas en las decisiones."
        )
    if objetivo in datos and datos[objetivo].isna().any():
        raise ErrorPreparacion("La variable objetivo tiene faltantes después de la preparación.")
    return datos, previos, registro


def _centinelas_a_faltantes(
    serie: pd.Series, columna: str, configuracion: ConfiguracionValidacion, registro: _Registro
) -> pd.Series:
    """Textos centinela → NaN; si el resto es numérico, la columna pasa a número."""
    if tipos_pandas.is_numeric_dtype(serie.dtype) or tipos_pandas.is_bool_dtype(serie.dtype):
        return serie.astype(int) if tipos_pandas.is_bool_dtype(serie.dtype) else serie
    centinela = serie.map(
        lambda v: isinstance(v, str) and v.strip() in configuracion.valores_centinela_faltantes
    ).astype(bool)
    if not centinela.any():
        return serie
    limpia = serie.mask(centinela)
    registro.anotar(columna, "centinelas_como_faltantes", centinelas=int(centinela.sum()))
    numerica = pd.to_numeric(limpia, errors="coerce")
    return numerica if numerica.notna().sum() == limpia.notna().sum() else limpia


def _codificar(
    datos: pd.DataFrame,
    objetivo: str,
    decisiones: DecisionesUsuario,
    previos: dict[str, Any],
    reproducir: bool,
    registro: _Registro,
) -> pd.DataFrame:
    guardadas = previos.setdefault("codificaciones", {})
    for columna, codificacion in decisiones.codificaciones.items():
        if columna not in datos:
            continue
        serie = datos[columna]
        if codificacion.tipo == "one_hot":
            categorias = (
                guardadas[columna]["categorias"] if reproducir
                else sorted((_nativo(v) for v in serie.dropna().unique()), key=str)
            )
            guardadas[columna] = {"tipo": "one_hot", "categorias": categorias}
            datos = _one_hot(datos, columna, categorias, registro)
            continue
        if reproducir:
            pares = guardadas[columna]["mapeo"]
        else:
            pares = _pares_codificacion(serie, columna, codificacion)
            guardadas[columna] = {"tipo": codificacion.tipo, "mapeo": pares}
        datos[columna] = _mapear(serie, pares, columna)
        nuevos = {n for _, n in pares}
        tipo = BINARIA if codificacion.tipo == "binaria" or len(nuevos) == 2 else ORDINAL
        if columna != objetivo:
            registro.tipo(columna, tipo)
        registro.anotar(columna, f"codificacion_{codificacion.tipo}", mapeo=pares)

    if objetivo in datos and not tipos_pandas.is_numeric_dtype(datos[objetivo].dtype):
        if reproducir:
            pares = previos["codificacion_objetivo"]
        else:
            valores = sorted((_nativo(v) for v in datos[objetivo].dropna().unique()), key=str)
            pares = [[valor, i] for i, valor in enumerate(valores)]
            previos["codificacion_objetivo"] = pares
        datos[objetivo] = _mapear(datos[objetivo], pares, objetivo)
        registro.anotar(objetivo, "codificacion_automatica_objetivo", mapeo=pares)
    return datos


def _pares_codificacion(serie: pd.Series, columna: str, codificacion: Codificacion) -> list[list[Any]]:
    valores = sorted((_nativo(v) for v in serie.dropna().unique()), key=str)
    if codificacion.tipo == "binaria":
        if len(valores) != 2:
            raise ErrorPreparacion(
                f"La codificación binaria de '{columna}' requiere exactamente 2 valores "
                f"distintos y tiene {len(valores)}."
            )
        positivo = codificacion.valor_positivo
        if positivo is None:
            positivo = valores[1]
        if not any(_mismo_valor(positivo, v) for v in valores):
            raise ErrorPreparacion(
                f"El valor positivo {positivo!r} no aparece en la columna '{columna}'."
            )
        return [[v, 1 if _mismo_valor(positivo, v) else 0] for v in valores]
    if codificacion.tipo == "ordinal":
        return [[valor, posicion] for posicion, valor in enumerate(codificacion.orden or [])]
    return [[original, nuevo] for original, nuevo in (codificacion.grupos or {}).items()]


def _one_hot(
    datos: pd.DataFrame, columna: str, categorias: list[Any], registro: _Registro
) -> pd.DataFrame:
    serie = datos[columna]
    posicion = list(datos.columns).index(columna)
    nuevas = {}
    for categoria in categorias[1:]:
        nombre = f"{columna}={categoria}"
        iguales = serie.map(lambda v, c=categoria: _mismo_valor(v, c) if pd.notna(v) else False)
        nuevas[nombre] = iguales.astype(float).where(serie.notna())
        registro.tipo(nombre, ONE_HOT)
        registro.anotar(
            nombre, "one_hot", columna_original=columna, categoria=categoria,
            referencia=categorias[0],
        )
    desconocidas = [
        _nativo(v) for v in serie.dropna().unique()
        if not any(_mismo_valor(v, c) for c in categorias)
    ]
    if desconocidas:
        raise ErrorPreparacion(
            f"La columna '{columna}' tiene categorías no vistas al preparar: "
            f"{', '.join(repr(v) for v in desconocidas[:10])}."
        )
    antes, despues = datos.iloc[:, :posicion], datos.iloc[:, posicion + 1:]
    return pd.concat([antes, pd.DataFrame(nuevas, index=datos.index), despues], axis=1)


# --- 2. Separación -------------------------------------------------------------------------------


def _fechas_separacion(
    serie: pd.Series, previos: dict[str, Any], reproducir: bool, configuracion: ConfiguracionValidacion
) -> pd.Series:
    if tipos_pandas.is_datetime64_any_dtype(serie.dtype):
        return serie
    if reproducir:
        formato = previos.get("formato_fecha")
    else:
        interpretacion = interpretar_fechas_texto(
            serie, configuracion.porcentaje_minimo_fechas_convertibles
        )
        formato = interpretacion.formato if interpretacion else None
        previos["formato_fecha"] = formato
    if formato is None:
        return pd.to_datetime(serie, errors="coerce")
    return convertir_fechas(serie, formato)


def _separar(
    datos: pd.DataFrame,
    objetivo: str,
    separacion: ConfiguracionSeparacion,
    previos: dict[str, Any],
    configuracion: ConfiguracionValidacion,
) -> tuple[list[int], list[int], dict[str, Any]]:
    indices = datos.index.to_numpy()
    if separacion.tipo == "estratificada":
        y = datos[objetivo]
        conteo = y.value_counts()
        estratificar = (
            len(conteo) <= configuracion.maximo_clases_objetivo and int(conteo.min()) >= 2
        )
        try:
            train, test = train_test_split(
                indices,
                test_size=separacion.proporcion_test,
                random_state=separacion.semilla,
                stratify=y.to_numpy() if estratificar else None,
            )
        except ValueError as error:
            raise ErrorPreparacion(f"No se pudo separar el dataset: {error}.") from error
        info = {"tipo": "estratificada" if estratificar else "aleatoria"}
    else:
        fechas = _fechas_separacion(
            datos[separacion.columna_fecha], previos, False, configuracion
        )
        sin_fecha = int(fechas.isna().sum())
        if sin_fecha:
            raise ErrorPreparacion(
                f"La columna '{separacion.columna_fecha}' tiene {sin_fecha} filas sin una fecha "
                "interpretable; no se puede separar temporalmente."
            )
        if separacion.corte is not None:
            try:
                corte = pd.Timestamp(separacion.corte)
            except ValueError as error:
                raise ErrorPreparacion(
                    f"Fecha de corte no válida: {separacion.corte!r}. Use el formato AAAA-MM-DD."
                ) from error
        else:
            ordenadas = fechas.sort_values(kind="stable")
            posicion = int(round(len(ordenadas) * (1 - separacion.proporcion_test)))
            corte = ordenadas.iloc[min(posicion, len(ordenadas) - 1)]
        en_train = (fechas < corte).to_numpy()
        train, test = indices[en_train], indices[~en_train]
        if len(train) == 0 or len(test) == 0:
            raise ErrorPreparacion(
                f"La fecha de corte {corte.date().isoformat()} deja vacío el conjunto de "
                f"{'entrenamiento' if len(train) == 0 else 'test'}."
            )
        info = {
            "tipo": "temporal",
            "columna_fecha": separacion.columna_fecha,
            "corte": corte.date().isoformat(),
            "formato_fecha": previos.get("formato_fecha"),
        }
    info.update({"filas_train": len(train), "filas_test": len(test)})
    return sorted(int(i) for i in train), sorted(int(i) for i in test), info


# --- 3. Pasos posteriores a la separación: imputación iterativa propia --------------------------


def _paso_imputacion(
    matriz: np.ndarray, faltante: np.ndarray, columna: int, otras: list[int],
    coeficientes: np.ndarray, intercepto: float,
) -> None:
    """Reemplaza en ``matriz`` los faltantes de ``columna`` con la regresión dada.

    Es la única operación que escribe valores imputados; la usan el ajuste y
    la aplicación, lo que garantiza resultados idénticos en ambos casos.
    """
    filas = faltante[:, columna]
    if filas.any():
        matriz[filas, columna] = matriz[np.ix_(filas, otras)] @ coeficientes + intercepto


def ajustar_imputacion_iterativa(
    datos: pd.DataFrame, columnas: list[str], rondas: int
) -> dict[str, Any]:
    """Ajusta una imputación iterativa por regresión lineal (solo con ``datos``).

    1. Relleno inicial de todos los faltantes con la mediana de cada columna.
    2. En cada una de ``rondas`` rondas, para cada columna de ``columnas``
       (en orden): regresión lineal por mínimos cuadrados sobre todas las
       demás columnas, ajustada con las filas donde la columna tenía dato, y
       reemplazo de sus valores faltantes con la predicción.

    Devuelve las medianas y los coeficientes de cada paso, serializables a
    JSON; ``aplicar_imputacion_iterativa`` los reproduce exactamente.
    """
    entrada = list(datos.columns)
    matriz = datos.to_numpy(dtype=float, copy=True)
    faltante = np.isnan(matriz)
    medianas = np.nan_to_num(np.nanmedian(np.where(faltante.all(axis=0), 0.0, matriz), axis=0))
    matriz[faltante] = np.broadcast_to(medianas, matriz.shape)[faltante]
    posiciones = {c: entrada.index(c) for c in columnas}
    secuencia = []
    for _ in range(rondas):
        ronda = []
        for columna in columnas:
            j = posiciones[columna]
            otras = [k for k in range(len(entrada)) if k != j]
            observadas = ~faltante[:, j]
            if not observadas.any():
                raise ErrorPreparacion(
                    f"No se puede imputar '{columna}': no tiene valores en entrenamiento."
                )
            diseno = np.column_stack([matriz[np.ix_(observadas, otras)], np.ones(observadas.sum())])
            solucion, *_ = np.linalg.lstsq(diseno, matriz[observadas, j], rcond=None)
            coeficientes, intercepto = solucion[:-1], float(solucion[-1])
            _paso_imputacion(matriz, faltante, j, otras, coeficientes, intercepto)
            ronda.append(
                {"columna": columna, "coeficientes": [float(c) for c in coeficientes],
                 "intercepto": intercepto}
            )
        secuencia.append(ronda)
    return {
        "columnas_entrada": entrada,
        "medianas_iniciales": [float(m) for m in medianas],
        "rondas": secuencia,
    }


def aplicar_imputacion_iterativa(datos: pd.DataFrame, parametros: dict[str, Any]) -> pd.DataFrame:
    """Aplica una imputación ajustada con ``ajustar_imputacion_iterativa``.

    Solo cambian las columnas imputadas; las demás conservan sus faltantes.
    """
    entrada = parametros["columnas_entrada"]
    matriz = datos[entrada].to_numpy(dtype=float, copy=True)
    faltante = np.isnan(matriz)
    medianas = np.asarray(parametros["medianas_iniciales"], dtype=float)
    matriz[faltante] = np.broadcast_to(medianas, matriz.shape)[faltante]
    imputadas = []
    for ronda in parametros["rondas"]:
        for paso in ronda:
            j = entrada.index(paso["columna"])
            otras = [k for k in range(len(entrada)) if k != j]
            _paso_imputacion(
                matriz, faltante, j, otras,
                np.asarray(paso["coeficientes"], dtype=float), paso["intercepto"],
            )
            imputadas.append(paso["columna"])
    resultado = datos.copy()
    for columna in dict.fromkeys(imputadas):
        resultado[columna] = matriz[:, entrada.index(columna)]
    return resultado


def _tratamientos_efectivos(
    decisiones: DecisionesUsuario, previos: dict[str, Any]
) -> dict[str, TratamientoColumna]:
    """Tratamientos por columna final: el de una columna codificada con one-hot
    se aplica a cada una de sus columnas nuevas."""
    efectivos = dict(decisiones.faltantes)
    for columna, codificacion in previos.get("codificaciones", {}).items():
        if codificacion["tipo"] == "one_hot" and columna in efectivos:
            tratamiento = efectivos.pop(columna)
            for categoria in codificacion["categorias"][1:]:
                efectivos[f"{columna}={categoria}"] = tratamiento
    return efectivos


def _ajustar_parametros(
    train: pd.DataFrame,
    objetivo: str,
    decisiones: DecisionesUsuario,
    previos: dict[str, Any],
    configuracion: ConfiguracionValidacion,
) -> dict[str, Any]:
    """Aprende medianas, imputador y mínimos/máximos SOLO con entrenamiento."""
    caracteristicas = [c for c in train.columns if c != objetivo]
    parametros: dict[str, Any] = {"medianas": {}, "imputador": None, "minimos": {}, "maximos": {}}
    tratamientos = _tratamientos_efectivos(decisiones, previos)
    for columna, tratamiento in tratamientos.items():
        if tratamiento.imputacion == "mediana" and columna in caracteristicas:
            mediana = train[columna].median()
            if pd.isna(mediana):
                raise ErrorPreparacion(
                    f"No se puede imputar '{columna}' con la mediana: no tiene valores en "
                    "entrenamiento."
                )
            parametros["medianas"][columna] = float(mediana)
    actual = _aplicar_parametros(train, objetivo, parametros)
    multivariadas = [
        c for c, t in tratamientos.items()
        if t.imputacion == "multivariada" and c in caracteristicas
    ]
    if multivariadas:
        if configuracion.rondas_imputacion_multivariada < 1:
            raise ErrorPreparacion("La imputación multivariada necesita al menos una ronda.")
        parametros["imputador"] = ajustar_imputacion_iterativa(
            actual[caracteristicas], multivariadas, configuracion.rondas_imputacion_multivariada
        )
        actual = _aplicar_parametros(actual, objetivo, {"imputador": parametros["imputador"]})
    if decisiones.normalizar:
        for columna in caracteristicas:
            if actual[columna].notna().any():
                parametros["minimos"][columna] = float(actual[columna].min())
                parametros["maximos"][columna] = float(actual[columna].max())
    return parametros


def _aplicar_parametros(
    datos: pd.DataFrame, objetivo: str, parametros: dict[str, Any]
) -> pd.DataFrame:
    resultado = datos.copy()
    for columna, mediana in parametros.get("medianas", {}).items():
        resultado[columna] = resultado[columna].fillna(mediana)
    if parametros.get("imputador"):
        resultado = aplicar_imputacion_iterativa(resultado, parametros["imputador"])
    for columna, minimo in parametros.get("minimos", {}).items():
        rango = parametros["maximos"][columna] - minimo
        valores = resultado[columna].astype(float)
        resultado[columna] = (valores - minimo) / rango if rango > 0 else valores * 0.0
    return resultado


# --- Metadatos ---------------------------------------------------------------------------------


def _metadatos(
    datos: pd.DataFrame, objetivo: str, registro: _Registro, parametros: dict[str, Any]
) -> list[MetadatosColumna]:
    metadatos = []
    for columna in datos.columns:
        entrada = registro.columnas.get(
            columna, {"tipo_final": None, "transformaciones": [], "parametros": {}}
        )
        transformaciones = list(entrada["transformaciones"])
        valores = dict(entrada["parametros"])
        if columna in parametros["medianas"]:
            transformaciones.append("imputacion_mediana")
            valores["mediana"] = parametros["medianas"][columna]
        if parametros["imputador"] and any(
            paso["columna"] == columna for paso in parametros["imputador"]["rondas"][0]
        ):
            transformaciones.append("imputacion_multivariada")
        if columna in parametros["minimos"]:
            transformaciones.append("normalizacion_min_max")
            valores.update(minimo=parametros["minimos"][columna], maximo=parametros["maximos"][columna])
        if columna == objetivo:
            tipo = OBJETIVO
        elif entrada["tipo_final"] is not None:
            tipo = entrada["tipo_final"]
        else:
            tipo = BINARIA if datos[columna].dropna().nunique() == 2 else CONTINUA
        metadatos.append(MetadatosColumna(str(columna), tipo, transformaciones, valores))
    return metadatos


# --- Funciones públicas ----------------------------------------------------------------------


def _fecha_temporal(separacion: ConfiguracionSeparacion) -> str | None:
    return separacion.columna_fecha if separacion.tipo == "temporal" else None


def preparar(
    dataframe: pd.DataFrame,
    objetivo: str,
    decisiones: DecisionesUsuario,
    configuracion: ConfiguracionValidacion | None = None,
    origen: OrigenDatos | None = None,
    separacion: ConfiguracionSeparacion | None = None,
) -> DatosPreparados:
    """Aplica las decisiones en el orden documentado, separa según ``separacion``
    (por defecto, estratificada) y devuelve los conjuntos. La separación queda en la receta.

    Raises:
        ErrorPreparacion: si las decisiones o la separación no son aplicables a los datos.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    separacion = separacion or ConfiguracionSeparacion()
    _validar_decisiones(decisiones, list(dataframe.columns), objetivo)
    validar_separacion(separacion, list(dataframe.columns), decisiones)
    fecha = _fecha_temporal(separacion)
    datos, previos, registro = _preprocesar(dataframe, objetivo, decisiones, fecha, configuracion, None)
    indices_train, indices_test, separacion_aplicada = _separar(
        datos, objetivo, separacion, previos, configuracion
    )
    datos = _ordenar_columnas(datos, objetivo, fecha)
    parametros = _ajustar_parametros(
        datos.loc[indices_train], objetivo, decisiones, previos, configuracion
    )
    tipo_objetivo = detectar_tipo_objetivo(
        datos[objetivo], detectar_tipo_columna(datos[objetivo], configuracion), configuracion
    )
    advertencias = [
        f"La codificación one-hot de '{c}' añade variables a PC."
        for c, cod in decisiones.codificaciones.items() if cod.tipo == "one_hot"
    ]
    receta = Receta(
        version=VERSION_RECETA,
        origen=origen or OrigenDatos(),
        objetivo=objetivo,
        tipo_objetivo=tipo_objetivo,
        decisiones=decisiones,
        separacion=separacion,
        separacion_aplicada=separacion_aplicada,
        indices_train=indices_train,
        indices_test=indices_test,
        parametros_previos=previos,
        parametros_aprendidos=parametros,
        columnas=_metadatos(datos, objetivo, registro, parametros),
        advertencias=advertencias,
    )
    return _datos_preparados(datos, receta)


def aplicar_receta(
    dataframe: pd.DataFrame, receta: Receta, configuracion: ConfiguracionValidacion | None = None
) -> DatosPreparados:
    """Reproduce exactamente la preparación registrada en ``receta``.

    Repite los pasos previos a la separación con las elecciones guardadas,
    usa los índices de entrenamiento y test guardados y aplica los
    parámetros aprendidos sin volver a ajustarlos.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    _validar_decisiones(receta.decisiones, list(dataframe.columns), receta.objetivo)
    fecha = _fecha_temporal(receta.separacion)
    datos, _, _ = _preprocesar(
        dataframe, receta.objetivo, receta.decisiones, fecha, configuracion, receta.parametros_previos
    )
    faltan = set(receta.indices_train + receta.indices_test) - set(datos.index)
    if faltan:
        raise ErrorPreparacion(
            "La receta no corresponde a estos datos: faltan filas usadas en la preparación."
        )
    datos = _ordenar_columnas(datos, receta.objetivo, fecha)
    return _datos_preparados(datos, receta)


@dataclass(frozen=True)
class ProblemaFila:
    """Fila de datos nuevos que no se pudo preparar (``fila`` = posición en el archivo, desde 0)."""

    fila: int
    mensaje: str


@dataclass(frozen=True)
class NuevosPreparados:
    """Filas nuevas preparadas con la receta (índice = posición en el archivo)."""

    datos: pd.DataFrame
    problemas: list[ProblemaFila]
    columnas_ignoradas: list[str]


def columnas_originales_requeridas(receta: Receta) -> list[str]:
    """Columnas del dataset original que necesita la receta para preparar filas nuevas."""
    requeridas: list[str] = []
    for columna in receta.columnas:
        if columna.nombre == receta.objetivo:
            continue
        p = columna.parametros
        if columna.tipo_final == ONE_HOT and "columna_original" in p:
            original = p["columna_original"]
        elif columna.tipo_final == INDICADOR and "columna_original" in p:
            original = p["columna_original"]
        else:
            original = columna.nombre
        if original not in requeridas:
            requeridas.append(original)
    return requeridas


def preparar_nuevos(
    dataframe: pd.DataFrame, receta: Receta, configuracion: ConfiguracionValidacion | None = None
) -> NuevosPreparados:
    """Prepara filas NUEVAS (p. ej. un CSV para prescribir) con la receta, sin aprender nada.

    Mismos pasos que ``aplicar_receta`` con estas diferencias: el objetivo no hace falta (si
    viene, se ignora), no se eliminan duplicados, y una fila que no se puede preparar (categoría
    no vista, valor no numérico, faltante en una columna de «eliminar filas») se informa en
    ``problemas`` en vez de detener todo.

    Raises:
        ErrorPreparacion: si faltan columnas que usa la receta.
    """
    configuracion = configuracion or ConfiguracionValidacion()
    requeridas = columnas_originales_requeridas(receta)
    faltan = [c for c in requeridas if c not in dataframe.columns]
    if faltan:
        raise ErrorPreparacion(
            "Faltan columnas del dataset original: " + ", ".join(repr(c) for c in faltan) + "."
        )
    ignoradas = [str(c) for c in dataframe.columns if c not in requeridas]
    datos = dataframe[requeridas].reset_index(drop=True)
    eliminar = [c for c, t in receta.decisiones.faltantes.items() if t.imputacion == "eliminar_filas"]
    decisiones = replace(
        receta.decisiones,
        eliminar_duplicados=False,
        faltantes={
            c: replace(t, imputacion=None) if t.imputacion == "eliminar_filas" else t
            for c, t in receta.decisiones.faltantes.items()
        },
    )

    def preprocesar(parte: pd.DataFrame) -> pd.DataFrame:
        resultado, _, _ = _preprocesar(
            parte, receta.objetivo, decisiones, None, configuracion, receta.parametros_previos
        )
        resultado.index = parte.index
        return resultado

    problemas: list[ProblemaFila] = []
    try:
        preparadas = preprocesar(datos)
    except ErrorPreparacion:
        partes = []
        for fila in range(len(datos)):
            try:
                partes.append(preprocesar(datos.iloc[[fila]]))
            except ErrorPreparacion as error:
                problemas.append(ProblemaFila(fila, str(error)))
        preparadas = pd.concat(partes) if partes else pd.DataFrame(columns=[c.nombre for c in receta.columnas])
    for columna in eliminar:
        if columna in preparadas:
            sin_valor = preparadas.index[preparadas[columna].isna()]
            problemas.extend(
                ProblemaFila(int(f), f"Falta '{columna}', que la preparación exige (se eliminaban esas filas).")
                for f in sin_valor
            )
            preparadas = preparadas.drop(index=sin_valor)
    columnas = [c.nombre for c in receta.columnas if c.nombre != receta.objetivo]
    preparadas = _aplicar_parametros(preparadas, receta.objetivo, receta.parametros_aprendidos)
    return NuevosPreparados(
        preparadas.reindex(columns=columnas), sorted(problemas, key=lambda p: p.fila), ignoradas
    )


def _ordenar_columnas(datos: pd.DataFrame, objetivo: str, fecha: str | None) -> pd.DataFrame:
    """Quita la columna de fecha de la separación temporal y deja el objetivo al final."""
    columnas = [c for c in datos.columns if c not in (objetivo, fecha)]
    return datos[[*columnas, objetivo]]


def _datos_preparados(datos: pd.DataFrame, receta: Receta) -> DatosPreparados:
    parametros = receta.parametros_aprendidos
    return DatosPreparados(
        train=_aplicar_parametros(datos.loc[receta.indices_train], receta.objetivo, parametros),
        test=_aplicar_parametros(datos.loc[receta.indices_test], receta.objetivo, parametros),
        objetivo=receta.objetivo,
        tipo_objetivo=receta.tipo_objetivo,
        columnas=receta.columnas,
        receta=receta,
    )


# --- Resumen para la interfaz ------------------------------------------------------------------

# Con más columnas finales PC se vuelve lento; por encima del máximo no se ejecuta.
COLUMNAS_PC_LENTO = 30
COLUMNAS_PC_MAXIMO = 50


@dataclass(frozen=True)
class LimiteColumnas:
    """Evaluación del número de columnas finales para PC.

    ``estado``: ``"ok"``, ``"lento"`` (más de ``COLUMNAS_PC_LENTO``) o ``"bloqueado"``
    (más de ``COLUMNAS_PC_MAXIMO``: la interfaz y el servidor no continúan; la
    terminal solo advierte).
    """

    estado: str
    columnas: int
    mensaje: str | None = None
    columnas_one_hot: dict[str, int] = field(default_factory=dict)


def evaluar_columnas(columnas: list[MetadatosColumna]) -> LimiteColumnas:
    """Evalúa las columnas finales (incluido el objetivo) de una preparación."""
    total = len(columnas)
    one_hot: dict[str, int] = {}
    for metadatos in columnas:
        if metadatos.tipo_final == ONE_HOT:
            origen = metadatos.nombre.split("=", 1)[0]
            one_hot[origen] = one_hot.get(origen, 0) + 1
    if total <= COLUMNAS_PC_LENTO:
        return LimiteColumnas("ok", total, None, one_hot)
    detalle = ""
    if one_hot:
        detalle = " Las codificaciones one-hot aportan " + ", ".join(
            f"{n} columnas ({origen})" for origen, n in sorted(one_hot.items(), key=lambda p: -p[1])
        ) + "."
    consejo = (
        " Vuelva a Decisiones para agrupar o excluir variables categóricas: con one-hot, "
        "cada categoría es una columna más."
    )
    if total > COLUMNAS_PC_MAXIMO:
        mensaje = (
            f"Hay {total} columnas finales y el máximo para PC es {COLUMNAS_PC_MAXIMO}: el análisis "
            "no terminaría en un tiempo razonable." + detalle + consejo
        )
        return LimiteColumnas("bloqueado", total, mensaje, one_hot)
    mensaje = (
        f"Hay {total} columnas finales (más de {COLUMNAS_PC_LENTO}): PC será lento." + detalle + consejo
    )
    return LimiteColumnas("lento", total, mensaje, one_hot)


def distribucion_objetivo(serie: pd.Series, tipo_objetivo: str | None) -> dict[str, Any]:
    """Distribución del objetivo en un conjunto: conteos por clase o, si es
    continuo, un resumen numérico."""
    presentes = serie.dropna()
    if tipo_objetivo == "continuo":
        return {
            "tipo": "continuo",
            "filas": int(len(serie)),
            "media": float(presentes.mean()) if len(presentes) else None,
            "mediana": float(presentes.median()) if len(presentes) else None,
            "minimo": float(presentes.min()) if len(presentes) else None,
            "maximo": float(presentes.max()) if len(presentes) else None,
        }
    conteos = presentes.value_counts().sort_index()
    return {
        "tipo": "clases",
        "filas": int(len(serie)),
        "clases": [
            {
                "valor": _nativo(valor),
                "conteo": int(n),
                "porcentaje": round(100 * int(n) / max(len(presentes), 1), 2),
            }
            for valor, n in conteos.items()
        ],
    }

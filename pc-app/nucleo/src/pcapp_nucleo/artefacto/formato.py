"""Formato del artefacto ``.scotty``: esquemas y validación de ``manifest.json``,
``esquema_entrada.json`` y ``controles.json``.

Un artefacto es un ``.zip`` con extensión ``.scotty`` que contiene todo lo aprendido por Scotty PC
para predecir, prescribir y calcular contrafactuales sin reentrenar nada:

========================  =====================================================================
``manifest.json``         identidad, versiones, objetivo, μ, huellas y sha256 de cada archivo
``receta.json``           receta de preparación del proyecto
``modelo_causal.json``    modelo causal por parámetros (mecanismos, GAM incluido)
``prescripcion.json``     configuración, modelo de referencia, calibración de μ y semilla
``train.parquet``         train preparado (índice y dtypes), para la huella y la evidencia
``predicciones_train.parquet``  (formato 2) eta de cada mecanismo sobre train: lo que resume la huella
``esquema_entrada.json``  lo que debe traer una fila nueva, en unidades originales
``controles.json``        variables prescriptivas y sus restricciones, para la interfaz
``evaluacion.json``       métricas del modelo causal y última evaluación del prescriptor
``golden.json``           casos de verificación (resultados esperados)
========================  =====================================================================

Nada se serializa con pickle: solo JSON y Parquet.

Los tres esquemas de este módulo se leen con ``*_desde_diccionario`` (que valida y acumula todos
los problemas en ``ErrorFormatoArtefacto.problemas``) y se escriben con ``a_diccionario``.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pcapp_nucleo.utilidades import a_diccionario_serializable

FORMATO = "scotty-artefacto"
VERSION_FORMATO = 2
# Formatos que ``cargar_artefacto`` sabe leer. El 1 no trae ``predicciones_train.parquet`` y se carga con la
# comprobación estricta (huella bit a bit y todas las librerías idénticas).
VERSIONES_SOPORTADAS = (1, 2)
EXTENSION = ".scotty"

MANIFEST = "manifest.json"
RECETA = "receta.json"
MODELO_CAUSAL = "modelo_causal.json"
PRESCRIPCION = "prescripcion.json"
TRAIN = "train.parquet"
ESQUEMA_ENTRADA = "esquema_entrada.json"
CONTROLES = "controles.json"
EVALUACION = "evaluacion.json"
PREDICCIONES_TRAIN = "predicciones_train.parquet"
GOLDEN = "golden.json"
# Archivos cuyo sha256 queda en el manifest (todos menos el propio manifest).
ARCHIVOS_CONTENIDO = (
    RECETA, MODELO_CAUSAL, PRESCRIPCION, TRAIN, PREDICCIONES_TRAIN, ESQUEMA_ENTRADA, CONTROLES, EVALUACION, GOLDEN,
)
ARCHIVOS_CONTENIDO_V1 = tuple(n for n in ARCHIVOS_CONTENIDO if n != PREDICCIONES_TRAIN)
# Librerías cuya versión debe coincidir exactamente al cargar un artefacto (los parámetros del modelo dependen de
# ellas). Las demás versiones del manifest (python, pandas, pyarrow, networkx) solo avisan si difieren.
LIBRERIAS_ESTRICTAS = ("pygam", "scikit-learn", "numpy", "scipy")


def archivos_de_version(version: int) -> tuple[str, ...]:
    """Archivos de contenido (con sha256 en el manifest) de un artefacto del formato ``version``."""
    return ARCHIVOS_CONTENIDO_V1 if version < 2 else ARCHIVOS_CONTENIDO

# Tipos de variable (esquema de entrada y controles).
CONTINUA, BINARIA, ORDINAL, CATEGORICA = "continua", "binaria", "ordinal", "categorica"
TIPOS_VARIABLE = (CONTINUA, BINARIA, ORDINAL, CATEGORICA)
# Roles de una columna original en el modelo. ``id`` queda reservado a columnas que la web use
# para identificar filas: la exportación actual no lo genera.
ANCESTRO_OBJETIVO, PRESCRIPTIVA, FUERA_DEL_SUBGRAFO, ID = "ancestro_objetivo", "prescriptiva", "fuera_del_subgrafo", "id"
ROLES = (ANCESTRO_OBJETIVO, PRESCRIPTIVA, FUERA_DEL_SUBGRAFO, ID)
# Tratamiento de un faltante al preparar una fila nueva.
IMPUTACIONES = ("eliminar_filas", "mediana", "multivariada", "ninguna")
DIRECCIONES = ("subir", "bajar", "ambas")
MU_ORIGENES = ("automatico", "manual")
TIPOS_OBJETIVO = ("binario", "continuo")
MEDIDAS = ("probabilidad", "valor")
DIRECCIONES_OBJETIVO = ("subir", "bajar")

_SHA256 = re.compile(r"[0-9a-f]{64}")
# Caracteres de control y de ancho cero que no deben verse en un nombre (tabuladores incluidos).
_INVISIBLES = re.compile("[\u0000-\u001f\u007f-\u009f​-‏ - ⁠﻿]")


# --- Utilidades comunes ------------------------------------------------------------------------


def json_canonico(valor: Any) -> bytes:
    """JSON canónico (claves ordenadas, sin espacios, UTF-8) para calcular huellas estables."""
    return json.dumps(
        a_diccionario_serializable(valor), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def version_instalada(paquete: str) -> str | None:
    """Versión instalada de ``paquete`` (``"python"`` es el intérprete), o ``None`` si no está instalado."""
    if paquete == "python":
        return platform.python_version()
    try:
        return importlib.metadata.version(paquete)
    except importlib.metadata.PackageNotFoundError:
        return None


def sha256_bytes(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def nombre_visible(nombre: str) -> str:
    """Nombre para mostrar: sin caracteres invisibles (tabuladores, ancho cero...) ni espacios sobrantes."""
    return " ".join(_INVISIBLES.sub(" ", nombre).split())


@dataclass(frozen=True)
class ProblemaFormato:
    campo: str
    mensaje: str


class ErrorFormatoArtefacto(ValueError):
    """Un archivo del artefacto no cumple el formato; ``problemas`` los lista todos."""

    def __init__(self, archivo: str, problemas: list[ProblemaFormato]) -> None:
        detalle = "; ".join(f"{p.campo}: {p.mensaje}" if p.campo else p.mensaje for p in problemas[:5])
        super().__init__(f"{archivo} no es válido: {detalle}" + (" (…)" if len(problemas) > 5 else ""))
        self.archivo = archivo
        self.problemas = problemas


class _Lector:
    """Lee campos de un diccionario acumulando todos los problemas (sin lanzar en el primero)."""

    def __init__(self, problemas: list[ProblemaFormato]) -> None:
        self.problemas = problemas

    def error(self, campo: str, mensaje: str) -> None:
        self.problemas.append(ProblemaFormato(campo, mensaje))

    def objeto(self, datos: Any, campo: str, permitidos: set[str]) -> dict[str, Any]:
        if not isinstance(datos, dict):
            self.error(campo, "Debe ser un objeto.")
            return {}
        for clave in sorted(set(datos) - permitidos):
            self.error(f"{campo}.{clave}" if campo else clave, "Campo desconocido.")
        return datos

    def campo(
        self, datos: dict[str, Any], clave: str, ruta: str, tipo: str, *, nulo: bool = False,
        opciones: tuple[Any, ...] | None = None, positivo: bool = False,
    ) -> Any:
        campo = f"{ruta}.{clave}" if ruta else clave
        if clave not in datos:
            if not nulo:
                self.error(campo, "Falta el campo.")
            return None
        valor = datos[clave]
        if valor is None:
            if not nulo:
                self.error(campo, "No puede ser nulo.")
            return None
        if not _es_de_tipo(valor, tipo):
            self.error(campo, f"Debe ser {_NOMBRES_TIPO[tipo]}.")
            return None
        if tipo == "sha256" and not _SHA256.fullmatch(valor):
            self.error(campo, "Debe ser un sha256 en hexadecimal minúscula (64 caracteres).")
            return None
        if tipo == "fecha":
            try:
                datetime.fromisoformat(valor)
            except ValueError:
                self.error(campo, "Debe ser una fecha ISO-8601.")
                return None
        if tipo == "texto" and not valor.strip():
            self.error(campo, "No puede estar vacío.")
            return None
        if opciones is not None and valor not in opciones:
            self.error(campo, f"Debe ser uno de: {', '.join(map(str, opciones))}.")
            return None
        if positivo and valor <= 0:
            self.error(campo, "Debe ser mayor que 0.")
            return None
        return valor

    def lista_de(self, valores: Any, campo: str, tipo: str) -> list[Any]:
        if not all(_es_de_tipo(v, tipo) for v in valores):
            self.error(campo, f"Todos los elementos deben ser {_NOMBRES_TIPO[tipo]}.")
            return []
        return list(valores)


_NOMBRES_TIPO = {
    "texto": "un texto", "bool": "verdadero o falso", "entero": "un entero", "numero": "un número finito",
    "lista": "una lista", "dict": "un objeto", "sha256": "un sha256", "fecha": "una fecha", "cualquiera": "un valor",
}


def _es_de_tipo(valor: Any, tipo: str) -> bool:
    if tipo in ("texto", "sha256", "fecha"):
        return isinstance(valor, str)
    if tipo == "bool":
        return isinstance(valor, bool)
    if tipo == "entero":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo == "numero":
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    if tipo == "lista":
        return isinstance(valor, list)
    if tipo == "dict":
        return isinstance(valor, dict)
    return True


def _lanzar(archivo: str, problemas: list[ProblemaFormato]) -> None:
    if problemas:
        raise ErrorFormatoArtefacto(archivo, problemas)


# --- manifest.json ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ProyectoManifest:
    id: str
    nombre: str
    archivo_original: str
    sha256_dataset: str


@dataclass(frozen=True)
class ObjetivoManifest:
    """``clase_positiva``: valores originales de la clase 1 (``None`` si no estaba codificada);
    ``clase_objetivo``: la clase (0 o 1) cuya probabilidad es ``deseado``."""

    columna: str
    tipo: str
    clase_positiva: list[Any] | None
    clase_objetivo: int | None
    medida: str
    direccion: str
    deseado: float
    umbral_decision: float | None


@dataclass(frozen=True)
class PrescripcionManifest:
    mu: float
    mu_origen: str
    optimizador: str


@dataclass(frozen=True)
class ModeloManifest:
    huella: str
    train_sha256: str
    version_resultado_pc: int | None


@dataclass(frozen=True)
class ResumenEvaluacion:
    """Métricas de test del modelo causal y tasa de éxito de la última evaluación del prescriptor.

    Binario: exactitud balanceada, AUC y Brier; continuo: R² y RMSE. Lo que no existe es ``None``.
    """

    exactitud_balanceada_test: float | None = None
    auc_test: float | None = None
    brier_test: float | None = None
    r2_test: float | None = None
    rmse_test: float | None = None
    tasa_exito_prescriptor: float | None = None
    filas_evaluadas: int | None = None


@dataclass(frozen=True)
class AdvertenciaManifest:
    codigo: str
    mensaje: str


@dataclass(frozen=True)
class Manifest:
    formato: str
    version_formato: int
    creado_en: str
    version_nucleo: str
    versiones_librerias: dict[str, str]
    proyecto: ProyectoManifest
    objetivo: ObjetivoManifest
    prescripcion: PrescripcionManifest
    modelo: ModeloManifest
    variables_prescriptivas: list[str]
    supuestos_confirmados: dict[str, str]
    resumen_evaluacion: ResumenEvaluacion
    aviso: str
    advertencias: list[AdvertenciaManifest] = field(default_factory=list)
    archivos: dict[str, str] = field(default_factory=dict)
    golden_sha256: str | None = None

    def a_diccionario(self) -> dict[str, Any]:
        return a_diccionario_serializable(self)


_CAMPOS_MANIFEST = {
    "formato", "version_formato", "creado_en", "version_nucleo", "versiones_librerias", "proyecto", "objetivo",
    "prescripcion", "modelo", "variables_prescriptivas", "supuestos_confirmados", "resumen_evaluacion", "aviso",
    "advertencias", "archivos", "golden_sha256",
}


def manifest_desde_diccionario(datos: Any) -> Manifest:
    """Raises: ErrorFormatoArtefacto con todos los problemas del manifest."""
    problemas: list[ProblemaFormato] = []
    v = _Lector(problemas)
    d = v.objeto(datos, "", _CAMPOS_MANIFEST)
    formato = v.campo(d, "formato", "", "texto")
    if formato is not None and formato != FORMATO:
        v.error("formato", f"Debe ser '{FORMATO}'.")
    version = v.campo(d, "version_formato", "", "entero")
    if version is not None and version not in VERSIONES_SOPORTADAS:
        v.error("version_formato", f"Esta versión solo lee los formatos {', '.join(map(str, VERSIONES_SOPORTADAS))} (el archivo es el {version}).")
    creado = v.campo(d, "creado_en", "", "fecha")
    version_nucleo = v.campo(d, "version_nucleo", "", "texto")
    libs = v.campo(d, "versiones_librerias", "", "dict") or {}
    for nombre, version_lib in libs.items():
        if not isinstance(version_lib, str) or not version_lib:
            v.error(f"versiones_librerias.{nombre}", "Debe ser un texto con la versión.")

    p = v.objeto(d.get("proyecto"), "proyecto", {"id", "nombre", "archivo_original", "sha256_dataset"})
    proyecto = ProyectoManifest(
        v.campo(p, "id", "proyecto", "texto"), v.campo(p, "nombre", "proyecto", "texto"),
        v.campo(p, "archivo_original", "proyecto", "texto"), v.campo(p, "sha256_dataset", "proyecto", "sha256"),
    )
    o = v.objeto(d.get("objetivo"), "objetivo", {
        "columna", "tipo", "clase_positiva", "clase_objetivo", "medida", "direccion", "deseado", "umbral_decision",
    })
    clase_positiva = v.campo(o, "clase_positiva", "objetivo", "lista", nulo=True)
    objetivo = ObjetivoManifest(
        v.campo(o, "columna", "objetivo", "texto"), v.campo(o, "tipo", "objetivo", "texto", opciones=TIPOS_OBJETIVO),
        clase_positiva, v.campo(o, "clase_objetivo", "objetivo", "entero", nulo=True, opciones=(0, 1)),
        v.campo(o, "medida", "objetivo", "texto", opciones=MEDIDAS),
        v.campo(o, "direccion", "objetivo", "texto", opciones=DIRECCIONES_OBJETIVO),
        v.campo(o, "deseado", "objetivo", "numero"),
        v.campo(o, "umbral_decision", "objetivo", "numero", nulo=True),
    )
    if objetivo.tipo == "binario" and objetivo.medida == "valor":
        v.error("objetivo.medida", "Un objetivo binario se mide como 'probabilidad'.")
    if objetivo.tipo == "continuo" and objetivo.medida == "probabilidad":
        v.error("objetivo.medida", "Un objetivo continuo se mide como 'valor'.")

    pr = v.objeto(d.get("prescripcion"), "prescripcion", {"mu", "mu_origen", "optimizador"})
    prescripcion = PrescripcionManifest(
        v.campo(pr, "mu", "prescripcion", "numero"),
        v.campo(pr, "mu_origen", "prescripcion", "texto", opciones=MU_ORIGENES),
        v.campo(pr, "optimizador", "prescripcion", "texto"),
    )
    if prescripcion.mu is not None and prescripcion.mu < 0:
        v.error("prescripcion.mu", "μ no puede ser negativo.")

    m = v.objeto(d.get("modelo"), "modelo", {"huella", "train_sha256", "version_resultado_pc"})
    modelo = ModeloManifest(
        v.campo(m, "huella", "modelo", "sha256"), v.campo(m, "train_sha256", "modelo", "sha256"),
        v.campo(m, "version_resultado_pc", "modelo", "entero", nulo=True),
    )

    variables = v.campo(d, "variables_prescriptivas", "", "lista") or []
    variables = v.lista_de(variables, "variables_prescriptivas", "texto")
    supuestos = v.campo(d, "supuestos_confirmados", "", "dict") or {}
    for nombre, fecha in supuestos.items():
        if not isinstance(fecha, str):
            v.error(f"supuestos_confirmados.{nombre}", "Debe ser la fecha de confirmación.")
    faltan = [x for x in variables if x not in supuestos]
    if faltan:
        v.error("supuestos_confirmados", f"Faltan los supuestos confirmados de: {', '.join(faltan)}.")

    campos_resumen = {f for f in ResumenEvaluacion.__dataclass_fields__}
    r = v.objeto(d.get("resumen_evaluacion"), "resumen_evaluacion", campos_resumen)
    resumen = ResumenEvaluacion(**{
        nombre: v.campo(r, nombre, "resumen_evaluacion", "entero" if nombre == "filas_evaluadas" else "numero", nulo=True)
        for nombre in campos_resumen
    })
    aviso = v.campo(d, "aviso", "", "texto")

    advertencias = []
    for i, a in enumerate(v.campo(d, "advertencias", "", "lista", nulo=True) or []):
        ruta = f"advertencias.{i}"
        a = v.objeto(a, ruta, {"codigo", "mensaje"})
        advertencias.append(AdvertenciaManifest(v.campo(a, "codigo", ruta, "texto"), v.campo(a, "mensaje", ruta, "texto")))

    archivos = v.campo(d, "archivos", "", "dict") or {}
    for nombre, huella in archivos.items():
        if nombre not in ARCHIVOS_CONTENIDO:
            v.error(f"archivos.{nombre}", "Archivo desconocido en el artefacto.")
        if not isinstance(huella, str) or not _SHA256.fullmatch(huella):
            v.error(f"archivos.{nombre}", "Debe ser un sha256 en hexadecimal minúscula (64 caracteres).")
    golden = v.campo(d, "golden_sha256", "", "sha256", nulo=True)

    _lanzar(MANIFEST, problemas)
    return Manifest(
        formato, version, creado, version_nucleo, dict(libs), proyecto, objetivo, prescripcion, modelo, variables,
        dict(supuestos), resumen, aviso, advertencias, dict(archivos), golden,
    )


# --- esquema_entrada.json ----------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnaEntrada:
    """Una columna original que debe traer una fila nueva (nombre EXACTO, sin limpiar).

    ``minimo`` y ``maximo`` (solo continuas) son los observados en train en las unidades del
    dataset tras la conversión de unidades de la receta (``conversion`` la describe si existe).
    ``admite_faltantes``/``imputacion`` dicen qué ocurre con una celda vacía.
    """

    nombre: str
    nombre_visible: str
    tipo: str
    categorias: list[Any] | None
    minimo: float | None
    maximo: float | None
    rol: str
    admite_faltantes: bool
    imputacion: str
    detalle_imputacion: str
    conversion: str | None = None


@dataclass(frozen=True)
class EsquemaEntrada:
    columnas: list[ColumnaEntrada]
    version_formato: int = VERSION_FORMATO

    def a_diccionario(self) -> dict[str, Any]:
        return a_diccionario_serializable(self)

    def columna(self, nombre: str) -> ColumnaEntrada | None:
        return next((c for c in self.columnas if c.nombre == nombre), None)


def _validar_dominio(v: _Lector, ruta: str, tipo: str | None, categorias: list[Any] | None,
                     minimo: float | None, maximo: float | None) -> None:
    if tipo is None:
        return
    if tipo == CONTINUA:
        if categorias is not None:
            v.error(f"{ruta}.categorias", "Una variable continua no tiene categorías.")
        if minimo is None or maximo is None:
            v.error(f"{ruta}.minimo", "Una variable continua necesita mínimo y máximo.")
        elif minimo > maximo:
            v.error(f"{ruta}.minimo", "El mínimo es mayor que el máximo.")
        return
    if not categorias:
        v.error(f"{ruta}.categorias", f"Una variable {tipo} necesita sus categorías.")
    elif len({json.dumps(c, sort_keys=True) for c in categorias}) != len(categorias):
        v.error(f"{ruta}.categorias", "Hay categorías repetidas.")
    elif tipo == BINARIA and len(categorias) != 2:
        v.error(f"{ruta}.categorias", "Una variable binaria tiene exactamente 2 valores.")
    if minimo is not None or maximo is not None:
        v.error(f"{ruta}.minimo", "Solo las variables continuas tienen mínimo y máximo.")


def esquema_entrada_desde_diccionario(datos: Any) -> EsquemaEntrada:
    """Raises: ErrorFormatoArtefacto con todos los problemas del esquema."""
    problemas: list[ProblemaFormato] = []
    v = _Lector(problemas)
    d = v.objeto(datos, "", {"version_formato", "columnas"})
    version = v.campo(d, "version_formato", "", "entero")
    if version is not None and version not in VERSIONES_SOPORTADAS:
        v.error("version_formato", f"Esta versión solo lee los formatos {', '.join(map(str, VERSIONES_SOPORTADAS))}.")
    columnas: list[ColumnaEntrada] = []
    nombres: set[str] = set()
    campos = {f for f in ColumnaEntrada.__dataclass_fields__}
    lista = v.campo(d, "columnas", "", "lista")
    for i, c in enumerate(lista or []):
        ruta = f"columnas.{i}"
        c = v.objeto(c, ruta, campos)
        nombre = v.campo(c, "nombre", ruta, "texto")
        if nombre is not None:
            if nombre in nombres:
                v.error(f"{ruta}.nombre", f"La columna '{nombre}' está repetida.")
            nombres.add(nombre)
        visible = v.campo(c, "nombre_visible", ruta, "texto")
        if visible is not None and visible != nombre_visible(visible):
            v.error(f"{ruta}.nombre_visible", "No debe llevar caracteres invisibles ni espacios sobrantes.")
        tipo = v.campo(c, "tipo", ruta, "texto", opciones=TIPOS_VARIABLE)
        categorias = v.campo(c, "categorias", ruta, "lista", nulo=True)
        minimo = v.campo(c, "minimo", ruta, "numero", nulo=True)
        maximo = v.campo(c, "maximo", ruta, "numero", nulo=True)
        _validar_dominio(v, ruta, tipo, categorias, minimo, maximo)
        rol = v.campo(c, "rol", ruta, "texto", opciones=ROLES)
        admite = v.campo(c, "admite_faltantes", ruta, "bool")
        imputacion = v.campo(c, "imputacion", ruta, "texto", opciones=IMPUTACIONES)
        if admite is not None and imputacion is not None and admite == (imputacion == "eliminar_filas"):
            v.error(f"{ruta}.admite_faltantes", "Debe ser falso exactamente cuando la imputación es 'eliminar_filas'.")
        detalle = v.campo(c, "detalle_imputacion", ruta, "texto")
        conversion = v.campo(c, "conversion", ruta, "texto", nulo=True)
        columnas.append(ColumnaEntrada(
            nombre, visible, tipo, categorias, minimo, maximo, rol, admite, imputacion, detalle, conversion,
        ))
    if lista is not None and not lista:
        v.error("columnas", "El esquema no tiene ninguna columna.")
    _lanzar(ESQUEMA_ENTRADA, problemas)
    return EsquemaEntrada(columnas, version)


# --- controles.json ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlVariable:
    """Una variable prescriptiva tal como la ve la interfaz (unidades originales).

    ``minimo``/``maximo`` son los límites absolutos permitidos al prescribir (continuas y ordinales,
    estas últimas sobre su código); ``cambio_maximo``, el cambio máximo respecto al valor actual
    (``None`` = sin límite);
    ``estados_permitidos``, los valores a los que se puede pasar (no continuas); ``paso`` es 1 si la
    variable original solo toma enteros en train y ``None`` en otro caso.
    """

    variable: str
    nombre_visible: str
    tipo: str
    direccion: str
    permitida: bool
    minimo: float | None
    maximo: float | None
    cambio_maximo: float | None
    costo: float
    estados_permitidos: list[Any] | None
    paso: int | None


@dataclass(frozen=True)
class Controles:
    controles: list[ControlVariable]
    version_formato: int = VERSION_FORMATO

    def a_diccionario(self) -> dict[str, Any]:
        return a_diccionario_serializable(self)

    def control(self, variable: str) -> ControlVariable | None:
        return next((c for c in self.controles if c.variable == variable), None)


def controles_desde_diccionario(datos: Any) -> Controles:
    """Raises: ErrorFormatoArtefacto con todos los problemas de los controles."""
    problemas: list[ProblemaFormato] = []
    v = _Lector(problemas)
    d = v.objeto(datos, "", {"version_formato", "controles"})
    version = v.campo(d, "version_formato", "", "entero")
    if version is not None and version not in VERSIONES_SOPORTADAS:
        v.error("version_formato", f"Esta versión solo lee los formatos {', '.join(map(str, VERSIONES_SOPORTADAS))}.")
    controles: list[ControlVariable] = []
    nombres: set[str] = set()
    campos = {f for f in ControlVariable.__dataclass_fields__}
    for i, c in enumerate(v.campo(d, "controles", "", "lista") or []):
        ruta = f"controles.{i}"
        c = v.objeto(c, ruta, campos)
        variable = v.campo(c, "variable", ruta, "texto")
        if variable is not None:
            if variable in nombres:
                v.error(f"{ruta}.variable", f"La variable '{variable}' está repetida.")
            nombres.add(variable)
        visible = v.campo(c, "nombre_visible", ruta, "texto")
        if visible is not None and visible != nombre_visible(visible):
            v.error(f"{ruta}.nombre_visible", "No debe llevar caracteres invisibles ni espacios sobrantes.")
        tipo = v.campo(c, "tipo", ruta, "texto", opciones=TIPOS_VARIABLE)
        direccion = v.campo(c, "direccion", ruta, "texto", opciones=DIRECCIONES)
        permitida = v.campo(c, "permitida", ruta, "bool")
        minimo = v.campo(c, "minimo", ruta, "numero", nulo=True)
        maximo = v.campo(c, "maximo", ruta, "numero", nulo=True)
        cambio = v.campo(c, "cambio_maximo", ruta, "numero", nulo=True, positivo=True)
        costo = v.campo(c, "costo", ruta, "numero", positivo=True)
        estados = v.campo(c, "estados_permitidos", ruta, "lista", nulo=True)
        paso = v.campo(c, "paso", ruta, "entero", nulo=True, positivo=True)
        if tipo == CONTINUA:
            if estados is not None:
                v.error(f"{ruta}.estados_permitidos", "Una variable continua no tiene estados.")
            if minimo is not None and maximo is not None and minimo > maximo:
                v.error(f"{ruta}.minimo", "El mínimo es mayor que el máximo.")
        elif tipo is not None:
            if not estados:
                v.error(f"{ruta}.estados_permitidos", f"Una variable {tipo} necesita sus estados permitidos.")
            if paso is not None:
                v.error(f"{ruta}.paso", "Solo las variables continuas tienen paso.")
            if tipo != ORDINAL and (minimo is not None or maximo is not None or cambio is not None):
                v.error(f"{ruta}.minimo", "Solo las continuas y las ordinales tienen mínimo, máximo y cambio máximo.")
        controles.append(ControlVariable(
            variable, visible, tipo, direccion, permitida, minimo, maximo, cambio, costo, estados, paso,
        ))
    _lanzar(CONTROLES, problemas)
    return Controles(controles, version)

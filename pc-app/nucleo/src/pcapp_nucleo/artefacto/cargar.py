"""Carga de un artefacto ``.scotty`` y su API de uso (predecir, prescribir, contrafactual, lote).

``cargar_artefacto`` abre el zip en memoria, comprueba formato, sha256 de cada archivo y versiones
de librerías, reconstruye el modelo causal con comprobación de huella y construye una sola vez la
configuración, la referencia y el índice de vecinos. No necesita carpeta de proyecto, SQLite ni el
dataset original.

Todo lo que entra y sale de ``Artefacto`` está en unidades ORIGINALES (las del dataset). Un caso se
arma siempre por el mismo camino: ``preparar_nuevos`` → ``caso_desde_test`` → fila preparada sin el
objetivo para el modelo de referencia, y la semilla del optimizador depende solo de los valores del
caso (no de su posición en el archivo): la misma fila da el mismo resultado venga donde venga.
"""

from __future__ import annotations

import gc
import io
import json
import zipfile
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo import __version__
from pcapp_nucleo.artefacto import formato as f
from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.causal import (
    ErrorContrafactual, ErrorModeloCausal, Intervencion, ModeloCausal, caso_desde_test, contrafactual,
    descripcion_variables, modelo_desde_diccionario, sha256_train,
)
from pcapp_nucleo.causal.aplicabilidad import BLOQUEANTE
from pcapp_nucleo.causal.contrafactuales import AvisoContrafactual, Caso, _en_rango, contrafactual_preparado
from pcapp_nucleo.causal.modelo import huella_de_predicciones, predicciones_train
from pcapp_nucleo.causal.unidades import GRUPO
from pcapp_nucleo.preparacion import (
    ErrorPreparacion, NuevosPreparados, Receta, _mismo_valor, preparar_nuevos, receta_desde_diccionario,
)
from pcapp_nucleo.prescripcion import (
    AUTOMATICO, ConfiguracionPrescripcion, ErrorConfiguracionPrescripcion, LoteCancelado, ModeloReferencia, completar,
    configuracion_desde_diccionario, evaluar_prescribibilidad, prescribir_caso, referencia_desde_diccionario,
    variables_prescriptivas,
)
from pcapp_nucleo.prescripcion.evidencia import IndiceVecinos, construir_indice
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion
from pcapp_nucleo.utilidades import a_diccionario_serializable

BLOQUE_LOTE = 20
TAMANO_MAXIMO = 1 << 30  # 1 GiB descomprimido: un artefacto real pesa megas
# Tolerancia con la que un artefacto de formato 2 se carga como "equivalente" cuando la huella exacta no coincide
# (BLAS/LAPACK distintos entre plataformas dan diferencias de 1 ULP, ~1e-16 relativo).
RTOL_CARGA = 1e-10
ATOL_CARGA = 1e-12
CARGA_EXACTA, CARGA_EQUIVALENTE = "exacta", "equivalente"


class ErrorArtefacto(Exception):
    """El artefacto no se puede cargar. ``codigo``: FORMATO, INTEGRIDAD, VERSIONES o MODELO."""

    def __init__(self, mensaje: str, codigo: str = "FORMATO") -> None:
        super().__init__(mensaje)
        self.codigo = codigo


class ErrorSolicitud(ValueError):
    """La entrada (una fila, unas intervenciones) no es válida; ``campo`` y ``problemas`` dicen cuál."""

    def __init__(self, mensaje: str, campo: str | None = None, problemas: list[dict[str, Any]] | None = None) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.problemas = problemas or []


# --- Informe de validación ---------------------------------------------------------------------------------


@dataclass
class ProblemaEntrada:
    """``fila``: posición en el archivo (desde 0) o ``None`` si afecta a todo el archivo."""

    fila: int | None
    columna: str | None
    tipo: str  # columna_faltante | categoria_no_vista | no_numerico | no_preparable
    mensaje: str


@dataclass
class InformeValidacion:
    filas: int
    filas_preparables: int
    columnas_faltantes: list[str]
    columnas_ignoradas: list[str]
    problemas: list[ProblemaEntrada] = field(default_factory=list)
    categorias_no_vistas: dict[str, list[Any]] = field(default_factory=dict)
    fuera_de_rango: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def correcto(self) -> bool:
        """Sin columnas faltantes y todas las filas preparables (salir del rango solo avisa)."""
        return not self.columnas_faltantes and not self.problemas

    def a_diccionario(self) -> dict[str, Any]:
        return {**a_diccionario_serializable(self), "correcto": self.correcto}


@dataclass
class BloqueLote:
    resultados: list[dict[str, Any]]  # {"fila": posición, "prescripcion": {...}}
    no_preparadas: list[ProblemaEntrada]


@dataclass
class ResultadoLote:
    filas: int
    resultados: list[dict[str, Any]]
    no_preparadas: list[ProblemaEntrada]

    def a_diccionario(self) -> dict[str, Any]:
        return a_diccionario_serializable(self)


@dataclass
class DiferenciaMecanismo:
    """Diferencia entre las predicciones de train recalculadas y las guardadas en el artefacto, de un mecanismo."""

    variable: str
    filas: int
    filas_distintas: int  # difieren en algún bit
    filas_fuera_de_tolerancia: int
    diferencia_maxima_absoluta: float
    diferencia_maxima_relativa: float  # |a − b| / |b| sobre las filas con b ≠ 0


@dataclass
class InformeCarga:
    """Cómo se reprodujo el modelo causal al cargar: ``exacta`` (la huella sha256 coincide, o formato 1) o
    ``equivalente`` (la huella difiere pero las predicciones están dentro de ``rtol``/``atol``)."""

    tipo: str
    rtol: float
    atol: float
    mecanismos: list[DiferenciaMecanismo] = field(default_factory=list)  # vacío si la carga es exacta

    @property
    def exacta(self) -> bool:
        return self.tipo == CARGA_EXACTA

    def a_diccionario(self) -> dict[str, Any]:
        return {**a_diccionario_serializable(self), "exacta": self.exacta}


# --- Lectura del zip ---------------------------------------------------------------------------------------------


def _leer_zip(origen: str | Path | bytes) -> tuple[bytes, dict[str, bytes]]:
    datos = bytes(origen) if isinstance(origen, (bytes, bytearray, memoryview)) else Path(origen).expanduser().read_bytes()
    try:
        zip_ = zipfile.ZipFile(io.BytesIO(datos))
    except zipfile.BadZipFile as error:
        raise ErrorArtefacto("El archivo no es un artefacto .scotty (no es un zip válido).") from error
    with zip_:
        info = zip_.infolist()
        nombres = [i.filename for i in info]
        if len(set(nombres)) != len(nombres):
            raise ErrorArtefacto("El artefacto tiene archivos repetidos.")
        desconocidos = [n for n in nombres if n != f.MANIFEST and n not in f.ARCHIVOS_CONTENIDO]
        if desconocidos:
            raise ErrorArtefacto(f"El artefacto trae archivos desconocidos: {', '.join(desconocidos)}.")
        if sum(i.file_size for i in info) > TAMANO_MAXIMO:
            raise ErrorArtefacto("El artefacto descomprimido es demasiado grande.")
        try:
            return datos, {i.filename: zip_.read(i) for i in info}
        except (zipfile.BadZipFile, OSError, RuntimeError) as error:
            raise ErrorArtefacto(f"El artefacto está dañado: {error}", "INTEGRIDAD") from error


def _json(nombre: str, contenido: bytes) -> Any:
    try:
        return json.loads(contenido.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ErrorArtefacto(f"{nombre} no es un JSON válido: {error}") from error


def _envolver(funcion: Callable[[Any], Any], datos: Any) -> Any:
    try:
        return funcion(datos)
    except f.ErrorFormatoArtefacto as error:
        raise ErrorArtefacto(str(error)) from error


def mu_efectivo(prescripcion: dict[str, Any]) -> tuple[float | None, str]:
    """(μ, origen): el manual si lo hay; si es automático, el calibrado (o ``None`` sin calibrar)."""
    mu = prescripcion["configuracion"].get("mu", AUTOMATICO)
    if mu != AUTOMATICO:
        return float(mu), "manual"
    calibracion = prescripcion.get("calibracion")
    return (float(calibracion["mu"]) if calibracion else None), "automatico"


def _comprobar_versiones(manifest: f.Manifest) -> list[str]:
    """Error si no coincide exactamente alguna librería de las que dependen los mecanismos (formato 1: todas las
    del manifest; formato 2: pygam, scikit-learn, numpy y scipy); la diferencia en las demás solo avisa."""
    distintas, avisos = [], []
    for paquete, esperada in manifest.versiones_librerias.items():
        instalada = f.version_instalada(paquete)
        if instalada == esperada:
            continue
        texto = f"{paquete} {esperada} (instalada: {instalada or 'ninguna'})"
        if manifest.version_formato < 2 or paquete in f.LIBRERIAS_ESTRICTAS:
            distintas.append(texto)
        else:
            avisos.append(texto)
    if distintas:
        raise ErrorArtefacto(
            "Las librerías instaladas no coinciden con las del artefacto, y sus resultados dependen de ellas: "
            + ", ".join(distintas) + ". Instale exactamente esas versiones.",
            "VERSIONES",
        )
    resultado = []
    if avisos:
        resultado.append("Versiones distintas de las del artefacto (no afectan a los mecanismos): " + ", ".join(avisos) + ".")
    if manifest.version_nucleo != __version__:
        resultado.append(
            f"El artefacto se exportó con pcapp_nucleo {manifest.version_nucleo} y está instalada la {__version__}: "
            "verifique el golden (verificar_golden) antes de servirlo."
        )
    return resultado


def _leer_predicciones(contenido: bytes) -> pd.DataFrame:
    try:
        return pd.read_parquet(io.BytesIO(contenido), engine="pyarrow")
    except Exception as error:  # pyarrow lanza varios tipos
        raise ErrorArtefacto(f"{f.PREDICCIONES_TRAIN} no se puede leer: {error}", "INTEGRIDAD") from error


def _comparar(
    variable: str, recalculada: np.ndarray, guardada: np.ndarray, rtol: float, atol: float
) -> tuple[DiferenciaMecanismo, bool]:
    """Compara el eta recalculado con el guardado (referencia): (diferencias, dentro de la tolerancia)."""
    a, b = np.asarray(recalculada, dtype=float), np.asarray(guardada, dtype=float)
    iguales = (a == b) | (np.isnan(a) & np.isnan(b))
    fuera = ~np.isclose(a, b, rtol=rtol, atol=atol, equal_nan=True)
    finitas = np.isfinite(a) & np.isfinite(b)
    absoluta = np.abs(a - b)[finitas]
    base = np.abs(b)[finitas]
    relativa = absoluta[base > 0] / base[base > 0]
    diferencia = DiferenciaMecanismo(
        variable, len(a), int((~iguales).sum()), int(fuera.sum()),
        float(absoluta.max()) if len(absoluta) else 0.0, float(relativa.max()) if len(relativa) else 0.0,
    )
    return diferencia, not bool(fuera.any())


def _cargar_modelo_v2(
    modelo_json: dict[str, Any], train: pd.DataFrame, contenido_predicciones: bytes, rtol: float, atol: float
) -> tuple[ModeloCausal, InformeCarga]:
    """Modelo causal de un artefacto de formato 2: carga ``exacta`` si la huella sha256 de las predicciones sobre
    train coincide; si no, ``equivalente`` si las predicciones recalculadas están dentro de la tolerancia de las
    guardadas al exportar. Fuera de ella, ``ErrorArtefacto``."""
    try:
        modelo = ModeloCausal(modelo_json)
        recalculadas = predicciones_train(modelo, train)
    except ErrorModeloCausal as error:
        raise ErrorArtefacto(f"El modelo causal no se reproduce: {error}", "MODELO") from error
    if huella_de_predicciones(recalculadas) == modelo_json.get("huella"):
        return modelo, InformeCarga(CARGA_EXACTA, rtol, atol)
    guardadas = _leer_predicciones(contenido_predicciones)
    if list(guardadas.columns) != list(recalculadas) or len(guardadas) != len(train):
        raise ErrorArtefacto(
            f"{f.PREDICCIONES_TRAIN} no corresponde a los mecanismos o al train del artefacto.", "INTEGRIDAD"
        )
    referencia = {v: guardadas[v].to_numpy(dtype=float) for v in guardadas.columns}
    if huella_de_predicciones(referencia) != modelo_json.get("huella"):
        raise ErrorArtefacto(f"{f.PREDICCIONES_TRAIN} no corresponde a la huella del modelo causal.", "INTEGRIDAD")
    diferencias, fuera = [], []
    for variable, eta in recalculadas.items():
        diferencia, dentro = _comparar(variable, eta, referencia[variable], rtol, atol)
        diferencias.append(diferencia)
        if not dentro:
            fuera.append(diferencia)
    if fuera:
        detalle = "; ".join(
            f"{d.variable}: {d.filas_fuera_de_tolerancia} de {d.filas} filas (diferencia máxima {d.diferencia_maxima_absoluta:.3g}, "
            f"relativa {d.diferencia_maxima_relativa:.3g})" for d in fuera
        )
        raise ErrorArtefacto(
            f"El modelo causal no se reproduce: las predicciones sobre train superan la tolerancia (rtol={rtol:g}, atol={atol:g}) "
            f"en {detalle}.", "MODELO",
        )
    return modelo, InformeCarga(CARGA_EQUIVALENTE, rtol, atol, diferencias)


# --- Carga -----------------------------------------------------------------------------------------------------------


def cargar_artefacto(
    origen: str | Path | bytes, *, permitir_sin_golden: bool = False, rtol: float = RTOL_CARGA, atol: float = ATOL_CARGA,
) -> Artefacto:
    """Abre y verifica un artefacto. ``permitir_sin_golden`` solo lo usa la exportación (el artefacto aún no lo tiene).

    El modelo causal se carga ``exacta`` si la huella sha256 de sus predicciones sobre train coincide; en el formato 2,
    si no coincide, se carga ``equivalente`` cuando las predicciones recalculadas están dentro de ``rtol``/``atol``
    de las guardadas en el artefacto (``Artefacto.informe_carga`` lo registra). El formato 1 exige igualdad exacta.

    Raises:
        ErrorArtefacto: formato, integridad (sha256), versiones de librerías o modelo no reproducible.
    """
    datos, archivos = _leer_zip(origen)
    if f.MANIFEST not in archivos:
        raise ErrorArtefacto(f"Falta {f.MANIFEST}: no es un artefacto .scotty.")
    manifest = _envolver(f.manifest_desde_diccionario, _json(f.MANIFEST, archivos[f.MANIFEST]))
    archivos_formato = f.archivos_de_version(manifest.version_formato)
    sobran = [n for n in archivos if n != f.MANIFEST and n not in archivos_formato]
    if sobran:
        raise ErrorArtefacto(f"El artefacto trae archivos desconocidos: {', '.join(sobran)}.")
    esperados = [n for n in archivos_formato if not (n == f.GOLDEN and permitir_sin_golden)]
    faltan = [n for n in esperados if n not in archivos or n not in manifest.archivos]
    if faltan:
        raise ErrorArtefacto(f"Faltan archivos del artefacto: {', '.join(faltan)}.")
    for nombre, huella in manifest.archivos.items():
        if nombre not in archivos:
            if nombre == f.GOLDEN and permitir_sin_golden:
                continue
            raise ErrorArtefacto(f"Falta {nombre}.", "INTEGRIDAD")
        if f.sha256_bytes(archivos[nombre]) != huella:
            raise ErrorArtefacto(f"{nombre} no coincide con su sha256 del manifest: el artefacto está alterado o dañado.", "INTEGRIDAD")
    if f.GOLDEN in archivos and f.GOLDEN not in manifest.archivos:
        raise ErrorArtefacto(f"{f.GOLDEN} no figura en el manifest.", "INTEGRIDAD")
    if manifest.golden_sha256 is None and not permitir_sin_golden:
        raise ErrorArtefacto("El manifest no fija el sha256 del golden.", "INTEGRIDAD")
    avisos = _comprobar_versiones(manifest)

    receta_json = _json(f.RECETA, archivos[f.RECETA])
    modelo_json = _json(f.MODELO_CAUSAL, archivos[f.MODELO_CAUSAL])
    prescripcion = _json(f.PRESCRIPCION, archivos[f.PRESCRIPCION])
    esquema = _envolver(f.esquema_entrada_desde_diccionario, _json(f.ESQUEMA_ENTRADA, archivos[f.ESQUEMA_ENTRADA]))
    controles = _envolver(f.controles_desde_diccionario, _json(f.CONTROLES, archivos[f.CONTROLES]))
    evaluacion = _json(f.EVALUACION, archivos[f.EVALUACION])
    golden = _json(f.GOLDEN, archivos[f.GOLDEN]) if f.GOLDEN in archivos else None
    try:
        train = pd.read_parquet(io.BytesIO(archivos[f.TRAIN]), engine="pyarrow")
    except Exception as error:  # pyarrow lanza varios tipos
        raise ErrorArtefacto(f"{f.TRAIN} no se puede leer: {error}", "INTEGRIDAD") from error

    if not (manifest.modelo.huella == modelo_json.get("huella") == (prescripcion.get("modelo_causal") or {}).get("huella")):
        raise ErrorArtefacto("La huella del modelo causal no coincide entre el manifest, el modelo y la prescripción.", "INTEGRIDAD")
    if not (manifest.modelo.train_sha256 == modelo_json.get("train_sha256") == sha256_train(train)):
        raise ErrorArtefacto("El train del artefacto no es el usado para construir el modelo causal.", "INTEGRIDAD")
    if manifest.version_formato < 2:  # comprobación estricta: huella bit a bit
        informe_carga = InformeCarga(CARGA_EXACTA, rtol, atol)
        try:
            modelo = modelo_desde_diccionario(modelo_json, train)
        except ErrorModeloCausal as error:
            raise ErrorArtefacto(f"El modelo causal no se reproduce: {error}", "MODELO") from error
    else:
        modelo, informe_carga = _cargar_modelo_v2(modelo_json, train, archivos[f.PREDICCIONES_TRAIN], rtol, atol)
        if not informe_carga.exacta:
            peor = max(informe_carga.mecanismos, key=lambda d: d.diferencia_maxima_absoluta)
            avisos.append(
                "El modelo causal se cargó como equivalente, no exacto: las predicciones sobre train difieren de las del "
                f"equipo que exportó (diferencia máxima {peor.diferencia_maxima_absoluta:.3g} en '{peor.variable}'), dentro de "
                f"rtol={rtol:g} y atol={atol:g}. Detalle en informe_carga."
            )
    try:
        configuracion = completar(modelo, configuracion_desde_diccionario(prescripcion["configuracion"]))
        receta = receta_desde_diccionario(receta_json)
        referencia = referencia_desde_diccionario(prescripcion["referencia"])
    except (ErrorConfiguracionPrescripcion, ErrorPreparacion, KeyError, TypeError, ValueError) as error:
        raise ErrorArtefacto(f"La prescripción o la receta no son válidas: {error}", "MODELO") from error
    problemas = evaluar_prescribibilidad(modelo, configuracion)
    bloqueantes = [p.mensaje for p in problemas if p.severidad == BLOQUEANTE]
    if bloqueantes:
        raise ErrorArtefacto("El artefacto no es prescribible: " + " ".join(bloqueantes), "MODELO")
    mu, _ = mu_efectivo(prescripcion)
    if mu is None or mu != manifest.prescripcion.mu:
        raise ErrorArtefacto("El μ del manifest no coincide con el de la prescripción.", "INTEGRIDAD")
    prescriptivas = [
        v for v in variables_prescriptivas(modelo, configuracion.modificables).prescriptivas if configuracion.acciones[v].permitida
    ]
    if prescriptivas != manifest.variables_prescriptivas:
        raise ErrorArtefacto("Las variables prescriptivas del manifest no coinciden con la configuración.", "INTEGRIDAD")
    if manifest.objetivo.columna != modelo.objetivo:
        raise ErrorArtefacto("El objetivo del manifest no coincide con el del modelo.", "INTEGRIDAD")
    indice = construir_indice(modelo, train, configuracion)
    return Artefacto(
        manifest, esquema, controles, evaluacion, golden, receta, modelo, configuracion, referencia, mu, indice, train,
        avisos, datos, informe_carga,
    )


# --- Artefacto ----------------------------------------------------------------------------------------------------------


class Artefacto:
    """Artefacto cargado y verificado. Sus métodos no modifican su estado: se puede usar desde varios hilos."""

    def __init__(
        self, manifest: f.Manifest, esquema_entrada: f.EsquemaEntrada, controles: f.Controles, evaluacion: dict[str, Any],
        golden: dict[str, Any] | None, receta: Receta, modelo, configuracion: ConfiguracionPrescripcion, referencia: ModeloReferencia,
        mu: float, indice: IndiceVecinos | None, train: pd.DataFrame, avisos_carga: list[str], datos: bytes,
        informe_carga: InformeCarga,
    ) -> None:
        self.manifest, self.esquema_entrada, self.controles, self.evaluacion, self.golden = manifest, esquema_entrada, controles, evaluacion, golden
        self.receta, self.modelo, self.configuracion, self.referencia, self.mu = receta, modelo, configuracion, referencia, mu
        self.indice, self.train, self.avisos_carga = indice, train, avisos_carga
        self._datos = datos
        self.informe_carga = informe_carga
        self._centinelas = set(ConfiguracionValidacion().valores_centinela_faltantes)
        self._controles = {d["nombre"]: d for d in descripcion_variables(modelo)}
        self._tipicos = self._valores_tipicos()

    # --- Validación -----------------------------------------------------------------------------------------------

    def _es_centinela(self, valor: Any) -> bool:
        return isinstance(valor, str) and valor.strip() in self._centinelas

    def _columnas_faltantes(self, df: pd.DataFrame) -> list[str]:
        return [c.nombre for c in self.esquema_entrada.columnas if c.nombre not in df.columns]

    def _pista_columna(self, df: pd.DataFrame, faltantes: list[str]) -> str:
        """Si el archivo trae el nombre con otros espacios o invisibles, lo dice (el nombre debe ser exacto)."""
        parecidas = []
        visibles = {f.nombre_visible(str(c)): str(c) for c in df.columns}
        for falta in faltantes:
            otra = visibles.get(f.nombre_visible(falta))
            if otra is not None:
                parecidas.append(f"'{falta}' (el archivo trae {otra!r}: el nombre debe coincidir exactamente)")
        return " Revise estos nombres: " + "; ".join(parecidas) + "." if parecidas else ""

    def _preparar(self, df: pd.DataFrame, desplazamiento: int = 0) -> tuple[InformeValidacion, NuevosPreparados | None]:
        """Valida y prepara ``df`` con la receta. Las filas que no se pueden preparar quedan en el informe
        y fuera de los datos preparados, cuyo índice es la posición en el archivo (+ ``desplazamiento``)."""
        nombres = [c.nombre for c in self.esquema_entrada.columnas]
        ignoradas = [str(c) for c in df.columns if c not in nombres]
        faltan = self._columnas_faltantes(df)
        if faltan:
            informe = InformeValidacion(len(df), 0, faltan, ignoradas, [ProblemaEntrada(
                None, c, "columna_faltante", f"Falta la columna '{c}'." + (self._pista_columna(df, [c]) if c else ""),
            ) for c in faltan])
            return informe, None
        repetidas = [n for n in nombres if int((df.columns == n).sum()) > 1]
        if repetidas:
            raise ErrorSolicitud(f"Columnas repetidas en el archivo: {', '.join(repr(c) for c in repetidas)}.")
        datos = df[nombres].reset_index(drop=True)
        problemas: list[ProblemaEntrada] = []
        marcadas: set[int] = set()
        no_vistas: dict[str, list[Any]] = {}
        fuera: dict[str, dict[str, Any]] = {}
        codificadas = set(self.receta.decisiones.codificaciones)

        def marcar(posiciones, columna: str, tipo: str, mensaje: Callable[[Any], str], serie: pd.Series) -> None:
            for fila in posiciones:
                if int(fila) not in marcadas:
                    marcadas.add(int(fila))
                    problemas.append(ProblemaEntrada(int(fila) + desplazamiento, columna, tipo, mensaje(serie.iloc[fila])))

        for columna in self.esquema_entrada.columnas:
            serie = datos[columna.nombre]
            es_centinela = serie.map(self._es_centinela).astype(bool)
            if columna.nombre not in codificadas:
                # Sin codificación la columna debe ser numérica. Se fuerza el tipo (una celda de texto la volvería
                # «object» y haría fallar a todas las filas); las celdas que no son número marcan su fila.
                numeros = pd.to_numeric(serie.mask(es_centinela), errors="coerce")
                malas = (serie.notna() & ~es_centinela & numeros.isna()).to_numpy()
                marcar(np.flatnonzero(malas), columna.nombre, "no_numerico", lambda v, c=columna.nombre: f"'{c}' debe ser un número y trae {v!r}.", serie)
                datos[columna.nombre] = numeros
                if columna.tipo == f.CONTINUA:
                    if columna.conversion is None:
                        tratamiento = self.receta.decisiones.faltantes.get(columna.nombre)
                        # Un cero tratado como faltante no es un valor: no sale del rango.
                        cero_faltante = (numeros == 0) if tratamiento and tratamiento.ceros_como_faltantes else pd.Series(False, index=numeros.index)
                        afuera = (((numeros < columna.minimo) | (numeros > columna.maximo)) & ~cero_faltante).to_numpy()
                        if afuera.any():
                            fuera[columna.nombre] = {
                                "filas": [int(i) + desplazamiento for i in np.flatnonzero(afuera)],
                                "minimo": columna.minimo, "maximo": columna.maximo,
                            }
                    continue
                serie = numeros  # binaria numérica: se comprueba su valor abajo
                es_centinela = pd.Series(False, index=serie.index)
            vistos = serie[serie.notna() & ~es_centinela]
            desconocidos = [v for v in pd.unique(vistos) if not any(_mismo_valor(v, c) for c in columna.categorias)]
            if desconocidos:
                no_vistas[columna.nombre] = [v.item() if isinstance(v, np.generic) else v for v in desconocidos]
                marcar(
                    np.flatnonzero(serie.isin(desconocidos).to_numpy()), columna.nombre, "categoria_no_vista",
                    lambda v, c=columna: f"'{v}' no es un valor conocido de '{c.nombre}' "
                    f"(valores posibles: {', '.join(repr(x) for x in c.categorias)}).", serie,
                )
        # Solo se preparan las filas sin problemas; la posición de cada una en el archivo se conserva.
        validas = [i for i in range(len(datos)) if i not in marcadas]
        if validas:
            try:
                nuevos = preparar_nuevos(datos.iloc[validas], self.receta)
            except ErrorPreparacion as error:
                raise ErrorSolicitud(str(error)) from error
            for p in nuevos.problemas:
                problemas.append(ProblemaEntrada(validas[p.fila] + desplazamiento, None, "no_preparable", p.mensaje))
            preparados = nuevos.datos.copy()  # ya sin las filas con problemas de preparación
            preparados.index = [validas[i] + desplazamiento for i in preparados.index]
        else:
            nuevos = NuevosPreparados(pd.DataFrame(), [], [])
            preparados = pd.DataFrame(columns=[c.nombre for c in self.receta.columnas if c.nombre != self.receta.objetivo])
        informe = InformeValidacion(
            len(datos), len(preparados), [], ignoradas, sorted(problemas, key=lambda p: (p.fila, p.columna or "")),
            no_vistas, fuera,
        )
        return informe, replace(nuevos, datos=preparados)

    def validar_filas(self, df_original: pd.DataFrame) -> InformeValidacion:
        """Columnas faltantes, categorías no vistas, valores no numéricos, filas que no se pueden preparar y
        valores fuera del rango de train (estos últimos solo avisan). ``fila`` = posición en el archivo (desde 0)."""
        return self._preparar(df_original)[0]

    # --- Casos ----------------------------------------------------------------------------------------------------------

    def _fila_a_df(self, fila: dict[str, Any]) -> pd.DataFrame:
        if not isinstance(fila, dict):
            raise ErrorSolicitud("La fila debe ser un objeto {columna: valor}.")
        faltan = [c.nombre for c in self.esquema_entrada.columnas if c.nombre not in fila]
        if faltan:
            raise ErrorSolicitud(
                "Faltan columnas en la fila: " + ", ".join(repr(c) for c in faltan) + ".", faltan[0],
                [{"campo": c, "mensaje": "Falta la columna."} for c in faltan],
            )
        return pd.DataFrame([{c.nombre: np.nan if fila[c.nombre] is None else fila[c.nombre] for c in self.esquema_entrada.columnas}])

    def _caso(self, fila: dict[str, Any]) -> tuple[Caso, pd.DataFrame, list[dict[str, Any]]]:
        """(caso, fila preparada sin el objetivo, avisos de la entrada) de una fila en unidades originales."""
        informe, nuevos = self._preparar(self._fila_a_df(fila))
        if not informe.correcto or nuevos is None or nuevos.datos.empty:
            detalles = [{"campo": p.columna or "", "mensaje": p.mensaje} for p in informe.problemas]
            raise ErrorSolicitud(
                "La fila no es válida: " + " ".join(p.mensaje for p in informe.problemas[:3]),
                informe.problemas[0].columna if informe.problemas else None, detalles,
            )
        indice = int(nuevos.datos.index[0])
        preparada = nuevos.datos.loc[[indice]].drop(columns=[self.modelo.objetivo], errors="ignore")
        caso = caso_desde_test(self.modelo, nuevos.datos, indice)
        extrapoladas = [v for v in self.modelo.ancestros if not np.isnan(caso.valores[v]) and not _en_rango(self.modelo, v, caso.valores[v])]
        avisos = list(caso.avisos)
        if extrapoladas:
            avisos.append(AvisoContrafactual(
                "CASO_FUERA_DE_RANGO",
                f"Valores fuera del rango de entrenamiento en {', '.join(extrapoladas)}: el resultado es una extrapolación.",
                extrapoladas,
            ))
        entrada = [
            {"codigo": "VALOR_FUERA_DE_RANGO", "mensaje": f"'{c}' está fuera del rango observado en train ({d['minimo']:g} a {d['maximo']:g}).", "variables": [c]}
            for c, d in informe.fuera_de_rango.items()
        ]
        return replace(caso, origen="usuario", avisos=avisos), preparada, entrada

    # --- Predecir ------------------------------------------------------------------------------------------------------

    def _valores_tipicos(self) -> dict[str, dict[str, float]]:
        """Categoría más frecuente de train de cada grupo one-hot (valor de referencia de sus contribuciones)."""
        tipicos = {}
        for nombre, grupo in self.modelo.unidades.grupos.items():
            columnas = [c for c in grupo.columnas if c in self.train.columns]
            activas = {c: float((self.train[c] >= 0.5).sum()) for c in columnas}
            conteos = [float(len(self.train)) - sum(activas.values()), *[activas.get(c, 0.0) for c in grupo.columnas]]
            moda = grupo.categorias[int(np.argmax(conteos))]
            tipicos[nombre] = self.modelo.unidades.dummies_de_categoria(nombre, moda)
        return tipicos

    def _causas(self, caso: Caso, problema: ProblemaPrescripcion, p_actual: float) -> list[dict[str, Any]]:
        """Ancestros del objetivo con su categoría (directa/indirecta) y su contribución: cuánto cambia la medida
        del modelo si la variable tomara su valor típico de train (mediana, o categoría más frecuente), con lo demás igual."""
        modelo = self.modelo
        directos = set(modelo.padres[modelo.objetivo])
        causas = []
        for nombre, d in self._controles.items():
            columnas = d["columnas_en_modelo"]
            if not columnas:
                continue
            if d["control"] == GRUPO:
                fijadas = {c: x for c, x in self._tipicos[nombre].items() if c in columnas}
                valor = modelo.unidades.categoria_de_grupo(nombre, {c: caso.valores.get(c, 0.0) for c in columnas})
                tipico = modelo.unidades.categoria_de_grupo(nombre, fijadas)
            else:
                mediana = modelo.info_variables[nombre]["mediana"]
                fijadas = {nombre: mediana}
                observada = problema.abduccion.observado.get(nombre, True)
                valor = modelo.unidades.a_original(nombre, float(np.mean(problema.abduccion.antes[nombre]))) if observada else None
                tipico = modelo.unidades.a_original(nombre, mediana)
            resultado = contrafactual_preparado(modelo, caso, fijadas, abduccion=problema.abduccion)
            causas.append({
                "variable": nombre,
                "categoria": "directa" if directos & set(columnas) else "indirecta",
                "valor": valor, "valor_tipico": tipico,
                "contribucion": resultado.antes - resultado.despues,
                "prescriptiva": nombre in self.manifest.variables_prescriptivas,
            })
        return sorted(causas, key=lambda c: (-abs(c["contribucion"]), c["variable"]))

    def predecir(self, fila_original: dict[str, Any]) -> dict[str, Any]:
        """Predicción del modelo causal para una fila en unidades originales.

        ``probabilidad`` (binario: la de la clase 1) o ``valor`` (continuo, unidades originales); ``clase`` según el
        umbral de decisión; ``cumple_objetivo`` según el objetivo deseado de la prescripción; ``causas`` con su
        contribución (ver ``_causas``).
        """
        caso, _, entrada = self._caso(fila_original)
        modelo = self.modelo
        problema = ProblemaPrescripcion(modelo, caso, self.configuracion, self.mu)
        p_objetivo = float(problema.p([np.zeros(problema.k)], [problema.actual])[0])
        p_modelo = float(np.mean(problema.abduccion.antes[modelo.objetivo]))
        avisos = [*a_diccionario_serializable(caso.avisos), *entrada]
        resultado: dict[str, Any] = {"objetivo": modelo.objetivo, "medida": "probabilidad" if modelo.binario else "valor"}
        if modelo.binario:
            clase = int(p_modelo >= modelo.umbral_decision)
            resultado.update(
                probabilidad=p_modelo, umbral_decision=modelo.umbral_decision, clase=clase,
                clase_etiqueta=modelo.unidades.a_original(modelo.objetivo, float(clase)),
                probabilidad_clase_objetivo=p_objetivo,
            )
        else:
            resultado["valor"] = modelo.unidades.a_original_numerico(modelo.objetivo, p_modelo)
        resultado.update(
            cumple_objetivo=bool(problema.alcanzado(p_objetivo)),
            causas=self._causas(caso, problema, p_modelo),
            extrapolacion=any(a["codigo"] in ("CASO_FUERA_DE_RANGO", "VALOR_FUERA_DE_RANGO") for a in avisos),
            avisos=avisos,
        )
        return a_diccionario_serializable(resultado)

    # --- Prescribir -------------------------------------------------------------------------------------------------

    def _prescribir_preparada(self, caso: Caso, preparada: pd.DataFrame) -> dict[str, Any]:
        resultado = prescribir_caso(
            self.modelo, caso, self.configuracion, self.mu, self.referencia, preparada, vecinos=self.indice,
            semilla_por_valores=True,
        )
        return a_diccionario_serializable(resultado)

    def prescribir(self, fila_original: dict[str, Any]) -> dict[str, Any]:
        """Prescripción de una fila (mismo formato que ``ResultadoPrescripcion`` serializado, con evidencia)."""
        caso, preparada, entrada = self._caso(fila_original)
        resultado = self._prescribir_preparada(caso, preparada)
        resultado["avisos"] = [*resultado["avisos"], *entrada]
        return resultado

    # --- Contrafactual ----------------------------------------------------------------------------------------------

    def contrafactual(self, fila_original: dict[str, Any], intervenciones: list[dict[str, Any]]) -> dict[str, Any]:
        """Contrafactual: ``intervenciones`` = [{variable, tipo: fijar|desplazar, valor}] en unidades originales."""
        caso, _, entrada = self._caso(fila_original)
        try:
            lista = [Intervencion(i["variable"], i["tipo"], i["valor"]) for i in intervenciones]
        except (KeyError, TypeError) as error:
            raise ErrorSolicitud("Cada intervención necesita variable, tipo y valor.", "intervenciones") from error
        try:
            resultado = contrafactual(self.modelo, caso, lista)
        except ErrorContrafactual as error:
            raise ErrorSolicitud(str(error), error.campo, [{"campo": error.campo or "", "mensaje": str(error)}]) from error
        datos = a_diccionario_serializable(resultado)
        datos["avisos"] = [*datos["avisos"], *entrada]
        return datos

    # --- Lote -----------------------------------------------------------------------------------------------------------

    def _prescribir_bloque(self, preparadas: pd.DataFrame) -> list[dict[str, Any]]:
        salida = []
        for indice in preparadas.index:
            caso = replace(caso_desde_test(self.modelo, preparadas, int(indice)), origen="usuario")
            fila = preparadas.loc[[indice]].drop(columns=[self.modelo.objetivo], errors="ignore")
            salida.append({"fila": int(indice), "prescripcion": self._prescribir_preparada(caso, fila)})
        return salida

    def iterar_lote(
        self, df_original: pd.DataFrame, progreso: Callable[[int, int], None] | None = None, cancelacion: Any = None,
        procesos: int = 1, tamano_bloque: int = BLOQUE_LOTE,
    ) -> Iterator[BloqueLote]:
        """Prescribe ``df_original`` por bloques y EN SECUENCIA, devolviendo cada bloque en cuanto está listo y liberando
        memoria entre bloques (cada bloque se valida, se prepara y se prescribe por separado). ``procesos`` > 1 reparte
        los bloques entre procesos, con un máximo de bloques pendientes (no se materializa todo el trabajo de golpe).

        Raises:
            ErrorSolicitud: si faltan columnas.
            LoteCancelado: si ``cancelacion.is_set()`` se activa.
        """
        faltan = self._columnas_faltantes(df_original)
        if faltan:
            raise ErrorSolicitud(
                "Faltan columnas: " + ", ".join(repr(c) for c in faltan) + "." + self._pista_columna(df_original, faltan),
                faltan[0], [{"campo": c, "mensaje": "Falta la columna."} for c in faltan],
            )
        total, avisar = len(df_original), progreso or (lambda *_: None)
        tamano_bloque = max(1, int(tamano_bloque))
        bloques = range(0, total, tamano_bloque)
        hechas = 0

        def cancelado() -> None:
            if cancelacion is not None and cancelacion.is_set():
                raise LoteCancelado()

        if procesos <= 1:
            for inicio in bloques:
                cancelado()
                informe, nuevos = self._preparar(df_original.iloc[inicio:inicio + tamano_bloque], inicio)
                resultados = self._prescribir_bloque(nuevos.datos) if nuevos is not None else []
                hechas = min(inicio + tamano_bloque, total)
                avisar(hechas, total)
                yield BloqueLote(resultados, informe.problemas)
                del informe, nuevos, resultados
                gc.collect()
            return
        with ProcessPoolExecutor(max_workers=procesos, initializer=_iniciar_trabajador, initargs=(self._datos, self.informe_carga.rtol, self.informe_carga.atol)) as ejecutor:
            pendientes: list[tuple[int, list[ProblemaEntrada], Future]] = []
            siguientes = iter(bloques)

            def lanzar() -> bool:
                inicio = next(siguientes, None)
                if inicio is None:
                    return False
                informe, nuevos = self._preparar(df_original.iloc[inicio:inicio + tamano_bloque], inicio)
                futuro = ejecutor.submit(_prescribir_en_trabajador, nuevos.datos if nuevos is not None else None)
                pendientes.append((inicio, informe.problemas, futuro))
                return True

            for _ in range(procesos * 2):
                if not lanzar():
                    break
            while pendientes:
                cancelado()
                inicio, problemas, futuro = pendientes.pop(0)  # en orden: los resultados salen por posición
                resultados = futuro.result()
                lanzar()
                avisar(min(inicio + tamano_bloque, total), total)
                yield BloqueLote(resultados, problemas)

    def prescribir_lote(
        self, df_original: pd.DataFrame, progreso: Callable[[int, int], None] | None = None, cancelacion: Any = None,
        procesos: int = 1, tamano_bloque: int = BLOQUE_LOTE,
    ) -> ResultadoLote:
        """Resultados por fila (``fila`` = posición en el archivo, desde 0) y filas que no se pudieron preparar.
        Para archivos enormes use ``iterar_lote`` y escriba cada bloque a disco."""
        resultados: list[dict[str, Any]] = []
        no_preparadas: list[ProblemaEntrada] = []
        for bloque in self.iterar_lote(df_original, progreso, cancelacion, procesos, tamano_bloque):
            resultados.extend(bloque.resultados)
            no_preparadas.extend(bloque.no_preparadas)
        return ResultadoLote(len(df_original), resultados, no_preparadas)


# Trabajadores de ``procesos`` > 1: cada uno carga el artefacto una vez.
_TRABAJADOR: Artefacto | None = None


def _iniciar_trabajador(datos: bytes, rtol: float, atol: float) -> None:
    global _TRABAJADOR
    _TRABAJADOR = cargar_artefacto(datos, rtol=rtol, atol=atol)


def _prescribir_en_trabajador(preparadas: pd.DataFrame | None) -> list[dict[str, Any]]:
    return _TRABAJADOR._prescribir_bloque(preparadas) if preparadas is not None else []

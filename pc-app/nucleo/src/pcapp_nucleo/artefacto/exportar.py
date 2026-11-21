"""Exporta un proyecto con prescripción vigente a un artefacto ``.scotty``.

No reimplementa nada: copia lo que el proyecto ya guarda (receta, modelo causal, prescripción),
guarda el train preparado en Parquet y deriva de la receta y del modelo los esquemas que necesita
la web (``esquema_entrada.json`` y ``controles.json``). El artefacto recién escrito se carga con
``cargar_artefacto`` para generar los casos golden con su propia API y se vuelve a cargar y
verificar al final: si no reproduce su propio golden, no se entrega.
"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo import __version__
from pcapp_nucleo.artefacto import formato as f
from pcapp_nucleo.artefacto.cargar import ErrorArtefacto, cargar_artefacto, mu_efectivo
from pcapp_nucleo.carga import ErrorCarga, cargar_dataset
from pcapp_nucleo.causal import ErrorModeloCausal, descripcion_variables, modelo_desde_diccionario, sha256_train
from pcapp_nucleo.causal.modelo import huella_de_predicciones, predicciones_train
from pcapp_nucleo.causal.aplicabilidad import ADVERTENCIA, BLOQUEANTE
from pcapp_nucleo.causal.modelo import INTERMEDIA, ModeloCausal
from pcapp_nucleo.causal.unidades import GRUPO, NUMERICA, ORDINAL, Unidades
from pcapp_nucleo.preparacion import (
    ErrorPreparacion, Receta, _mismo_valor, aplicar_receta, columnas_originales_requeridas, receta_desde_diccionario,
)
from pcapp_nucleo.prescripcion import (
    AVISO_PERMANENTE, ConfiguracionPrescripcion, ErrorConfiguracionPrescripcion, completar,
    configuracion_desde_diccionario, evaluar_prescribibilidad, problemas_configuracion, variables_prescriptivas,
)
from pcapp_nucleo.prescripcion.configuracion import migrar_limites, rango_original
from pcapp_nucleo.utilidades import a_diccionario_serializable

ARCHIVO_RECETA = "receta.json"
ARCHIVO_MODELO = "modelo_causal/modelo_causal.json"
ARCHIVO_EVALUACION_MODELO = "modelo_causal/evaluacion.json"
ARCHIVO_PRESCRIPCION = "prescripcion/prescripcion.json"
# Además de las librerías del modelo, el manifest registra estas (solo avisan si difieren al cargar).
LIBRERIAS_ENTORNO = ("python", "pandas", "pyarrow", "networkx")
FECHA_ZIP = (1980, 1, 1, 0, 0, 0)  # fija: el zip no depende del momento en que se escribe


class ErrorExportacion(Exception):
    """El proyecto no se puede exportar; el mensaje dice qué falta y qué hacer."""

    def __init__(self, mensaje: str, problemas: list[Any] | None = None) -> None:
        super().__init__(mensaje)
        self.problemas = problemas or []


class ExportacionCancelada(Exception):
    pass


@dataclass
class ProyectoParaExportar:
    """Lo que la exportación necesita de un proyecto (también se puede armar sin carpeta, p. ej. en pruebas)."""

    id: str
    nombre: str
    archivo_original: str
    receta: dict[str, Any]
    modelo_causal: dict[str, Any]
    evaluacion_modelo: dict[str, Any] | None
    prescripcion: dict[str, Any] | None
    original: pd.DataFrame
    evaluaciones: list[tuple[dict[str, Any], dict[str, Any]]] = field(default_factory=list)  # (meta, evaluacion)


@dataclass
class ResultadoExportacion:
    ruta: Path
    advertencias: list[f.AdvertenciaManifest]
    comparacion: dict[str, Any] | None = None  # comparación informativa con el flujo de Scotty PC


# --- Lectura de un proyecto de Scotty PC ---------------------------------------------------------------


def _leer_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _datos_en_base(carpeta: Path) -> tuple[str, str] | None:
    """(nombre, archivo original) del proyecto según ``app.db`` (``<datos>/app.db``), si existe."""
    base = carpeta.parent.parent / "app.db"
    if not base.is_file():
        return None
    try:
        conexion = sqlite3.connect(f"file:{base.as_posix()}?mode=ro", uri=True)
        try:
            fila = conexion.execute("SELECT nombre, archivo_original FROM proyectos WHERE id = ?", (carpeta.name,)).fetchone()
        finally:
            conexion.close()
    except sqlite3.Error:
        return None
    return (fila[0], fila[1]) if fila else None


def cargar_proyecto(carpeta: str | Path) -> ProyectoParaExportar:
    """Lee la carpeta de un proyecto (``<datos>/proyectos/<id>``).

    Raises:
        ErrorExportacion: si falta la receta, el modelo causal o la prescripción, o no se puede leer el dataset.
    """
    carpeta = Path(carpeta).expanduser().resolve()
    if not carpeta.is_dir():
        raise ErrorExportacion(f"La carpeta del proyecto '{carpeta}' no existe.")
    if not (carpeta / ARCHIVO_RECETA).is_file():
        raise ErrorExportacion("El proyecto no tiene receta de preparación: prepare los datos primero.")
    if not (carpeta / ARCHIVO_MODELO).is_file():
        raise ErrorExportacion("El proyecto no tiene modelo causal: constrúyalo antes de exportar.")
    if not (carpeta / ARCHIVO_PRESCRIPCION).is_file():
        raise ErrorExportacion(
            "El proyecto no tiene una configuración de prescripción guardada: configure y guarde la prescripción "
            "(con variables prescriptivas) antes de exportar."
        )
    receta = _leer_json(carpeta / ARCHIVO_RECETA)
    origen = receta.get("origen") or {}
    ruta_datos = carpeta / (origen.get("archivo") or "")
    try:
        original = cargar_dataset(ruta_datos, hoja=origen.get("hoja"))
    except (ErrorCarga, OSError) as error:
        raise ErrorExportacion(f"No se puede leer el dataset original del proyecto ('{ruta_datos.name}'): {error}") from error
    nombre, archivo = _datos_en_base(carpeta) or (carpeta.name, origen.get("archivo") or ruta_datos.name)
    evaluaciones = []
    carpeta_evaluaciones = carpeta / "prescripcion" / "evaluaciones"
    if carpeta_evaluaciones.is_dir():
        for numero in sorted(int(p.name) for p in carpeta_evaluaciones.iterdir() if p.is_dir() and p.name.isdigit()):
            sub = carpeta_evaluaciones / str(numero)
            if (sub / "meta.json").is_file() and (sub / "evaluacion.json").is_file():
                evaluaciones.append((_leer_json(sub / "meta.json"), _leer_json(sub / "evaluacion.json")))
    evaluacion_modelo = carpeta / ARCHIVO_EVALUACION_MODELO
    return ProyectoParaExportar(
        id=carpeta.name, nombre=nombre, archivo_original=archivo, receta=receta,
        modelo_causal=_leer_json(carpeta / ARCHIVO_MODELO),
        evaluacion_modelo=_leer_json(evaluacion_modelo) if evaluacion_modelo.is_file() else None,
        prescripcion=_leer_json(carpeta / ARCHIVO_PRESCRIPCION), original=original, evaluaciones=evaluaciones,
    )


# --- Condiciones ------------------------------------------------------------------------------------------


@dataclass
class _Validado:
    receta: Receta
    train: pd.DataFrame
    test: pd.DataFrame
    modelo: ModeloCausal
    configuracion: ConfiguracionPrescripcion
    mu: float
    mu_origen: str
    prescriptivas: list[str]  # las que el prescriptor puede modificar (permitidas)
    advertencias: list[f.AdvertenciaManifest]


def _versiones_instaladas() -> dict[str, str]:
    from pcapp_nucleo.causal.modelo import _versiones

    return _versiones()


def _validar(proyecto: ProyectoParaExportar) -> _Validado:
    if not proyecto.prescripcion:
        raise ErrorExportacion("El proyecto no tiene prescripción guardada: configúrela y guárdela antes de exportar.")
    datos_modelo, datos_prescripcion = proyecto.modelo_causal, proyecto.prescripcion
    ligada = (datos_prescripcion.get("modelo_causal") or {}).get("huella")
    if ligada != datos_modelo.get("huella"):
        raise ErrorExportacion(
            "La prescripción no está vigente: se guardó con otra versión del modelo causal. Vuelva a guardar la "
            "configuración de la prescripción (y recalibre μ) sobre el modelo causal actual."
        )
    guardadas, instaladas = datos_modelo.get("versiones") or {}, _versiones_instaladas()
    distintas = {k: (v, instaladas.get(k)) for k, v in guardadas.items() if instaladas.get(k) != v}
    if distintas:
        detalle = ", ".join(f"{k} {v[0]} (instalada: {v[1]})" for k, v in distintas.items())
        raise ErrorExportacion(
            f"Las librerías instaladas no son las que usó el modelo causal al construirse: {detalle}. El artefacto "
            "debe servirse con exactamente esas versiones: instálelas o reconstruya el modelo causal."
        )
    try:
        receta = receta_desde_diccionario(proyecto.receta)
        datos = aplicar_receta(proyecto.original, receta)
    except ErrorPreparacion as error:
        raise ErrorExportacion(f"La receta no se puede aplicar al dataset del proyecto: {error}") from error
    if sha256_train(datos.train) != datos_modelo.get("train_sha256"):
        raise ErrorExportacion(
            "El train que reconstruyen la receta y el dataset no es el usado para construir el modelo causal: "
            "el dataset o la preparación cambiaron. Reconstruya el modelo causal."
        )
    try:
        modelo = modelo_desde_diccionario(datos_modelo, datos.train)
    except ErrorModeloCausal as error:
        raise ErrorExportacion(f"El modelo causal no se reproduce con los datos del proyecto: {error}") from error
    try:
        configuracion = completar(modelo, configuracion_desde_diccionario(datos_prescripcion["configuracion"]))
    except ErrorConfiguracionPrescripcion as error:
        raise ErrorExportacion(f"La configuración de la prescripción no es válida: {error}", error.problemas) from error
    errores = problemas_configuracion(modelo, configuracion)
    if errores:
        raise ErrorExportacion(
            "La configuración de la prescripción no es válida: " + "; ".join(f"{e.campo}: {e.mensaje}" for e in errores),
            errores,
        )
    problemas = evaluar_prescribibilidad(modelo, configuracion)
    bloqueantes = [p for p in problemas if p.severidad == BLOQUEANTE]
    if bloqueantes:
        raise ErrorExportacion(
            "No se puede exportar: " + " ".join(p.mensaje for p in bloqueantes), bloqueantes,
        )
    mu, origen = mu_efectivo(datos_prescripcion)
    if mu is None:
        raise ErrorExportacion("μ es automático y todavía no se calibró: ejecute la calibración de μ o fije un valor.")
    prescriptivas = [
        v for v in variables_prescriptivas(modelo, configuracion.modificables).prescriptivas
        if configuracion.acciones[v].permitida
    ]
    advertencias = [f.AdvertenciaManifest(p.codigo, p.mensaje) for p in problemas if p.severidad == ADVERTENCIA]
    return _Validado(receta, datos.train, datos.test, modelo, configuracion, mu, origen, prescriptivas, advertencias)


def _evaluacion_vigente(
    proyecto: ProyectoParaExportar, validado: _Validado
) -> tuple[tuple[dict[str, Any], dict[str, Any]] | None, list[f.AdvertenciaManifest]]:
    """Última evaluación del prescriptor que corresponde a este modelo y a este μ (o ``None`` con su aviso)."""
    if not proyecto.evaluaciones:
        return None, [f.AdvertenciaManifest(
            "SIN_EVALUACION_PRESCRIPTOR",
            "El proyecto no tiene una evaluación del prescriptor: no se sabe qué tasa de éxito logra sobre test.",
        )]
    meta, evaluacion = proyecto.evaluaciones[-1]
    vigente = meta.get("huella_modelo") == validado.modelo.datos["huella"] and abs(float(meta.get("mu", -1)) - validado.mu) <= 1e-12
    if not vigente:
        return None, [f.AdvertenciaManifest(
            "EVALUACION_PRESCRIPTOR_OBSOLETA",
            "La última evaluación del prescriptor se hizo con otro modelo o con otro μ: no se incluye.",
        )]
    return (meta, evaluacion), []


# --- Esquema de entrada ------------------------------------------------------------------------------------


def _original_de(columna) -> str:
    if columna.tipo_final in ("one_hot", "indicador") and "columna_original" in columna.parametros:
        return columna.parametros["columna_original"]
    return columna.nombre


def _numero(x: float) -> float | int:
    return int(x) if float(x).is_integer() else float(x)


def _rango_en_train(unidades: Unidades, train: pd.DataFrame, columna: str) -> tuple[float, float]:
    valores = train[columna].dropna().to_numpy(dtype=float)
    return (
        float(unidades.a_original_numerico(columna, float(valores.min()))),
        float(unidades.a_original_numerico(columna, float(valores.max()))),
    )


def _categorias_de(unidades: Unidades, train: pd.DataFrame, columna: str) -> list[Any]:
    """Valores válidos de una columna binaria u ordinal (los originales de su codificación)."""
    mapeo = unidades.mapeo(columna)
    if mapeo is not None:
        return [original for original, _ in sorted(mapeo, key=lambda par: par[1])]
    observados = np.unique(train[columna].dropna().to_numpy(dtype=float))
    return [_numero(unidades.a_original_numerico(columna, float(v))) for v in observados]


def _descripcion_conversion(receta: Receta, columna: str) -> str | None:
    textos = []
    for c in receta.decisiones.conversiones:
        if c.columna == columna:
            textos.append(c.descripcion or f"Si {columna} {c.condicion} {c.umbral:g}: (x − {c.restar:g}) × {c.multiplicar:g}.")
    return " ".join(textos) or None


def _imputacion(receta: Receta, modelo: ModeloCausal, derivadas: list[str], columna: str) -> tuple[bool, str, str]:
    tratamiento = receta.decisiones.faltantes.get(columna)
    ceros = " Los ceros se tratan como faltantes." if tratamiento and tratamiento.ceros_como_faltantes else ""
    imputacion = tratamiento.imputacion if tratamiento else None
    if imputacion == "eliminar_filas":
        return False, "eliminar_filas", "Una fila sin este dato no se puede preparar y se informa como problema." + ceros
    if imputacion == "mediana":
        return True, "mediana", "Se imputa con la mediana de train." + ceros
    if imputacion == "multivariada":
        return True, "multivariada", (
            "Se imputa con una regresión lineal sobre las demás columnas (imputación iterativa ajustada en train)." + ceros
        )
    en_modelo = [c for c in derivadas if c in modelo.info_variables]
    if not en_modelo:
        detalle = "No se imputa: el modelo causal no usa esta columna."
    elif all(modelo.info_variables[c]["rol"] == INTERMEDIA for c in en_modelo):
        detalle = (
            "No se imputa al preparar; el modelo usa la predicción de su mecanismo a partir de sus padres "
            "(sin el residuo propio del caso)."
        )
    else:
        detalle = "No se imputa al preparar; el modelo usa la mediana de train."
    return True, "ninguna", detalle + ceros


def derivar_esquema_entrada(
    receta: Receta, modelo: ModeloCausal, train: pd.DataFrame, prescriptivas: list[str]
) -> f.EsquemaEntrada:
    """Columnas originales que necesita una fila nueva, a partir de la receta y del modelo."""
    unidades = Unidades(receta.columnas)  # todas las columnas de la receta, no solo las del subgrafo
    metadatos = {c.nombre: c for c in receta.columnas}
    columnas = []
    for original in columnas_originales_requeridas(receta):
        derivadas = [c.nombre for c in receta.columnas if c.nombre != receta.objetivo and _original_de(c) == original]
        categorias: list[Any] | None = None
        minimo = maximo = None
        if original in unidades.grupos:
            tipo = f.CATEGORICA
            categorias = list(unidades.grupos[original].categorias)
        else:
            tipo_final = metadatos[original].tipo_final if original in metadatos else None
            if tipo_final == "ordinal":
                tipo, categorias = f.ORDINAL, _categorias_de(unidades, train, original)
            elif tipo_final == "binaria":
                tipo, categorias = f.BINARIA, _categorias_de(unidades, train, original)
            else:
                tipo = f.CONTINUA
                minimo, maximo = _rango_en_train(unidades, train, original)
        if original in prescriptivas:
            rol = f.PRESCRIPTIVA
        elif any(c in modelo.ancestros for c in derivadas):
            rol = f.ANCESTRO_OBJETIVO
        else:
            rol = f.FUERA_DEL_SUBGRAFO
        admite, imputacion, detalle = _imputacion(receta, modelo, derivadas, original)
        columnas.append(f.ColumnaEntrada(
            nombre=original, nombre_visible=f.nombre_visible(original), tipo=tipo, categorias=categorias,
            minimo=minimo, maximo=maximo, rol=rol, admite_faltantes=admite, imputacion=imputacion,
            detalle_imputacion=detalle, conversion=_descripcion_conversion(receta, original),
        ))
    return f.EsquemaEntrada(columnas)


# --- Controles -----------------------------------------------------------------------------------------------


def _solo_enteros(unidades: Unidades, train: pd.DataFrame, columna: str) -> bool:
    valores = np.unique(train[columna].dropna().to_numpy(dtype=float))
    if not len(valores):
        return False
    originales = np.array([unidades.a_original_numerico(columna, float(v)) for v in valores])
    return bool(np.all(np.abs(originales - np.round(originales)) <= 1e-6 * np.maximum(1.0, np.abs(originales))))


def _valores_permitidos_ordinal(unidades: Unidades, variable: str, accion, estados: list[Any]) -> list[dict[str, Any]]:
    """Niveles de una ordinal a los que se puede pasar: los estados permitidos que además están entre el
    mínimo y el máximo, con su valor original y, si el nivel es texto, su etiqueta."""
    numericas = unidades.etiquetas_numericas(variable)
    dentro = set(unidades.niveles_permitidos(variable, accion.minimo, accion.maximo))
    salida = []
    for etiqueta, codigo in sorted(unidades.mapeo(variable) or [], key=lambda par: par[1]):
        if float(codigo) not in dentro or not any(_mismo_valor(etiqueta, e) for e in estados):
            continue
        valor = unidades.valor_de_codigo(variable, float(codigo))
        salida.append({"valor": valor, "etiqueta": None if numericas else etiqueta})
    return salida


def controles_a_formato_3(
    controles: f.Controles, modelo: ModeloCausal, configuracion: ConfiguracionPrescripcion, train: pd.DataFrame
) -> f.Controles:
    """Controles de un artefacto de formato 1 o 2 con las ordinales en valores originales (allí iban en
    códigos): se toman de la configuración, ya migrada, que es la que prescribe. El resto no cambia."""
    configuracion, _ = migrar_limites(modelo, configuracion)  # idempotente: ya viene migrada desde la carga
    nuevos = {c.variable: c for c in derivar_controles(modelo, configuracion, train).controles}
    return f.Controles(
        [nuevos[c.variable] if c.tipo == f.ORDINAL and c.variable in nuevos else c for c in controles.controles],
        controles.version_formato,
    )


def derivar_controles(
    modelo: ModeloCausal, configuracion: ConfiguracionPrescripcion, train: pd.DataFrame
) -> f.Controles:
    """Variables prescriptivas con sus restricciones en unidades originales (``permitida`` dice si se pueden modificar)."""
    descripciones = {d["nombre"]: d for d in descripcion_variables(modelo)}
    controles = []
    for variable in variables_prescriptivas(modelo, configuracion.modificables).prescriptivas:
        accion = configuracion.acciones[variable]
        d = descripciones[variable]
        control = d["control"]
        estados: list[Any] | None = None
        minimo = maximo = paso = valores = None
        if control == NUMERICA:
            tipo = f.CONTINUA
            rango = rango_original(modelo, variable)
            minimo = accion.minimo if accion.minimo is not None else rango[0]
            maximo = accion.maximo if accion.maximo is not None else rango[1]
            paso = float(accion.paso) if accion.paso is not None else None  # el paso con el que se prescribe
        else:
            tipo = {ORDINAL: f.ORDINAL, GRUPO: f.CATEGORICA}.get(control, f.BINARIA if len(d["categorias"]) == 2 else f.CATEGORICA)
            estados = list(accion.estados_permitidos) if accion.estados_permitidos is not None else list(d["categorias"])
            if tipo == f.ORDINAL:
                # límites en valores originales; los niveles se listan por si el portal los muestra o valida
                minimo, maximo = accion.minimo, accion.maximo
                valores = _valores_permitidos_ordinal(modelo.unidades, variable, accion, estados)
        controles.append(f.ControlVariable(
            variable=variable, nombre_visible=f.nombre_visible(variable), tipo=tipo, direccion=accion.direccion,
            permitida=accion.permitida, minimo=minimo, maximo=maximo,
            cambio_maximo=accion.cambio_maximo if tipo in (f.CONTINUA, f.ORDINAL) else None, costo=accion.costo,
            estados_permitidos=estados, paso=paso, valores_permitidos=valores,
        ))
    return f.Controles(controles)


# --- Evaluación y manifest -------------------------------------------------------------------------------------


def _resumen_evaluacion(
    evaluacion_modelo: dict[str, Any] | None, prescriptor: tuple[dict[str, Any], dict[str, Any]] | None
) -> f.ResumenEvaluacion:
    test = ((evaluacion_modelo or {}).get("evaluacion_objetivo") or {}).get("test") or {}
    meta = prescriptor[0] if prescriptor else {}
    return f.ResumenEvaluacion(
        exactitud_balanceada_test=test.get("exactitud_balanceada"), auc_test=test.get("auc"), brier_test=test.get("brier"),
        r2_test=test.get("r2"), rmse_test=test.get("rmse"),
        tasa_exito_prescriptor=meta.get("tasa_exito"), filas_evaluadas=meta.get("casos"),
    )


def _sha256_dataframe(df: pd.DataFrame) -> str:
    """Huella del contenido de un dataset (respaldo si la receta no guarda el sha256 del archivo)."""
    valores = pd.util.hash_pandas_object(df, index=True).to_numpy()
    return f.sha256_bytes(valores.tobytes() + ",".join(map(str, df.columns)).encode("utf-8"))


def _versiones_manifest(datos_modelo: dict[str, Any]) -> dict[str, str]:
    """Versiones de las librerías del modelo (las que se exigen al cargar) y del entorno de exportación."""
    versiones = dict(datos_modelo["versiones"])
    for paquete in LIBRERIAS_ENTORNO:
        versiones[paquete] = f.version_instalada(paquete) or "desconocida"
    return versiones


def _json_bytes(valor: Any) -> bytes:
    return json.dumps(a_diccionario_serializable(valor), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def _parquet_bytes(train: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    train.to_parquet(buffer, engine="pyarrow", index=True, compression="zstd")
    return buffer.getvalue()


def _predicciones_parquet(v: "_Validado", huella_modelo: str) -> bytes:
    """eta de cada mecanismo sobre train (el vector que resume la huella), sin pérdida, para cargar en otra plataforma."""
    predicciones = predicciones_train(v.modelo, v.train)
    buffer = io.BytesIO()
    pd.DataFrame(predicciones).to_parquet(buffer, engine="pyarrow", index=False, compression="zstd")
    contenido = buffer.getvalue()
    releidas = pd.read_parquet(io.BytesIO(contenido), engine="pyarrow")
    if huella_de_predicciones({c: releidas[c].to_numpy(dtype=float) for c in releidas.columns}) != huella_modelo:
        raise ErrorExportacion("El Parquet no conserva exactamente las predicciones de train de los mecanismos.")
    return contenido


def _manifest(proyecto: ProyectoParaExportar, v: _Validado, contenidos: dict[str, bytes], resumen: f.ResumenEvaluacion,
              advertencias: list[f.AdvertenciaManifest], golden_sha256: str | None) -> f.Manifest:
    datos_modelo = proyecto.modelo_causal
    objetivo = v.configuracion.objetivo
    return f.Manifest(
        formato=f.FORMATO, version_formato=f.VERSION_FORMATO, creado_en=datetime.now().isoformat(timespec="seconds"),
        version_nucleo=__version__, versiones_librerias=_versiones_manifest(datos_modelo),
        proyecto=f.ProyectoManifest(
            id=proyecto.id, nombre=proyecto.nombre, archivo_original=proyecto.archivo_original,
            sha256_dataset=(proyecto.receta.get("origen") or {}).get("sha256") or _sha256_dataframe(proyecto.original),
        ),
        objetivo=f.ObjetivoManifest(
            columna=v.modelo.objetivo, tipo="binario" if v.modelo.binario else "continuo",
            clase_positiva=datos_modelo.get("clase_positiva"),
            clase_objetivo=objetivo.clase_positiva if v.modelo.binario else None,
            medida="probabilidad" if v.modelo.binario else "valor", direccion=objetivo.direccion,
            deseado=objetivo.valor, umbral_decision=v.modelo.umbral_decision,
        ),
        prescripcion=f.PrescripcionManifest(v.mu, v.mu_origen, v.configuracion.optimizador),
        modelo=f.ModeloManifest(
            huella=datos_modelo["huella"], train_sha256=datos_modelo["train_sha256"],
            version_resultado_pc=(datos_modelo.get("resultado_pc") or {}).get("version"),
        ),
        variables_prescriptivas=list(v.prescriptivas),
        supuestos_confirmados={x: v.configuracion.supuestos[x].confirmado_en for x in v.prescriptivas},
        resumen_evaluacion=resumen, aviso=AVISO_PERMANENTE, advertencias=advertencias,
        archivos={nombre: f.sha256_bytes(c) for nombre, c in contenidos.items()}, golden_sha256=golden_sha256,
    )


def empaquetar(manifest: f.Manifest, contenidos: dict[str, bytes]) -> bytes:
    """Zip del artefacto, con el manifest primero y fechas fijas (el contenido no depende del momento)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_:
        for nombre, contenido in {f.MANIFEST: _json_bytes(manifest.a_diccionario()), **contenidos}.items():
            info = zipfile.ZipInfo(nombre, FECHA_ZIP)
            info.compress_type = zipfile.ZIP_STORED if nombre == f.TRAIN else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zip_.writestr(info, contenido)
    return buffer.getvalue()


def _nombre_archivo(proyecto: ProyectoParaExportar, version: int | None) -> str:
    base = re.sub(r"[^\w\-]+", "_", proyecto.nombre).strip("_") or "proyecto"
    return f"{base}_v{version if version is not None else 0}_{datetime.now().strftime('%Y%m%d-%H%M%S')}{f.EXTENSION}"


def _ruta_destino(destino: Path, proyecto: ProyectoParaExportar, version: int | None) -> Path:
    destino = Path(destino).expanduser()
    if destino.suffix.lower() == f.EXTENSION:
        ruta = destino
        ruta.parent.mkdir(parents=True, exist_ok=True)
    else:
        destino.mkdir(parents=True, exist_ok=True)
        ruta = destino / _nombre_archivo(proyecto, version)
    candidata, sufijo = ruta, 2
    while candidata.exists():  # nunca se sobrescribe un artefacto
        candidata = ruta.with_name(f"{ruta.stem}_{sufijo}{ruta.suffix}")
        sufijo += 1
    return candidata


# --- Exportación -------------------------------------------------------------------------------------------------


def exportar_artefacto_completo(
    proyecto: ProyectoParaExportar | str | Path, destino: str | Path,
    progreso: Callable[[int, int, str], None] | None = None, cancelacion: Any = None,
) -> ResultadoExportacion:
    """Exporta ``proyecto`` (objetos o carpeta) a ``destino`` y devuelve la ruta, las advertencias y la
    comparación informativa con el flujo de Scotty PC.

    ``destino``: una carpeta (el archivo se llama ``<proyecto>_v<versión>_<AAAAMMDD-HHMMSS>.scotty``) o
    una ruta que termine en ``.scotty``. Nunca sobrescribe.

    Raises:
        ErrorExportacion: si no se cumplen las condiciones, o si el artefacto no supera su verificación.
        ExportacionCancelada: si ``cancelacion.is_set()`` se activa.
    """
    from pcapp_nucleo.artefacto import golden

    avisar = progreso or (lambda *_: None)
    total = golden.MAXIMO_CASOS + 5

    def comprobar() -> None:
        if cancelacion is not None and cancelacion.is_set():
            raise ExportacionCancelada()

    if not isinstance(proyecto, ProyectoParaExportar):
        proyecto = cargar_proyecto(proyecto)
    avisar(0, total, "Comprobando las condiciones")
    v = _validar(proyecto)
    comprobar()
    vigente, avisos_evaluacion = _evaluacion_vigente(proyecto, v)
    advertencias = [*v.advertencias, *avisos_evaluacion]
    version = (proyecto.modelo_causal.get("resultado_pc") or {}).get("version")
    ruta = _ruta_destino(Path(destino), proyecto, version)

    avisar(1, total, "Empaquetando el modelo")
    train_parquet = _parquet_bytes(v.train)
    recargado = pd.read_parquet(io.BytesIO(train_parquet), engine="pyarrow")
    if sha256_train(recargado) != proyecto.modelo_causal["train_sha256"]:
        raise ErrorExportacion(
            "El Parquet no conserva exactamente el train preparado (la huella del modelo no coincide al releerlo)."
        )
    evaluacion = {
        "version_formato": f.VERSION_FORMATO,
        "modelo_causal": proyecto.evaluacion_modelo,
        "prescriptor": {"meta": vigente[0], "evaluacion": vigente[1]} if vigente else None,
    }
    contenidos = {
        f.RECETA: _json_bytes(proyecto.receta),
        f.MODELO_CAUSAL: _json_bytes(proyecto.modelo_causal),
        f.PRESCRIPCION: _json_bytes(proyecto.prescripcion),
        f.TRAIN: train_parquet,
        f.PREDICCIONES_TRAIN: _predicciones_parquet(v, proyecto.modelo_causal["huella"]),
        f.ESQUEMA_ENTRADA: _json_bytes(derivar_esquema_entrada(v.receta, v.modelo, v.train, v.prescriptivas).a_diccionario()),
        f.CONTROLES: _json_bytes(derivar_controles(v.modelo, v.configuracion, v.train).a_diccionario()),
        f.EVALUACION: _json_bytes(evaluacion),
    }
    resumen = _resumen_evaluacion(proyecto.evaluacion_modelo, vigente)
    provisional = _manifest(proyecto, v, contenidos, resumen, advertencias, None)
    comprobar()

    avisar(2, total, "Cargando el artefacto")
    try:
        art = cargar_artefacto(empaquetar(provisional, contenidos), permitir_sin_golden=True)
    except ErrorArtefacto as error:
        raise ErrorExportacion(f"El artefacto no se puede cargar: {error}") from error

    casos_golden = golden.generar_golden(
        art, proyecto.original, v.test,
        progreso=lambda hechos, n: avisar(3 + hechos, total, f"Casos de verificación {hechos}/{n}"), cancelacion=cancelacion,
    )
    contenidos[f.GOLDEN] = _json_bytes(casos_golden)
    manifest = _manifest(proyecto, v, contenidos, resumen, advertencias, golden.sha256_golden(casos_golden))
    datos = empaquetar(manifest, contenidos)

    avisar(total - 2, total, "Verificando el artefacto")
    comprobar()
    try:
        final = cargar_artefacto(datos)
        informe = golden.verificar_golden(final)
    except ErrorArtefacto as error:
        raise ErrorExportacion(f"El artefacto exportado no se puede cargar: {error}") from error
    if not informe.correcto:
        raise ErrorExportacion(
            "El artefacto exportado no reproduce su propio golden: " + "; ".join(informe.diferencias[:3]), informe.diferencias,
        )
    comparacion = golden.comparar_con_scotty_pc(final, v.test, casos_golden)

    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_bytes(datos)
    temporal.replace(ruta)
    avisar(total, total, "Listo")
    return ResultadoExportacion(ruta, advertencias, comparacion)


def exportar_artefacto(
    proyecto: ProyectoParaExportar | str | Path, destino: str | Path,
    progreso: Callable[[int, int, str], None] | None = None, cancelacion: Any = None,
) -> Path:
    """Exporta el proyecto a un artefacto ``.scotty`` y devuelve su ruta (ver ``exportar_artefacto_completo``)."""
    return exportar_artefacto_completo(proyecto, destino, progreso, cancelacion).ruta

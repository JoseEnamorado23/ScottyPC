"""Servicios de cada etapa del flujo: llaman al núcleo y gestionan archivos y etapas."""

from __future__ import annotations

import re
import shutil
import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pcapp_nucleo.analisis import analizar_dataset, resultado_a_diccionario
from pcapp_nucleo.caracterizacion import caracterizar
from pcapp_nucleo.carga import ErrorCarga, cargar_dataset, obtener_hojas_excel
from pcapp_nucleo.exportacion import disposicion_por_niveles, exportar
from pcapp_nucleo.informe import (
    etiqueta_version,
    informe_html,
    orientaciones_nuevas,
    resumen_decisiones,
    resumen_separacion,
)
from pcapp_nucleo.modelos import Hallazgo, InformeRevision, PerfilColumna, Severidad, TipoHallazgo
from pcapp_nucleo.pc_bootstrap import ProgresoBootstrap, agregar, ejecutar_bootstrap, matriz_spearman
from pcapp_nucleo.pc_config import (
    ErrorConfiguracionPC,
    advertencias_configuracion,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    problemas_configuracion,
)
from pcapp_nucleo.plantilla import ErrorEleccion, aplicar_elecciones
from pcapp_nucleo.preparacion import (
    ConfiguracionSeparacion,
    DatosPreparados,
    ErrorPreparacion,
    LimiteColumnas,
    OrigenDatos,
    aplicar_receta,
    calcular_sha256,
    decisiones_desde_diccionario,
    distribucion_objetivo,
    evaluar_columnas,
    preparar,
    receta_a_diccionario,
    receta_desde_diccionario,
    separacion_desde_diccionario,
    separacion_heredada,
    separacion_sugerida,
)
from pcapp_nucleo.reagregacion import (
    ErrorReagregacion,
    Reagregacion,
    avisos_resultado,
    escribir_reagregacion,
    migrar_resultado,
    reagregar,
    tiene_cuentas,
)
from pcapp_nucleo.seleccion_prueba import (
    AlternativaPrueba,
    DiagnosticoVariable,
    RecomendacionPrueba,
    evaluar_eleccion,
    recomendar_prueba,
)
from pcapp_nucleo.utilidades import a_diccionario_serializable

from pcapp_servidor.almacenamiento.archivos import ANTERIORES, Archivos, dentro_de
from pcapp_servidor.almacenamiento.base_datos import BaseDatos, ahora
from pcapp_servidor.almacenamiento.repositorio import (
    Proyecto,
    RepositorioEtapas,
    RepositorioProyectos,
    RepositorioTrabajos,
    Trabajo,
)
from pcapp_servidor.configuracion import ConfiguracionServidor
from pcapp_servidor.errores import conflicto, invalido, no_encontrado
from pcapp_servidor.etapas import REQUISITOS, GestorEtapas
from pcapp_servidor.procesos import GrupoProcesos
from pcapp_servidor.trabajos import REANUDABLES, Contexto, FuncionTrabajo, GestorTrabajos
from pcapp_servidor.validacion_campos import validar_decisiones, validar_separacion_campos

FORMATOS = (".csv", ".xlsx")
FILAS_VISTA_PREVIA = 20
CARPETA_PC = "pc"
# Versiones del resultado: la 1 (original) vive en pc/; las ajustadas, en pc/versiones/<n>/.
CARPETA_VERSIONES = "versiones"
INDICE_VERSIONES = "versiones.json"
ARCHIVOS_RESULTADO = {
    "grafo.png": "image/png",
    "aristas.csv": "text/csv",
    "mascara.csv": "text/csv",
    "matriz_frecuencias.csv": "text/csv",
    "resultado.json": "application/json",
}


MAXIMO_CATEGORIAS = 20


def _campo_de_separacion(mensaje: str) -> str | None:
    """Campo de la separación al que se refiere un error de preparación, si es de la separación."""
    texto = mensaje.lower()
    if "corte" in texto:
        return "separacion.corte"
    if "proporción de test" in texto:
        return "separacion.proporcion_test"
    if "fecha" in texto:
        return "separacion.columna_fecha"
    return None
INTERVALOS_HISTOGRAMA = 20


def describir_distribucion(serie: pd.Series, columna: str) -> dict[str, Any]:
    """Conteos por valor (los más frecuentes y 'otros') o, si la columna es
    numérica con muchos valores distintos, un histograma."""
    presentes = serie.dropna()
    total, distintos = int(len(serie)), int(presentes.nunique())
    resultado: dict[str, Any] = {
        "columna": columna, "total": total, "faltantes": total - int(len(presentes)),
        "valores_distintos": distintos, "categorias": [], "histograma": None,
    }
    numerica = pd.api.types.is_numeric_dtype(serie.dtype) and not pd.api.types.is_bool_dtype(serie.dtype)
    if numerica and distintos > MAXIMO_CATEGORIAS:
        conteos, limites = np.histogram(presentes.to_numpy(dtype=float), bins=INTERVALOS_HISTOGRAMA)
        resultado.update(tipo="histograma", histograma={"limites": limites.tolist(), "conteos": conteos.tolist()})
        return resultado
    frecuencias = presentes.value_counts()
    principales = frecuencias.iloc[:MAXIMO_CATEGORIAS]
    categorias = [
        {"valor": valor, "conteo": int(n), "porcentaje": round(100 * n / max(len(presentes), 1), 2)}
        for valor, n in principales.items()
    ]
    otros = int(frecuencias.iloc[MAXIMO_CATEGORIAS:].sum())
    if otros:
        categorias.append({"valor": "otros", "conteo": otros, "porcentaje": round(100 * otros / len(presentes), 2)})
    resultado.update(tipo="categorias", categorias=a_diccionario_serializable(categorias))
    return resultado


class Servicios:
    def __init__(self, configuracion: ConfiguracionServidor, base: BaseDatos) -> None:
        self.archivos = Archivos(configuracion.datos)
        self.proyectos = RepositorioProyectos(base)
        self.etapas = GestorEtapas(RepositorioEtapas(base), self.proyectos, self.archivos)
        self.trabajos = GestorTrabajos(RepositorioTrabajos(base))
        self.grupo = GrupoProcesos(configuracion.procesos)
        self._cerrojo_versiones = threading.RLock()

    def apagar(self) -> None:
        self.trabajos.detener_todos()
        self.grupo.cerrar()

    # --- Auxiliares -----------------------------------------------------------------------

    def proyecto(self, proyecto_id: str) -> Proyecto:
        self.archivos.carpeta(proyecto_id)  # valida el formato del id
        proyecto = self.proyectos.obtener(proyecto_id)
        if proyecto is None:
            raise no_encontrado("El proyecto no existe.", "PROYECTO_NO_ENCONTRADO")
        return proyecto

    def vista(self, proyecto: Proyecto) -> dict[str, Any]:
        datos = asdict(proyecto)
        datos.pop("archivo")
        activo = self.trabajos.repositorio.activo_de(proyecto.id)
        datos["etapas"] = self.etapas.etapas.estados(proyecto.id)
        datos["trabajo_activo"] = activo.id if activo else None
        ultimo = self.trabajos.repositorio.ultimo_de(proyecto.id)
        datos["ultimo_trabajo"] = None if ultimo is None else {
            "id": ultimo.id, "tipo": ultimo.tipo, "estado": ultimo.estado,
            "completadas": ultimo.completadas, "total": ultimo.total, "mensaje": ultimo.mensaje,
            "reanudable": self._reanudable(ultimo),
        }
        return datos

    def _reanudable(self, trabajo: Trabajo) -> bool:
        if trabajo.estado not in REANUDABLES:
            return False
        requisito = REQUISITOS["analisis" if trabajo.tipo == "pc" else "recomendacion"]
        return requisito in self.etapas.vigentes(trabajo.proyecto_id)

    def _ruta(self, proyecto: Proyecto, nombre: str) -> Path:
        return self.archivos.carpeta(proyecto.id) / nombre

    def _cargar(self, proyecto: Proyecto, hoja: str | None) -> pd.DataFrame:
        try:
            return cargar_dataset(self._ruta(proyecto, proyecto.archivo), hoja=hoja)
        except ErrorCarga as error:
            campo = "hoja" if "HOJA" in error.problema.codigo else ""
            raise invalido(
                error.problema.codigo, error.problema.mensaje,
                [{"campo": campo, "mensaje": error.problema.mensaje}] if campo else error.problema.evidencia,
            ) from error

    def _leer(self, proyecto: Proyecto, nombre: str) -> Any:
        return self.archivos.leer_json(self._ruta(proyecto, nombre))

    def _datos_preparados(self, proyecto: Proyecto) -> DatosPreparados:
        receta = receta_desde_diccionario(self._leer(proyecto, "receta.json"))
        return aplicar_receta(self._cargar(proyecto, receta.origen.hoja), receta)

    # --- Proyectos --------------------------------------------------------------------------

    def crear_proyecto(self, ruta_archivo: str, nombre: str | None) -> dict[str, Any]:
        origen = Path(ruta_archivo).expanduser()
        if not origen.is_file():
            raise invalido(
                "ARCHIVO_NO_ENCONTRADO", f"No existe el archivo '{origen}'.",
                [{"campo": "ruta_archivo", "mensaje": "El archivo no existe."}],
            )
        extension = origen.suffix.lower()
        if extension not in FORMATOS:
            raise invalido(
                "FORMATO_NO_SOPORTADO", "Formato de archivo no soportado. Los formatos aceptados son CSV y XLSX.",
                [{"campo": "ruta_archivo", "mensaje": "Use un archivo CSV o XLSX."}],
            )
        proyecto_id = uuid.uuid4().hex
        carpeta = self.archivos.carpeta(proyecto_id)
        carpeta.mkdir(parents=True)
        copia = carpeta / f"original{extension}"
        try:
            shutil.copy2(origen, copia)
            hojas = obtener_hojas_excel(copia) if extension == ".xlsx" else None
            hoja_vista = hojas[0] if hojas else None
            dataframe = cargar_dataset(copia, hoja=hoja_vista)
        except ErrorCarga as error:
            self.archivos.borrar_carpeta(proyecto_id)
            raise invalido(error.problema.codigo, error.problema.mensaje) from error
        except BaseException:
            self.archivos.borrar_carpeta(proyecto_id)
            raise
        momento = ahora()
        proyecto = Proyecto(
            id=proyecto_id, nombre=nombre or origen.stem, archivo_original=origen.name,
            archivo=copia.name, hoja=None, sha256=calcular_sha256(copia), objetivo=None,
            etapa_actual=None, creado_en=momento, actualizado_en=momento,
        )
        self.proyectos.crear(proyecto)
        return {
            **self.vista(proyecto),
            "hojas": hojas,
            "hoja_vista": hoja_vista,
            "filas": int(len(dataframe)),
            "columnas": [str(c) for c in dataframe.columns],
            "vista_previa": a_diccionario_serializable(
                dataframe.head(FILAS_VISTA_PREVIA).to_dict(orient="records")
            ),
        }

    def listar(self) -> list[dict[str, Any]]:
        return [self.vista(p) for p in self.proyectos.listar()]

    def eliminar(self, proyecto_id: str) -> None:
        self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.archivos.borrar_carpeta(proyecto_id)
        self.proyectos.eliminar(proyecto_id)

    # --- Revisión y decisiones ------------------------------------------------------------

    def revisar(self, proyecto_id: str, objetivo: str, hoja: str | None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        resultado = analizar_dataset(self._cargar(proyecto, hoja), objetivo)
        datos = resultado_a_diccionario(resultado)
        if not resultado.valido:
            raise invalido(
                "DATASET_NO_VALIDO", "El dataset no cumple las condiciones mínimas para continuar.",
                datos["validacion"]["errores"],
            )
        self.etapas.preparar_escritura(proyecto_id, "revision")
        self.archivos.escribir_json(self._ruta(proyecto, "revision.json"), datos)
        self.proyectos.actualizar(proyecto_id, objetivo=objetivo, hoja=hoja)
        self.etapas.registrar(proyecto_id, "revision")
        return datos

    def revision(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "revision")
        return self._leer(proyecto, "revision.json")

    def _informe_guardado(self, proyecto: Proyecto) -> InformeRevision:
        """``InformeRevision`` reconstruido desde revision.json (sin volver a analizar)."""
        datos = self._leer(proyecto, "revision.json")
        return InformeRevision(
            resumen=datos["resumen"],
            hallazgos=[Hallazgo(**{**h, "severidad": Severidad(h["severidad"])}) for h in datos["hallazgos"]],
            perfiles_columnas=[PerfilColumna(**p) for p in datos["perfiles_columnas"]],
            objetivo=datos["objetivo"],
            informacion_objetivo=datos["informacion_objetivo"],
        )

    def plantilla_decisiones(self, proyecto_id: str) -> dict[str, Any]:
        return self.previsualizar_decisiones(proyecto_id, {})

    def previsualizar_decisiones(self, proyecto_id: str, elecciones: dict[str, str]) -> dict[str, Any]:
        """Decisiones que resultan de las acciones elegidas (calculadas por el núcleo)."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "decisiones")
        try:
            decisiones = aplicar_elecciones(self._informe_guardado(proyecto), elecciones)
        except ErrorEleccion as error:
            raise invalido(
                "ELECCION_NO_VALIDA", str(error),
                [{"campo": f"elecciones.{error.identificador}", "mensaje": str(error)}],
            ) from error
        return a_diccionario_serializable(decisiones)

    def datos_hoja(self, proyecto_id: str, hoja: str | None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        ruta = self._ruta(proyecto, proyecto.archivo)
        hojas = obtener_hojas_excel(ruta) if ruta.suffix.lower() == ".xlsx" else None
        if hoja is None and hojas:
            hoja = proyecto.hoja or hojas[0]
        dataframe = self._cargar(proyecto, hoja)
        return {
            "hoja": hoja,
            "hojas": hojas,
            "filas": int(len(dataframe)),
            "columnas": [str(c) for c in dataframe.columns],
            "vista_previa": a_diccionario_serializable(
                dataframe.head(FILAS_VISTA_PREVIA).to_dict(orient="records")
            ),
        }

    def distribucion(self, proyecto_id: str, columna: str, hoja: str | None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        dataframe = self._cargar(proyecto, hoja if hoja is not None else proyecto.hoja)
        columnas = [str(c) for c in dataframe.columns]
        if columna not in columnas:
            raise invalido(
                "COLUMNA_NO_ENCONTRADA", f"La columna '{columna}' no existe.",
                [{"campo": "columna", "mensaje": "La columna no existe."}],
            )
        return describir_distribucion(dataframe.iloc[:, columnas.index(columna)], columna)

    def decisiones(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "decisiones")
        return self._leer(proyecto, "decisiones.json")

    def guardar_decisiones(self, proyecto_id: str, datos: dict[str, Any]) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "decisiones")
        columnas = [str(c) for c in self._cargar(proyecto, proyecto.hoja).columns]
        errores = validar_decisiones(datos, columnas, proyecto.objetivo)
        if errores:
            raise invalido("DECISIONES_NO_VALIDAS", "Hay decisiones no válidas.", errores)
        try:
            decisiones = decisiones_desde_diccionario(datos)
        except ErrorPreparacion as error:
            raise invalido("DECISIONES_NO_VALIDAS", str(error)) from error
        contenido = a_diccionario_serializable(decisiones)
        self.etapas.preparar_escritura(proyecto_id, "decisiones")
        self.archivos.escribir_json(self._ruta(proyecto, "decisiones.json"), contenido)
        self.etapas.registrar(proyecto_id, "decisiones")
        return contenido

    # --- Preparación ------------------------------------------------------------------------

    def _receta_mas_reciente(self, proyecto: Proyecto) -> dict[str, Any] | None:
        """La receta vigente o, si se archivó (p. ej. al cambiar las decisiones), la última archivada."""
        actual = self._ruta(proyecto, "receta.json")
        if actual.is_file():
            return self.archivos.leer_json(actual)
        anteriores = self._ruta(proyecto, ANTERIORES)
        archivadas = sorted(anteriores.glob("*/receta.json")) if anteriores.is_dir() else []
        return self.archivos.leer_json(archivadas[-1]) if archivadas else None

    def _separacion_inicial(self, proyecto: Proyecto, decisiones_json: dict[str, Any]) -> ConfiguracionSeparacion:
        """La separación vive solo en la receta; sin receta, la sugerida por las decisiones
        (o la de un archivo de decisiones antiguo que aún la tenga)."""
        receta = self._receta_mas_reciente(proyecto)
        if receta is not None:
            try:
                return receta_desde_diccionario(receta).separacion
            except ErrorPreparacion:
                pass
        decisiones = decisiones_desde_diccionario(decisiones_json)
        return separacion_sugerida(decisiones, separacion_heredada(decisiones_json))

    @staticmethod
    def _limite_columnas(receta: dict[str, Any]) -> LimiteColumnas:
        return evaluar_columnas(receta_desde_diccionario(receta).columnas)

    def _exigir_columnas_permitidas(self, proyecto: Proyecto) -> None:
        """409 si hay demasiadas columnas para PC (la terminal solo advierte)."""
        limite = self._limite_columnas(self._leer(proyecto, "receta.json"))
        if limite.estado == "bloqueado":
            raise conflicto("DEMASIADAS_COLUMNAS", limite.mensaje, {"columnas": limite.columnas})

    @staticmethod
    def _resumen_preparacion(datos: DatosPreparados) -> dict[str, Any]:
        objetivo, tipo = datos.objetivo, datos.tipo_objetivo
        faltantes = datos.train.drop(columns=[objetivo]).isna().sum()
        return a_diccionario_serializable({
            "filas_train": int(len(datos.train)),
            "filas_test": int(len(datos.test)),
            "tipo_objetivo": tipo,
            "columnas": datos.columnas,
            "faltantes_restantes": {str(c): int(n) for c, n in faltantes.items() if n},
            "separacion": datos.receta.separacion_aplicada,
            "separacion_configurada": datos.receta.separacion,
            "distribucion_objetivo": {
                "train": distribucion_objetivo(datos.train[objetivo], tipo),
                "test": distribucion_objetivo(datos.test[objetivo], tipo),
            },
            "limite_columnas": evaluar_columnas(datos.columnas),
            "advertencias": datos.receta.advertencias,
        })

    def preparar(self, proyecto_id: str, separacion: dict[str, Any] | None = None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "preparacion")
        decisiones_json = self._leer(proyecto, "decisiones.json")
        decisiones = decisiones_desde_diccionario(decisiones_json)
        if separacion is None:
            elegida = self._separacion_inicial(proyecto, decisiones_json)
        else:
            errores = validar_separacion_campos(separacion, decisiones.columnas_fecha_disponibles)
            if errores:
                raise invalido("SEPARACION_NO_VALIDA", "La separación no es válida.", errores)
            elegida = separacion_desde_diccionario(separacion)
        origen = OrigenDatos(archivo=proyecto.archivo, hoja=proyecto.hoja, sha256=proyecto.sha256)
        try:
            datos = preparar(
                self._cargar(proyecto, proyecto.hoja), proyecto.objetivo, decisiones,
                origen=origen, separacion=elegida,
            )
        except ErrorPreparacion as error:
            mensaje = str(error)
            campo = _campo_de_separacion(mensaje)
            raise invalido(
                "PREPARACION_NO_VALIDA", mensaje, [{"campo": campo, "mensaje": mensaje}] if campo else None
            ) from error
        resumen = self._resumen_preparacion(datos)
        self.etapas.preparar_escritura(proyecto_id, "preparacion")
        self.archivos.escribir_json(self._ruta(proyecto, "receta.json"), receta_a_diccionario(datos.receta))
        self.archivos.escribir_json(self._ruta(proyecto, "preparacion.json"), resumen)
        datos.train.to_csv(self._ruta(proyecto, "train.csv"), index=False)
        datos.test.to_csv(self._ruta(proyecto, "test.csv"), index=False)
        self.etapas.registrar(proyecto_id, "preparacion")
        return resumen

    def estado_preparacion(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "preparacion")
        decisiones_json = self._leer(proyecto, "decisiones.json")
        vigente = "preparacion" in self.etapas.vigentes(proyecto_id)
        resumen = None
        if vigente:
            ruta = self._ruta(proyecto, "preparacion.json")
            if ruta.is_file():
                resumen = self.archivos.leer_json(ruta)
            else:  # preparación hecha con una versión anterior: se reconstruye desde la receta
                resumen = self._resumen_preparacion(self._datos_preparados(proyecto))
                self.archivos.escribir_json(ruta, resumen)
        return {
            "vigente": vigente,
            "resumen": resumen,
            "separacion": a_diccionario_serializable(self._separacion_inicial(proyecto, decisiones_json)),
            "columnas_fecha_disponibles": decisiones_desde_diccionario(decisiones_json).columnas_fecha_disponibles,
        }

    # --- Recomendación (trabajo) --------------------------------------------------------------

    def _funcion_recomendacion(self, proyecto_id: str, estimar: bool) -> FuncionTrabajo:
        def ejecutar(contexto: Contexto) -> str | None:
            proyecto = self.proyecto(proyecto_id)
            contexto.reportar(completadas=0, total=1)
            recomendacion = recomendar_prueba(self._datos_preparados(proyecto), estimar=estimar)
            if contexto.cancelacion.is_set():
                return None  # la estimación no puede interrumpirse: se descarta su resultado
            self.etapas.preparar_escritura(proyecto_id, "recomendacion")
            self.archivos.escribir_json(
                self._ruta(proyecto, "recomendacion.json"), a_diccionario_serializable(recomendacion)
            )
            self.etapas.registrar(proyecto_id, "recomendacion")
            contexto.reportar(completadas=1, total=1)
            return f"Prueba recomendada: {recomendacion.prueba}."

        return ejecutar

    def lanzar_recomendacion(self, proyecto_id: str, estimar: bool) -> Trabajo:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "recomendacion")
        self._exigir_columnas_permitidas(proyecto)
        return self.trabajos.iniciar(
            proyecto_id, "recomendacion", self._funcion_recomendacion(proyecto_id, estimar),
            {"estimar_tiempo": estimar},
        )

    def _recomendacion_guardada(self, proyecto: Proyecto) -> RecomendacionPrueba:
        datos = dict(self._leer(proyecto, "recomendacion.json"))
        datos["diagnosticos"] = [DiagnosticoVariable(**d) for d in datos["diagnosticos"]]
        datos["alternativas"] = [AlternativaPrueba(**a) for a in datos["alternativas"]]
        return RecomendacionPrueba(**datos)

    def evaluar_prueba(self, proyecto_id: str, prueba: str, max_k: int | None) -> dict[str, Any]:
        """Advertencias si la prueba o el max_k elegidos contradicen los datos (no guarda nada)."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "recomendacion")
        evaluacion = evaluar_eleccion(self._recomendacion_guardada(proyecto), prueba, max_k)
        return a_diccionario_serializable(evaluacion)

    # --- Configuración de PC -------------------------------------------------------------------

    def configuracion_pc(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        if "configuracion_pc" in self.etapas.vigentes(proyecto_id):
            return {"configuracion": self._leer(proyecto, "pc.json"), "guardada": True}
        return {"configuracion": self.plantilla_configuracion_pc(proyecto_id), "guardada": False}

    def plantilla_configuracion_pc(self, proyecto_id: str) -> dict[str, Any]:
        """Todas las variables en un nivel y el objetivo al final, con la prueba recomendada."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        prueba, max_k = None, None
        if "recomendacion" in self.etapas.vigentes(proyecto_id):
            recomendacion = self._leer(proyecto, "recomendacion.json")
            prueba, max_k = recomendacion["prueba"], recomendacion.get("max_k_sugerido")
        datos = self._datos_preparados(proyecto)
        if prueba is None:
            prueba = recomendar_prueba(datos, estimar=False).prueba
        configuracion = configuracion_por_defecto(list(datos.train.columns), datos.objetivo, prueba, max_k)
        return a_diccionario_serializable(configuracion)

    def _problemas_configuracion(self, proyecto: Proyecto, datos: dict[str, Any]):
        receta = self._leer(proyecto, "receta.json")
        variables = [c["nombre"] for c in receta["columnas"]]
        try:
            configuracion = configuracion_desde_diccionario(datos)
        except ErrorConfiguracionPC as error:
            raise invalido("CONFIGURACION_NO_VALIDA", str(error)) from error
        return (
            configuracion,
            problemas_configuracion(configuracion, variables, receta["objetivo"]),
            advertencias_configuracion(configuracion, receta["objetivo"]),
        )

    def validar_configuracion_pc(self, proyecto_id: str, datos: dict[str, Any]) -> dict[str, Any]:
        """Errores y advertencias de la configuración sin guardarla."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        _, errores, advertencias = self._problemas_configuracion(proyecto, datos)
        return a_diccionario_serializable(
            {"valida": not errores, "errores": errores, "advertencias": advertencias}
        )

    def guardar_configuracion_pc(self, proyecto_id: str, datos: dict[str, Any]) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        configuracion, errores, _ = self._problemas_configuracion(proyecto, datos)
        if errores:
            raise invalido(
                "CONFIGURACION_NO_VALIDA", errores[0].mensaje, a_diccionario_serializable(errores)
            )
        contenido = a_diccionario_serializable(configuracion)
        self.etapas.preparar_escritura(proyecto_id, "configuracion_pc")
        self.archivos.escribir_json(self._ruta(proyecto, "pc.json"), contenido)
        self.etapas.registrar(proyecto_id, "configuracion_pc")
        return {"configuracion": contenido, "guardada": True}

    # --- Análisis PC (trabajo) -------------------------------------------------------------------

    def _grupos_redundantes(self, proyecto: Proyecto) -> list[list[str]]:
        revision = self._leer(proyecto, "revision.json")
        return [
            h["columnas_involucradas"] for h in revision["hallazgos"]
            if h["tipo"] == TipoHallazgo.GRUPO_REDUNDANTE
        ]

    def _funcion_pc(self, proyecto_id: str) -> FuncionTrabajo:
        def ejecutar(contexto: Contexto) -> str | None:
            proyecto = self.proyecto(proyecto_id)
            datos = self._datos_preparados(proyecto)
            configuracion = configuracion_desde_diccionario(self._leer(proyecto, "pc.json"))
            carpeta = self._ruta(proyecto, CARPETA_PC)
            carpeta.mkdir(exist_ok=True)

            def progreso(avance: ProgresoBootstrap) -> None:
                hechas_ahora = avance.completadas - avance.completadas_al_inicio
                restantes = (
                    avance.segundos_esta_sesion / hechas_ahora * (avance.total - avance.completadas)
                    if hechas_ahora else None
                )
                contexto.reportar(
                    completadas=avance.completadas, total=avance.total, fallidas=avance.fallidas,
                    segundos=avance.segundos, restantes_s=restantes,
                )

            try:
                with self.grupo.uso() as ejecutor:
                    resultado = ejecutar_bootstrap(
                        datos, configuracion, cancelacion=contexto.cancelacion,
                        punto_control=carpeta / "punto_control.json", reanudar=contexto.reanudar,
                        progreso_detallado=progreso, ejecutor=ejecutor,
                        al_decidir_modo=lambda modo, procesos: contexto.detallar(modo=modo, procesos=procesos),
                    )
                    if not resultado.completo and resultado.ejecucion and resultado.ejecucion.modo_usado == "paralelo":
                        self.grupo.reciclar_al_liberar()
            except ErrorConfiguracionPC as error:
                raise invalido("CONFIGURACION_NO_VALIDA", str(error)) from error
            if not resultado.completo:
                return f"Se completaron {resultado.corridas_completadas} de {resultado.corridas_totales} corridas."
            spearman = matriz_spearman(datos.train, resultado.variables)
            grafo = agregar(resultado, datos, configuracion, spearman)
            caracterizacion = caracterizar(
                grafo, resultado, configuracion.modificables, self._grupos_redundantes(proyecto)
            )
            exportar(carpeta, configuracion, datos.receta, resultado, grafo, caracterizacion, spearman)
            self._indice_versiones(proyecto)
            self.etapas.registrar(proyecto_id, "analisis")
            return caracterizacion.mensaje

        return ejecutar

    def lanzar_pc(self, proyecto_id: str) -> Trabajo:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "analisis")
        self._exigir_columnas_permitidas(proyecto)
        self.etapas.preparar_escritura(proyecto_id, "analisis")
        return self.trabajos.iniciar(proyecto_id, "pc", self._funcion_pc(proyecto_id), {})

    def reanudar_trabajo(self, trabajo_id: str) -> Trabajo:
        trabajo, _ = self.trabajos.obtener(trabajo_id)
        proyecto = self.proyecto(trabajo.proyecto_id)
        self._exigir_columnas_permitidas(proyecto)
        if trabajo.tipo == "pc":
            self.etapas.exigir(trabajo.proyecto_id, "analisis")
            funcion = self._funcion_pc(trabajo.proyecto_id)
        else:
            self.etapas.exigir(trabajo.proyecto_id, "recomendacion")
            funcion = self._funcion_recomendacion(trabajo.proyecto_id, trabajo.parametros.get("estimar_tiempo", True))
        return self.trabajos.reanudar(trabajo_id, funcion)

    # --- Resultados y versiones --------------------------------------------------------------------
    #
    # pc/ guarda la versión 1 (la del análisis). Cada ajuste guardado (otro umbral u otras
    # orientaciones manuales, sin volver a ejecutar PC) crea pc/versiones/<n>/ con sus propios
    # resultado.json, grafo.png y CSV. pc/versiones.json es el índice: parámetros de cada versión
    # y la versión actual. Ninguna versión se modifica ni se borra; pc.json no cambia. Al
    # desactualizarse el análisis se archiva toda la carpeta pc/ (con sus versiones).

    def _carpeta_version(self, proyecto: Proyecto, version: int) -> Path:
        carpeta = self._ruta(proyecto, CARPETA_PC)
        return carpeta if version == 1 else carpeta / CARPETA_VERSIONES / str(version)

    @staticmethod
    def _entrada_version(
        version: int, base: int | None, agregacion: dict[str, Any], migrada: bool
    ) -> dict[str, Any]:
        return {
            "version": version,
            "base": base,
            "umbral_frecuencia": agregacion["umbral_frecuencia"],
            "orientaciones_manuales": agregacion["orientaciones_manuales"],
            "creada_en": ahora(),
            "migrada": migrada,
        }

    def _indice_versiones(self, proyecto: Proyecto) -> dict[str, Any]:
        """Índice de versiones. Si no existe lo crea con la versión 1; un resultado anterior a
        las versiones (sin las cuentas del bootstrap) se migra y se marca ``migrada``."""
        ruta = self._ruta(proyecto, f"{CARPETA_PC}/{INDICE_VERSIONES}")
        with self._cerrojo_versiones:
            if ruta.is_file():
                return self.archivos.leer_json(ruta)
            ruta_resultado = self._ruta(proyecto, f"{CARPETA_PC}/resultado.json")
            contenido = self.archivos.leer_json(ruta_resultado)
            migrada = not tiene_cuentas(contenido)
            if migrada:
                train = self._datos_preparados(proyecto).train
                try:
                    contenido = migrar_resultado(contenido, matriz_spearman(train, contenido["variables"]))
                except ErrorReagregacion as error:
                    raise conflicto("RESULTADO_NO_AJUSTABLE", str(error)) from error
                self.archivos.escribir_json(ruta_resultado, contenido)
            indice = {
                "version_actual": 1,
                "versiones": [self._entrada_version(1, None, contenido["agregacion"], migrada)],
            }
            self.archivos.escribir_json(ruta, indice)
            return indice

    def _version_pedida(self, proyecto: Proyecto, version: int | None) -> tuple[dict[str, Any], int]:
        indice = self._indice_versiones(proyecto)
        numero = indice["version_actual"] if version is None else version
        if numero not in {v["version"] for v in indice["versiones"]}:
            raise no_encontrado(f"No existe la versión {numero} del resultado.", "VERSION_NO_ENCONTRADA")
        return indice, numero

    def _contenido_original(self, proyecto: Proyecto) -> dict[str, Any]:
        self._indice_versiones(proyecto)  # migra el resultado si hace falta
        return self._leer(proyecto, f"{CARPETA_PC}/resultado.json")

    def _avisos(self, proyecto: Proyecto, contenido: dict[str, Any]) -> list[Any]:
        """Advertencias de interpretación: resultado, revisión y prueba recomendada."""
        hallazgos = self._leer(proyecto, "revision.json").get("hallazgos", [])
        prueba = None
        if "recomendacion" in self.etapas.vigentes(proyecto.id):
            prueba = self._leer(proyecto, "recomendacion.json").get("prueba")
        return avisos_resultado(contenido, hallazgos, prueba)

    def _vista_resultado(self, proyecto: Proyecto, contenido: dict[str, Any], version: int | None) -> dict[str, Any]:
        configuracion, agregacion = contenido["configuracion"], contenido["agregacion"]
        columnas = disposicion_por_niveles(
            contenido["variables"], [(a["origen"], a["destino"]) for a in contenido["aristas"]],
            configuracion["niveles"], configuracion.get("nombres_niveles"),
        )
        vista = {k: v for k, v in contenido.items() if k not in ("cuentas", "spearman")}
        vista.update(
            version=version,
            etiqueta=etiqueta_version(
                agregacion["umbral_frecuencia"], configuracion["umbral_frecuencia"],
                orientaciones_nuevas(agregacion, configuracion),
            ),
            avisos=a_diccionario_serializable(self._avisos(proyecto, contenido)),
            disposicion=[{"titulo": titulo, "variables": variables} for titulo, variables in columnas],
        )
        return vista

    def _vista_versiones(self, proyecto: Proyecto, indice: dict[str, Any]) -> dict[str, Any]:
        configuracion = self._leer(proyecto, f"{CARPETA_PC}/resultado.json")["configuracion"]
        original = configuracion["umbral_frecuencia"]
        return {
            "version_actual": indice["version_actual"],
            "umbral_original": original,
            "versiones": [
                {**v, "etiqueta": etiqueta_version(v["umbral_frecuencia"], original, orientaciones_nuevas(v, configuracion))}
                for v in indice["versiones"]
            ],
        }

    def resultado(self, proyecto_id: str, version: int | None = None) -> dict[str, Any]:
        """Resultado de una versión (por defecto, la actual)."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        _, numero = self._version_pedida(proyecto, version)
        contenido = self.archivos.leer_json(self._carpeta_version(proyecto, numero) / "resultado.json")
        return self._vista_resultado(proyecto, contenido, numero)

    def versiones(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        return self._vista_versiones(proyecto, self._indice_versiones(proyecto))

    def _reagregar(
        self, proyecto: Proyecto, umbral: float, orientaciones: list[dict[str, Any]]
    ) -> Reagregacion:
        try:
            return reagregar(self._contenido_original(proyecto), umbral, orientaciones)
        except ErrorReagregacion as error:
            raise invalido(
                "AJUSTE_NO_VALIDO", str(error), a_diccionario_serializable(error.problemas)
            ) from error

    def previsualizar_reagregacion(
        self, proyecto_id: str, umbral: float, orientaciones: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Resultado con otro umbral u otras orientaciones, sin guardar nada."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        reagregado = self._reagregar(proyecto, umbral, orientaciones)
        return self._vista_resultado(proyecto, reagregado.contenido, None)

    def guardar_version(
        self, proyecto_id: str, umbral: float, orientaciones: list[dict[str, Any]], base: int | None
    ) -> dict[str, Any]:
        """Guarda el ajuste como una versión nueva (sin tocar las anteriores) y la hace actual."""
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        if base is not None:
            self._version_pedida(proyecto, base)
        reagregado = self._reagregar(proyecto, umbral, orientaciones)
        ruta = self._ruta(proyecto, f"{CARPETA_PC}/{INDICE_VERSIONES}")
        with self._cerrojo_versiones:
            indice = self.archivos.leer_json(ruta)
            numero = max(v["version"] for v in indice["versiones"]) + 1
            carpeta = self._carpeta_version(proyecto, numero)
            carpeta.mkdir(parents=True, exist_ok=True)
            escribir_reagregacion(carpeta, reagregado)
            indice["versiones"].append(
                self._entrada_version(numero, base, reagregado.contenido["agregacion"], False)
            )
            indice["version_actual"] = numero
            self.archivos.escribir_json(ruta, indice)
        return self._vista_versiones(proyecto, indice)

    def cambiar_version_actual(self, proyecto_id: str, version: int) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        with self._cerrojo_versiones:
            indice, numero = self._version_pedida(proyecto, version)
            indice["version_actual"] = numero
            self.archivos.escribir_json(self._ruta(proyecto, f"{CARPETA_PC}/{INDICE_VERSIONES}"), indice)
        return self._vista_versiones(proyecto, indice)

    def procedencia(self, proyecto_id: str) -> dict[str, Any]:
        """Con qué datos, decisiones y configuración se obtuvo el resultado."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        receta = self._leer(proyecto, "receta.json")
        configuracion = self._leer(proyecto, f"{CARPETA_PC}/resultado.json")["configuracion"]
        recomendacion = None
        if "recomendacion" in self.etapas.vigentes(proyecto_id):
            recomendacion = self._leer(proyecto, "recomendacion.json")
        origen = receta.get("origen") or {}
        aplicada = receta.get("separacion_aplicada") or {}
        return {
            "archivo": Path(proyecto.archivo_original).name,
            "hoja": origen.get("hoja"),
            "sha256": origen.get("sha256"),
            "objetivo": receta["objetivo"],
            "tipo_objetivo": receta.get("tipo_objetivo"),
            "filas_train": aplicada.get("filas_train"),
            "filas_test": aplicada.get("filas_test"),
            "decisiones": a_diccionario_serializable(resumen_decisiones(receta.get("decisiones") or {})),
            "separacion": a_diccionario_serializable(resumen_separacion(receta)),
            "configuracion": configuracion,
            "prueba_recomendada": recomendacion["prueba"] if recomendacion else None,
        }

    def archivo_resultado(self, proyecto_id: str, nombre: str, version: int | None = None) -> tuple[Path, str]:
        proyecto = self.proyecto(proyecto_id)
        if nombre not in ARCHIVOS_RESULTADO:
            raise no_encontrado(f"No existe el archivo de resultados '{nombre}'.", "ARCHIVO_NO_ENCONTRADO")
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        _, numero = self._version_pedida(proyecto, version)
        ruta = self._carpeta_version(proyecto, numero) / nombre
        if not dentro_de(ruta, self._ruta(proyecto, CARPETA_PC)) or not ruta.is_file():
            raise no_encontrado(f"No existe el archivo de resultados '{nombre}'.", "ARCHIVO_NO_ENCONTRADO")
        return ruta, ARCHIVOS_RESULTADO[nombre]

    def exportar(self, proyecto_id: str, carpeta_destino: str, version: int | None = None) -> dict[str, Any]:
        """Copia los archivos de una versión (por defecto, la actual) y la receta, y escribe
        ``informe.html`` (autocontenido) con el historial de versiones."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        destino = Path(carpeta_destino).expanduser()
        if not destino.is_dir():
            raise invalido(
                "CARPETA_NO_ENCONTRADA", f"La carpeta '{destino}' no existe.",
                [{"campo": "carpeta_destino", "mensaje": "La carpeta no existe."}],
            )
        indice, numero = self._version_pedida(proyecto, version)
        origen = self._carpeta_version(proyecto, numero)
        base = re.sub(r"[^\w\-]+", "_", proyecto.nombre).strip("_") or "proyecto"
        marca = datetime.now().strftime("%Y%m%d-%H%M%S")
        salida = destino / f"{base}_v{numero}_{marca}"
        sufijo = 2
        while salida.exists():
            salida = destino / f"{base}_v{numero}_{marca}_{sufijo}"
            sufijo += 1
        salida.mkdir()
        copiados = []
        for nombre in ARCHIVOS_RESULTADO:
            shutil.copy2(origen / nombre, salida / nombre)
            copiados.append(nombre)
        shutil.copy2(self._ruta(proyecto, "receta.json"), salida / "receta.json")
        copiados.append("receta.json")
        contenido = self.archivos.leer_json(origen / "resultado.json")
        receta = self._leer(proyecto, "receta.json")
        # La receta nombra la copia del proyecto; el informe muestra el archivo del usuario.
        receta["origen"] = {**(receta.get("origen") or {}), "archivo": Path(proyecto.archivo_original).name}
        informe = informe_html(
            contenido, receta, self._avisos(proyecto, contenido),
            (origen / "grafo.png").read_bytes(), indice["versiones"], numero, proyecto.nombre,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        (salida / "informe.html").write_text(informe, encoding="utf-8")
        copiados.append("informe.html")
        return {"carpeta": str(salida), "archivos": copiados, "version": numero}

    # --- Trabajos -------------------------------------------------------------------------------------

    def estado_trabajo(self, trabajo_id: str) -> dict[str, Any]:
        trabajo, restantes = self.trabajos.obtener(trabajo_id)
        return self.vista_trabajo(trabajo, restantes, self.trabajos.detalles(trabajo_id))

    @staticmethod
    def vista_trabajo(
        trabajo: Trabajo, restantes: float | None = None, detalles: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        datos = asdict(trabajo)
        datos["detalles"] = detalles if trabajo.estado == "en_curso" else None
        datos["segundos_transcurridos"] = datos.pop("segundos")
        datos["segundos_restantes_estimados"] = restantes if trabajo.estado == "en_curso" else None
        datos.pop("actualizado_en")
        return datos

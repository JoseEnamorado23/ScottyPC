"""Servicios de cada etapa del flujo: llaman al núcleo y gestionan archivos y etapas."""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pcapp_nucleo.analisis import analizar_dataset, resultado_a_diccionario
from pcapp_nucleo.caracterizacion import caracterizar
from pcapp_nucleo.carga import ErrorCarga, cargar_dataset, obtener_hojas_excel
from pcapp_nucleo.exportacion import exportar
from pcapp_nucleo.modelos import TipoHallazgo
from pcapp_nucleo.pc_bootstrap import ProgresoBootstrap, agregar, ejecutar_bootstrap
from pcapp_nucleo.pc_config import (
    ErrorConfiguracionPC,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    validar_configuracion,
)
from pcapp_nucleo.plantilla import generar_plantilla
from pcapp_nucleo.preparacion import (
    DatosPreparados,
    ErrorPreparacion,
    OrigenDatos,
    aplicar_receta,
    calcular_sha256,
    decisiones_desde_diccionario,
    preparar,
    receta_a_diccionario,
    receta_desde_diccionario,
)
from pcapp_nucleo.seleccion_prueba import recomendar_prueba
from pcapp_nucleo.utilidades import a_diccionario_serializable

from pcapp_servidor.almacenamiento.archivos import Archivos, dentro_de
from pcapp_servidor.almacenamiento.base_datos import BaseDatos, ahora
from pcapp_servidor.almacenamiento.repositorio import (
    Proyecto,
    RepositorioEtapas,
    RepositorioProyectos,
    RepositorioTrabajos,
    Trabajo,
)
from pcapp_servidor.configuracion import ConfiguracionServidor
from pcapp_servidor.errores import invalido, no_encontrado
from pcapp_servidor.etapas import GestorEtapas
from pcapp_servidor.procesos import GrupoProcesos
from pcapp_servidor.trabajos import Contexto, FuncionTrabajo, GestorTrabajos
from pcapp_servidor.validacion_campos import campo_de_configuracion, validar_decisiones

FORMATOS = (".csv", ".xlsx")
FILAS_VISTA_PREVIA = 20
CARPETA_PC = "pc"
ARCHIVOS_RESULTADO = {
    "grafo.png": "image/png",
    "aristas.csv": "text/csv",
    "mascara.csv": "text/csv",
    "matriz_frecuencias.csv": "text/csv",
    "resultado.json": "application/json",
}


class Servicios:
    def __init__(self, configuracion: ConfiguracionServidor, base: BaseDatos) -> None:
        self.archivos = Archivos(configuracion.datos)
        self.proyectos = RepositorioProyectos(base)
        self.etapas = GestorEtapas(RepositorioEtapas(base), self.proyectos, self.archivos)
        self.trabajos = GestorTrabajos(RepositorioTrabajos(base))
        self.grupo = GrupoProcesos(configuracion.procesos)

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
        return datos

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

    def plantilla_decisiones(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "decisiones")
        informe = analizar_dataset(self._cargar(proyecto, proyecto.hoja), proyecto.objetivo).informe
        return a_diccionario_serializable(generar_plantilla(informe))

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

    def preparar(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "preparacion")
        decisiones = decisiones_desde_diccionario(self._leer(proyecto, "decisiones.json"))
        origen = OrigenDatos(archivo=proyecto.archivo, hoja=proyecto.hoja, sha256=proyecto.sha256)
        try:
            datos = preparar(self._cargar(proyecto, proyecto.hoja), proyecto.objetivo, decisiones, origen=origen)
        except ErrorPreparacion as error:
            raise invalido("PREPARACION_NO_VALIDA", str(error)) from error
        self.etapas.preparar_escritura(proyecto_id, "preparacion")
        self.archivos.escribir_json(self._ruta(proyecto, "receta.json"), receta_a_diccionario(datos.receta))
        datos.train.to_csv(self._ruta(proyecto, "train.csv"), index=False)
        datos.test.to_csv(self._ruta(proyecto, "test.csv"), index=False)
        self.etapas.registrar(proyecto_id, "preparacion")
        faltantes = datos.train.drop(columns=[datos.objetivo]).isna().sum()
        return {
            "filas_train": int(len(datos.train)),
            "filas_test": int(len(datos.test)),
            "tipo_objetivo": datos.tipo_objetivo,
            "columnas": a_diccionario_serializable(datos.columnas),
            "faltantes_restantes": {str(c): int(n) for c, n in faltantes.items() if n},
            "separacion": datos.receta.separacion_aplicada,
            "advertencias": datos.receta.advertencias,
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
        self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "recomendacion")
        return self.trabajos.iniciar(
            proyecto_id, "recomendacion", self._funcion_recomendacion(proyecto_id, estimar),
            {"estimar_tiempo": estimar},
        )

    # --- Configuración de PC -------------------------------------------------------------------

    def configuracion_pc(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        if "configuracion_pc" in self.etapas.vigentes(proyecto_id):
            return {"configuracion": self._leer(proyecto, "pc.json"), "guardada": True}
        prueba, max_k = None, None
        if "recomendacion" in self.etapas.vigentes(proyecto_id):
            recomendacion = self._leer(proyecto, "recomendacion.json")
            prueba, max_k = recomendacion["prueba"], recomendacion.get("max_k_sugerido")
        datos = self._datos_preparados(proyecto)
        if prueba is None:
            prueba = recomendar_prueba(datos, estimar=False).prueba
        configuracion = configuracion_por_defecto(list(datos.train.columns), datos.objetivo, prueba, max_k)
        return {"configuracion": a_diccionario_serializable(configuracion), "guardada": False}

    def guardar_configuracion_pc(self, proyecto_id: str, datos: dict[str, Any]) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        receta = self._leer(proyecto, "receta.json")
        variables = [c["nombre"] for c in receta["columnas"]]
        try:
            configuracion = configuracion_desde_diccionario(datos)
            validar_configuracion(configuracion, variables, receta["objetivo"])
        except ErrorConfiguracionPC as error:
            raise invalido(
                "CONFIGURACION_NO_VALIDA", str(error),
                [{"campo": campo_de_configuracion(str(error)), "mensaje": str(error)}],
            ) from error
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
                    )
                    if not resultado.completo and resultado.ejecucion and resultado.ejecucion.modo_usado == "paralelo":
                        self.grupo.reciclar_al_liberar()
            except ErrorConfiguracionPC as error:
                raise invalido("CONFIGURACION_NO_VALIDA", str(error)) from error
            if not resultado.completo:
                return f"Se completaron {resultado.corridas_completadas} de {resultado.corridas_totales} corridas."
            grafo = agregar(resultado, datos, configuracion)
            caracterizacion = caracterizar(
                grafo, resultado, configuracion.modificables, self._grupos_redundantes(proyecto)
            )
            exportar(carpeta, configuracion, datos.receta, resultado, grafo, caracterizacion)
            self.etapas.registrar(proyecto_id, "analisis")
            return caracterizacion.mensaje

        return ejecutar

    def lanzar_pc(self, proyecto_id: str) -> Trabajo:
        self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self.etapas.exigir(proyecto_id, "analisis")
        self.etapas.preparar_escritura(proyecto_id, "analisis")
        return self.trabajos.iniciar(proyecto_id, "pc", self._funcion_pc(proyecto_id), {})

    def reanudar_trabajo(self, trabajo_id: str) -> Trabajo:
        trabajo, _ = self.trabajos.obtener(trabajo_id)
        self.proyecto(trabajo.proyecto_id)
        if trabajo.tipo == "pc":
            self.etapas.exigir(trabajo.proyecto_id, "analisis")
            funcion = self._funcion_pc(trabajo.proyecto_id)
        else:
            self.etapas.exigir(trabajo.proyecto_id, "recomendacion")
            funcion = self._funcion_recomendacion(trabajo.proyecto_id, trabajo.parametros.get("estimar_tiempo", True))
        return self.trabajos.reanudar(trabajo_id, funcion)

    # --- Resultados --------------------------------------------------------------------------------

    def resultado(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        return self._leer(proyecto, f"{CARPETA_PC}/resultado.json")

    def archivo_resultado(self, proyecto_id: str, nombre: str) -> tuple[Path, str]:
        proyecto = self.proyecto(proyecto_id)
        if nombre not in ARCHIVOS_RESULTADO:
            raise no_encontrado(f"No existe el archivo de resultados '{nombre}'.", "ARCHIVO_NO_ENCONTRADO")
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        carpeta = self._ruta(proyecto, CARPETA_PC)
        ruta = carpeta / nombre
        if not dentro_de(ruta, carpeta) or not ruta.is_file():
            raise no_encontrado(f"No existe el archivo de resultados '{nombre}'.", "ARCHIVO_NO_ENCONTRADO")
        return ruta, ARCHIVOS_RESULTADO[nombre]

    def exportar(self, proyecto_id: str, carpeta_destino: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        destino = Path(carpeta_destino).expanduser()
        if not destino.is_dir():
            raise invalido(
                "CARPETA_NO_ENCONTRADA", f"La carpeta '{destino}' no existe.",
                [{"campo": "carpeta_destino", "mensaje": "La carpeta no existe."}],
            )
        base = re.sub(r"[^\w\-]+", "_", proyecto.nombre).strip("_") or "proyecto"
        marca = datetime.now().strftime("%Y%m%d-%H%M%S")
        salida = destino / f"{base}_{marca}"
        numero = 2
        while salida.exists():
            salida = destino / f"{base}_{marca}_{numero}"
            numero += 1
        salida.mkdir()
        copiados = []
        for nombre in ARCHIVOS_RESULTADO:
            shutil.copy2(self._ruta(proyecto, f"{CARPETA_PC}/{nombre}"), salida / nombre)
            copiados.append(nombre)
        shutil.copy2(self._ruta(proyecto, "receta.json"), salida / "receta.json")
        copiados.append("receta.json")
        return {"carpeta": str(salida), "archivos": copiados}

    # --- Trabajos -------------------------------------------------------------------------------------

    def estado_trabajo(self, trabajo_id: str) -> dict[str, Any]:
        trabajo, restantes = self.trabajos.obtener(trabajo_id)
        return self.vista_trabajo(trabajo, restantes)

    @staticmethod
    def vista_trabajo(trabajo: Trabajo, restantes: float | None = None) -> dict[str, Any]:
        datos = asdict(trabajo)
        datos["segundos_transcurridos"] = datos.pop("segundos")
        datos["segundos_restantes_estimados"] = restantes if trabajo.estado == "en_curso" else None
        datos.pop("actualizado_en")
        return datos

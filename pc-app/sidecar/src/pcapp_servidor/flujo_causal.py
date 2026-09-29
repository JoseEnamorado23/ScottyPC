"""Servicios del modelo causal: aplicabilidad, construcción (trabajo), consulta y contrafactuales.

El modelo se guarda en ``modelo_causal/`` (``modelo_causal.json`` y ``evaluacion.json``) y
queda ligado a la versión del resultado de PC con la que se construyó (número y sha256 de
su ``resultado.json``). Cambiar la versión actual o guardar una nueva lo desactualiza.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pandas as pd
from pcapp_nucleo.causal import (
    ConfiguracionModeloCausal,
    ConstruccionCancelada,
    ContextoResultado,
    ErrorConfiguracionCausal,
    ErrorContrafactual,
    ErrorModeloCausal,
    Intervencion,
    ModeloCausal,
    caso_desde_test,
    caso_desde_valores,
    configuracion_desde_diccionario,
    construir_modelo,
    contrafactual,
    descripcion_variables,
    evaluar_aplicabilidad,
    hay_bloqueantes,
    modelo_desde_diccionario,
)
from pcapp_nucleo.causal.aplicabilidad import ANALISIS, BLOQUEANTE, ProblemaAplicabilidad
from pcapp_nucleo.causal.subgrafo import subgrafo_objetivo
from pcapp_nucleo.preparacion import DatosPreparados, calcular_sha256
from pcapp_nucleo.utilidades import a_diccionario_serializable

from pcapp_servidor.errores import conflicto, invalido
from pcapp_servidor.trabajos import Contexto, FuncionTrabajo

CARPETA_MODELO = "modelo_causal"
ARCHIVO_MODELO = "modelo_causal.json"
ARCHIVO_EVALUACION = "evaluacion.json"
FILAS_POR_PAGINA = 50


class ServiciosModeloCausal:
    """Mezcla de ``Servicios`` (usa sus repositorios, archivos y versiones del resultado)."""

    _cache_modelo: dict[str, tuple[float, ModeloCausal, DatosPreparados]]
    _cerrojo_modelo: threading.Lock

    def _iniciar_modelo_causal(self) -> None:
        self._cache_modelo = {}
        self._cerrojo_modelo = threading.Lock()

    # --- Auxiliares -------------------------------------------------------------------------

    def _resultado_actual(self, proyecto) -> tuple[dict[str, Any], int, str]:
        _, numero = self._version_pedida(proyecto, None)
        ruta = self._carpeta_version(proyecto, numero) / "resultado.json"
        return self.archivos.leer_json(ruta), numero, calcular_sha256(ruta)

    def _diagnosticos(self, proyecto) -> list[dict[str, Any]]:
        if "recomendacion" not in self.etapas.vigentes(proyecto.id):
            return []
        return self._leer(proyecto, "recomendacion.json").get("diagnosticos", [])

    @staticmethod
    def _configuracion_causal(datos: dict[str, Any] | None) -> ConfiguracionModeloCausal:
        try:
            return configuracion_desde_diccionario(datos)
        except ErrorConfiguracionCausal as error:
            raise invalido(
                "CONFIGURACION_NO_VALIDA", str(error), [{"campo": error.campo, "mensaje": str(error)}]
            ) from error

    def _problema_analisis(self, proyecto_id: str) -> ProblemaAplicabilidad | None:
        """Bloqueante si el análisis no está vigente (desactualizado o sin completar)."""
        estado = self.etapas.etapas.estados(proyecto_id).get("analisis")
        if estado == "vigente":
            return None
        if estado == "desactualizada":
            return ProblemaAplicabilidad(
                "RESULTADO_DESACTUALIZADO", BLOQUEANTE,
                "El resultado de PC está desactualizado: alguna etapa anterior cambió después del análisis.",
                "Vuelva a ejecutar el análisis.", ANALISIS,
            )
        return ProblemaAplicabilidad(
            "RESULTADO_INCOMPLETO", BLOQUEANTE,
            "No hay un resultado de PC completo.", "Ejecute (o reanude) el análisis hasta completarlo.", ANALISIS,
        )

    # --- Aplicabilidad ----------------------------------------------------------------------

    def aplicabilidad_modelo(self, proyecto_id: str, configuracion: dict[str, Any] | None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir(proyecto_id, "configuracion_pc")
        conf = self._configuracion_causal(configuracion)
        problema = self._problema_analisis(proyecto_id)
        if problema is not None:
            return {
                "problemas": a_diccionario_serializable([problema]), "bloqueado": True,
                "version_resultado": None, "subgrafo": None,
            }
        contenido, version, _ = self._resultado_actual(proyecto)
        datos = self._datos_preparados(proyecto)
        problemas = evaluar_aplicabilidad(contenido, datos, conf)
        sub = subgrafo_objetivo(list(contenido["variables"]), list(contenido["aristas"]), datos.objetivo)
        return {
            "problemas": a_diccionario_serializable(problemas),
            "bloqueado": hay_bloqueantes(problemas),
            "version_resultado": version,
            "subgrafo": {
                "objetivo": sub.objetivo,
                "variables": sub.variables,
                "padres": sub.padres,
                "aristas": [list(a) for a in sub.aristas],
                "sin_orientar": [list(a) for a in sub.sin_orientar],
                "fuera": sub.fuera,
            },
        }

    # --- Construcción (trabajo) ---------------------------------------------------------------

    def _funcion_modelo_causal(self, proyecto_id: str, configuracion: dict[str, Any]) -> FuncionTrabajo:
        def ejecutar(contexto: Contexto) -> str | None:
            proyecto = self.proyecto(proyecto_id)
            conf = self._configuracion_causal(configuracion)
            contenido, version, sha = self._resultado_actual(proyecto)
            datos = self._datos_preparados(proyecto)
            try:
                modelo_json, evaluacion = construir_modelo(
                    contenido, datos, self._diagnosticos(proyecto), conf, ContextoResultado(version, sha),
                    progreso=lambda hechas, total, _: contexto.reportar(completadas=hechas, total=total),
                    cancelacion=contexto.cancelacion,
                )
            except ConstruccionCancelada:
                return None
            except ErrorModeloCausal as error:
                raise conflicto(
                    "MODELO_NO_APLICABLE", str(error), {"problemas": a_diccionario_serializable(error.problemas)}
                ) from error
            if self._resultado_actual(proyecto)[2] != sha:
                raise conflicto(
                    "RESULTADO_CAMBIADO",
                    "La versión del resultado de PC cambió mientras se construía el modelo; vuelva a construirlo.",
                )
            self.etapas.preparar_escritura(proyecto_id, "modelo_causal")
            carpeta = self._ruta(proyecto, CARPETA_MODELO)
            carpeta.mkdir(exist_ok=True)
            self.archivos.escribir_json(carpeta / ARCHIVO_MODELO, modelo_json)
            self.archivos.escribir_json(carpeta / ARCHIVO_EVALUACION, evaluacion)
            self.etapas.registrar(proyecto_id, "modelo_causal")
            mecanismos = len(modelo_json["mecanismos"])
            return f"Modelo causal construido: {mecanismos} mecanismo(s) sobre la versión {version} del resultado."

        return ejecutar

    def lanzar_modelo_causal(self, proyecto_id: str, configuracion: dict[str, Any] | None) -> Any:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        conf = self._configuracion_causal(configuracion)
        problema = self._problema_analisis(proyecto_id)
        problemas = [problema] if problema else None
        if problemas is None:
            contenido, _, _ = self._resultado_actual(proyecto)
            problemas = evaluar_aplicabilidad(contenido, self._datos_preparados(proyecto), conf)
        if hay_bloqueantes(problemas):
            bloqueantes = [p for p in problemas if p.severidad == BLOQUEANTE]
            raise conflicto(
                "MODELO_NO_APLICABLE",
                f"No se puede construir el modelo causal: {bloqueantes[0].mensaje}",
                {"problemas": a_diccionario_serializable(problemas)},
            )
        parametros = {"configuracion": a_diccionario_serializable(configuracion or {})}
        return self.trabajos.iniciar(
            proyecto_id, "modelo_causal", self._funcion_modelo_causal(proyecto_id, parametros["configuracion"]),
            parametros,
        )

    def invalidar_modelo_causal(self, proyecto_id: str) -> None:
        """La versión actual del resultado cambió: el modelo causal queda desactualizado."""
        if "modelo_causal" in self.etapas.etapas.estados(proyecto_id):
            self.etapas.preparar_escritura(proyecto_id, "modelo_causal")

    # --- Consulta ----------------------------------------------------------------------------

    def _carpeta_modelo(self, proyecto) -> Path:
        return self._ruta(proyecto, CARPETA_MODELO)

    def _modelo_cargado(self, proyecto) -> tuple[ModeloCausal, DatosPreparados]:
        """Modelo y datos preparados, en caché mientras no cambie ``modelo_causal.json``."""
        ruta = self._carpeta_modelo(proyecto) / ARCHIVO_MODELO
        marca = ruta.stat().st_mtime
        with self._cerrojo_modelo:
            en_cache = self._cache_modelo.get(proyecto.id)
            if en_cache and en_cache[0] == marca:
                return en_cache[1], en_cache[2]
        datos = self._datos_preparados(proyecto)
        try:
            modelo = modelo_desde_diccionario(self.archivos.leer_json(ruta), datos.train)
        except ErrorModeloCausal as error:
            raise conflicto("MODELO_NO_REPRODUCIBLE", str(error)) from error
        with self._cerrojo_modelo:
            self._cache_modelo[proyecto.id] = (marca, modelo, datos)
        return modelo, datos

    def modelo_causal(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "modelo_causal")
        carpeta = self._carpeta_modelo(proyecto)
        modelo_json = self.archivos.leer_json(carpeta / ARCHIVO_MODELO)
        evaluacion = self.archivos.leer_json(carpeta / ARCHIVO_EVALUACION)
        _, version, sha = self._resultado_actual(proyecto)
        ligado = modelo_json["resultado_pc"]
        vigente = ligado["version"] == version and ligado["sha256"] == sha
        modelo, datos = self._modelo_cargado(proyecto)
        resumen = {k: v for k, v in modelo_json.items() if k not in ("columnas", "mecanismos")}
        resumen["mecanismos"] = {
            v: {k: m[k] for k in ("familia", "padres", "binaria", "seleccion")}
            for v, m in modelo_json["mecanismos"].items()
        }
        return {
            "modelo": resumen,
            "evaluacion": evaluacion,
            "controles": descripcion_variables(modelo),
            "vigente": vigente,
            "motivo_desactualizado": None if vigente else (
                f"El modelo se construyó con la versión {ligado['version']} del resultado y la actual es la "
                f"{version}: vuelva a construirlo."
            ),
            "filas_test": len(datos.test),
        }

    def casos_modelo(self, proyecto_id: str, pagina: int) -> dict[str, Any]:
        """Filas de test en unidades originales (para elegir un caso)."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "modelo_causal")
        modelo, datos = self._modelo_cargado(proyecto)
        test = datos.test
        inicio = max(pagina - 1, 0) * FILAS_POR_PAGINA
        controles = descripcion_variables(modelo)
        filas = []
        for indice, fila in test.iloc[inicio:inicio + FILAS_POR_PAGINA].iterrows():
            valores = {}
            for control in controles:
                if control["control"] == "grupo_one_hot":
                    dummies = {c: float(fila[c]) for c in control["columnas"] if c in fila and pd.notna(fila[c])}
                    valores[control["nombre"]] = modelo.unidades.categoria_de_grupo(control["nombre"], dummies)
                else:
                    x = fila[control["nombre"]]
                    valores[control["nombre"]] = None if pd.isna(x) else modelo.unidades.a_original(control["nombre"], float(x))
            observado = fila[modelo.objetivo]
            filas.append({
                "indice": int(indice),
                "valores": valores,
                "objetivo": None if pd.isna(observado) else modelo.unidades.a_original(modelo.objetivo, float(observado)),
            })
        return a_diccionario_serializable({
            "total": len(test), "pagina": max(pagina, 1), "por_pagina": FILAS_POR_PAGINA, "filas": filas,
        })

    def contrafactual_modelo(
        self, proyecto_id: str, caso: dict[str, Any], intervenciones: list[dict[str, Any]]
    ) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "modelo_causal")
        if (caso.get("indice_test") is None) == (caso.get("valores") is None):
            raise invalido(
                "CASO_NO_VALIDO", "Indique una fila de test (indice_test) o valores propios (valores), no ambos.",
                [{"campo": "caso", "mensaje": "Indique indice_test o valores."}],
            )
        modelo, datos = self._modelo_cargado(proyecto)
        try:
            if caso.get("indice_test") is not None:
                caso_nucleo = caso_desde_test(modelo, datos.test, int(caso["indice_test"]))
            else:
                caso_nucleo = caso_desde_valores(modelo, caso.get("valores") or {})
            resultado = contrafactual(
                modelo, caso_nucleo, [Intervencion(i["variable"], i["tipo"], i["valor"]) for i in intervenciones]
            )
        except ErrorContrafactual as error:
            detalles = [{"campo": error.campo, "mensaje": str(error)}] if error.campo else None
            raise invalido("CONTRAFACTUAL_NO_VALIDO", str(error), detalles) from error
        return a_diccionario_serializable(resultado)

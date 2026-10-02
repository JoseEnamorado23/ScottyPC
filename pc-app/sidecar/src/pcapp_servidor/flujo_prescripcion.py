"""Servicios de la prescripción: configuración, condiciones, calibración de μ (trabajo), caso,
lotes (trabajo), evaluación (trabajo) y exportación.

``prescripcion/prescripcion.json`` guarda la configuración, la huella del modelo causal al que
está ligada, el modelo de referencia (ajustado con train) y la calibración de μ. Los lotes y las
evaluaciones se guardan numerados en ``prescripcion/lotes/<n>/`` y ``prescripcion/evaluaciones/<n>/``,
sin sobrescribir los anteriores.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pcapp_nucleo.carga import ErrorCarga, cargar_dataset
from pcapp_nucleo.causal import ErrorContrafactual, caso_desde_test, caso_desde_valores, descripcion_variables
from pcapp_nucleo.causal.aplicabilidad import BLOQUEANTE
from pcapp_nucleo.preparacion import ErrorPreparacion, preparar_nuevos, receta_desde_diccionario
from pcapp_nucleo.prescripcion import (
    AUTOMATICO,
    AVISO_PERMANENTE,
    CalibracionCancelada,
    ErrorConfiguracionPrescripcion,
    LoteCancelado,
    ajustar_referencia,
    calibrar_mu,
    completar,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    evaluar_prescribibilidad,
    evaluar_prescriptor,
    informe_prescripcion_html,
    prescribir_caso,
    prescribir_lote,
    prescripciones_csv,
    problemas_configuracion,
    que_no_cumplen,
    referencia_desde_diccionario,
    variables_prescriptivas,
)
from pcapp_nucleo.utilidades import a_diccionario_serializable

from pcapp_servidor.almacenamiento.base_datos import ahora
from pcapp_servidor.errores import conflicto, invalido, no_encontrado
from pcapp_servidor.trabajos import Contexto, FuncionTrabajo

CARPETA = "prescripcion"
ARCHIVO = "prescripcion.json"
FILAS_POR_PAGINA = 50
FILTROS = ("alcanzado", "no_alcanzable", "requiere_revision", "ya_cumple")


class ServiciosPrescripcion:
    """Mezcla de ``Servicios`` (usa el modelo causal cargado, las etapas y los trabajos)."""

    # --- Auxiliares -------------------------------------------------------------------------

    def _carpeta_prescripcion(self, proyecto) -> Path:
        return self._ruta(proyecto, CARPETA)

    def _estado_modelo(self, proyecto):
        """(modelo, datos, vigente): vigente = etapa vigente y ligado a la versión actual de PC."""
        if self.etapas.etapas.estados(proyecto.id).get("modelo_causal") != "vigente":
            return None, None, False
        modelo, datos = self._modelo_cargado(proyecto)
        _, version, sha = self._resultado_actual(proyecto)
        ligado = modelo.datos["resultado_pc"]
        return modelo, datos, ligado["version"] == version and ligado["sha256"] == sha

    def _modelo_vigente(self, proyecto):
        modelo, datos, vigente = self._estado_modelo(proyecto)
        if not vigente:
            raise conflicto(
                "MODELO_NO_VIGENTE",
                "La prescripción necesita un modelo causal vigente: construya (o reconstruya) el modelo causal.",
            )
        return modelo, datos

    def _contenido_prescripcion(self, proyecto) -> dict[str, Any] | None:
        ruta = self._carpeta_prescripcion(proyecto) / ARCHIVO
        if "prescripcion" not in self.etapas.vigentes(proyecto.id) or not ruta.is_file():
            return None
        return self.archivos.leer_json(ruta)

    def modificables_prescripcion(self, proyecto) -> list[str] | None:
        """Lista de modificables de la configuración de prescripción, si existe (aunque esté
        desactualizada): Resultados la usa para las candidatas prescriptivas."""
        ruta = self._carpeta_prescripcion(proyecto) / ARCHIVO
        if not ruta.is_file():
            return None
        return list(self.archivos.leer_json(ruta)["configuracion"]["modificables"])

    def _configuracion_de(self, modelo, datos: dict[str, Any]):
        try:
            configuracion = configuracion_desde_diccionario(datos)
        except ErrorConfiguracionPrescripcion as error:
            raise invalido("CONFIGURACION_NO_VALIDA", str(error), a_diccionario_serializable(error.problemas)) from error
        return completar(modelo, configuracion)

    def _vista_configuracion(self, proyecto, modelo, configuracion, guardada: bool, contenido) -> dict[str, Any]:
        variables = variables_prescriptivas(modelo, configuracion.modificables)
        controles = [c for c in descripcion_variables(modelo) if c["nombre"] in variables.prescriptivas]
        grafo = self._resultado_actual(proyecto)[0]["variables"]
        return {
            "configuracion": a_diccionario_serializable(configuracion),
            "guardada": guardada,
            "prescriptivas": variables.prescriptivas,
            "sin_camino": variables.sin_camino,
            "desconocidas": variables.desconocidas,
            "controles": controles,
            "variables_grafo": [v for v in grafo if v != modelo.objetivo],
            "modificables_pc": list(self._leer(proyecto, "pc.json").get("modificables", [])),
            "medida": "probabilidad" if modelo.binario else "valor",
            "umbral_decision": modelo.umbral_decision,
            "calibracion": (contenido or {}).get("calibracion"),
            "mu_efectivo": self._mu_efectivo(contenido) if contenido else None,
            "aviso": AVISO_PERMANENTE,
        }

    @staticmethod
    def _mu_efectivo(contenido: dict[str, Any]) -> float | None:
        mu = contenido["configuracion"]["mu"]
        if mu != AUTOMATICO:
            return float(mu)
        calibracion = contenido.get("calibracion")
        return float(calibracion["mu"]) if calibracion else None

    # --- Configuración y condiciones ------------------------------------------------------------

    def configuracion_prescripcion(self, proyecto_id: str) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        modelo, _ = self._modelo_vigente(proyecto)
        contenido = self._contenido_prescripcion(proyecto)
        if contenido is not None:
            configuracion = self._configuracion_de(modelo, contenido["configuracion"])
            return self._vista_configuracion(proyecto, modelo, configuracion, True, contenido)
        modificables = self.modificables_prescripcion(proyecto) or self._leer(proyecto, "pc.json").get("modificables", [])
        return self._vista_configuracion(proyecto, modelo, configuracion_por_defecto(modelo, modificables), False, None)

    def validar_configuracion_prescripcion(self, proyecto_id: str, datos: dict[str, Any]) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        modelo, _ = self._modelo_vigente(proyecto)
        configuracion = self._configuracion_de(modelo, datos)
        errores = problemas_configuracion(modelo, configuracion)
        return {
            "valida": not errores,
            "errores": a_diccionario_serializable(errores),
            "condiciones": a_diccionario_serializable(evaluar_prescribibilidad(modelo, configuracion)),
            "configuracion": a_diccionario_serializable(configuracion),
        }

    def guardar_configuracion_prescripcion(self, proyecto_id: str, datos: dict[str, Any]) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        modelo, datos_preparados = self._modelo_vigente(proyecto)
        configuracion = self._configuracion_de(modelo, datos)
        errores = problemas_configuracion(modelo, configuracion)
        if errores:
            raise invalido("CONFIGURACION_NO_VALIDA", "Hay datos no válidos en la configuración.", a_diccionario_serializable(errores))
        referencia = ajustar_referencia(datos_preparados.train, modelo.objetivo, modelo.binario)
        contenido = {
            "configuracion": a_diccionario_serializable(configuracion),
            "modelo_causal": {"huella": modelo.datos["huella"], "version_resultado": modelo.datos["resultado_pc"]["version"]},
            "referencia": a_diccionario_serializable(referencia),
            "calibracion": None,
            "semilla": modelo.semilla,
            "guardada_en": ahora(),
        }
        self.etapas.preparar_escritura(proyecto_id, "prescripcion")
        carpeta = self._carpeta_prescripcion(proyecto)
        carpeta.mkdir(exist_ok=True)
        self.archivos.escribir_json(carpeta / ARCHIVO, contenido)
        self.etapas.registrar(proyecto_id, "prescripcion")
        return self._vista_configuracion(proyecto, modelo, configuracion, True, contenido)

    def condiciones_prescripcion(self, proyecto_id: str, datos: dict[str, Any] | None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        modelo, _, vigente = self._estado_modelo(proyecto)
        configuracion = None
        if modelo is not None:
            if datos is not None:
                configuracion = self._configuracion_de(modelo, datos)
            else:
                contenido = self._contenido_prescripcion(proyecto)
                configuracion = (
                    self._configuracion_de(modelo, contenido["configuracion"]) if contenido
                    else configuracion_por_defecto(modelo, self._leer(proyecto, "pc.json").get("modificables", []))
                )
        problemas = evaluar_prescribibilidad(modelo, configuracion, vigente)
        return {
            "problemas": a_diccionario_serializable(problemas),
            "bloqueado": any(p.severidad == BLOQUEANTE for p in problemas),
            "aviso": AVISO_PERMANENTE,
        }

    def _preparada(self, proyecto) -> tuple[Any, Any, Any, dict[str, Any], float]:
        """Modelo, datos, configuración, contenido y μ, exigiendo que se pueda prescribir."""
        self.etapas.exigir_vigente(proyecto.id, "prescripcion")
        modelo, datos = self._modelo_vigente(proyecto)
        contenido = self._contenido_prescripcion(proyecto)
        if contenido["modelo_causal"]["huella"] != modelo.datos["huella"]:
            raise conflicto("PRESCRIPCION_DESACTUALIZADA", "El modelo causal cambió: vuelva a guardar la configuración.")
        configuracion = self._configuracion_de(modelo, contenido["configuracion"])
        problemas = evaluar_prescribibilidad(modelo, configuracion)
        bloqueantes = [p for p in problemas if p.severidad == BLOQUEANTE]
        if bloqueantes:
            raise conflicto(
                "PRESCRIPCION_BLOQUEADA", f"No se puede prescribir: {bloqueantes[0].mensaje}",
                {"problemas": a_diccionario_serializable(problemas)},
            )
        mu = self._mu_efectivo(contenido)
        return modelo, datos, configuracion, contenido, mu

    def _exigir_mu(self, mu: float | None) -> float:
        if mu is None:
            raise conflicto(
                "MU_SIN_CALIBRAR", "μ es automático y todavía no se calibró: ejecute la calibración de μ o fije un valor.",
            )
        return mu

    # --- Calibración de μ (trabajo) ---------------------------------------------------------------

    def _funcion_calibracion(self, proyecto_id: str) -> FuncionTrabajo:
        def ejecutar(contexto: Contexto) -> str | None:
            proyecto = self.proyecto(proyecto_id)
            modelo, datos, configuracion, contenido, _ = self._preparada(proyecto)
            try:
                with self.grupo.uso() as ejecutor:
                    resultado = calibrar_mu(
                        modelo, datos.train, configuracion,
                        progreso=lambda hechos, total: contexto.reportar(completadas=hechos, total=total),
                        cancelacion=contexto.cancelacion, ejecutor=ejecutor,
                    )
            except CalibracionCancelada:
                return None
            contenido["calibracion"] = {**a_diccionario_serializable(resultado), "calibrada_en": ahora()}
            self.archivos.escribir_json(self._carpeta_prescripcion(proyecto) / ARCHIVO, contenido)
            return f"μ calibrado: {resultado.mu:g} ({resultado.alcanzables} casos alcanzables de train)."

        return ejecutar

    def lanzar_calibracion_mu(self, proyecto_id: str):
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        self._preparada(proyecto)
        return self.trabajos.iniciar(proyecto_id, "calibracion_mu", self._funcion_calibracion(proyecto_id), {})

    # --- Caso individual -------------------------------------------------------------------------

    def prescribir_caso_api(self, proyecto_id: str, caso: dict[str, Any]) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        modelo, datos, configuracion, contenido, mu = self._preparada(proyecto)
        mu = self._exigir_mu(mu)
        if (caso.get("indice_test") is None) == (caso.get("valores") is None):
            raise invalido(
                "CASO_NO_VALIDO", "Indique una fila de test (indice_test) o valores propios (valores), no ambos.",
                [{"campo": "caso", "mensaje": "Indique indice_test o valores."}],
            )
        referencia = referencia_desde_diccionario(contenido["referencia"])
        try:
            if caso.get("indice_test") is not None:
                indice = int(caso["indice_test"])
                caso_nucleo = caso_desde_test(modelo, datos.test, indice)
                fila = datos.test.loc[[indice]].drop(columns=[modelo.objetivo])
            else:
                caso_nucleo = caso_desde_valores(modelo, caso.get("valores") or {})
                fila = None
        except ErrorContrafactual as error:
            detalles = [{"campo": error.campo, "mensaje": str(error)}] if error.campo else None
            raise invalido("CASO_NO_VALIDO", str(error), detalles) from error
        resultado = prescribir_caso(modelo, caso_nucleo, configuracion, mu, referencia, fila)
        return a_diccionario_serializable(resultado)

    # --- Lotes (trabajo) ---------------------------------------------------------------------------

    def _siguiente(self, carpeta: Path) -> int:
        carpeta.mkdir(parents=True, exist_ok=True)
        numeros = [int(p.name) for p in carpeta.iterdir() if p.is_dir() and p.name.isdigit()]
        return max(numeros, default=0) + 1

    def _filas_lote(self, proyecto, modelo, datos, configuracion, origen: str, ruta_csv: str | None):
        if origen == "test":
            return que_no_cumplen(modelo, datos.test.drop(columns=[modelo.objetivo]), configuracion), [], []
        ruta = Path(ruta_csv or "").expanduser()
        if not ruta.is_file():
            raise invalido("ARCHIVO_NO_ENCONTRADO", f"No existe el archivo '{ruta}'.", [{"campo": "ruta_csv", "mensaje": "No existe el archivo."}])
        try:
            dataframe = cargar_dataset(ruta)
        except ErrorCarga as error:
            raise invalido(error.problema.codigo, error.problema.mensaje, [{"campo": "ruta_csv", "mensaje": error.problema.mensaje}]) from error
        receta = receta_desde_diccionario(self._leer(proyecto, "receta.json"))
        try:
            nuevos = preparar_nuevos(dataframe, receta)
        except ErrorPreparacion as error:
            raise invalido("COLUMNAS_NO_VALIDAS", str(error), [{"campo": "ruta_csv", "mensaje": str(error)}]) from error
        return nuevos.datos, a_diccionario_serializable(nuevos.problemas), nuevos.columnas_ignoradas

    def _funcion_lote(self, proyecto_id: str, origen: str, ruta_csv: str | None) -> FuncionTrabajo:
        def ejecutar(contexto: Contexto) -> str | None:
            proyecto = self.proyecto(proyecto_id)
            modelo, datos, configuracion, contenido, mu = self._preparada(proyecto)
            mu = self._exigir_mu(mu)
            filas, problemas, ignoradas = self._filas_lote(proyecto, modelo, datos, configuracion, origen, ruta_csv)
            referencia = referencia_desde_diccionario(contenido["referencia"])
            try:
                with self.grupo.uso() as ejecutor:
                    resultados = prescribir_lote(
                        modelo, filas, configuracion, mu, referencia,
                        progreso=lambda hechos, total: contexto.reportar(completadas=hechos, total=total),
                        cancelacion=contexto.cancelacion, ejecutor=ejecutor,
                    )
            except LoteCancelado:
                return None
            carpeta = self._carpeta_prescripcion(proyecto) / "lotes"
            numero = self._siguiente(carpeta)
            destino = carpeta / str(numero)
            destino.mkdir()
            meta = {
                "numero": numero, "origen": origen, "ruta_csv": ruta_csv, "casos": len(resultados), "mu": mu,
                "optimizador": configuracion.optimizador, "filas_con_problemas": problemas, "columnas_ignoradas": ignoradas,
                "huella_modelo": modelo.datos["huella"], "creado_en": ahora(),
                "resumen": _resumen(resultados),
            }
            self.archivos.escribir_json(destino / "meta.json", meta)
            self.archivos.escribir_json(destino / "resultados.json", resultados)
            return f"Lote {numero}: {len(resultados)} casos prescritos."

        return ejecutar

    def lanzar_lote(self, proyecto_id: str, origen: str, ruta_csv: str | None):
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        _, _, _, _, mu = self._preparada(proyecto)
        self._exigir_mu(mu)
        if origen == "csv" and not Path(ruta_csv or "").expanduser().is_file():
            raise invalido("ARCHIVO_NO_ENCONTRADO", f"No existe el archivo '{ruta_csv}'.", [{"campo": "ruta_csv", "mensaje": "No existe el archivo."}])
        return self.trabajos.iniciar(
            proyecto_id, "lote_prescripcion", self._funcion_lote(proyecto_id, origen, ruta_csv),
            {"origen": origen, "ruta_csv": ruta_csv},
        )

    def _listar(self, proyecto, subcarpeta: str) -> list[dict[str, Any]]:
        carpeta = self._carpeta_prescripcion(proyecto) / subcarpeta
        if not carpeta.is_dir():
            return []
        numeros = sorted(int(p.name) for p in carpeta.iterdir() if p.is_dir() and p.name.isdigit())
        return [self.archivos.leer_json(carpeta / str(n) / "meta.json") for n in numeros]

    def lotes(self, proyecto_id: str) -> list[dict[str, Any]]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "prescripcion")
        return self._listar(proyecto, "lotes")

    def _leer_lote(self, proyecto, numero: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        carpeta = self._carpeta_prescripcion(proyecto) / "lotes" / str(numero)
        if not (carpeta / "meta.json").is_file():
            raise no_encontrado(f"No existe el lote {numero}.", "LOTE_NO_ENCONTRADO")
        return self.archivos.leer_json(carpeta / "meta.json"), self.archivos.leer_json(carpeta / "resultados.json")

    def lote(self, proyecto_id: str, numero: int, pagina: int, filtro: str | None) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "prescripcion")
        meta, resultados = self._leer_lote(proyecto, numero)
        if filtro is not None and filtro not in FILTROS:
            raise invalido("FILTRO_NO_VALIDO", f"Filtro no válido: {filtro}.", [{"campo": "filtro", "mensaje": "Filtro no válido."}])
        filtrados = [r for r in resultados if _cumple_filtro(r, filtro)]
        inicio = max(pagina - 1, 0) * FILAS_POR_PAGINA
        return {
            "meta": meta, "total": len(filtrados), "pagina": max(pagina, 1), "por_pagina": FILAS_POR_PAGINA,
            "filas": filtrados[inicio:inicio + FILAS_POR_PAGINA],
        }

    # --- Evaluación (trabajo) ------------------------------------------------------------------------

    def _funcion_evaluacion(self, proyecto_id: str) -> FuncionTrabajo:
        def ejecutar(contexto: Contexto) -> str | None:
            proyecto = self.proyecto(proyecto_id)
            modelo, datos, configuracion, contenido, mu = self._preparada(proyecto)
            mu = self._exigir_mu(mu)
            referencia = referencia_desde_diccionario(contenido["referencia"])
            try:
                with self.grupo.uso() as ejecutor:
                    evaluacion = evaluar_prescriptor(
                        modelo, datos.test, configuracion, mu, referencia,
                        progreso=lambda hechos, total: contexto.reportar(completadas=hechos, total=total),
                        cancelacion=contexto.cancelacion, ejecutor=ejecutor,
                    )
            except LoteCancelado:
                return None
            carpeta = self._carpeta_prescripcion(proyecto) / "evaluaciones"
            numero = self._siguiente(carpeta)
            destino = carpeta / str(numero)
            destino.mkdir()
            meta = {
                "numero": numero, "casos": evaluacion.casos, "mu": mu, "optimizador": configuracion.optimizador,
                "tasa_exito": evaluacion.tasa_exito, "huella_modelo": modelo.datos["huella"], "creado_en": ahora(),
            }
            self.archivos.escribir_json(destino / "meta.json", meta)
            self.archivos.escribir_json(destino / "evaluacion.json", a_diccionario_serializable(evaluacion))
            return f"Evaluación {numero}: éxito en el {100 * evaluacion.tasa_exito:.1f} % de {evaluacion.casos} casos."

        return ejecutar

    def lanzar_evaluacion(self, proyecto_id: str):
        proyecto = self.proyecto(proyecto_id)
        self.trabajos.exigir_sin_activo(proyecto_id)
        _, _, _, _, mu = self._preparada(proyecto)
        self._exigir_mu(mu)
        return self.trabajos.iniciar(proyecto_id, "evaluacion_prescripcion", self._funcion_evaluacion(proyecto_id), {})

    def evaluaciones(self, proyecto_id: str) -> list[dict[str, Any]]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "prescripcion")
        return self._listar(proyecto, "evaluaciones")

    def evaluacion(self, proyecto_id: str, numero: int) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "prescripcion")
        ruta = self._carpeta_prescripcion(proyecto) / "evaluaciones" / str(numero)
        if not (ruta / "evaluacion.json").is_file():
            raise no_encontrado(f"No existe la evaluación {numero}.", "EVALUACION_NO_ENCONTRADA")
        return {"meta": self.archivos.leer_json(ruta / "meta.json"), "evaluacion": self.archivos.leer_json(ruta / "evaluacion.json")}

    # --- Exportación ---------------------------------------------------------------------------------

    def exportar_prescripcion(
        self, proyecto_id: str, carpeta_destino: str, lote: int | None, evaluacion: int | None
    ) -> dict[str, Any]:
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "prescripcion")
        modelo, _ = self._modelo_vigente(proyecto)
        contenido = self._contenido_prescripcion(proyecto)
        destino = Path(carpeta_destino).expanduser()
        if not destino.is_dir():
            raise invalido(
                "CARPETA_NO_ENCONTRADA", f"La carpeta '{destino}' no existe.",
                [{"campo": "carpeta_destino", "mensaje": "La carpeta no existe."}],
            )
        base = re.sub(r"[^\w\-]+", "_", proyecto.nombre).strip("_") or "proyecto"
        salida = destino / f"{base}_prescripcion_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        sufijo = 2
        while salida.exists():
            salida = destino / f"{base}_prescripcion_{datetime.now().strftime('%Y%m%d-%H%M%S')}_{sufijo}"
            sufijo += 1
        salida.mkdir()
        archivos = []
        resultados = None
        if lote is not None:
            _, resultados = self._leer_lote(proyecto, lote)
            (salida / "prescripciones.csv").write_text(prescripciones_csv(resultados), encoding="utf-8")
            archivos.append("prescripciones.csv")
        datos_evaluacion = self.evaluacion(proyecto_id, evaluacion)["evaluacion"] if evaluacion is not None else None
        configuracion = self._configuracion_de(modelo, contenido["configuracion"])
        advertencias = [p for p in evaluar_prescribibilidad(modelo, configuracion) if p.severidad != BLOQUEANTE]
        html = informe_prescripcion_html(
            proyecto.nombre, datetime.now().strftime("%Y-%m-%d %H:%M"), contenido["configuracion"],
            contenido.get("calibracion"), a_diccionario_serializable(advertencias), datos_evaluacion, resultados,
            "probabilidad" if modelo.binario else "valor",
        )
        (salida / "informe_prescripcion.html").write_text(html, encoding="utf-8")
        archivos.append("informe_prescripcion.html")
        return {"carpeta": str(salida), "archivos": archivos}


def _cumple_filtro(r: dict[str, Any], filtro: str | None) -> bool:
    if filtro is None:
        return True
    if filtro == "alcanzado":
        return r["alcanzado"] and not r["ya_cumple"]
    if filtro == "no_alcanzable":
        return not r["alcanzado"]
    if filtro == "ya_cumple":
        return r["ya_cumple"]
    return r["requiere_revision"]


def _resumen(resultados: list[dict[str, Any]]) -> dict[str, int]:
    return {filtro: sum(1 for r in resultados if _cumple_filtro(r, filtro)) for filtro in FILTROS}

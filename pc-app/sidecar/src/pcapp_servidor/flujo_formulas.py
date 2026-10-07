"""Servicios del explorador de fórmulas: trazas de las decisiones de cada etapa (solo lectura)."""

from __future__ import annotations

from typing import Any

from pcapp_nucleo.causal import ModeloCausal
from pcapp_nucleo.formulas import (
    explicar_analisis_pc,
    explicar_calibracion,
    explicar_caso,
    explicar_modelo_causal,
    explicar_seleccion_prueba,
)
from pcapp_nucleo.prescripcion import referencia_desde_diccionario
from pcapp_nucleo.utilidades import a_diccionario_serializable

from pcapp_servidor.errores import conflicto, invalido
from pcapp_servidor.flujo_causal import ARCHIVO_EVALUACION, ARCHIVO_MODELO


class ServiciosFormulas:
    """Mezcla de ``Servicios`` (usa ``proyecto``, ``etapas`` y ``_recomendacion_guardada``)."""

    def formulas_seleccion_prueba(
        self, proyecto_id: str, umbrales: dict[str, float], k: int
    ) -> dict[str, Any]:
        """Traza de la selección de prueba con la evidencia de la recomendación guardada.

        No guarda nada ni lee el dataset: ``umbrales`` y ``k`` solo cambian lo que se muestra.
        """
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "recomendacion")
        try:
            traza = explicar_seleccion_prueba(self._recomendacion_guardada(proyecto), umbrales, k)
        except ValueError as error:
            raise invalido("UMBRAL_INVALIDO", str(error)) from error
        return a_diccionario_serializable(traza)

    def formulas_analisis_pc(
        self, proyecto_id: str, umbral: float | None, version: int | None
    ) -> dict[str, Any]:
        """Traza del grafo agregado de una versión del resultado (por defecto, la actual).

        No guarda nada ni vuelve a ejecutar PC: ``umbral`` solo cambia lo que se muestra.
        """
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "analisis")
        _, numero = self._version_pedida(proyecto, version)
        contenido = self.archivos.leer_json(self._carpeta_version(proyecto, numero) / "resultado.json")
        try:
            traza = explicar_analisis_pc(contenido, umbral)
        except ValueError as error:
            raise invalido("UMBRAL_INVALIDO", str(error)) from error
        return {**a_diccionario_serializable(traza), "version": numero}

    def formulas_modelo_causal(
        self, proyecto_id: str, umbrales: dict[str, float], valores: dict[str, float]
    ) -> dict[str, Any]:
        """Traza del modelo causal guardado. No reajusta ni guarda nada: ``umbrales`` reevalúa las
        decisiones sobre las puntuaciones guardadas y ``valores`` es el caso en que se evalúa cada
        mecanismo (unidades preparadas)."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "modelo_causal")
        carpeta = self._carpeta_modelo(proyecto)
        modelo_json = self.archivos.leer_json(carpeta / ARCHIVO_MODELO)
        evaluacion = self.archivos.leer_json(carpeta / ARCHIVO_EVALUACION)
        try:
            traza = explicar_modelo_causal(modelo_json, evaluacion, umbrales, valores, ModeloCausal(modelo_json))
        except ValueError as error:
            raise invalido("UMBRAL_INVALIDO", str(error)) from error
        return a_diccionario_serializable(traza)

    def formulas_calibracion(self, proyecto_id: str, exito: float | None) -> dict[str, Any]:
        """Regla de elección de μ sobre la rejilla guardada (409 si todavía no se calibró)."""
        proyecto = self.proyecto(proyecto_id)
        self.etapas.exigir_vigente(proyecto_id, "prescripcion")
        calibracion = (self._contenido_prescripcion(proyecto) or {}).get("calibracion")
        if not calibracion:
            raise conflicto("MU_SIN_CALIBRAR", "Todavía no se calibró μ: ejecute la calibración en Prescripción.")
        try:
            return a_diccionario_serializable(explicar_calibracion(calibracion, exito))
        except ValueError as error:
            raise invalido("UMBRAL_INVALIDO", str(error)) from error

    def formulas_caso_prescripcion(self, proyecto_id: str, caso: dict[str, Any], mu: float | None) -> dict[str, Any]:
        """Prescribe el caso como la pantalla de Prescripción (con ``mu`` si se indica) y descompone
        la función objetivo. No guarda nada."""
        proyecto = self.proyecto(proyecto_id)
        modelo, datos, configuracion, contenido, mu_efectivo = self._preparada(proyecto)
        mu = self._exigir_mu(mu_efectivo) if mu is None else mu
        referencia = referencia_desde_diccionario(contenido["referencia"])
        caso_nucleo, fila = self._caso_de_solicitud(modelo, datos, caso)
        try:
            traza = explicar_caso(modelo, caso_nucleo, configuracion, mu, referencia, fila)
        except ValueError as error:
            raise invalido("UMBRAL_INVALIDO", str(error)) from error
        return {**a_diccionario_serializable(traza), "mu_guardado": mu_efectivo}

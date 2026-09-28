"""Etapas del flujo, sus requisitos y la invalidación de las posteriores.

Al registrar (o rehacer) una etapa, sus archivos anteriores y los de todas las
etapas posteriores se mueven a ``anteriores/<fecha-hora>/`` y esas etapas
quedan desactualizadas. Una etapa solo puede ejecutarse si su requisito está
vigente; si no, la API responde 409.
"""

from __future__ import annotations

from pcapp_servidor.almacenamiento.archivos import Archivos
from pcapp_servidor.almacenamiento.repositorio import RepositorioEtapas, RepositorioProyectos
from pcapp_servidor.errores import conflicto

ETAPAS = ("revision", "decisiones", "preparacion", "recomendacion", "configuracion_pc", "analisis")

REQUISITOS: dict[str, str | None] = {
    "revision": None,
    "decisiones": "revision",
    "preparacion": "decisiones",
    "recomendacion": "preparacion",
    "configuracion_pc": "preparacion",
    "analisis": "configuracion_pc",
}

ARCHIVOS = {
    "revision": ["revision.json"],
    "decisiones": ["decisiones.json"],
    "preparacion": ["receta.json", "preparacion.json", "train.csv", "test.csv"],
    "recomendacion": ["recomendacion.json"],
    "configuracion_pc": ["pc.json"],
    "analisis": ["pc"],
}

_NOMBRES = {
    "revision": "la revisión",
    "decisiones": "las decisiones",
    "preparacion": "la preparación",
    "recomendacion": "la recomendación de prueba",
    "configuracion_pc": "la configuración de PC",
    "analisis": "el análisis",
}

_COMO_HACERLA = {
    "revision": "POST /proyectos/{id}/revision",
    "decisiones": "PUT /proyectos/{id}/decisiones",
    "preparacion": "POST /proyectos/{id}/preparar",
    "recomendacion": "POST /proyectos/{id}/recomendacion",
    "configuracion_pc": "PUT /proyectos/{id}/configuracion-pc",
    "analisis": "POST /proyectos/{id}/pc",
}


def posteriores(etapa: str) -> list[str]:
    return list(ETAPAS[ETAPAS.index(etapa) + 1:])


class GestorEtapas:
    def __init__(
        self, etapas: RepositorioEtapas, proyectos: RepositorioProyectos, archivos: Archivos
    ) -> None:
        self.etapas, self.proyectos, self.archivos = etapas, proyectos, archivos

    def vigentes(self, proyecto_id: str) -> set[str]:
        return {e for e, estado in self.etapas.estados(proyecto_id).items() if estado == "vigente"}

    def exigir(self, proyecto_id: str, etapa: str) -> None:
        """409 si el requisito de ``etapa`` no está vigente."""
        requisito = REQUISITOS[etapa]
        if requisito is not None and requisito not in self.vigentes(proyecto_id):
            raise conflicto(
                "ETAPA_REQUERIDA",
                f"Para {_NOMBRES[etapa]} primero se necesita {_NOMBRES[requisito]} vigente "
                f"({_COMO_HACERLA[requisito]}).",
                {"etapa": etapa, "requiere": requisito},
            )

    def exigir_vigente(self, proyecto_id: str, etapa: str) -> None:
        """409 si ``etapa`` misma no está vigente."""
        if etapa not in self.vigentes(proyecto_id):
            raise conflicto(
                "ETAPA_REQUERIDA",
                f"No hay {_NOMBRES[etapa]} vigente ({_COMO_HACERLA[etapa]}).",
                {"etapa": etapa, "requiere": etapa},
            )

    def preparar_escritura(self, proyecto_id: str, etapa: str, conservar: list[str] | None = None) -> None:
        """Archiva los archivos de ``etapa`` y de las posteriores, y marca las
        posteriores como desactualizadas. ``conservar`` excluye nombres del
        archivado (p. ej. la carpeta de un análisis que se va a reanudar)."""
        nombres = [n for e in (etapa, *posteriores(etapa)) for n in ARCHIVOS[e] if n not in (conservar or [])]
        self.archivos.archivar(proyecto_id, nombres)
        existentes = self.etapas.estados(proyecto_id)
        self.etapas.marcar(
            proyecto_id, {e: "desactualizada" for e in (etapa, *posteriores(etapa)) if e in existentes}
        )

    def registrar(self, proyecto_id: str, etapa: str) -> None:
        """Marca ``etapa`` como vigente (tras escribir sus archivos)."""
        self.etapas.marcar(proyecto_id, {etapa: "vigente"})
        self.proyectos.actualizar(proyecto_id, etapa_actual=etapa)

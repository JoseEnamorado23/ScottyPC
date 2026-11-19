"""Comando ``exportar-artefacto``: escribe el artefacto ``.scotty`` de un proyecto de Scotty PC."""

from __future__ import annotations

import sys
from pathlib import Path

from pcapp_nucleo.cli_comun import SALIDA_CORRECTA, SALIDA_ERROR, SEPARADOR, error


def ejecutar_exportar_artefacto(carpeta_proyecto: Path, destino: Path) -> int:
    """Exporta el proyecto, lo verifica (golden) y muestra el resumen. Código 1 si no se puede exportar."""
    from pcapp_nucleo.artefacto.exportar import ErrorExportacion, exportar_artefacto_completo

    def progreso(hechos: int, total: int, mensaje: str) -> None:
        print(f"[{hechos}/{total}] {mensaje}", file=sys.stderr, flush=True)

    try:
        resultado = exportar_artefacto_completo(carpeta_proyecto, destino, progreso=progreso)
    except ErrorExportacion as problema:
        error(f"Error: {problema}")
        return SALIDA_ERROR
    lineas = ["", SEPARADOR, "ARTEFACTO EXPORTADO", SEPARADOR, "", f"Archivo: {resultado.ruta}",
              f"Tamaño: {resultado.ruta.stat().st_size:,} bytes"]
    if resultado.advertencias:
        lineas += ["", "Advertencias (guardadas en el manifest):"]
        lineas += [f"- {a.mensaje}" for a in resultado.advertencias]
    if resultado.comparacion:
        c = resultado.comparacion
        lineas += ["", "Comparación informativa con Scotty PC:",
                   f"- acuerdo en 'alcanzado': {c['acuerdo_alcanzado']:.0%} de {c['casos']} casos",
                   f"- diferencia media de 'después': {c['diferencia_media_despues']:.2g}"]
    lineas += ["", "Resultado:", "EXPORTACIÓN COMPLETADA"]
    print("\n".join(lineas))
    return SALIDA_CORRECTA

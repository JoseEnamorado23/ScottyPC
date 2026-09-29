"""Exportación de los resultados de PC: JSON, CSV y figura del grafo.

Las funciones ``tabla_*``, ``matriz_*`` y ``resultado_a_diccionario`` son
puras; ``exportar`` escribe los archivos en una carpeta.

CSV de matrices (formato pandas): primera columna con los nombres, fila =
origen, columna = destino.

- ``mascara.csv``: 1 si se acepta la arista origen→destino (incluidas las
  manuales); una arista sin orientar pone 1 en las dos direcciones.
- ``matriz_frecuencias.csv``: frecuencia de origen→destino más la frecuencia
  sin orientar, sobre las corridas válidas.

``resultado.json`` guarda además las cuentas exactas del bootstrap
(``cuentas``), el ρ de Spearman de todos los pares (``spearman``) y los
parámetros de la agregación (``agregacion``): con ellos
``reagregacion.reagregar`` rehace el grafo con otro umbral u otras
orientaciones manuales sin volver a ejecutar PC ni leer los datos.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo.caracterizacion import CAUSA_DIRECTA, Caracterizacion
from pcapp_nucleo.pc_bootstrap import GrafoAgregado, ResultadoBootstrap
from pcapp_nucleo.pc_config import ConfiguracionPC
from pcapp_nucleo.preparacion import Receta
from pcapp_nucleo.utilidades import a_diccionario_serializable

ARCHIVOS = ("resultado.json", "aristas.csv", "mascara.csv", "matriz_frecuencias.csv", "grafo.png")

_COLOR_OBJETIVO = "#c62828"
_COLOR_CAUSA = "#2e7d32"
_COLOR_NODO = "#eceff1"
_COLOR_POSITIVA = "#1565c0"
_COLOR_NEGATIVA = "#c62828"
_COLOR_SIN_SIGNO = "#757575"


# --- Tablas y matrices ---------------------------------------------------------------------


def tabla_aristas(grafo: GrafoAgregado) -> pd.DataFrame:
    filas = [
        {
            "origen": a.origen,
            "destino": a.destino,
            "tipo": a.tipo,
            "frecuencia_total": a.frecuencia_total,
            "frecuencia_origen_destino": a.frecuencia_origen_destino,
            "frecuencia_destino_origen": a.frecuencia_destino_origen,
            "frecuencia_sin_orientar": a.frecuencia_sin_orientar,
            "signo": a.signo,
            "spearman": a.spearman,
            "justificacion": a.justificacion,
        }
        for a in grafo.aristas
    ]
    columnas = [
        "origen", "destino", "tipo", "frecuencia_total", "frecuencia_origen_destino",
        "frecuencia_destino_origen", "frecuencia_sin_orientar", "signo", "spearman", "justificacion",
    ]
    return pd.DataFrame(filas, columns=columnas)


def matriz_mascara(grafo: GrafoAgregado) -> pd.DataFrame:
    mascara = pd.DataFrame(0, index=grafo.variables, columns=grafo.variables)
    for arista in grafo.aristas:
        mascara.loc[arista.origen, arista.destino] = 1
        if arista.tipo == "sin_orientar":
            mascara.loc[arista.destino, arista.origen] = 1
    return mascara


def matriz_frecuencias(resultado: ResultadoBootstrap) -> pd.DataFrame:
    validas = max(resultado.corridas_validas, 1)
    valores = (np.asarray(resultado.dirigidas) + np.asarray(resultado.sin_orientar)) / validas
    return pd.DataFrame(valores, index=resultado.variables, columns=resultado.variables).round(4)


def resultado_a_diccionario(
    configuracion: ConfiguracionPC,
    receta: Receta,
    resultado: ResultadoBootstrap,
    grafo: GrafoAgregado,
    caracterizacion: Caracterizacion,
    spearman: list[list[float | None]],
) -> dict[str, Any]:
    """Contenido de ``resultado.json`` (base para la visualización del frontend).

    ``configuracion`` es la de la ejecución; ``agregacion`` guarda el umbral y las
    orientaciones manuales con que se agregó (en una versión reagregada difieren
    de los de ``configuracion``).
    """
    validas = max(resultado.corridas_validas, 1)
    return {
        "configuracion": a_diccionario_serializable(configuracion),
        "receta": {
            "archivo": receta.origen.archivo,
            "hoja": receta.origen.hoja,
            "sha256": receta.origen.sha256,
            "objetivo": receta.objetivo,
            "tipo_objetivo": receta.tipo_objetivo,
        },
        "corridas": {
            "totales": resultado.corridas_totales,
            "completadas": resultado.corridas_completadas,
            "validas": resultado.corridas_validas,
            "fallidas": a_diccionario_serializable(resultado.corridas_fallidas),
            "completo": resultado.completo,
        },
        "tiempo_s": resultado.tiempo_s,
        "ejecucion": a_diccionario_serializable(resultado.ejecucion),
        "limites_discretizacion": resultado.limites_discretizacion,
        "variables": resultado.variables,
        "aristas": a_diccionario_serializable(grafo.aristas),
        "ciclos": grafo.ciclos,
        "caracterizacion": a_diccionario_serializable(caracterizacion),
        "matrices": {
            "frecuencia_dirigida": (np.asarray(resultado.dirigidas) / validas).round(4).tolist(),
            "frecuencia_sin_orientar": (np.asarray(resultado.sin_orientar) / validas).round(4).tolist(),
        },
        "advertencias": grafo.advertencias,
        "agregacion": {
            "umbral_frecuencia": grafo.umbral_frecuencia,
            "orientaciones_manuales": a_diccionario_serializable(configuracion.orientaciones_manuales),
        },
        "cuentas": {
            "dirigidas": np.asarray(resultado.dirigidas, dtype=int).tolist(),
            "sin_orientar": np.asarray(resultado.sin_orientar, dtype=int).tolist(),
            "bidireccionales": resultado.bidireccionales,
        },
        "spearman": spearman,
    }


# --- Figura --------------------------------------------------------------------------------


def partir_etiqueta(nombre: str, ancho: int = 18) -> str:
    """Parte un nombre largo en líneas de hasta ``ancho`` caracteres, cortando
    preferentemente en espacios, guiones bajos o cambios de minúscula a mayúscula."""
    piezas = [p for p in re.split(r"(?<=[\s_])|(?<=[a-z])(?=[A-Z])", nombre) if p]
    lineas = [""]
    for pieza in piezas:
        if lineas[-1] and len(lineas[-1]) + len(pieza) > ancho:
            lineas.append("")
        lineas[-1] += pieza
    partidas = []
    for linea in lineas:
        partidas += textwrap.wrap(linea.strip(), ancho, break_long_words=True) or [linea]
    return "\n".join(partidas) or nombre



def _orden_por_baricentro(
    niveles: list[list[str]], vecinos: dict[str, set[str]], rondas: int = 4
) -> list[list[str]]:
    """Reordena cada nivel según la posición media de sus vecinos (reduce cruces)."""
    orden = [list(nivel) for nivel in niveles]
    for _ in range(rondas):
        posicion = {v: i / max(len(nivel) - 1, 1) for nivel in orden for i, v in enumerate(nivel)}
        for nivel in orden:
            actual = {v: posicion[v] for v in nivel}
            nivel.sort(
                key=lambda v: (
                    np.mean([posicion[w] for w in vecinos[v]]) if vecinos[v] else actual[v],
                    actual[v],
                )
            )
    return orden


def disposicion_por_niveles(
    variables: list[str],
    aristas: list[tuple[str, str]],
    niveles: list[list[str]],
    nombres: list[str] | None = None,
) -> list[tuple[str, list[str]]]:
    """Columnas del dibujo del grafo: (título, variables) por nivel no vacío, con las
    variables de cada nivel ordenadas para reducir cruces de ``aristas``."""
    if nombres is None or len(nombres) != len(niveles):
        nombres = [f"Nivel {i + 1}" for i in range(len(niveles))]
    con_nombre = [(nombre, [v for v in nivel if v in variables]) for nombre, nivel in zip(nombres, niveles)]
    con_nombre = [(nombre, nivel) for nombre, nivel in con_nombre if nivel]
    vecinos: dict[str, set[str]] = {v: set() for v in variables}
    for origen, destino in aristas:
        vecinos[origen].add(destino)
        vecinos[destino].add(origen)
    ordenados = _orden_por_baricentro([nivel for _, nivel in con_nombre], vecinos)
    return [(nombre, nivel) for (nombre, _), nivel in zip(con_nombre, ordenados)]


def dibujar_grafo(
    grafo: GrafoAgregado,
    caracterizacion: Caracterizacion,
    niveles: list[list[str]],
    nombres: list[str] | None = None,
    umbral_original: float | None = None,
):
    """Figura de matplotlib con las variables en columnas por nivel.

    ``umbral_original``: si difiere del umbral del grafo (versión ajustada), el título
    lo indica.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch, Patch

    columnas = disposicion_por_niveles(
        grafo.variables, [(a.origen, a.destino) for a in grafo.aristas], niveles, nombres
    )
    titulos = [nombre for nombre, _ in columnas]
    niveles = [nivel for _, nivel in columnas]
    causas = {c.variable for c in caracterizacion.variables if c.categoria == CAUSA_DIRECTA}

    mas_poblado = max(len(nivel) for nivel in niveles)
    separacion_x, separacion_y = 4.0, 1.1
    ancho = max(7.0, 3.2 * len(niveles) + 1.5 + 0.12 * mas_poblado)
    alto = max(4.5, 0.62 * mas_poblado + 2.2)
    figura, ejes = plt.subplots(figsize=(ancho, alto), dpi=150)
    posiciones: dict[str, tuple[float, float]] = {}
    for columna, nivel in enumerate(niveles):
        for fila, variable in enumerate(nivel):
            posiciones[variable] = (columna * separacion_x, ((len(nivel) - 1) / 2 - fila) * separacion_y)
        ejes.text(
            columna * separacion_x, (mas_poblado - 1) / 2 * separacion_y + 0.9, partir_etiqueta(titulos[columna]),
            ha="center", va="bottom", fontsize=9, color="#546e7a", fontweight="bold",
        )

    cajas = {}
    for variable, (x, y) in posiciones.items():
        if variable == grafo.objetivo:
            fondo, texto, borde = _COLOR_OBJETIVO, "white", _COLOR_OBJETIVO
        elif variable in causas:
            fondo, texto, borde = _COLOR_CAUSA, "white", _COLOR_CAUSA
        else:
            fondo, texto, borde = _COLOR_NODO, "#263238", "#90a4ae"
        etiqueta = partir_etiqueta(variable)
        cajas[variable] = ejes.text(
            x, y, etiqueta, ha="center", va="center", fontsize=7.5, color=texto, zorder=3,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": fondo, "edgecolor": borde, "linewidth": 1},
        )

    for arista in grafo.aristas:
        if arista.origen not in posiciones or arista.destino not in posiciones:
            continue
        (x1, y1), (x2, y2) = posiciones[arista.origen], posiciones[arista.destino]
        color = {1: _COLOR_POSITIVA, -1: _COLOR_NEGATIVA}.get(arista.signo, _COLOR_SIN_SIGNO)
        sin_orientar = arista.tipo == "sin_orientar"
        # Dentro de un nivel, el arco sale siempre por la izquierda de la columna (las
        # aristas hacia otros niveles salen por la derecha) para no tapar etiquetas.
        curvatura = (0.32 if y2 < y1 else -0.32) if x1 == x2 else 0.05
        ejes.add_patch(
            FancyArrowPatch(
                posiciones[arista.origen], posiciones[arista.destino],
                patchA=cajas[arista.origen].get_bbox_patch(),
                patchB=cajas[arista.destino].get_bbox_patch(),
                arrowstyle="-" if sin_orientar else "-|>",
                mutation_scale=11,
                connectionstyle=f"arc3,rad={curvatura}",
                color=color, linewidth=0.5 + 1.5 * arista.frecuencia_total,
                linestyle="--" if sin_orientar else "-", alpha=0.75, zorder=2,
            )
        )

    ejes.legend(
        handles=[
            Patch(facecolor=_COLOR_OBJETIVO, label="Objetivo"),
            Patch(facecolor=_COLOR_CAUSA, label="Causa directa"),
            Line2D([], [], color=_COLOR_POSITIVA, label="Relación positiva"),
            Line2D([], [], color=_COLOR_NEGATIVA, label="Relación negativa"),
            Line2D([], [], color="#455a64", linestyle="--", label="Sin orientar"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=5, fontsize=7.5, frameon=False,
    )
    titulo = (
        f"Grafo causal (aristas en al menos el {100 * grafo.umbral_frecuencia:.0f} % de "
        f"{grafo.corridas_validas} corridas; grosor = frecuencia)"
    )
    if umbral_original is not None and abs(umbral_original - grafo.umbral_frecuencia) > 1e-9:
        ajustado, original = (f"{u:g}".replace(".", ",") for u in (grafo.umbral_frecuencia, umbral_original))
        titulo += f"\nVersión ajustada: umbral {ajustado}, original {original}"
    ejes.set_title(titulo, fontsize=9.5)
    margen_arcos = 0.2 * (mas_poblado - 1) * separacion_y
    ejes.set_xlim(
        -separacion_x * 0.5 - margen_arcos, (len(niveles) - 1) * separacion_x + separacion_x * 0.5
    )
    ejes.set_ylim(-(mas_poblado / 2) * separacion_y - 0.4, (mas_poblado / 2) * separacion_y + 1.1)
    ejes.axis("off")
    figura.tight_layout()
    return figura


# --- Escritura -------------------------------------------------------------------------------


def exportar(
    carpeta: str | Path,
    configuracion: ConfiguracionPC,
    receta: Receta,
    resultado: ResultadoBootstrap,
    grafo: GrafoAgregado,
    caracterizacion: Caracterizacion,
    spearman: list[list[float | None]],
) -> dict[str, Path]:
    """Escribe los archivos de resultados en ``carpeta`` (debe existir) y devuelve sus rutas.

    ``spearman``: matriz de ``pc_bootstrap.matriz_spearman`` (la misma que usó ``agregar``).
    """
    contenido = resultado_a_diccionario(configuracion, receta, resultado, grafo, caracterizacion, spearman)
    return escribir_resultados(carpeta, contenido, resultado, grafo, caracterizacion, configuracion)


def escribir_resultados(
    carpeta: str | Path,
    contenido: dict[str, Any],
    resultado: ResultadoBootstrap,
    grafo: GrafoAgregado,
    caracterizacion: Caracterizacion,
    configuracion: ConfiguracionPC,
) -> dict[str, Path]:
    """Escribe ``contenido`` como ``resultado.json`` y el resto de archivos a partir del grafo
    (``configuracion`` es la de la ejecución: niveles, títulos y umbral original)."""
    import json

    import matplotlib.pyplot as plt

    carpeta = Path(carpeta)
    rutas = {nombre: carpeta / nombre for nombre in ARCHIVOS}
    rutas["resultado.json"].write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
    tabla_aristas(grafo).to_csv(rutas["aristas.csv"], index=False)
    matriz_mascara(grafo).to_csv(rutas["mascara.csv"])
    matriz_frecuencias(resultado).to_csv(rutas["matriz_frecuencias.csv"])
    figura = dibujar_grafo(
        grafo, caracterizacion, configuracion.niveles, configuracion.nombres_niveles,
        umbral_original=configuracion.umbral_frecuencia,
    )
    figura.savefig(rutas["grafo.png"], bbox_inches="tight")
    plt.close(figura)
    return rutas

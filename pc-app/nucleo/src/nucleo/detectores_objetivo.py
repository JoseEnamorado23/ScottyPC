"""Detectores que necesitan el DataFrame y la variable objetivo a la vez.

Interfaz: ``(dataframe, posicion_objetivo, tipo_objetivo, configuracion,
perfiles) -> list[Hallazgo]``. Solo se ejecutan si el objetivo existe en
una única columna. Como todos los detectores, no modifican los datos.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.detectores import _nativo, _porcentaje
from nucleo.modelos import Hallazgo, PerfilColumna, Severidad, TipoHallazgo, TipoObjetivo

_CATEGORICOS = (TipoObjetivo.BINARIO, TipoObjetivo.MULTICLASE)


def mascara_faltantes(serie: pd.Series, centinelas: tuple[str, ...]) -> np.ndarray:
    """Faltantes reales de pandas o textos centinela (sin espacios al inicio o al final)."""
    centinela = serie.map(lambda v: isinstance(v, str) and v.strip() in centinelas)
    return (serie.isna() | centinela.astype(bool)).to_numpy()


# --- Faltantes que dependen del objetivo ----------------------------------------


def detectar_faltantes_dependientes_objetivo(
    dataframe: pd.DataFrame,
    posicion_objetivo: int,
    tipo_objetivo: str | None,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas cuyos faltantes no parecen al azar respecto al objetivo.

    - Objetivo categórico: tabla faltante × clase con chi-cuadrado (o prueba
      exacta de Fisher en tablas 2×2 con frecuencias esperadas < 5). Se
      informa si p < ``alfa_faltantes_objetivo`` y la diferencia entre el
      mayor y el menor porcentaje de faltantes por clase es de al menos
      ``diferencia_minima_faltantes_objetivo`` puntos.
    - Objetivo continuo: Mann-Whitney entre los valores del objetivo en filas
      con y sin faltante; se informa si p < ``alfa_faltantes_objetivo``.

    Con muchas columnas, algún p pequeño puede aparecer por azar; el umbral
    de diferencia mínima reduce ese riesgo en objetivos categóricos.
    """
    if tipo_objetivo is None:
        return []
    objetivo = dataframe.iloc[:, posicion_objetivo]
    con_objetivo = objetivo.notna().to_numpy()
    hallazgos = []
    for posicion, perfil in enumerate(perfiles):
        if posicion == posicion_objetivo:
            continue
        faltante = mascara_faltantes(
            dataframe.iloc[:, posicion], configuracion.valores_centinela_faltantes
        )[con_objetivo]
        if not faltante.any() or faltante.all():
            continue
        valores_objetivo = objetivo[con_objetivo]
        if tipo_objetivo in _CATEGORICOS:
            evidencia = _faltantes_por_clase(faltante, valores_objetivo, configuracion)
        else:
            evidencia = _faltantes_objetivo_continuo(faltante, valores_objetivo, configuracion)
        if evidencia is not None:
            hallazgos.append(_hallazgo_faltantes(perfil.nombre, str(objetivo.name), evidencia))
    return hallazgos


def _faltantes_por_clase(
    faltante: np.ndarray, objetivo: pd.Series, configuracion: ConfiguracionValidacion
) -> dict[str, Any] | None:
    tabla = pd.crosstab(faltante, objetivo.to_numpy())
    if tabla.shape[0] < 2 or tabla.shape[1] < 2:
        return None
    esperadas = stats.contingency.expected_freq(tabla.to_numpy())
    if tabla.shape == (2, 2) and esperadas.min() < 5:
        prueba, p = "fisher", float(stats.fisher_exact(tabla.to_numpy())[1])
    else:
        prueba, p = "chi_cuadrado", float(stats.chi2_contingency(tabla.to_numpy())[1])
    por_clase = {
        str(_nativo(clase)): _porcentaje(int(tabla.loc[True, clase]), int(tabla[clase].sum()))
        for clase in tabla.columns
    }
    diferencia = round(max(por_clase.values()) - min(por_clase.values()), 2)
    if p >= configuracion.alfa_faltantes_objetivo:
        return None
    if diferencia < configuracion.diferencia_minima_faltantes_objetivo:
        return None
    return {
        "prueba": prueba,
        "p_valor": p,
        "porcentaje_faltantes_por_clase": por_clase,
        "diferencia_puntos": diferencia,
        "faltantes": int(faltante.sum()),
    }


def _faltantes_objetivo_continuo(
    faltante: np.ndarray, objetivo: pd.Series, configuracion: ConfiguracionValidacion
) -> dict[str, Any] | None:
    valores = objetivo.to_numpy(dtype=float)
    con, sin = valores[faltante], valores[~faltante]
    p = float(stats.mannwhitneyu(con, sin).pvalue)
    if p >= configuracion.alfa_faltantes_objetivo:
        return None
    return {
        "prueba": "mann_whitney",
        "p_valor": p,
        "mediana_objetivo_con_faltante": float(np.median(con)),
        "mediana_objetivo_sin_faltante": float(np.median(sin)),
        "faltantes": int(faltante.sum()),
    }


def _hallazgo_faltantes(columna: str, objetivo: str, evidencia: dict[str, Any]) -> Hallazgo:
    if "porcentaje_faltantes_por_clase" in evidencia:
        partes = "; ".join(
            f"clase {clase}: {pct:.1f} %"
            for clase, pct in evidencia["porcentaje_faltantes_por_clase"].items()
        )
        prueba = "chi-cuadrado" if evidencia["prueba"] == "chi_cuadrado" else "prueba exacta de Fisher"
        comparacion = f"El porcentaje de faltantes cambia según la clase de '{objetivo}': {partes}"
    else:
        prueba = "Mann-Whitney"
        comparacion = (
            f"La mediana de '{objetivo}' es {evidencia['mediana_objetivo_con_faltante']:g} en las filas "
            f"sin dato y {evidencia['mediana_objetivo_sin_faltante']:g} en las filas con dato"
        )
    return Hallazgo(
        tipo=TipoHallazgo.FALTANTES_DEPENDIENTES_OBJETIVO,
        columnas_involucradas=[columna, objetivo],
        severidad=Severidad.ALTA,
        detalle=(
            f"Los faltantes de '{columna}' dependen del objetivo. {comparacion} "
            f"({prueba}, p = {evidencia['p_valor']:.2g}). Tratarlos como faltantes al azar "
            "puede sesgar el descubrimiento causal."
        ),
        evidencia=evidencia,
        acciones_posibles=[
            "Excluir la variable.",
            "Imputar y agregar un indicador de 'dato medido'.",
            "Usar solo casos completos.",
            "Conservar la variable como está.",
        ],
        accion_sugerida="Imputar y agregar un indicador de 'dato medido'.",
    )


# --- Tamaño efectivo de la muestra ------------------------------------------------


def detectar_tamano_efectivo(
    dataframe: pd.DataFrame,
    posicion_objetivo: int,
    tipo_objetivo: str | None,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Objetivo categórico con pocos casos en la clase minoritaria.

    Se advierte si la clase minoritaria tiene menos de
    ``minimo_casos_clase_minoritaria`` casos o menos de
    ``minimo_casos_por_variable`` casos por cada variable candidata (todas
    las columnas excepto el objetivo).
    """
    if tipo_objetivo not in _CATEGORICOS:
        return []
    conteo = dataframe.iloc[:, posicion_objetivo].value_counts()
    clase, casos = _nativo(conteo.index[-1]), int(conteo.iloc[-1])
    candidatas = len(perfiles) - 1
    por_variable = casos / candidatas if candidatas else float("inf")
    pocos_casos = casos < configuracion.minimo_casos_clase_minoritaria
    pocos_por_variable = por_variable < configuracion.minimo_casos_por_variable
    if not (pocos_casos or pocos_por_variable):
        return []
    motivos = []
    if pocos_casos:
        motivos.append(
            f"tiene {casos} casos (se recomiendan al menos "
            f"{configuracion.minimo_casos_clase_minoritaria})"
        )
    if pocos_por_variable:
        motivos.append(
            f"aporta {por_variable:.1f} casos por cada una de las {candidatas} variables "
            f"candidatas (se recomiendan al menos {configuracion.minimo_casos_por_variable})"
        )
    objetivo = perfiles[posicion_objetivo].nombre
    return [
        Hallazgo(
            tipo=TipoHallazgo.TAMANO_EFECTIVO_INSUFICIENTE,
            columnas_involucradas=[objetivo],
            severidad=Severidad.MEDIA,
            detalle=(
                f"La clase minoritaria de '{objetivo}' ('{clase}') " + " y ".join(motivos) + ". "
                "PC tendrá poca potencia: encontrará pocas causas y omitirá efectos moderados."
            ),
            evidencia={
                "clase_minoritaria": clase,
                "casos_clase_minoritaria": casos,
                "variables_candidatas": candidatas,
                "casos_por_variable": round(por_variable, 2),
                "minimo_casos_clase_minoritaria": configuracion.minimo_casos_clase_minoritaria,
                "minimo_casos_por_variable": configuracion.minimo_casos_por_variable,
            },
            acciones_posibles=[
                "Interpretar con cautela la ausencia de aristas en el grafo.",
                "Reducir el número de variables candidatas.",
                "Conseguir más casos de la clase minoritaria.",
            ],
            accion_sugerida="Interpretar con cautela la ausencia de aristas en el grafo.",
        )
    ]

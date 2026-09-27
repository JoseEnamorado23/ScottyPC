"""Detectores avanzados: relaciones entre columnas y posibles mezclas de unidades.

Son detectores conservadores: informan que unas columnas *parecen*
relacionadas y, cuando es razonable, sugieren cuál podría ser la variable
original y cuál la derivada. Nunca eliminan ni modifican columnas.

Para no repetir hallazgos sobre un mismo par de columnas se aplica una
jerarquía: copia exacta > recodificación uno a uno > correlación casi
perfecta (que incluye las transformaciones lineales exactas). Las relaciones
de suma/resta entre tres columnas y las binarias derivadas de un umbral se
informan aparte porque describen relaciones distintas.

Además, las columnas que son copia exacta de otra anterior se ignoran en
los demás detectores de relaciones: la copia ya tiene su propio hallazgo y
repetir cada relación para ella solo añadiría ruido.

Todos los detectores comparan solo filas sin faltantes en las columnas
implicadas y usan la interfaz ``(dataframe, configuracion, perfiles)``.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.detectores import _columnas, _es_numerica, _evidencia_fecha, _nativo, _porcentaje
from nucleo.modelos import Hallazgo, PerfilColumna, Severidad, TipoHallazgo

_ACCIONES_DERIVADA = [
    "Revisar la relación entre las columnas.",
    "Considerar eliminar la variable derivada y conservar la original.",
]


# --- Auxiliares --------------------------------------------------------------


def _a_flotantes(serie: pd.Series) -> np.ndarray:
    return serie.to_numpy(dtype=float, na_value=np.nan)


def _cerca(x: np.ndarray, y: np.ndarray, configuracion: ConfiguracionValidacion) -> np.ndarray:
    return np.isclose(
        x,
        y,
        rtol=configuracion.tolerancia_relativa_relaciones,
        atol=configuracion.tolerancia_absoluta_relaciones,
    )


def _indices_numericos(dataframe: pd.DataFrame, perfiles: list[PerfilColumna]) -> list[int]:
    """Posiciones de columnas numéricas (no booleanas) con al menos dos valores."""
    return [
        posicion
        for posicion, (serie, perfil) in enumerate(_columnas(dataframe, perfiles))
        if _es_numerica(serie) and perfil.valores_unicos >= 2
    ]


def _son_copia(a: pd.Series, b: pd.Series, configuracion: ConfiguracionValidacion) -> int | None:
    """Filas comparadas si ``a`` y ``b`` son iguales fila por fila; si no, ``None``.

    Los faltantes deben estar en las mismas filas. Primero se comparan las
    ``filas_muestra_relaciones`` primeras filas, lo que descarta casi todos
    los pares sin recorrer las columnas completas.
    """
    muestra = configuracion.filas_muestra_relaciones
    if len(a) > muestra and _comparar_copia(a.iloc[:muestra], b.iloc[:muestra], configuracion, 0) is None:
        return None
    return _comparar_copia(a, b, configuracion, configuracion.minimo_filas_relacion)


def _comparar_copia(
    a: pd.Series, b: pd.Series, configuracion: ConfiguracionValidacion, minimo_filas: int
) -> int | None:
    nulos = a.isna().to_numpy()
    if not np.array_equal(nulos, b.isna().to_numpy()):
        return None
    validos = ~nulos
    filas = int(validos.sum())
    if filas < minimo_filas:
        return None
    if _es_numerica(a) and _es_numerica(b):
        iguales = _cerca(_a_flotantes(a)[validos], _a_flotantes(b)[validos], configuracion)
        return filas if bool(iguales.all()) else None
    try:
        iguales = a.to_numpy(dtype=object)[validos] == b.to_numpy(dtype=object)[validos]
        return filas if bool(np.all(iguales)) else None
    except (TypeError, ValueError):
        return None


def _recodificacion(
    a: pd.Series, b: pd.Series, configuracion: ConfiguracionValidacion
) -> tuple[int, pd.DataFrame] | None:
    """Correspondencia biyectiva entre los valores de ``a`` y ``b``.

    Se exige: entre 2 y ``maximo_valores_categorica`` valores distintos en
    cada columna, valores repetidos (si no, cualquier par de columnas sin
    repeticiones sería trivialmente biyectivo) y que cada valor de una
    columna corresponda a un único valor de la otra en todas las filas
    comparables.
    """
    validos = (a.notna() & b.notna()).to_numpy()
    filas = int(validos.sum())
    if filas < configuracion.minimo_filas_relacion:
        return None
    pares = pd.DataFrame(
        {"a": a.to_numpy(dtype=object)[validos], "b": b.to_numpy(dtype=object)[validos]}
    )
    try:
        distintos_a, distintos_b = pares["a"].nunique(), pares["b"].nunique()
        if distintos_a != distintos_b or distintos_a >= filas:
            return None
        if not 2 <= distintos_a <= configuracion.maximo_valores_categorica:
            return None
        combinaciones = pares.drop_duplicates()
    except TypeError:
        return None
    return (filas, combinaciones) if len(combinaciones) == distintos_a else None


def _clave_copia(serie: pd.Series, configuracion: ConfiguracionValidacion) -> tuple:
    """Clave barata que coincide en columnas que pueden ser copia una de otra.

    Usa el número de faltantes y los valores de las primeras filas
    (numéricos redondeados, para respetar la tolerancia). Dos columnas con
    claves distintas no se comparan completas.
    """
    muestra = serie.iloc[: configuracion.filas_muestra_relaciones]
    if _es_numerica(serie):
        valores = tuple(None if np.isnan(v) else round(float(v), 6) for v in _a_flotantes(muestra))
    else:
        valores = tuple(repr(v) for v in muestra)
    return int(serie.isna().sum()), valores


def _pares_copia(
    dataframe: pd.DataFrame, posiciones: list[int], configuracion: ConfiguracionValidacion
) -> list[tuple[int, int, int]]:
    """Pares ``(i, j, filas)`` con ``i < j`` que son copia exacta, en orden estable."""
    grupos: dict[tuple, list[int]] = {}
    for posicion in posiciones:
        clave = _clave_copia(dataframe.iloc[:, posicion], configuracion)
        grupos.setdefault(clave, []).append(posicion)
    pares = []
    for grupo in grupos.values():
        for i, j in combinations(grupo, 2):
            filas = _son_copia(dataframe.iloc[:, i], dataframe.iloc[:, j], configuracion)
            if filas is not None:
                pares.append((i, j, filas))
    return sorted(pares)


def _sin_copias(
    dataframe: pd.DataFrame, posiciones: list[int], configuracion: ConfiguracionValidacion
) -> list[int]:
    """Quita las posiciones que son copia exacta de una posición anterior."""
    copias = {j for _, j, _ in _pares_copia(dataframe, posiciones, configuracion)}
    return [posicion for posicion in posiciones if posicion not in copias]


def _nombres(perfiles: list[PerfilColumna], posiciones: list[int]) -> list[str]:
    return [perfiles[p].nombre for p in sorted(posiciones)]


# --- 12. Copias exactas ------------------------------------------------------


def detectar_copias_exactas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Pares de columnas con los mismos valores fila por fila.

    Se sugiere como original la columna situada más a la izquierda.
    """
    candidatas = [i for i, perfil in enumerate(perfiles) if perfil.valores_unicos >= 2]
    hallazgos = []
    for i, j, filas in _pares_copia(dataframe, candidatas, configuracion):
        original, copia = perfiles[i].nombre, perfiles[j].nombre
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.COLUMNAS_REDUNDANTES,
                columnas_involucradas=[original, copia],
                severidad=Severidad.MEDIA,
                detalle=(
                    f"Las columnas '{original}' y '{copia}' contienen exactamente los "
                    "mismos valores en todas las filas."
                ),
                evidencia={
                    "tipo_relacion": "copia_exacta",
                    "coincidencia": 1.0,
                    "filas_comparadas": filas,
                    "original_sugerida": [original],
                    "derivada_sugerida": [copia],
                },
                acciones_posibles=list(_ACCIONES_DERIVADA),
                accion_sugerida="Revisar la relación entre las columnas.",
            )
        )
    return hallazgos


# --- 13. Recodificaciones uno a uno ------------------------------------------


def detectar_recodificaciones(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Pares de columnas cuyos valores se corresponden uno a uno (p. ej. M↔1, F↔0).

    Las relaciones muchos-a-uno (ciudad → departamento) no se reportan, ni
    los pares que ya son copias exactas.
    """
    candidatas = _sin_copias(
        dataframe,
        [
            i
            for i, perfil in enumerate(perfiles)
            if 2 <= perfil.valores_unicos <= configuracion.maximo_valores_categorica
        ],
        configuracion,
    )
    hallazgos = []
    for i, j in combinations(candidatas, 2):
        a, b = dataframe.iloc[:, i], dataframe.iloc[:, j]
        resultado = _recodificacion(a, b, configuracion)
        if resultado is None:
            continue
        filas, combinaciones = resultado
        correspondencia = sorted(
            ({"valor_a": _nativo(x), "valor_b": _nativo(y)} for x, y in combinaciones.itertuples(index=False)),
            key=lambda par: str(par["valor_a"]),
        )
        nombre_a, nombre_b = perfiles[i].nombre, perfiles[j].nombre
        texto = ", ".join(f"{par['valor_a']} → {par['valor_b']}" for par in correspondencia)
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.RECODIFICACION_UNO_A_UNO,
                columnas_involucradas=[nombre_a, nombre_b],
                severidad=Severidad.MEDIA,
                detalle=(
                    f"Las columnas '{nombre_a}' y '{nombre_b}' parecen ser una "
                    f"recodificación una de la otra ({texto})."
                ),
                evidencia={
                    "tipo_relacion": "recodificacion_uno_a_uno",
                    "coincidencia": 1.0,
                    "filas_comparadas": filas,
                    "columna_a": nombre_a,
                    "columna_b": nombre_b,
                    "correspondencia": correspondencia,
                },
                acciones_posibles=[
                    "Revisar la relación entre las columnas.",
                    "Considerar conservar solo una de las dos codificaciones.",
                ],
                accion_sugerida="Revisar la relación entre las columnas.",
            )
        )
    return hallazgos


# --- 14. Relaciones matemáticas (suma y resta) -------------------------------


def detectar_relaciones_matematicas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Tríos de columnas numéricas donde una es la suma de las otras dos.

    ``C = A + B``, ``C = A - B`` y ``C = B - A`` son la misma relación entre
    tres columnas (``A = B + C``), por lo que cada trío se informa una vez.
    Se sugiere como derivada la columna situada más a la derecha y se
    expresa como suma o resta de las otras dos (p. ej.
    ``ancho = maximo - minimo``).

    Para no evaluar todas las combinaciones sobre todas las filas, primero
    se descartan candidatos con ``filas_muestra_relaciones`` filas y luego
    se verifica cada candidato completo.
    """
    indices = _sin_copias(dataframe, _indices_numericos(dataframe, perfiles), configuracion)
    if len(indices) < 3:
        return []
    matriz = np.column_stack([_a_flotantes(dataframe.iloc[:, i]) for i in indices])
    muestra = matriz[: configuracion.filas_muestra_relaciones]
    vistos: set[frozenset[int]] = set()
    hallazgos = []
    for a, b in combinations(range(len(indices)), 2):
        for s in _candidatos_suma(muestra, a, b, configuracion):
            trio = frozenset((a, b, s))
            if trio in vistos:
                continue
            verificacion = _verificar_suma(matriz[:, a], matriz[:, b], matriz[:, s], configuracion)
            if verificacion is None:
                continue
            vistos.add(trio)
            filas, error = verificacion
            hallazgos.append(
                _hallazgo_suma(indices[a], indices[b], indices[s], filas, error, perfiles)
            )
    return hallazgos


def _candidatos_suma(
    muestra: np.ndarray, a: int, b: int, configuracion: ConfiguracionValidacion
) -> list[int]:
    """Columnas que coinciden con ``a + b`` en las filas de muestra comparables."""
    suma = muestra[:, a] + muestra[:, b]
    validos = ~np.isnan(muestra) & ~np.isnan(suma)[:, None]
    coincide = _cerca(muestra, suma[:, None], configuracion) | ~validos
    candidatos = np.flatnonzero(coincide.all(axis=0))
    return [int(s) for s in candidatos if s not in (a, b)]


def _verificar_suma(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, configuracion: ConfiguracionValidacion
) -> tuple[int, float] | None:
    validos = ~(np.isnan(x) | np.isnan(y) | np.isnan(z))
    filas = int(validos.sum())
    if filas < configuracion.minimo_filas_relacion:
        return None
    suma, objetivo = x[validos] + y[validos], z[validos]
    if not bool(_cerca(objetivo, suma, configuracion).all()):
        return None
    return filas, float(np.max(np.abs(objetivo - suma)))


def _hallazgo_suma(
    a: int, b: int, s: int, filas: int, error: float, perfiles: list[PerfilColumna]
) -> Hallazgo:
    """Construye el hallazgo para ``s = a + b`` (posiciones en el DataFrame)."""
    nombre = {p: perfiles[p].nombre for p in (a, b, s)}
    derivada = max(a, b, s)
    if derivada == s:
        sumandos = sorted((a, b))
        tipo_relacion = "suma"
        expresion = f"{nombre[sumandos[0]]} + {nombre[sumandos[1]]}"
        originales = sumandos
    else:
        otra = b if derivada == a else a
        tipo_relacion = "resta"
        expresion = f"{nombre[s]} - {nombre[otra]}"
        originales = [s, otra]
    return Hallazgo(
        tipo=TipoHallazgo.COLUMNA_DERIVADA,
        columnas_involucradas=_nombres(perfiles, [a, b, s]),
        severidad=Severidad.MEDIA,
        detalle=(
            f"La columna '{nombre[derivada]}' parece ser igual a {expresion} "
            f"en todas las filas comparables ({filas})."
        ),
        evidencia={
            "tipo_relacion": tipo_relacion,
            "operacion": f"{nombre[derivada]} = {expresion}",
            "coincidencia": 1.0,
            "filas_comparadas": filas,
            "error_maximo": error,
            "original_sugerida": [nombre[p] for p in originales],
            "derivada_sugerida": [nombre[derivada]],
        },
        acciones_posibles=list(_ACCIONES_DERIVADA),
        accion_sugerida="Revisar la relación entre las columnas.",
    )


# --- 15. Binarias derivadas de un umbral --------------------------------------


def detectar_binarias_derivadas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas con dos valores que parecen resultar de aplicar un umbral a
    una variable numérica (p. ej. ``adulto = edad >= 18``).

    Se busca el umbral que mejor separa las dos clases según el acierto
    balanceado (media del porcentaje de acierto de cada clase). Se informa
    solo si ese acierto alcanza ``porcentaje_minimo_acierto_umbral`` y cada
    clase tiene ``minimo_por_clase_binaria_derivada`` observaciones.

    El acierto balanceado evita falsos positivos con clases muy
    desbalanceadas: si una clase tiene 7 filas de 2 000, predecir siempre la
    mayoritaria acierta el 99.7 % de las filas pero el 50 % en promedio por
    clase, así que no cuenta como regla.
    """
    binarias = _sin_copias(
        dataframe, [i for i, perfil in enumerate(perfiles) if perfil.valores_unicos == 2], configuracion
    )
    numericas = _sin_copias(
        dataframe,
        [
            i
            for i in _indices_numericos(dataframe, perfiles)
            if perfiles[i].valores_unicos >= configuracion.minimo_valores_distintos_umbral
        ],
        configuracion,
    )
    hallazgos = []
    for ib in binarias:
        for ix in numericas:
            if ix == ib:
                continue
            regla = _regla_umbral(dataframe.iloc[:, ix], dataframe.iloc[:, ib], configuracion)
            if regla is not None:
                hallazgos.append(_hallazgo_binaria(perfiles[ix].nombre, perfiles[ib].nombre, regla))
    return hallazgos


def _regla_umbral(
    numerica: pd.Series, binaria: pd.Series, configuracion: ConfiguracionValidacion
) -> dict[str, Any] | None:
    validos = (numerica.notna() & binaria.notna()).to_numpy()
    n = int(validos.sum())
    if n < configuracion.minimo_filas_relacion:
        return None
    clases = binaria[validos]
    try:
        clase_a, clase_b = sorted(set(clases), key=str)
    except (TypeError, ValueError):
        return None
    es_b = (clases == clase_b).to_numpy()
    if min(int(es_b.sum()), n - int(es_b.sum())) < configuracion.minimo_por_clase_binaria_derivada:
        return None

    orden = np.argsort(_a_flotantes(numerica)[validos], kind="stable")
    x_ordenada = _a_flotantes(numerica)[validos][orden]
    b_ordenada = es_b[orden]
    # Corte k: filas [0, k) quedan por debajo del umbral y [k, n) por encima.
    cortes = np.flatnonzero(x_ordenada[1:] > x_ordenada[:-1]) + 1
    if len(cortes) == 0:
        return None
    total_b = int(b_ordenada.sum())
    total_a = n - total_b
    b_antes = np.concatenate([[0], np.cumsum(b_ordenada)])[cortes]
    a_antes = cortes - b_antes
    # Acierto de cada clase en las dos orientaciones posibles de la regla.
    # Clase b por encima del umbral: aciertan las a de abajo y las b de arriba.
    balanceado_b_arriba = (a_antes / total_a + (total_b - b_antes) / total_b) / 2
    # Clase b por debajo del umbral: el complemento.
    balanceado_b_abajo = 1 - balanceado_b_arriba
    balanceado = np.maximum(balanceado_b_arriba, balanceado_b_abajo)
    mejor = int(np.argmax(balanceado))
    porcentaje_balanceado = 100.0 * float(balanceado[mejor])
    if porcentaje_balanceado < configuracion.porcentaje_minimo_acierto_umbral:
        return None
    b_arriba = bool(balanceado_b_arriba[mejor] >= balanceado_b_abajo[mejor])
    corte = int(cortes[mejor])
    a_abajo, b_abajo = int(a_antes[mejor]), int(b_antes[mejor])
    aciertos = (a_abajo + total_b - b_abajo) if b_arriba else (b_abajo + total_a - a_abajo)
    umbral = numerica[validos].to_numpy()[orden][corte]
    return {
        "umbral": _nativo(umbral),
        "clase_superior": _nativo(clase_b if b_arriba else clase_a),
        "clase_inferior": _nativo(clase_a if b_arriba else clase_b),
        "coincidencia": round(aciertos / n, 4),
        "acierto_balanceado": round(porcentaje_balanceado / 100.0, 4),
        "errores": n - aciertos,
        "filas_comparadas": n,
    }


def _hallazgo_binaria(numerica: str, binaria: str, regla: dict[str, Any]) -> Hallazgo:
    texto_regla = (
        f"{binaria} = {regla['clase_superior']} si {numerica} >= {regla['umbral']}; "
        f"{regla['clase_inferior']} en otro caso"
    )
    return Hallazgo(
        tipo=TipoHallazgo.BINARIA_DERIVADA,
        columnas_involucradas=[numerica, binaria],
        severidad=Severidad.MEDIA,
        detalle=(
            f"La columna '{binaria}' parece derivarse de '{numerica}' mediante un umbral "
            f"({texto_regla}); la regla coincide en el "
            f"{100 * regla['coincidencia']:.1f} % de las filas y su acierto balanceado "
            f"entre clases es del {100 * regla['acierto_balanceado']:.1f} %."
        ),
        evidencia={"tipo_relacion": "umbral", "regla": texto_regla, **regla,
                   "original_sugerida": [numerica], "derivada_sugerida": [binaria]},
        acciones_posibles=list(_ACCIONES_DERIVADA),
        accion_sugerida="Revisar la relación entre las columnas.",
    )


# --- 16. Correlaciones casi perfectas ----------------------------------------


def detectar_correlaciones_casi_perfectas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Pares de columnas numéricas con ``|r| > umbral_correlacion_casi_perfecta``.

    Si los valores se ajustan exactamente a una recta se indica
    ``tipo_relacion = "transformacion_lineal"`` con pendiente e intercepto.
    Los pares que son copias exactas o recodificaciones se omiten porque ya
    los informan sus detectores.
    """
    indices = _sin_copias(dataframe, _indices_numericos(dataframe, perfiles), configuracion)
    if len(indices) < 2:
        return []
    tabla = pd.DataFrame({k: _a_flotantes(dataframe.iloc[:, i]) for k, i in enumerate(indices)})
    correlaciones = tabla.corr(min_periods=max(2, configuracion.minimo_filas_relacion)).to_numpy()
    umbral = configuracion.umbral_correlacion_casi_perfecta
    hallazgos = []
    for a, b in combinations(range(len(indices)), 2):
        r = float(correlaciones[a, b])
        if math.isnan(r) or abs(r) <= umbral:
            continue
        serie_a, serie_b = dataframe.iloc[:, indices[a]], dataframe.iloc[:, indices[b]]
        if _recodificacion(serie_a, serie_b, configuracion) is not None:
            continue
        hallazgos.append(
            _hallazgo_correlacion(
                perfiles[indices[a]].nombre, perfiles[indices[b]].nombre,
                serie_a, serie_b, r, configuracion,
            )
        )
    return hallazgos


def _ajuste_lineal(
    x: np.ndarray, y: np.ndarray, configuracion: ConfiguracionValidacion
) -> tuple[float, float] | None:
    """Pendiente e intercepto si ``y`` es exactamente lineal en ``x``."""
    diseno = np.column_stack([x, np.ones_like(x)])
    (pendiente, intercepto), *_ = np.linalg.lstsq(diseno, y, rcond=None)
    escala = configuracion.tolerancia_relativa_relaciones * float(np.max(np.abs(y)))
    error = np.abs(pendiente * x + intercepto - y)
    if not bool(np.all(error <= configuracion.tolerancia_absoluta_relaciones + escala)):
        return None
    # "+ 0.0" normaliza -0.0.
    return round(float(pendiente), 10) + 0.0, round(float(intercepto), 10) + 0.0


def _hallazgo_correlacion(
    nombre_a: str,
    nombre_b: str,
    serie_a: pd.Series,
    serie_b: pd.Series,
    r: float,
    configuracion: ConfiguracionValidacion,
) -> Hallazgo:
    validos = (serie_a.notna() & serie_b.notna()).to_numpy()
    x, y = _a_flotantes(serie_a)[validos], _a_flotantes(serie_b)[validos]
    ajuste = _ajuste_lineal(x, y, configuracion)
    detalle = (
        f"Las variables '{nombre_a}' y '{nombre_b}' presentan una correlación casi "
        f"perfecta (r = {r:.4f}). Esto puede indicar redundancia, transformación de "
        "escala u otra relación determinista."
    )
    evidencia: dict[str, Any] = {
        "tipo_relacion": "correlacion",
        "correlacion": round(r, 6),
        "umbral": configuracion.umbral_correlacion_casi_perfecta,
        "filas_comparadas": int(validos.sum()),
    }
    if ajuste is not None:
        pendiente, intercepto = ajuste
        detalle += (
            f" Los valores cumplen exactamente {nombre_b} = {pendiente:g} × {nombre_a} "
            f"+ {intercepto:g}."
        )
        evidencia.update(
            {"tipo_relacion": "transformacion_lineal", "pendiente": pendiente, "intercepto": intercepto}
        )
    return Hallazgo(
        tipo=TipoHallazgo.CORRELACION_CASI_PERFECTA,
        columnas_involucradas=[nombre_a, nombre_b],
        severidad=Severidad.MEDIA,
        detalle=detalle,
        evidencia=evidencia,
        acciones_posibles=[
            "Revisar si ambas variables miden lo mismo.",
            "Considerar conservar solo una de ellas en el análisis.",
        ],
        accion_sugerida="Revisar si ambas variables miden lo mismo.",
    )


# --- 17. Posibles mezclas de unidades o escalas -------------------------------


def detectar_mezcla_unidades(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Variables continuas cuyos valores forman dos grupos claramente separados.

    Método: se ordenan los valores y se busca la mayor brecha entre valores
    consecutivos que deje en cada lado al menos
    ``porcentaje_minimo_grupo_mezcla`` de las observaciones. Se informa si
    la brecha es al menos ``proporcion_minima_brecha_mezcla`` del rango total
    y ``factor_brecha_dispersion_mezcla`` veces la desviación estándar del
    grupo más disperso, y cada grupo tiene al menos dos valores distintos
    (un grupo de un solo valor, como ceros o códigos, no es una escala).

    Si hay una columna de fechas y los grupos ocupan periodos que no se
    solapan, se añaden esos periodos como evidencia.
    """
    columna_fecha: tuple[str, pd.Series] | None = None
    fecha_buscada = False
    hallazgos = []
    for posicion in _indices_numericos(dataframe, perfiles):
        perfil = perfiles[posicion]
        if perfil.valores_unicos < configuracion.minimo_valores_distintos_continua:
            continue
        serie = dataframe.iloc[:, posicion]
        grupos = _grupos_separados(_a_flotantes(serie), configuracion)
        if grupos is None:
            continue
        if not fecha_buscada:
            columna_fecha = _primera_columna_fecha(dataframe, perfiles, configuracion)
            fecha_buscada = True
        hallazgos.append(_hallazgo_mezcla(perfil.nombre, serie, grupos, columna_fecha))
    return hallazgos


def _grupos_separados(
    valores: np.ndarray, configuracion: ConfiguracionValidacion
) -> dict[str, Any] | None:
    ordenados = np.sort(valores[~np.isnan(valores)])
    n = len(ordenados)
    if n < configuracion.minimo_observaciones_mezcla:
        return None
    minimo_grupo = max(1, math.ceil(n * configuracion.porcentaje_minimo_grupo_mezcla / 100))
    brechas = np.diff(ordenados)
    # Posición i: el grupo bajo es ordenados[: i + 1].
    permitidas = brechas[minimo_grupo - 1 : n - minimo_grupo]
    if len(permitidas) == 0:
        return None
    i = int(np.argmax(permitidas)) + minimo_grupo - 1
    bajo, alto = ordenados[: i + 1], ordenados[i + 1 :]
    brecha = float(brechas[i])
    rango = float(ordenados[-1] - ordenados[0])
    if len(np.unique(bajo)) < 2 or len(np.unique(alto)) < 2 or rango == 0:
        return None
    dispersion = max(float(np.std(bajo)), float(np.std(alto)))
    if brecha / rango < configuracion.proporcion_minima_brecha_mezcla:
        return None
    if brecha < configuracion.factor_brecha_dispersion_mezcla * dispersion:
        return None
    return {"bajo": bajo, "alto": alto, "brecha": brecha, "rango": rango, "corte": float(bajo[-1])}


def _resumen_grupo(valores: np.ndarray) -> dict[str, Any]:
    return {
        "minimo": float(valores[0]),
        "maximo": float(valores[-1]),
        "mediana": float(np.median(valores)),
        "observaciones": int(len(valores)),
    }


def _primera_columna_fecha(
    dataframe: pd.DataFrame, perfiles: list[PerfilColumna], configuracion: ConfiguracionValidacion
) -> tuple[str, pd.Series] | None:
    """Nombre y serie temporal derivada de la primera columna con fechas."""
    for serie, perfil in _columnas(dataframe, perfiles):
        evidencia = _evidencia_fecha(serie, configuracion)
        if evidencia is None:
            continue
        if evidencia["origen"] == "texto":
            textos = serie.map(lambda v: v.strip() if isinstance(v, str) else v)
            fechas = pd.to_datetime(textos, format=evidencia["formato"], errors="coerce")
        else:
            fechas = pd.to_datetime(serie, errors="coerce")
        return perfil.nombre, fechas
    return None


def _periodos(
    serie: pd.Series, corte: float, fechas: pd.Series
) -> dict[str, dict[str, str]] | None:
    """Periodos de cada grupo si no se solapan en el tiempo."""
    valores = _a_flotantes(serie)
    con_fecha = fechas.notna().to_numpy()
    periodos = {}
    for nombre, mascara in (("grupo_bajo", valores <= corte), ("grupo_alto", valores > corte)):
        del_grupo = fechas[mascara & con_fecha]
        if len(del_grupo) < 2:
            return None
        periodos[nombre] = (del_grupo.min(), del_grupo.max())
    (inicio_bajo, fin_bajo), (inicio_alto, fin_alto) = periodos.values()
    if not (fin_bajo < inicio_alto or fin_alto < inicio_bajo):
        return None
    return {
        nombre: {"desde": desde.date().isoformat(), "hasta": hasta.date().isoformat()}
        for nombre, (desde, hasta) in periodos.items()
    }


def _hallazgo_mezcla(
    nombre: str,
    serie: pd.Series,
    grupos: dict[str, Any],
    columna_fecha: tuple[str, pd.Series] | None,
) -> Hallazgo:
    bajo, alto = _resumen_grupo(grupos["bajo"]), _resumen_grupo(grupos["alto"])
    detalle = (
        f"La variable '{nombre}' presenta dos grupos de valores claramente separados "
        f"({bajo['minimo']:g}–{bajo['maximo']:g} y {alto['minimo']:g}–{alto['maximo']:g}). "
        "Esto podría deberse a diferentes unidades, escalas, poblaciones o procesos "
        "de medición."
    )
    evidencia: dict[str, Any] = {
        "grupo_bajo": bajo,
        "grupo_alto": alto,
        "brecha": grupos["brecha"],
        "proporcion_brecha_rango": round(grupos["brecha"] / grupos["rango"], 4),
        "razon_medianas": (
            round(alto["mediana"] / bajo["mediana"], 4) if bajo["mediana"] > 0 else None
        ),
        "porcentaje_grupo_bajo": _porcentaje(bajo["observaciones"],
                                             bajo["observaciones"] + alto["observaciones"]),
    }
    columnas = [nombre]
    if columna_fecha is not None and columna_fecha[0] != nombre:
        nombre_fecha, fechas = columna_fecha
        periodos = _periodos(serie, grupos["corte"], fechas)
        if periodos is not None:
            columnas.append(nombre_fecha)
            evidencia["columna_fecha"] = nombre_fecha
            evidencia["periodos"] = periodos
            detalle += (
                f" Según '{nombre_fecha}', los grupos corresponden a periodos distintos: "
                f"grupo bajo del {periodos['grupo_bajo']['desde']} al "
                f"{periodos['grupo_bajo']['hasta']}; grupo alto del "
                f"{periodos['grupo_alto']['desde']} al {periodos['grupo_alto']['hasta']}."
            )
    return Hallazgo(
        tipo=TipoHallazgo.POSIBLE_MEZCLA_UNIDADES,
        columnas_involucradas=columnas,
        severidad=Severidad.MEDIA,
        detalle=detalle,
        evidencia=evidencia,
        acciones_posibles=[
            "Revisar el origen de los valores de cada grupo.",
            "Verificar si se usaron unidades o escalas distintas.",
            "Mantener los valores si corresponden a poblaciones reales distintas.",
        ],
        accion_sugerida="Revisar el origen de los valores de cada grupo.",
    )

"""Detectores básicos de revisión.

Cada detector es una función independiente que observa los datos y devuelve
``list[Hallazgo]``. Ningún detector modifica el DataFrame ni corrige nada:
solo detecta, informa y sugiere acciones que el usuario decide.

Detectores de columnas: ``(dataframe, configuracion, perfiles)``.
Detectores del objetivo: ``(serie_objetivo, tipo_objetivo, configuracion)``.

Criterio de severidad (niveles existentes en ``Severidad``):

- ``baja``: información descriptiva que no es necesariamente un problema.
- ``media``: situación que conviene revisar (advertencia).
- ``alta``: situación que probablemente impide usar la columna tal cual.

Las columnas se recorren por posición para tolerar nombres repetidos.
"""

from __future__ import annotations

import datetime
import re
from collections import Counter
from collections.abc import Iterator
from typing import Any

import numpy as np
import pandas as pd
from pandas.api import types as tipos_pandas

from nucleo.configuracion import ConfiguracionValidacion
from nucleo.fechas import interpretar_fechas_texto
from nucleo.modelos import Hallazgo, PerfilColumna, Severidad, TipoHallazgo, TipoObjetivo

_PATRON_NOMBRE_FECHA = re.compile(r"fecha|date|datetime|timestamp|hora", re.IGNORECASE)
_PATRON_NOMBRE_IDENTIFICADOR = re.compile(
    r"(^|[_\s])(id|cod|codigo|código|documento|dni|matricula|matrícula)($|[_\s])",
    re.IGNORECASE,
)
# Escalas con orden natural conocido, de menor a mayor.
_ESCALAS_ORDINALES = (
    ("muy bajo", "bajo", "medio", "alto", "muy alto"),
    ("bajo", "moderado", "alto"),
    ("nunca", "rara vez", "a veces", "casi siempre", "siempre"),
    ("muy en desacuerdo", "en desacuerdo", "neutral", "de acuerdo", "muy de acuerdo"),
    ("muy malo", "malo", "regular", "bueno", "muy bueno", "excelente"),
    ("insuficiente", "suficiente", "notable", "sobresaliente"),
    ("pequeño", "mediano", "grande"),
    ("low", "medium", "high"),
)


# --- Auxiliares --------------------------------------------------------------


def _columnas(
    dataframe: pd.DataFrame, perfiles: list[PerfilColumna]
) -> Iterator[tuple[pd.Series, PerfilColumna]]:
    for posicion, perfil in enumerate(perfiles):
        yield dataframe.iloc[:, posicion], perfil


def _porcentaje(parte: int, total: int) -> float:
    return round(100.0 * parte / total, 2) if total else 0.0


def _nativo(valor: Any) -> Any:
    return valor.item() if isinstance(valor, np.generic) else valor


def _ejemplos(valores: pd.Series, configuracion: ConfiguracionValidacion) -> list[Any]:
    return [_nativo(v) for v in valores.iloc[: configuracion.maximo_ejemplos_evidencia]]


def _conteo_valores(valores: pd.Series) -> pd.Series:
    """Conteo vectorizado de valores no faltantes (no hashables: por ``repr``)."""
    presentes = valores.dropna()
    try:
        return presentes.value_counts()
    except TypeError:
        return presentes.map(repr).value_counts()


def _frecuencias(valores: pd.Series) -> list[tuple[Any, int]]:
    """Frecuencias de valores no faltantes, de mayor a menor (orden estable)."""
    conteo = _conteo_valores(valores)
    return sorted(
        ((_nativo(valor), int(n)) for valor, n in conteo.items()),
        key=lambda par: (-par[1], str(par[0])),
    )


def _es_numerica(serie: pd.Series) -> bool:
    return tipos_pandas.is_numeric_dtype(serie.dtype) and not tipos_pandas.is_bool_dtype(
        serie.dtype
    )


def _son_textos(valores: pd.Series) -> bool:
    return not valores.empty and all(isinstance(v, str) for v in valores)


def _son_enteros(valores: pd.Series) -> bool:
    return not valores.empty and bool((valores % 1 == 0).all())


def _son_enteros_consecutivos(valores: pd.Series) -> bool:
    """Valores enteros distintos que cubren un rango sin huecos (paso 1)."""
    unicos = valores.nunique()
    return int(valores.max()) - int(valores.min()) + 1 == unicos


def _mascara_filas_duplicadas(dataframe: pd.DataFrame) -> pd.Series:
    """Marca las repeticiones exactas de una fila anterior (sin la primera)."""
    posicional = dataframe.set_axis(range(dataframe.shape[1]), axis=1)
    try:
        return posicional.duplicated(keep="first")
    except TypeError:
        return posicional.map(repr).duplicated(keep="first")


def _metricas_texto(valores: pd.Series) -> dict[str, float] | None:
    if not _son_textos(valores):
        return None
    textos = [v.strip() for v in valores]
    return {
        "longitud_media": round(float(np.mean([len(t) for t in textos])), 1),
        "palabras_media": round(float(np.mean([len(t.split()) for t in textos])), 1),
        "porcentaje_valores_unicos": _porcentaje(len(set(textos)), len(textos)),
    }


def _cumple_texto_libre(metricas: dict[str, float] | None, configuracion) -> bool:
    return metricas is not None and (
        metricas["porcentaje_valores_unicos"] >= configuracion.porcentaje_unicos_texto_libre
        and metricas["longitud_media"] >= configuracion.longitud_media_minima_texto_libre
        and metricas["palabras_media"] >= configuracion.promedio_minimo_palabras_texto_libre
    )


def _evidencia_fecha(
    serie: pd.Series, configuracion: ConfiguracionValidacion
) -> dict[str, Any] | None:
    """Evidencia de que la columna contiene fechas, o ``None`` si no la hay.

    Las conversiones se hacen sobre series temporales derivadas; la columna
    original no cambia.
    """
    if tipos_pandas.is_datetime64_any_dtype(serie.dtype):
        return {"origen": "tipo_fecha"}
    valores = serie.dropna()
    if valores.empty:
        return None
    if all(isinstance(v, (datetime.date, np.datetime64)) for v in valores):
        return {"origen": "objetos_fecha"}
    interpretacion = interpretar_fechas_texto(
        valores, configuracion.porcentaje_minimo_fechas_convertibles
    )
    if interpretacion is None:
        return None
    return {
        "origen": "texto",
        "formato": interpretacion.formato,
        "porcentaje_convertible": interpretacion.porcentaje_convertible,
        "formatos_alternativos": list(interpretacion.formatos_alternativos),
    }


def _orden_sugerido(serie: pd.Series, valores: pd.Series) -> tuple[str, list[Any]] | None:
    """Orden natural de los valores, si hay evidencia razonable."""
    if isinstance(serie.dtype, pd.CategoricalDtype):
        if not serie.cat.ordered:
            return None
        observados = set(valores)
        return "categoria_ordenada", [c for c in serie.cat.categories if c in observados]
    if _son_textos(valores):
        distintos = sorted(set(valores))
        normalizados = {v: v.strip().lower() for v in distintos}
        for escala in _ESCALAS_ORDINALES:
            if set(normalizados.values()) <= set(escala):
                orden = sorted(distintos, key=lambda v: escala.index(normalizados[v]))
                return "escala_conocida", orden
        return None
    if _son_enteros_consecutivos(valores):
        return "enteros_consecutivos", sorted(_nativo(v) for v in valores.unique())
    return None


# --- 1. Filas duplicadas -----------------------------------------------------


def detectar_filas_duplicadas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Filas idénticas en todas las columnas a una fila anterior.

    ``posiciones_ejemplo`` son posiciones de fila (base 0) de las repeticiones.
    """
    if dataframe.empty:
        return []
    mascara = _mascara_filas_duplicadas(dataframe)
    cantidad = int(mascara.sum())
    if cantidad == 0:
        return []
    porcentaje = _porcentaje(cantidad, len(dataframe))
    posiciones = np.flatnonzero(mascara.to_numpy())[: configuracion.maximo_ejemplos_evidencia]
    return [
        Hallazgo(
            tipo=TipoHallazgo.FILAS_DUPLICADAS,
            columnas_involucradas=[perfil.nombre for perfil in perfiles],
            severidad=Severidad.MEDIA,
            detalle=(
                f"Se encontraron {cantidad} filas duplicadas exactamente. "
                f"Representan el {porcentaje:.1f} % del dataset."
            ),
            evidencia={
                "filas_duplicadas": cantidad,
                "porcentaje": porcentaje,
                "filas": int(len(dataframe)),
                "posiciones_ejemplo": [int(p) for p in posiciones],
            },
            acciones_posibles=[
                "Revisar las filas duplicadas.",
                "Conservarlas si representan observaciones distintas y legítimas.",
                "Eliminarlas en la fase de preparación si son registros repetidos por error.",
            ],
            accion_sugerida="Revisar las filas duplicadas.",
        )
    ]


# --- 2. Valores faltantes ----------------------------------------------------


def contar_centinelas(serie: pd.Series, centinelas: tuple[str, ...]) -> dict[str, int]:
    """Cuenta textos centinela (sin espacios al inicio o al final)."""
    conteo = Counter(v.strip() for v in serie.dropna() if isinstance(v, str))
    return {centinela: conteo[centinela] for centinela in centinelas if conteo[centinela]}


def detectar_valores_faltantes(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Faltantes reales de pandas y textos centinela, por columna.

    Si el porcentaje supera ``porcentaje_maximo_faltantes_advertencia`` se
    añade un hallazgo de alta proporción.
    """
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        hallazgos.extend(_hallazgos_faltantes(serie, perfil.nombre, configuracion))
    return hallazgos


def _hallazgos_faltantes(
    serie: pd.Series, nombre: str, configuracion: ConfiguracionValidacion
) -> list[Hallazgo]:
    nulos = int(serie.isna().sum())
    centinelas = contar_centinelas(serie, configuracion.valores_centinela_faltantes)
    codificados = sum(centinelas.values())
    total = nulos + codificados
    if total == 0:
        return []
    porcentaje = _porcentaje(total, len(serie))
    detalle = f"La columna '{nombre}' contiene {total} valores faltantes ({porcentaje:.1f} %)"
    if codificados:
        lista = ", ".join(f"'{c}': {n}" for c, n in centinelas.items())
        detalle += f" (nulos: {nulos}; codificados como texto: {codificados}, {lista})"
    evidencia = {
        "faltantes": total,
        "porcentaje": porcentaje,
        "faltantes_nulos": nulos,
        "faltantes_centinela": codificados,
        "valores_centinela": centinelas,
        "tipos_faltante": [t for t, n in (("nulo", nulos), ("centinela", codificados)) if n],
    }
    hallazgos = [
        Hallazgo(
            tipo=TipoHallazgo.VALORES_FALTANTES,
            columnas_involucradas=[nombre],
            severidad=Severidad.MEDIA,
            detalle=detalle + ".",
            evidencia=evidencia,
            acciones_posibles=[
                "Revisar el origen de los valores faltantes.",
                "Decidir en la fase de preparación si se imputan o se excluyen.",
            ],
            accion_sugerida="Revisar el origen de los valores faltantes.",
        )
    ]
    umbral = configuracion.porcentaje_maximo_faltantes_advertencia
    if porcentaje > umbral:
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.ALTA_PROPORCION_FALTANTES,
                columnas_involucradas=[nombre],
                severidad=Severidad.ALTA,
                detalle=(
                    f"El {porcentaje:.1f} % de los valores de la columna '{nombre}' "
                    f"faltan, por encima del umbral del {umbral:.1f} %."
                ),
                evidencia={"porcentaje": porcentaje, "umbral": umbral},
                acciones_posibles=[
                    "Evaluar si la columna aporta información suficiente.",
                    "Considerar excluirla del análisis.",
                ],
                accion_sugerida="Evaluar si la columna aporta información suficiente.",
            )
        )
    return hallazgos


# --- 3. Ceros sospechosos ----------------------------------------------------


def detectar_ceros_sospechosos(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Ceros en variables numéricas continuas sin valores negativos.

    Se consideran continuas las columnas numéricas con al menos
    ``minimo_valores_distintos_continua`` valores distintos. Si la columna
    tiene negativos, el cero forma parte natural del rango y no se reporta.
    """
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        if not _es_numerica(serie):
            continue
        valores = serie.dropna()
        if valores.nunique() < configuracion.minimo_valores_distintos_continua:
            continue
        ceros = int((valores == 0).sum())
        if ceros == 0 or bool((valores < 0).any()):
            continue
        porcentaje = _porcentaje(ceros, len(serie))
        positivos = valores[valores > 0]
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.CEROS_SOSPECHOSOS,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.MEDIA,
                detalle=(
                    f"La variable '{perfil.nombre}' contiene {ceros} valores iguales a 0 "
                    f"({porcentaje:.1f} %). Estos valores podrían representar datos "
                    "faltantes codificados como cero."
                ),
                evidencia={
                    "ceros": ceros,
                    "porcentaje": porcentaje,
                    "minimo_distinto_de_cero": _nativo(positivos.min()) if len(positivos) else None,
                    "maximo": _nativo(valores.max()),
                },
                acciones_posibles=[
                    "Verificar si el cero es un valor posible para esta variable.",
                    "Mantener los ceros si representan mediciones reales.",
                    "Tratarlos como faltantes en la fase de preparación si no son válidos.",
                ],
                accion_sugerida="Verificar si el cero es un valor posible para esta variable.",
            )
        )
    return hallazgos


# --- 4. Constantes -----------------------------------------------------------


def detectar_constantes(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas cuyos valores no faltantes son todos iguales."""
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        # El perfil ya contó los valores distintos: solo se inspeccionan las
        # columnas con un único valor.
        if perfil.valores_unicos != 1:
            continue
        [(valor, _)] = _frecuencias(serie)
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.CONSTANTE,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.ALTA,
                detalle=f"La columna '{perfil.nombre}' contiene un único valor ('{valor}').",
                evidencia={"valor": valor, "valores_no_faltantes": int(serie.notna().sum())},
                acciones_posibles=[
                    "Revisar si la columna aporta información.",
                    "Considerar excluirla del análisis.",
                ],
                accion_sugerida="Revisar si la columna aporta información.",
            )
        )
    return hallazgos


# --- 5. Casi constantes ------------------------------------------------------


def detectar_casi_constantes(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas con más de un valor donde el más frecuente supera
    ``porcentaje_casi_constante`` de los valores no faltantes."""
    hallazgos = []
    umbral = configuracion.porcentaje_casi_constante
    for serie, perfil in _columnas(dataframe, perfiles):
        if perfil.valores_unicos < 2:
            continue
        conteo = _conteo_valores(serie)
        validos = int(conteo.sum())
        frecuencia = int(conteo.max())
        if 100.0 * frecuencia / validos <= umbral:
            continue
        # Solo se ordenan los valores empatados en la frecuencia máxima para
        # elegir el principal de forma estable.
        valor = min((_nativo(v) for v in conteo.index[conteo == frecuencia]), key=str)
        porcentaje = _porcentaje(frecuencia, validos)
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.CASI_CONSTANTE,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.MEDIA,
                detalle=(
                    f"El {porcentaje:.1f} % de los registros de la columna "
                    f"'{perfil.nombre}' contienen el mismo valor ('{valor}')."
                ),
                evidencia={
                    "valor_principal": valor,
                    "frecuencia": frecuencia,
                    "porcentaje": porcentaje,
                    "valores_no_faltantes": validos,
                    "valores_distintos": int(len(conteo)),
                    "umbral": umbral,
                },
                acciones_posibles=[
                    "Revisar si la columna aporta información.",
                    "Considerar excluirla del análisis.",
                ],
                accion_sugerida="Revisar si la columna aporta información.",
            )
        )
    return hallazgos


# --- 6. Posibles identificadores ---------------------------------------------


def detectar_posibles_identificadores(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas que probablemente identifican registros.

    Las filas duplicadas exactas se ignoran: repetir un registro completo no
    impide que su columna identificadora lo sea. Criterios:

    - numéricas enteras sin repetir que forman una secuencia consecutivas;
    - numéricas enteras sin repetir cuyo nombre sugiere un identificador;
    - texto con un valor distinto por fila (salvo texto libre o fechas).
    """
    if dataframe.empty:
        return []
    filas_unicas = (~_mascara_filas_duplicadas(dataframe)).to_numpy()
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        valores = serie[filas_unicas]
        criterio = _criterio_identificador(valores, perfil.nombre, configuracion)
        if criterio is None:
            continue
        detalles = {
            "enteros_consecutivos": (
                f"La columna '{perfil.nombre}' contiene enteros consecutivos sin repetir "
                f"({_nativo(valores.min())} a {_nativo(valores.max())})."
            ),
            "nombre_sugerente": (
                f"La columna '{perfil.nombre}' contiene enteros sin repetir y su nombre "
                "sugiere un identificador."
            ),
            "valor_unico_por_fila": (
                f"La columna '{perfil.nombre}' tiene un valor distinto en cada fila."
            ),
        }
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.POSIBLE_IDENTIFICADOR,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.MEDIA,
                detalle=detalles[criterio] + " Probablemente es un identificador.",
                evidencia={
                    "criterio": criterio,
                    "valores_unicos": int(valores.nunique()),
                    "filas_analizadas": int(len(valores)),
                    "ejemplos": _ejemplos(valores, configuracion),
                },
                acciones_posibles=[
                    "Revisar si debe utilizarse como variable predictora.",
                    "Excluirla del análisis si solo identifica registros.",
                ],
                accion_sugerida="Revisar si debe utilizarse como variable predictora.",
            )
        )
    return hallazgos


def _criterio_identificador(
    valores: pd.Series, nombre: str, configuracion: ConfiguracionValidacion
) -> str | None:
    if len(valores) < configuracion.minimo_filas_identificador or valores.isna().any():
        return None
    if _es_numerica(valores):
        if not _son_enteros(valores) or valores.nunique() != len(valores):
            return None
        if _son_enteros_consecutivos(valores):
            return "enteros_consecutivos"
        if _PATRON_NOMBRE_IDENTIFICADOR.search(nombre):
            return "nombre_sugerente"
        return None
    if not _son_textos(valores) or valores.nunique() != len(valores):
        return None
    if _cumple_texto_libre(_metricas_texto(valores), configuracion):
        return None
    if _evidencia_fecha(valores, configuracion) is not None:
        return None
    return "valor_unico_por_fila"


# --- 7. Texto libre ----------------------------------------------------------


def detectar_texto_libre(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas de texto con muchos valores distintos, largos y de varias palabras.

    Deben cumplirse a la vez los umbrales de valores únicos, longitud media y
    palabras por valor, de modo que nombres o códigos no se confundan con
    texto libre.
    """
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        valores = serie.dropna()
        metricas = _metricas_texto(valores)
        if not _cumple_texto_libre(metricas, configuracion):
            continue
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.TEXTO_LIBRE,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.MEDIA,
                detalle=(
                    f"La columna '{perfil.nombre}' parece contener texto libre: "
                    f"longitud media de {metricas['longitud_media']:.1f} caracteres, "
                    f"{metricas['palabras_media']:.1f} palabras por valor y "
                    f"{metricas['porcentaje_valores_unicos']:.1f} % de valores distintos."
                ),
                evidencia={**metricas, "ejemplos": _ejemplos(valores, configuracion)},
                acciones_posibles=[
                    "Revisar si la columna debe excluirse del análisis.",
                    "Derivar variables estructuradas a partir del texto en una fase posterior.",
                ],
                accion_sugerida="Revisar si la columna debe excluirse del análisis.",
            )
        )
    return hallazgos


# --- 8. Fechas ---------------------------------------------------------------


def detectar_fechas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Columnas con fechas: dtype datetime, objetos fecha o texto convertible.

    La detección es conservadora: al menos
    ``porcentaje_minimo_fechas_convertibles`` de los valores deben
    interpretarse con un mismo formato con separadores (ver
    ``nucleo.fechas``). Un nombre sugerente solo se registra como evidencia.
    """
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        evidencia = _evidencia_fecha(serie, configuracion)
        if evidencia is None:
            continue
        if evidencia["origen"] == "texto":
            detalle = (
                f"La columna '{perfil.nombre}' parece contener fechas escritas como texto "
                f"(formato {evidencia['formato']} en el "
                f"{evidencia['porcentaje_convertible']:.1f} % de los valores)."
            )
        else:
            detalle = f"La columna '{perfil.nombre}' contiene fechas."
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.POSIBLE_FECHA,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.BAJA,
                detalle=detalle,
                evidencia={
                    **evidencia,
                    "nombre_sugerente": bool(_PATRON_NOMBRE_FECHA.search(perfil.nombre)),
                    "ejemplos": _ejemplos(serie.dropna(), configuracion),
                },
                acciones_posibles=[
                    "Decidir cómo representar la fecha antes del análisis.",
                    "Derivar variables numéricas (año, mes, antigüedad) en la fase de preparación.",
                    "Excluir la columna si no aporta al análisis.",
                ],
                accion_sugerida="Decidir cómo representar la fecha antes del análisis.",
            )
        )
    return hallazgos


# --- 9. Categóricas ----------------------------------------------------------


def detectar_categoricas(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Variables categóricas y, si hay evidencia de orden, posibles ordinales.

    Candidatas: dtype ``category``; texto con valores repetidos y hasta
    ``maximo_valores_categorica`` valores distintos; enteros con valores
    repetidos y entre ``minimo_valores_categorica_entera`` y
    ``maximo_valores_categorica_entera`` valores distintos.
    """
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        valores = serie.dropna()
        origen = _origen_categorica(serie, valores, configuracion)
        if origen is None:
            continue
        frecuencias = _frecuencias(valores)
        nombres = ", ".join(str(v) for v, _ in frecuencias)
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.VARIABLE_CATEGORICA,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.BAJA,
                detalle=(
                    f"La columna '{perfil.nombre}' parece categórica: "
                    f"{len(frecuencias)} valores distintos ({nombres})."
                ),
                evidencia={
                    "origen": origen,
                    "valores_distintos": len(frecuencias),
                    "categorias": [{"valor": v, "conteo": n} for v, n in frecuencias],
                },
                acciones_posibles=[
                    "Confirmar si la variable es categórica.",
                    "Definir su codificación en la fase de preparación.",
                ],
                accion_sugerida="Confirmar si la variable es categórica.",
            )
        )
        orden = _orden_sugerido(serie, valores)
        if orden is not None:
            criterio, valores_ordenados = orden
            hallazgos.append(
                Hallazgo(
                    tipo=TipoHallazgo.POSIBLE_VARIABLE_ORDINAL,
                    columnas_involucradas=[perfil.nombre],
                    severidad=Severidad.BAJA,
                    detalle=(
                        f"Los valores de la columna '{perfil.nombre}' sugieren un orden "
                        f"natural: {' < '.join(str(v) for v in valores_ordenados)}."
                    ),
                    evidencia={"criterio": criterio, "orden_sugerido": valores_ordenados},
                    acciones_posibles=[
                        "Confirmar si el orden sugerido es correcto.",
                        "Tratarla como ordinal en la fase de preparación.",
                    ],
                    accion_sugerida="Confirmar si el orden sugerido es correcto.",
                )
            )
    return hallazgos


def _origen_categorica(
    serie: pd.Series, valores: pd.Series, configuracion: ConfiguracionValidacion
) -> str | None:
    if valores.empty:
        return None
    if isinstance(serie.dtype, pd.CategoricalDtype):
        return "tipo_categoria"
    if _son_textos(valores):
        distintos = valores.nunique()
        if not 2 <= distintos <= configuracion.maximo_valores_categorica:
            return None
        if distintos >= len(valores) or _evidencia_fecha(valores, configuracion) is not None:
            return None
        return "texto"
    if _es_numerica(serie) and _son_enteros(valores):
        distintos = valores.nunique()
        minimo = configuracion.minimo_valores_categorica_entera
        maximo = configuracion.maximo_valores_categorica_entera
        if not minimo <= distintos <= maximo or distintos >= len(valores):
            return None
        return "enteros"
    return None


# --- Asimetría fuerte ---------------------------------------------------------------


def detectar_asimetria(
    dataframe: pd.DataFrame,
    configuracion: ConfiguracionValidacion,
    perfiles: list[PerfilColumna],
) -> list[Hallazgo]:
    """Variables continuas estrictamente positivas y muy asimétricas a la derecha.

    Se informa si la asimetría (coeficiente de Fisher-Pearson ajustado de
    pandas) supera ``umbral_asimetria``; una transformación logarítmica suele
    acercarlas a la normalidad que suponen pruebas como Fisher-z.
    """
    hallazgos = []
    for serie, perfil in _columnas(dataframe, perfiles):
        if not _es_numerica(serie):
            continue
        if perfil.valores_unicos < configuracion.minimo_valores_distintos_continua:
            continue
        valores = serie.dropna()
        if float(valores.min()) <= 0:
            continue
        asimetria = float(valores.skew())
        if asimetria <= configuracion.umbral_asimetria:
            continue
        hallazgos.append(
            Hallazgo(
                tipo=TipoHallazgo.ASIMETRIA_FUERTE,
                columnas_involucradas=[perfil.nombre],
                severidad=Severidad.BAJA,
                detalle=(
                    f"La variable '{perfil.nombre}' es positiva y muy asimétrica "
                    f"(asimetría = {asimetria:.2f}). Una transformación logarítmica puede "
                    "hacer su distribución más simétrica."
                ),
                evidencia={
                    "asimetria": round(asimetria, 4),
                    "umbral": configuracion.umbral_asimetria,
                    "minimo": _nativo(valores.min()),
                    "mediana": float(valores.median()),
                    "maximo": _nativo(valores.max()),
                },
                acciones_posibles=[
                    "Aplicar una transformación logarítmica.",
                    "Conservar la variable como está.",
                ],
                accion_sugerida="Aplicar una transformación logarítmica.",
            )
        )
    return hallazgos


# --- 10. Distribución del objetivo ------------------------------------------


def detectar_distribucion_objetivo(
    serie: pd.Series,
    tipo_objetivo: str | None,
    configuracion: ConfiguracionValidacion,
) -> list[Hallazgo]:
    """Cantidad y porcentaje por clase de un objetivo binario o multiclase."""
    if tipo_objetivo not in (TipoObjetivo.BINARIO, TipoObjetivo.MULTICLASE):
        return []
    frecuencias = _frecuencias(serie)
    total = sum(n for _, n in frecuencias)
    distribucion = [
        {"valor": v, "conteo": n, "porcentaje": _porcentaje(n, total)} for v, n in frecuencias
    ]
    resumen = "; ".join(
        f"{d['valor']}: {d['conteo']} ({d['porcentaje']:.1f} %)" for d in distribucion
    )
    return [
        Hallazgo(
            tipo=TipoHallazgo.DISTRIBUCION_OBJETIVO,
            columnas_involucradas=[str(serie.name)],
            severidad=Severidad.BAJA,
            detalle=(
                f"La variable objetivo '{serie.name}' tiene {len(distribucion)} clases. "
                f"{resumen}."
            ),
            evidencia={
                "tipo_objetivo": tipo_objetivo,
                "clases": len(distribucion),
                "valores_no_faltantes": total,
                "distribucion": distribucion,
            },
            acciones_posibles=["Comprobar que las clases sean las esperadas."],
            accion_sugerida="Comprobar que las clases sean las esperadas.",
        )
    ]


# --- 11. Desbalance de clases ------------------------------------------------


def detectar_desbalance_objetivo(
    serie: pd.Series,
    tipo_objetivo: str | None,
    configuracion: ConfiguracionValidacion,
) -> list[Hallazgo]:
    """Objetivo binario cuya clase minoritaria es menor que
    ``porcentaje_desbalance_clase`` (comparación estricta)."""
    if tipo_objetivo != TipoObjetivo.BINARIO:
        return []
    frecuencias = _frecuencias(serie)
    total = sum(n for _, n in frecuencias)
    clase, conteo = frecuencias[-1]
    umbral = configuracion.porcentaje_desbalance_clase
    if 100.0 * conteo / total >= umbral:
        return []
    porcentaje = _porcentaje(conteo, total)
    return [
        Hallazgo(
            tipo=TipoHallazgo.DESBALANCE_CLASES,
            columnas_involucradas=[str(serie.name)],
            severidad=Severidad.MEDIA,
            detalle=(
                f"La clase minoritaria ('{clase}') representa el {porcentaje:.1f} % de los "
                "registros. Puede existir un problema de desbalance de clases."
            ),
            evidencia={
                "clase_minoritaria": clase,
                "conteo": conteo,
                "porcentaje": porcentaje,
                "umbral": umbral,
            },
            acciones_posibles=[
                "Tener en cuenta el desbalance al interpretar los resultados.",
                "Considerar técnicas de balanceo en una fase posterior.",
            ],
            accion_sugerida="Tener en cuenta el desbalance al interpretar los resultados.",
        )
    ]

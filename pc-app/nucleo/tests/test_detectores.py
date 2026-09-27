"""Pruebas de los detectores básicos de revisión."""

import datetime
import json

import numpy as np
import pandas as pd
import pytest

from nucleo import detectores as det
from nucleo.configuracion import ConfiguracionValidacion
from nucleo.modelos import Severidad, TipoHallazgo, TipoObjetivo
from nucleo.perfilado import perfilar_columnas
from nucleo.revision import DETECTORES, DETECTORES_OBJETIVO, revisar_dataset
from nucleo.utilidades import a_diccionario_serializable
from nucleo.validacion import validar_dataset

CONFIG = ConfiguracionValidacion()


def ejecutar(detector, dataframe, configuracion=CONFIG):
    return detector(dataframe, configuracion, perfilar_columnas(dataframe, configuracion))


def columna(detector, valores, nombre="columna"):
    return ejecutar(detector, pd.DataFrame({nombre: valores}))


def tipos(hallazgos):
    return [h.tipo for h in hallazgos]


def frases(n):
    temas = ["matemáticas", "lectura", "ciencias", "historia", "arte"]
    return [
        f"El estudiante {i} mostró interés en {temas[i % 5]} durante la actividad {i}."
        for i in range(n)
    ]


# --- No modificación (todos los detectores) ----------------------------------


def dataset_problematico():
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 1],
            "texto": [" NA ", "?", None, "x", "y", " NA "],
            "peso": [0.0, 61.2, np.nan, 70.4, 0.0, 0.0],
            "fecha": ["2024-01-01", "2024-01-02", None, "2024-01-04", "2024-01-05", "2024-01-01"],
            "lista": [[1], [2], [1], [3], [4], [1]],
            "constante": ["A"] * 6,
        }
    )


@pytest.mark.parametrize("detector", DETECTORES, ids=lambda d: d.__name__)
def test_detectores_no_modifican_el_dataframe(detector):
    dataframe = dataset_problematico()
    copia = dataframe.copy(deep=True)

    ejecutar(detector, dataframe)

    pd.testing.assert_frame_equal(dataframe, copia)


@pytest.mark.parametrize("detector", DETECTORES_OBJETIVO, ids=lambda d: d.__name__)
def test_detectores_objetivo_no_modifican_la_serie(detector):
    serie = pd.Series(["A"] * 9 + ["B"], name="objetivo")
    copia = serie.copy()

    detector(serie, TipoObjetivo.BINARIO, CONFIG)

    pd.testing.assert_series_equal(serie, copia)


# --- 1. Filas duplicadas -----------------------------------------------------


def test_duplicados_detecta_fila_repetida():
    dataframe = pd.DataFrame({"A": [1, 2, 1], "B": ["x", "y", "x"]})

    [hallazgo] = ejecutar(det.detectar_filas_duplicadas, dataframe)

    assert hallazgo.tipo == TipoHallazgo.FILAS_DUPLICADAS
    assert hallazgo.columnas_involucradas == ["A", "B"]
    assert hallazgo.evidencia["filas_duplicadas"] == 1
    assert hallazgo.evidencia["porcentaje"] == 33.33
    assert hallazgo.evidencia["posiciones_ejemplo"] == [2]


def test_duplicados_filas_distintas():
    dataframe = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})

    assert ejecutar(det.detectar_filas_duplicadas, dataframe) == []


def test_duplicados_parciales_no_cuentan():
    dataframe = pd.DataFrame({"A": [1, 1, 1], "B": ["x", "y", "z"]})

    assert ejecutar(det.detectar_filas_duplicadas, dataframe) == []


def test_duplicados_con_faltantes_y_valores_no_hashables():
    dataframe = pd.DataFrame({"A": [np.nan, np.nan, 1.0], "B": [[1], [1], [2]]})

    [hallazgo] = ejecutar(det.detectar_filas_duplicadas, dataframe)

    assert hallazgo.evidencia["filas_duplicadas"] == 1


# --- 2. Valores faltantes ----------------------------------------------------


def test_faltantes_reales_y_centinela():
    valores = [np.nan, None, pd.NA, "NA", "?", "-", " NA ", " ? ", " - ", "a"]

    hallazgo, alta = columna(
        det.detectar_valores_faltantes, pd.Series(valores, dtype=object), "peso"
    )

    assert hallazgo.tipo == TipoHallazgo.VALORES_FALTANTES
    assert alta.tipo == TipoHallazgo.ALTA_PROPORCION_FALTANTES
    assert hallazgo.evidencia["faltantes"] == 9
    assert hallazgo.evidencia["faltantes_nulos"] == 3
    assert hallazgo.evidencia["faltantes_centinela"] == 6
    assert hallazgo.evidencia["valores_centinela"] == {"NA": 2, "?": 2, "-": 2}
    assert hallazgo.evidencia["tipos_faltante"] == ["nulo", "centinela"]
    assert hallazgo.detalle.startswith("La columna 'peso' contiene 9 valores faltantes (90.0 %)")


def test_faltantes_mensaje_solo_nulos():
    valores = [1.0] * 132 + [np.nan] * 18

    [hallazgo] = columna(det.detectar_valores_faltantes, valores, "peso")

    assert hallazgo.detalle == "La columna 'peso' contiene 18 valores faltantes (12.0 %)."


def test_faltantes_sin_faltantes():
    assert columna(det.detectar_valores_faltantes, ["NAtural", "-5", "¿?", "a", "N/A"]) == []
    assert columna(det.detectar_valores_faltantes, [1, 2, 3]) == []


@pytest.mark.parametrize("faltantes, alta", [(40, False), (41, True)])
def test_faltantes_umbral_alta_proporcion(faltantes, alta):
    valores = [np.nan] * faltantes + [1.0] * (100 - faltantes)

    hallazgos = columna(det.detectar_valores_faltantes, valores)

    esperado = [TipoHallazgo.VALORES_FALTANTES]
    if alta:
        esperado.append(TipoHallazgo.ALTA_PROPORCION_FALTANTES)
    assert tipos(hallazgos) == esperado


def test_faltantes_umbral_configurable():
    configuracion = ConfiguracionValidacion(porcentaje_maximo_faltantes_advertencia=10.0)
    dataframe = pd.DataFrame({"a": [np.nan] * 2 + [1.0] * 8})

    hallazgos = ejecutar(det.detectar_valores_faltantes, dataframe, configuracion)

    assert TipoHallazgo.ALTA_PROPORCION_FALTANTES in tipos(hallazgos)


# --- 3. Ceros sospechosos ----------------------------------------------------


def continua(n=50, semilla=0):
    return np.random.default_rng(semilla).normal(70, 8, n).round(1)


def test_ceros_en_variable_continua():
    valores = continua()
    valores[[3, 10, 20]] = 0

    [hallazgo] = columna(det.detectar_ceros_sospechosos, valores, "peso")

    assert hallazgo.tipo == TipoHallazgo.CEROS_SOSPECHOSOS
    assert hallazgo.evidencia["ceros"] == 3
    assert hallazgo.evidencia["porcentaje"] == 6.0
    assert hallazgo.evidencia["minimo_distinto_de_cero"] > 0
    assert hallazgo.detalle.startswith("La variable 'peso' contiene 3 valores iguales a 0 (6.0 %).")


def test_ceros_sin_ceros():
    assert columna(det.detectar_ceros_sospechosos, continua()) == []


def test_ceros_en_variable_discreta_no_se_reportan():
    assert columna(det.detectar_ceros_sospechosos, [0, 1] * 25) == []


def test_ceros_con_valores_negativos_no_se_reportan():
    valores = np.linspace(-10, 10, 21)

    assert 0 in valores
    assert columna(det.detectar_ceros_sospechosos, valores) == []


# --- 4 y 5. Constantes y casi constantes -------------------------------------


def test_constante():
    [hallazgo] = columna(det.detectar_constantes, ["A"] * 5, "sexo")

    assert hallazgo.tipo == TipoHallazgo.CONSTANTE
    assert hallazgo.severidad == Severidad.ALTA
    assert hallazgo.detalle == "La columna 'sexo' contiene un único valor ('A')."


def test_constante_ignora_faltantes():
    assert tipos(columna(det.detectar_constantes, ["A", None, "A"])) == [TipoHallazgo.CONSTANTE]


def test_no_constante():
    assert columna(det.detectar_constantes, ["A", "B", "A"]) == []
    assert columna(det.detectar_constantes, [np.nan, np.nan]) == []


def test_casi_constante():
    [hallazgo] = columna(det.detectar_casi_constantes, ["A"] * 999 + ["B"], "estado")

    assert hallazgo.tipo == TipoHallazgo.CASI_CONSTANTE
    assert hallazgo.evidencia["valor_principal"] == "A"
    assert hallazgo.evidencia["porcentaje"] == 99.9


@pytest.mark.parametrize("mayoritarios, total", [(990, 1000), (9, 10)])
def test_casi_constante_no_supera_umbral(mayoritarios, total):
    valores = ["A"] * mayoritarios + ["B"] * (total - mayoritarios)

    assert columna(det.detectar_casi_constantes, valores) == []


def test_constante_no_es_casi_constante():
    assert columna(det.detectar_casi_constantes, ["A"] * 1000) == []


# --- 6. Posibles identificadores ---------------------------------------------


def test_identificador_enteros_consecutivos():
    [hallazgo] = columna(det.detectar_posibles_identificadores, [3, 1, 2, 5, 4], "id")

    assert hallazgo.tipo == TipoHallazgo.POSIBLE_IDENTIFICADOR
    assert hallazgo.evidencia["criterio"] == "enteros_consecutivos"


def test_enteros_unicos_no_consecutivos_no_son_identificador():
    assert columna(det.detectar_posibles_identificadores, [10, 20, 30, 40, 50]) == []


def test_enteros_unicos_con_nombre_sugerente():
    valores = [48213, 10442, 77, 5, 9021]

    [hallazgo] = columna(det.detectar_posibles_identificadores, valores, "id_estudiante")

    assert hallazgo.evidencia["criterio"] == "nombre_sugerente"


def test_valores_repetidos_no_son_identificador():
    assert columna(det.detectar_posibles_identificadores, [1, 2, 2, 3, 4]) == []


def test_codigos_de_texto_unicos():
    codigos = [f"A{i:03d}" for i in range(8)]

    [hallazgo] = columna(det.detectar_posibles_identificadores, codigos, "codigo")

    assert hallazgo.evidencia["criterio"] == "valor_unico_por_fila"


def test_identificador_tolera_filas_duplicadas_completas():
    dataframe = pd.DataFrame({"id": [1, 2, 3, 4, 5, 1], "x": [7, 8, 9, 7, 8, 7]})

    hallazgos = ejecutar(det.detectar_posibles_identificadores, dataframe)

    assert [h.columnas_involucradas for h in hallazgos] == [["id"]]


def test_continuas_texto_libre_y_fechas_no_son_identificador():
    dataframe = pd.DataFrame(
        {
            "peso": continua(20) + np.linspace(0, 0.5, 20),
            "observacion": frases(20),
            "fecha": pd.date_range("2024-01-01", periods=20).strftime("%Y-%m-%d"),
        }
    )

    assert ejecutar(det.detectar_posibles_identificadores, dataframe) == []


def test_identificador_minimo_de_filas():
    assert columna(det.detectar_posibles_identificadores, [1, 2, 3, 4]) == []


# --- 7. Texto libre ----------------------------------------------------------


def test_texto_libre():
    [hallazgo] = columna(det.detectar_texto_libre, frases(30), "observaciones")

    assert hallazgo.tipo == TipoHallazgo.TEXTO_LIBRE
    assert hallazgo.evidencia["porcentaje_valores_unicos"] == 100.0
    assert hallazgo.evidencia["palabras_media"] >= 4


def test_categoria_no_es_texto_libre():
    assert columna(det.detectar_texto_libre, ["M", "F", "M", "F"], "sexo") == []


def test_nombres_unicos_no_son_texto_libre():
    nombres = ["Ana Pérez", "Luis Gómez", "María Ruiz", "Pedro Sosa", "Julia Vera"]

    assert columna(det.detectar_texto_libre, nombres, "nombre") == []


def test_frases_largas_repetidas_no_son_texto_libre():
    valores = ["El estudiante aprobó todas las evaluaciones del curso."] * 8 + [
        "El estudiante no presentó la evaluación final del curso."
    ] * 8

    assert columna(det.detectar_texto_libre, valores) == []


# --- 8. Fechas ---------------------------------------------------------------


def test_fecha_datetime():
    [hallazgo] = columna(det.detectar_fechas, pd.date_range("2024-01-01", periods=5), "fecha")

    assert hallazgo.tipo == TipoHallazgo.POSIBLE_FECHA
    assert hallazgo.evidencia["origen"] == "tipo_fecha"
    assert hallazgo.evidencia["nombre_sugerente"] is True
    json.dumps(a_diccionario_serializable(hallazgo))


def test_fecha_objetos_date():
    valores = [datetime.date(2024, 1, d) for d in range(1, 6)]

    [hallazgo] = columna(det.detectar_fechas, valores, "ingreso")

    assert hallazgo.evidencia["origen"] == "objetos_fecha"


@pytest.mark.parametrize(
    "valores, formato",
    [
        (["2024-01-05", "2024-02-10", " 2024-03-15 ", None], "%Y-%m-%d"),
        (["05/01/2024", "10/02/2024", "15/03/2024"], "%d/%m/%Y"),
    ],
)
def test_fecha_texto(valores, formato):
    [hallazgo] = columna(det.detectar_fechas, valores, "registro")

    assert hallazgo.evidencia["origen"] == "texto"
    assert hallazgo.evidencia["formato"] == formato
    assert hallazgo.evidencia["nombre_sugerente"] is False


def test_texto_normal_no_es_fecha():
    assert columna(det.detectar_fechas, ["hola", "mundo", "2024"], "fecha") == []


def test_enteros_con_forma_de_fecha_no_son_fecha():
    assert columna(det.detectar_fechas, [20240101, 20240102, 20240103], "fecha") == []


def test_fechas_insuficientes_no_se_reportan():
    valores = [f"2024-01-{d:02d}" for d in range(1, 10)] + ["sin fecha"]

    assert columna(det.detectar_fechas, valores) == []


# --- 9. Categóricas ----------------------------------------------------------


def test_categorica_texto_con_orden():
    valores = ["medio", "bajo", "alto", "Alto", "bajo", "medio"]

    categorica, ordinal = columna(det.detectar_categoricas, valores, "nivel")

    assert categorica.tipo == TipoHallazgo.VARIABLE_CATEGORICA
    assert categorica.evidencia["origen"] == "texto"
    assert ordinal.tipo == TipoHallazgo.POSIBLE_VARIABLE_ORDINAL
    assert ordinal.evidencia["orden_sugerido"] == ["bajo", "medio", "Alto", "alto"]


def test_categorica_texto_sin_orden():
    hallazgos = columna(det.detectar_categoricas, ["M", "F", "M", "F"], "sexo")

    assert tipos(hallazgos) == [TipoHallazgo.VARIABLE_CATEGORICA]
    assert hallazgos[0].evidencia["categorias"] == [
        {"valor": "F", "conteo": 2},
        {"valor": "M", "conteo": 2},
    ]


def test_categorica_enteros_ordinal():
    categorica, ordinal = columna(det.detectar_categoricas, [1, 2, 3] * 10, "nivel")

    assert categorica.evidencia["origen"] == "enteros"
    assert ordinal.evidencia == {
        "criterio": "enteros_consecutivos",
        "orden_sugerido": [1, 2, 3],
    }


def test_categorica_dtype_category_ordenada():
    serie = pd.Categorical(["b", "a", "c", "a"], categories=["c", "b", "a"], ordered=True)

    categorica, ordinal = columna(det.detectar_categoricas, serie)

    assert categorica.evidencia["origen"] == "tipo_categoria"
    assert ordinal.evidencia["orden_sugerido"] == ["c", "b", "a"]


@pytest.mark.parametrize(
    "valores",
    [
        continua(),  # continua con muchos valores distintos
        [0, 1] * 20,  # entero binario
        list(range(30)) * 2,  # demasiados valores enteros distintos
        [10, 20, 30, 40, 50],  # enteros sin repetición
        ["A1", "A2", "A3", "A4"],  # texto sin repetición
        ["2024-01-01", "2024-01-02"] * 3,  # fechas
    ],
)
def test_no_categoricas(valores):
    assert columna(det.detectar_categoricas, valores) == []


# --- 10 y 11. Objetivo -------------------------------------------------------


def serie_objetivo(conteos, nombre="aprobado"):
    return pd.Series([v for v, n in conteos.items() for _ in range(n)], name=nombre)


def test_distribucion_objetivo_binario():
    serie = serie_objetivo({1: 720, 0: 280})

    [hallazgo] = det.detectar_distribucion_objetivo(serie, TipoObjetivo.BINARIO, CONFIG)

    assert hallazgo.tipo == TipoHallazgo.DISTRIBUCION_OBJETIVO
    assert hallazgo.evidencia["clases"] == 2
    assert hallazgo.evidencia["distribucion"] == [
        {"valor": 1, "conteo": 720, "porcentaje": 72.0},
        {"valor": 0, "conteo": 280, "porcentaje": 28.0},
    ]
    assert "1: 720 (72.0 %); 0: 280 (28.0 %)" in hallazgo.detalle


def test_distribucion_objetivo_multiclase():
    serie = serie_objetivo({"A": 50, "B": 30, "C": 20})

    [hallazgo] = det.detectar_distribucion_objetivo(serie, TipoObjetivo.MULTICLASE, CONFIG)

    assert [d["valor"] for d in hallazgo.evidencia["distribucion"]] == ["A", "B", "C"]
    assert [d["porcentaje"] for d in hallazgo.evidencia["distribucion"]] == [50.0, 30.0, 20.0]


def test_distribucion_no_aplica_a_objetivo_continuo():
    serie = pd.Series(continua(), name="y")

    assert det.detectar_distribucion_objetivo(serie, TipoObjetivo.CONTINUO, CONFIG) == []


def test_desbalance_detectado():
    serie = serie_objetivo({"A": 90, "B": 10})

    [hallazgo] = det.detectar_desbalance_objetivo(serie, TipoObjetivo.BINARIO, CONFIG)

    assert hallazgo.tipo == TipoHallazgo.DESBALANCE_CLASES
    assert hallazgo.evidencia["clase_minoritaria"] == "B"
    assert hallazgo.detalle.startswith("La clase minoritaria ('B') representa el 10.0 %")


def test_desbalance_limite_estricto():
    serie = serie_objetivo({"A": 80, "B": 20})

    assert det.detectar_desbalance_objetivo(serie, TipoObjetivo.BINARIO, CONFIG) == []


def test_desbalance_solo_para_binarios():
    serie = serie_objetivo({"A": 80, "B": 15, "C": 5})

    assert det.detectar_desbalance_objetivo(serie, TipoObjetivo.MULTICLASE, CONFIG) == []


# --- Integración -------------------------------------------------------------

# Posición del detector que produce cada tipo de hallazgo.
ORDEN_DETECTOR = {
    TipoHallazgo.FILAS_DUPLICADAS: 0,
    TipoHallazgo.VALORES_FALTANTES: 1,
    TipoHallazgo.ALTA_PROPORCION_FALTANTES: 1,
    TipoHallazgo.CEROS_SOSPECHOSOS: 2,
    TipoHallazgo.CONSTANTE: 3,
    TipoHallazgo.CASI_CONSTANTE: 4,
    TipoHallazgo.POSIBLE_IDENTIFICADOR: 5,
    TipoHallazgo.TEXTO_LIBRE: 6,
    TipoHallazgo.POSIBLE_FECHA: 7,
    TipoHallazgo.VARIABLE_CATEGORICA: 8,
    TipoHallazgo.POSIBLE_VARIABLE_ORDINAL: 8,
    TipoHallazgo.DISTRIBUCION_OBJETIVO: 9,
    TipoHallazgo.DESBALANCE_CLASES: 10,
    TipoHallazgo.COLUMNAS_REDUNDANTES: 11,
    TipoHallazgo.RECODIFICACION_UNO_A_UNO: 12,
    TipoHallazgo.COLUMNA_DERIVADA: 13,
    TipoHallazgo.BINARIA_DERIVADA: 14,
    TipoHallazgo.CORRELACION_CASI_PERFECTA: 15,
    TipoHallazgo.POSIBLE_MEZCLA_UNIDADES: 16,
}


def dataset_integracion():
    n = 118
    rng = np.random.default_rng(42)
    peso = rng.normal(70, 10, n).round(1)
    peso[[5, 17, 40]] = 0
    altura = list(rng.normal(1.70, 0.1, n).round(2))
    altura[3], altura[8], altura[20] = np.nan, "NA", " ? "
    base = pd.DataFrame(
        {
            "id": range(1, n + 1),
            "peso": peso,
            "altura": pd.Series(altura, dtype=object),
            "pais": "Perú",
            "estado": ["activo"] * (n - 1) + ["inactivo"],
            "observaciones": frases(n),
            "fecha_registro": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
            "nivel": ["bajo", "medio", "alto"] * 39 + ["bajo"],
            "aprobado": ["no" if i % 10 == 0 else "si" for i in range(n)],
        }
    )
    return pd.concat([base, base.iloc[:2]], ignore_index=True)


def test_integracion_revision_completa():
    dataframe = dataset_integracion()
    copia = dataframe.copy(deep=True)
    assert validar_dataset(dataframe, "aprobado").valido

    informe = revisar_dataset(dataframe, "aprobado")

    pd.testing.assert_frame_equal(dataframe, copia)
    encontrados = {(h.tipo, tuple(h.columnas_involucradas)) for h in informe.hallazgos}
    assert {
        (TipoHallazgo.FILAS_DUPLICADAS, tuple(dataframe.columns)),
        (TipoHallazgo.VALORES_FALTANTES, ("altura",)),
        (TipoHallazgo.CEROS_SOSPECHOSOS, ("peso",)),
        (TipoHallazgo.CONSTANTE, ("pais",)),
        (TipoHallazgo.CASI_CONSTANTE, ("estado",)),
        (TipoHallazgo.POSIBLE_IDENTIFICADOR, ("id",)),
        (TipoHallazgo.TEXTO_LIBRE, ("observaciones",)),
        (TipoHallazgo.POSIBLE_FECHA, ("fecha_registro",)),
        (TipoHallazgo.VARIABLE_CATEGORICA, ("nivel",)),
        (TipoHallazgo.POSIBLE_VARIABLE_ORDINAL, ("nivel",)),
        (TipoHallazgo.DISTRIBUCION_OBJETIVO, ("aprobado",)),
        (TipoHallazgo.DESBALANCE_CLASES, ("aprobado",)),
    } <= encontrados
    # Sin falsos positivos obvios.
    assert (TipoHallazgo.POSIBLE_IDENTIFICADOR, ("observaciones",)) not in encontrados
    assert (TipoHallazgo.POSIBLE_IDENTIFICADOR, ("fecha_registro",)) not in encontrados
    assert (TipoHallazgo.TEXTO_LIBRE, ("nivel",)) not in encontrados
    assert not any(tipo == TipoHallazgo.CEROS_SOSPECHOSOS and cols != ("peso",)
                   for tipo, cols in encontrados)


def test_integracion_orden_estable_y_reproducible():
    primero = revisar_dataset(dataset_integracion(), "aprobado")
    segundo = revisar_dataset(dataset_integracion(), "aprobado")

    orden = tipos(primero.hallazgos)
    assert orden == sorted(orden, key=ORDEN_DETECTOR.__getitem__)
    assert a_diccionario_serializable(primero) == a_diccionario_serializable(segundo)


def test_integracion_serializable_a_json():
    dataframe = dataset_integracion()
    dataframe["momento"] = pd.date_range("2024-01-01", periods=len(dataframe), freq="h")

    informe = revisar_dataset(dataframe, "aprobado")
    texto = json.dumps(a_diccionario_serializable(informe), ensure_ascii=False)

    datos = json.loads(texto)
    assert len(datos["hallazgos"]) == len(informe.hallazgos)
    assert all(isinstance(h["severidad"], str) for h in datos["hallazgos"])


def test_objetivo_inexistente_no_ejecuta_detectores_de_objetivo():
    informe = revisar_dataset(dataset_integracion(), "no_existe")

    assert TipoHallazgo.DISTRIBUCION_OBJETIVO not in tipos(informe.hallazgos)

"""Pruebas de los detectores de relaciones entre columnas y mezcla de unidades."""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo import detectores_relaciones as rel
from pcapp_nucleo.carga import cargar_dataset, obtener_hojas_excel
from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.modelos import TipoHallazgo
from pcapp_nucleo.perfilado import perfilar_columnas
from pcapp_nucleo.revision import DETECTORES_RELACIONES, revisar_dataset
from pcapp_nucleo.utilidades import a_diccionario_serializable

CONFIG = ConfiguracionValidacion()
DATASETS_PRUEBA = Path(__file__).resolve().parents[2] / "datasets_prueba"


def ejecutar(detector, dataframe, configuracion=CONFIG):
    return detector(dataframe, configuracion, perfilar_columnas(dataframe, configuracion))


def tipos(hallazgos):
    return [h.tipo for h in hallazgos]


# --- No modificación y serialización ------------------------------------------


def dataset_con_relaciones():
    n = 120
    rng = np.random.default_rng(7)
    edad = rng.integers(10, 60, n)
    minimo = rng.integers(0, 50, n)
    altura_m = rng.normal(1.7, 0.1, n).round(3)
    peso = np.concatenate([rng.normal(25, 4, n // 2), rng.normal(75, 5, n // 2)]).round(1)
    return pd.DataFrame(
        {
            "fecha": pd.date_range("2024-01-01", periods=n, freq="D"),
            "sexo": ["M", "F"] * (n // 2),
            "sexo_codigo": np.array([1, 0] * (n // 2), dtype=np.int64),
            "edad": edad,
            "edad_copia": edad.copy(),
            "adulto": (edad >= 18).astype(int),
            "minimo": minimo,
            "maximo": minimo + rng.integers(1, 30, n),
            "altura_m": altura_m,
            "altura_cm": altura_m * 100,
            "peso": peso,
            "nota": [np.nan if i % 7 == 0 else float(i % 11) for i in range(n)],
        }
    ).assign(ancho=lambda d: d["maximo"] - d["minimo"])


@pytest.mark.parametrize("detector", DETECTORES_RELACIONES, ids=lambda d: d.__name__)
def test_detectores_no_modifican_el_dataframe(detector):
    dataframe = dataset_con_relaciones()
    copia = dataframe.copy(deep=True)

    ejecutar(detector, dataframe)

    assert dataframe.equals(copia)
    pd.testing.assert_frame_equal(dataframe, copia)


@pytest.mark.parametrize("detector", DETECTORES_RELACIONES, ids=lambda d: d.__name__)
def test_hallazgos_serializables(detector):
    hallazgos = ejecutar(detector, dataset_con_relaciones())

    assert hallazgos, "el dataset de prueba debe producir al menos un hallazgo"
    json.dumps(a_diccionario_serializable(hallazgos), ensure_ascii=False)


# --- 12. Copias exactas ------------------------------------------------------


def test_copia_exacta():
    dataframe = pd.DataFrame({"A": [10, 20, 30], "B": [10, 20, 30]})

    [hallazgo] = ejecutar(rel.detectar_copias_exactas, dataframe)

    assert hallazgo.tipo == TipoHallazgo.COLUMNAS_REDUNDANTES
    assert hallazgo.columnas_involucradas == ["A", "B"]
    assert hallazgo.evidencia["tipo_relacion"] == "copia_exacta"
    assert hallazgo.evidencia["coincidencia"] == 1.0
    assert hallazgo.evidencia["original_sugerida"] == ["A"]
    assert hallazgo.evidencia["derivada_sugerida"] == ["B"]


def test_no_copia_si_difiere():
    dataframe = pd.DataFrame({"A": [10, 20, 30], "B": [11, 21, 31]})

    assert ejecutar(rel.detectar_copias_exactas, dataframe) == []


def test_copia_con_faltantes_en_las_mismas_filas_y_texto():
    dataframe = pd.DataFrame(
        {
            "a": [1.0, np.nan, 3.0, 4.0],
            "b": [1.0, np.nan, 3.0, 4.0],
            "c": [1.0, 2.0, 3.0, np.nan],
            "t1": ["x", "y", "x", "z"],
            "t2": ["x", "y", "x", "z"],
        }
    )

    hallazgos = ejecutar(rel.detectar_copias_exactas, dataframe)

    assert [h.columnas_involucradas for h in hallazgos] == [["a", "b"], ["t1", "t2"]]


def test_copias_en_datasets_grandes_con_tipos_y_faltantes_distintos():
    n = 300
    valores = np.arange(n, dtype=np.int64)
    con_faltantes = np.where(valores % 4 == 0, np.nan, valores * 0.5)
    dataframe = pd.DataFrame(
        {
            "entero": valores,
            "decimal": valores.astype(float),
            "f1": con_faltantes,
            "f2": con_faltantes.copy(),
            "otra": np.random.default_rng(0).normal(size=n),
        }
    )

    hallazgos = ejecutar(rel.detectar_copias_exactas, dataframe)

    assert [h.columnas_involucradas for h in hallazgos] == [["entero", "decimal"], ["f1", "f2"]]


def test_columnas_constantes_iguales_no_son_copias():
    dataframe = pd.DataFrame({"a": [1, 1, 1], "b": [1, 1, 1]})

    assert ejecutar(rel.detectar_copias_exactas, dataframe) == []


# --- 13. Recodificación uno a uno --------------------------------------------


def test_recodificacion_uno_a_uno():
    dataframe = pd.DataFrame({"sexo": ["M", "F", "M", "F"], "codigo": [1, 0, 1, 0]})

    [hallazgo] = ejecutar(rel.detectar_recodificaciones, dataframe)

    assert hallazgo.tipo == TipoHallazgo.RECODIFICACION_UNO_A_UNO
    assert hallazgo.evidencia["correspondencia"] == [
        {"valor_a": "F", "valor_b": 0},
        {"valor_a": "M", "valor_b": 1},
    ]


def test_muchos_a_uno_no_es_recodificacion():
    dataframe = pd.DataFrame(
        {
            "ciudad": ["Montería", "Lorica", "Sincelejo"] * 2,
            "departamento": ["Córdoba", "Córdoba", "Sucre"] * 2,
        }
    )

    assert ejecutar(rel.detectar_recodificaciones, dataframe) == []


def test_correspondencia_incompleta_no_es_recodificacion():
    dataframe = pd.DataFrame({"sexo": ["M", "F", "M", "F", "M"], "codigo": [1, 0, 1, 0, 0]})

    assert ejecutar(rel.detectar_recodificaciones, dataframe) == []


def test_copia_y_columnas_sin_repeticion_no_son_recodificacion():
    dataframe = pd.DataFrame(
        {"s1": ["M", "F", "M"], "s2": ["M", "F", "M"], "x": [1.5, 2.5, 3.5], "y": [7, 8, 9]}
    )

    assert ejecutar(rel.detectar_recodificaciones, dataframe) == []


# --- 14. Relaciones matemáticas ------------------------------------------------


def relacion(dataframe):
    [hallazgo] = ejecutar(rel.detectar_relaciones_matematicas, dataframe)
    assert hallazgo.tipo == TipoHallazgo.COLUMNA_DERIVADA
    return hallazgo


def test_suma():
    hallazgo = relacion(pd.DataFrame({"A": [10, 20, 30], "B": [5, 7, 8], "C": [15, 27, 38]}))

    assert hallazgo.evidencia["operacion"] == "C = A + B"
    assert hallazgo.evidencia["tipo_relacion"] == "suma"
    assert hallazgo.columnas_involucradas == ["A", "B", "C"]


def test_suma_que_falla_en_una_fila():
    dataframe = pd.DataFrame({"A": [10, 20, 30], "B": [5, 7, 8], "C": [15, 27, 39]})

    assert ejecutar(rel.detectar_relaciones_matematicas, dataframe) == []


def test_resta():
    hallazgo = relacion(pd.DataFrame({"A": [20, 30, 40], "B": [5, 8, 10], "C": [15, 22, 30]}))

    assert hallazgo.evidencia["operacion"] == "C = A - B"
    assert hallazgo.evidencia["tipo_relacion"] == "resta"


def test_resta_invertida():
    hallazgo = relacion(pd.DataFrame({"B": [5, 8, 10], "A": [20, 30, 40], "C": [-15, -22, -30]}))

    assert hallazgo.evidencia["operacion"] == "C = B - A"


def test_ancho_igual_a_maximo_menos_minimo():
    dataframe = pd.DataFrame(
        {"minimo": [10, 20, 5], "maximo": [25, 30, 18], "ancho": [15, 10, 13]}
    )

    hallazgo = relacion(dataframe)

    assert hallazgo.evidencia["operacion"] == "ancho = maximo - minimo"
    assert hallazgo.evidencia["original_sugerida"] == ["maximo", "minimo"]
    assert hallazgo.evidencia["derivada_sugerida"] == ["ancho"]
    assert hallazgo.detalle.startswith("La columna 'ancho' parece ser igual a maximo - minimo")


def test_tolerancia_punto_flotante():
    a, b = [0.1, 0.2, 0.3], [0.2, 0.3, 0.4]
    assert 0.1 + 0.2 != 0.3  # la suma exacta en binario no coincide

    hallazgo = relacion(pd.DataFrame({"A": a, "B": b, "C": [0.3, 0.5, 0.7]}))

    assert hallazgo.evidencia["error_maximo"] < 1e-12


def test_diferencia_real_no_se_acepta():
    dataframe = pd.DataFrame({"A": [0.1, 0.2, 0.3], "B": [0.2, 0.3, 0.4], "C": [0.3, 0.5, 0.7001]})

    assert ejecutar(rel.detectar_relaciones_matematicas, dataframe) == []


def test_relacion_con_faltantes_y_muchas_filas():
    n = 500
    rng = np.random.default_rng(3)
    dataframe = pd.DataFrame(
        {"base": rng.normal(100, 20, n), "impuesto": rng.normal(10, 2, n), "ruido": rng.normal(size=n)}
    )
    dataframe["total"] = dataframe["base"] + dataframe["impuesto"]
    dataframe.loc[[0, 10, 60], "total"] = np.nan

    hallazgo = relacion(dataframe)

    assert hallazgo.evidencia["operacion"] == "total = base + impuesto"
    assert hallazgo.evidencia["filas_comparadas"] == n - 3


# --- 15. Binarias derivadas --------------------------------------------------


def test_binaria_derivada_de_umbral():
    dataframe = pd.DataFrame({"edad": [10, 15, 17, 18, 20, 30], "adulto": [0, 0, 0, 1, 1, 1]})

    [hallazgo] = ejecutar(rel.detectar_binarias_derivadas, dataframe)

    assert hallazgo.tipo == TipoHallazgo.BINARIA_DERIVADA
    assert hallazgo.columnas_involucradas == ["edad", "adulto"]
    assert hallazgo.evidencia["umbral"] == 18
    assert hallazgo.evidencia["clase_superior"] == 1
    assert hallazgo.evidencia["regla"] == "adulto = 1 si edad >= 18; 0 en otro caso"
    assert hallazgo.evidencia["derivada_sugerida"] == ["adulto"]
    assert hallazgo.evidencia["acierto_balanceado"] == 1.0


def test_binaria_sin_separacion():
    dataframe = pd.DataFrame({"edad": [10, 15, 18, 20], "grupo": [0, 1, 0, 1]})

    assert ejecutar(rel.detectar_binarias_derivadas, dataframe) == []


def test_binaria_aleatoria_no_es_derivada():
    rng = np.random.default_rng(5)
    dataframe = pd.DataFrame({"x": rng.normal(size=200), "grupo": rng.integers(0, 2, 200)})

    assert ejecutar(rel.detectar_binarias_derivadas, dataframe) == []


@pytest.mark.parametrize("errores, detectada", [(1, True), (5, False)])
def test_binaria_casi_perfecta(errores, detectada):
    x = np.arange(200, dtype=float)
    grupo = np.where(x >= 100, "alto", "bajo")
    # Errores intercalados bajo el umbral (98, 96, ...): ningún otro umbral los evita.
    grupo[98 - 2 * np.arange(errores)] = "alto"
    dataframe = pd.DataFrame({"x": x, "grupo": grupo})

    hallazgos = ejecutar(rel.detectar_binarias_derivadas, dataframe)

    assert bool(hallazgos) is detectada


def test_clase_muy_minoritaria_sin_separacion_no_es_derivada():
    # Caso real (fetal_health): 7 valores minoritarios de 2126. Predecir
    # siempre la clase mayoritaria acierta el 99.7 % de las filas.
    n = 2126
    x = np.random.default_rng(4).normal(140, 10, n)
    rara = np.zeros(n)
    rara[np.argsort(x)[[10, 500, 900, 1300, 1800, 2000, 2120]]] = 0.001
    dataframe = pd.DataFrame({"x": x, "rara": rara})

    assert ejecutar(rel.detectar_binarias_derivadas, dataframe) == []


def test_clase_minoritaria_separada_perfectamente_si_es_derivada():
    x = np.arange(500, dtype=float)
    dataframe = pd.DataFrame({"x": x, "extremo": (x >= 495).astype(int)})

    [hallazgo] = ejecutar(rel.detectar_binarias_derivadas, dataframe)

    assert hallazgo.evidencia["umbral"] == 495.0
    assert hallazgo.evidencia["errores"] == 0


# --- 16. Correlaciones casi perfectas ----------------------------------------


def test_correlacion_lineal_exacta():
    dataframe = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [2, 4, 6, 8, 10]})

    [hallazgo] = ejecutar(rel.detectar_correlaciones_casi_perfectas, dataframe)

    assert hallazgo.tipo == TipoHallazgo.CORRELACION_CASI_PERFECTA
    assert hallazgo.evidencia["correlacion"] == 1.0
    assert hallazgo.evidencia["tipo_relacion"] == "transformacion_lineal"
    assert (hallazgo.evidencia["pendiente"], hallazgo.evidencia["intercepto"]) == (2.0, 0.0)
    assert "puede indicar redundancia" in hallazgo.detalle


def test_correlacion_por_debajo_del_umbral():
    dataframe = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [2, 1, 4, 3, 5]})

    assert ejecutar(rel.detectar_correlaciones_casi_perfectas, dataframe) == []


def test_correlacion_alta_no_lineal_exacta():
    x = np.linspace(0, 10, 200)
    ruido = np.random.default_rng(1).normal(0, 0.05, 200)
    dataframe = pd.DataFrame({"x": x, "y": 3 * x + ruido})

    [hallazgo] = ejecutar(rel.detectar_correlaciones_casi_perfectas, dataframe)

    assert hallazgo.evidencia["tipo_relacion"] == "correlacion"
    assert abs(hallazgo.evidencia["correlacion"]) > CONFIG.umbral_correlacion_casi_perfecta


def test_correlacion_negativa():
    dataframe = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [10, 8, 6, 4, 2]})

    [hallazgo] = ejecutar(rel.detectar_correlaciones_casi_perfectas, dataframe)

    assert hallazgo.evidencia["correlacion"] == -1.0


def test_umbral_de_correlacion_es_estricto():
    configuracion = ConfiguracionValidacion(umbral_correlacion_casi_perfecta=1.0)
    dataframe = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [2, 4, 6, 8, 10]})

    assert ejecutar(rel.detectar_correlaciones_casi_perfectas, dataframe, configuracion) == []


def test_relaciones_no_se_repiten_para_copias():
    dataframe = pd.DataFrame(
        {"A": [10, 20, 30], "A2": [10, 20, 30], "B": [5, 7, 8], "C": [15, 27, 38]}
    )

    hallazgos = ejecutar(rel.detectar_relaciones_matematicas, dataframe)

    assert [h.evidencia["operacion"] for h in hallazgos] == ["C = A + B"]


def test_copias_y_recodificaciones_no_se_repiten_como_correlacion():
    dataframe = pd.DataFrame(
        {"a": [1, 2, 3, 4], "a_copia": [1, 2, 3, 4], "s": [0, 1, 0, 1], "s_inv": [1, 0, 1, 0]}
    )

    assert ejecutar(rel.detectar_correlaciones_casi_perfectas, dataframe) == []


# --- 17. Posible mezcla de unidades ------------------------------------------


def test_mezcla_de_unidades():
    dataframe = pd.DataFrame({"peso": [18, 21, 24, 30, 33, 65, 70, 75, 80, 85]})

    [hallazgo] = ejecutar(rel.detectar_mezcla_unidades, dataframe)

    assert hallazgo.tipo == TipoHallazgo.POSIBLE_MEZCLA_UNIDADES
    assert hallazgo.evidencia["grupo_bajo"]["maximo"] == 33
    assert hallazgo.evidencia["grupo_alto"]["minimo"] == 65
    assert "podría deberse a diferentes unidades" in hallazgo.detalle
    assert "periodos" not in hallazgo.evidencia


def test_distribucion_uniforme_no_es_mezcla():
    dataframe = pd.DataFrame({"edad": [18, 20, 21, 23, 25, 27, 29, 31, 33, 35]})

    assert ejecutar(rel.detectar_mezcla_unidades, dataframe) == []


def test_normal_y_asimetrica_no_son_mezcla():
    rng = np.random.default_rng(11)
    dataframe = pd.DataFrame(
        {"normal": rng.normal(50, 10, 1000), "ingresos": rng.lognormal(10, 0.8, 1000)}
    )

    assert ejecutar(rel.detectar_mezcla_unidades, dataframe) == []


def test_ceros_o_codigos_aislados_no_son_mezcla():
    valores = list(np.linspace(60, 80, 40)) + [0.0] * 10

    assert ejecutar(rel.detectar_mezcla_unidades, pd.DataFrame({"peso": valores})) == []


def test_mezcla_con_periodos_temporales():
    rng = np.random.default_rng(2)
    fechas = pd.date_range("2024-01-01", "2024-12-31", periods=120)
    peso = np.where(fechas < "2024-07-01", rng.uniform(18, 34, 120), rng.uniform(60, 89, 120))
    dataframe = pd.DataFrame({"fecha": fechas.strftime("%Y-%m-%d"), "peso": peso.round(1)})

    [hallazgo] = ejecutar(rel.detectar_mezcla_unidades, dataframe)

    assert hallazgo.columnas_involucradas == ["peso", "fecha"]
    periodos = hallazgo.evidencia["periodos"]
    assert periodos["grupo_bajo"]["desde"] == "2024-01-01"
    assert periodos["grupo_alto"]["hasta"] == "2024-12-31"
    assert periodos["grupo_bajo"]["hasta"] < periodos["grupo_alto"]["desde"]


def test_mezcla_sin_relacion_temporal_no_inventa_periodos():
    peso = [18, 21, 24, 30, 33, 65, 70, 75, 80, 85] * 3
    fechas = pd.date_range("2024-01-01", periods=30).strftime("%Y-%m-%d")

    [hallazgo] = ejecutar(rel.detectar_mezcla_unidades, pd.DataFrame({"f": fechas, "peso": peso}))

    assert "periodos" not in hallazgo.evidencia
    assert hallazgo.columnas_involucradas == ["peso"]


# --- Integración ---------------------------------------------------------------


def test_integracion_revision_con_relaciones():
    dataframe = dataset_con_relaciones()
    copia = dataframe.copy(deep=True)

    informe = revisar_dataset(dataframe, "adulto")

    assert dataframe.equals(copia)
    encontrados = {(h.tipo, tuple(h.columnas_involucradas)) for h in informe.hallazgos}
    assert {
        (TipoHallazgo.COLUMNAS_REDUNDANTES, ("edad", "edad_copia")),
        (TipoHallazgo.RECODIFICACION_UNO_A_UNO, ("sexo", "sexo_codigo")),
        (TipoHallazgo.COLUMNA_DERIVADA, ("minimo", "maximo", "ancho")),
        (TipoHallazgo.BINARIA_DERIVADA, ("edad", "adulto")),
        (TipoHallazgo.CORRELACION_CASI_PERFECTA, ("altura_m", "altura_cm")),
        (TipoHallazgo.POSIBLE_MEZCLA_UNIDADES, ("peso", "fecha")),
    } <= encontrados
    # La copia exacta no se repite como correlación ni como recodificación.
    pares_edad = [h for h in informe.hallazgos if set(h.columnas_involucradas) == {"edad", "edad_copia"}]
    assert tipos(pares_edad) == [TipoHallazgo.COLUMNAS_REDUNDANTES]
    # Las relaciones de la copia no se repiten (adulto solo deriva de edad).
    binarias = [h for h in informe.hallazgos if h.tipo == TipoHallazgo.BINARIA_DERIVADA]
    assert [h.columnas_involucradas for h in binarias] == [["edad", "adulto"]]
    # La transformación lineal se informa una sola vez.
    pares_altura = [h for h in informe.hallazgos if set(h.columnas_involucradas) == {"altura_m", "altura_cm"}]
    assert tipos(pares_altura) == [TipoHallazgo.CORRELACION_CASI_PERFECTA]
    assert pares_altura[0].evidencia["tipo_relacion"] == "transformacion_lineal"
    json.dumps(a_diccionario_serializable(informe), ensure_ascii=False)


def test_detectores_avanzados_despues_de_los_del_objetivo():
    informe = revisar_dataset(dataset_con_relaciones(), "adulto")
    orden = tipos(informe.hallazgos)

    ultimo_objetivo = max(
        i for i, t in enumerate(orden)
        if t in (TipoHallazgo.DISTRIBUCION_OBJETIVO, TipoHallazgo.DESBALANCE_CLASES)
    )
    primero_avanzado = orden.index(TipoHallazgo.COLUMNAS_REDUNDANTES)
    assert ultimo_objetivo < primero_avanzado


# --- Datasets reales (si existen) -----------------------------------------------


def datasets_reales():
    """CSV y XLSX de datasets_prueba/, sin los conjuntos generados por 'preparar'."""
    if not DATASETS_PRUEBA.is_dir():
        return []
    generado = re.compile(r".*_(train|test)(_\d+)?\.csv$", re.IGNORECASE)
    return sorted(
        ruta for ruta in DATASETS_PRUEBA.iterdir()
        if ruta.suffix.lower() in (".csv", ".xlsx") and not generado.match(ruta.name)
    )


@pytest.mark.skipif(not datasets_reales(), reason="No hay datasets reales en datasets_prueba/.")
@pytest.mark.parametrize("ruta", datasets_reales(), ids=lambda r: r.name)
def test_datasets_reales_se_revisan_sin_errores(ruta):
    hojas = obtener_hojas_excel(ruta) if ruta.suffix.lower() == ".xlsx" else [None]
    for hoja in hojas:
        dataframe = cargar_dataset(ruta, hoja=hoja)
        copia = dataframe.copy(deep=True)

        informe = revisar_dataset(dataframe, None)

        assert dataframe.equals(copia)
        json.dumps(a_diccionario_serializable(informe), ensure_ascii=False)

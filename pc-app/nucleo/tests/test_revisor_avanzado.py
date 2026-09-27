"""Pruebas de los ajustes al revisor: fechas, faltantes dependientes del objetivo,
grupos redundantes, tamaño efectivo, asimetría e identificadores de hallazgos."""

import json

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo import detectores as det
from pcapp_nucleo.configuracion import ConfiguracionValidacion
from pcapp_nucleo.detectores_objetivo import (
    detectar_faltantes_dependientes_objetivo,
    detectar_tamano_efectivo,
)
from pcapp_nucleo.detectores_relaciones import detectar_grupos_redundantes
from pcapp_nucleo.fechas import interpretar_fechas_texto
from pcapp_nucleo.modelos import Hallazgo, Severidad, TipoColumna, TipoHallazgo, TipoObjetivo
from pcapp_nucleo.perfilado import perfilar_columna, perfilar_columnas
from pcapp_nucleo.revision import DETECTORES_CON_OBJETIVO, revisar_dataset
from pcapp_nucleo.utilidades import a_diccionario_serializable

CONFIG = ConfiguracionValidacion()


def ejecutar(detector, dataframe):
    return detector(dataframe, CONFIG, perfilar_columnas(dataframe, CONFIG))


def ejecutar_con_objetivo(detector, dataframe, objetivo, tipo):
    posicion = list(dataframe.columns).index(objetivo)
    return detector(dataframe, posicion, tipo, CONFIG, perfilar_columnas(dataframe, CONFIG))


# --- A1. Fechas ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valores, formato",
    [
        (["01.01.23", "02.01.23", "15.03.23", "31.12.23"], "%d.%m.%y"),
        (["05/01/2024", "31/12/2024", "15/06/2024"], "%d/%m/%Y"),
        (["2024-01-05", "2024-12-31", "2024-06-15"], "%Y-%m-%d"),
        (["2024/01/05", "2024/12/31"], "%Y/%m/%d"),
        (["12-31-2024", "01-15-2024"], "%m-%d-%Y"),
    ],
)
def test_formatos_de_fecha(valores, formato):
    [hallazgo] = ejecutar(det.detectar_fechas, pd.DataFrame({"Date": valores}))

    assert hallazgo.evidencia["formato"] == formato
    assert hallazgo.evidencia["porcentaje_convertible"] == 100.0
    assert perfilar_columna(pd.Series(valores), "Date").tipo_detectado == TipoColumna.FECHA


def test_fecha_ambigua_prefiere_dia_primero_e_informa_alternativa():
    [hallazgo] = ejecutar(det.detectar_fechas, pd.DataFrame({"f": ["01.02.23", "03.04.23"]}))

    assert hallazgo.evidencia["formato"] == "%d.%m.%y"
    assert "%m.%d.%y" in hallazgo.evidencia["formatos_alternativos"]


@pytest.mark.parametrize("validas, detectada", [(9, True), (8, False)])
def test_umbral_del_90_por_ciento(validas, detectada):
    valores = [f"{d:02d}.01.23" for d in range(1, validas + 1)] + ["sin dato"] * (10 - validas)

    assert (interpretar_fechas_texto(pd.Series(valores), 90.0) is not None) is detectada


@pytest.mark.parametrize("valores", [["20240101", "20240102"], ["1.5", "2.25"], ["hola", "mundo"]])
def test_no_son_fechas(valores):
    assert interpretar_fechas_texto(pd.Series(valores), 90.0) is None


def test_fechas_con_y_sin_hora():
    valores = ["05/01/2024", "10/02/2024 08:30", "11/02/2024T10:00:00"]

    assert interpretar_fechas_texto(pd.Series(valores), 90.0).formato == "%d/%m/%Y"


# --- A2. Faltantes que dependen del objetivo ---------------------------------------------------


def dataset_faltantes(n=600, semilla=0):
    rng = np.random.default_rng(semilla)
    objetivo = np.repeat([0, 1], n // 2)
    aleatoria = rng.normal(size=n)
    aleatoria[rng.random(n) < 0.25] = np.nan
    ferritina = rng.normal(500, 100, n)
    probabilidad = np.where(objetivo == 0, 0.45, 0.09)  # como en el dengue pediátrico
    ferritina[rng.random(n) < probabilidad] = np.nan
    return pd.DataFrame({"aleatoria": aleatoria, "ferritina": ferritina, "grupo": objetivo})


def test_faltantes_concentrados_en_una_clase():
    hallazgos = ejecutar_con_objetivo(
        detectar_faltantes_dependientes_objetivo, dataset_faltantes(), "grupo", TipoObjetivo.BINARIO
    )

    assert [h.columnas_involucradas for h in hallazgos] == [["ferritina", "grupo"]]
    hallazgo = hallazgos[0]
    assert hallazgo.severidad == Severidad.ALTA
    por_clase = hallazgo.evidencia["porcentaje_faltantes_por_clase"]
    assert por_clase["0"] > 35 and por_clase["1"] < 15
    assert hallazgo.evidencia["p_valor"] < 0.05
    assert "Imputar y agregar un indicador de 'dato medido'." in hallazgo.acciones_posibles


def test_faltantes_al_azar_no_se_marcan():
    dataframe = dataset_faltantes().drop(columns=["ferritina"])

    assert ejecutar_con_objetivo(
        detectar_faltantes_dependientes_objetivo, dataframe, "grupo", TipoObjetivo.BINARIO
    ) == []


def test_diferencia_pequena_aunque_significativa_no_se_marca():
    rng = np.random.default_rng(1)
    n = 20000
    objetivo = np.repeat([0, 1], n // 2)
    x = rng.normal(size=n)
    x[rng.random(n) < np.where(objetivo == 0, 0.20, 0.25)] = np.nan
    dataframe = pd.DataFrame({"x": x, "y": objetivo})

    assert ejecutar_con_objetivo(
        detectar_faltantes_dependientes_objetivo, dataframe, "y", TipoObjetivo.BINARIO
    ) == []


def test_faltantes_centinela_cuentan():
    dataframe = dataset_faltantes()
    texto = dataframe["ferritina"].round(1).astype(object)
    texto[texto.isna()] = "NA"
    dataframe["ferritina"] = texto

    hallazgos = ejecutar_con_objetivo(
        detectar_faltantes_dependientes_objetivo, dataframe, "grupo", TipoObjetivo.BINARIO
    )

    assert [h.columnas_involucradas[0] for h in hallazgos] == ["ferritina"]


def test_objetivo_continuo_mann_whitney():
    rng = np.random.default_rng(2)
    y = rng.normal(size=500)
    medida = rng.normal(size=500)
    medida[y > 0.8] = np.nan  # falta cuando el objetivo es alto
    azar = rng.normal(size=500)
    azar[rng.random(500) < 0.2] = np.nan
    dataframe = pd.DataFrame({"medida": medida, "azar": azar, "y": y})

    hallazgos = ejecutar_con_objetivo(
        detectar_faltantes_dependientes_objetivo, dataframe, "y", TipoObjetivo.CONTINUO
    )

    assert [h.columnas_involucradas[0] for h in hallazgos] == ["medida"]
    assert hallazgos[0].evidencia["prueba"] == "mann_whitney"


# --- A3. Grupos redundantes --------------------------------------------------------------------


def test_grupo_de_tres_variables_relacionadas():
    rng = np.random.default_rng(3)
    a = rng.normal(size=300)
    dataframe = pd.DataFrame(
        {
            "hb": a,
            "pcv": 3 * a + rng.normal(0, 0.8, 300),
            "exp_hb": np.exp(a) + rng.normal(0, 0.05, 300),
            "otra": rng.normal(size=300),
            "y": a + rng.normal(size=300),
        }
    )

    [hallazgo] = ejecutar_con_objetivo(detectar_grupos_redundantes, dataframe, "y", TipoObjetivo.CONTINUO)

    assert hallazgo.tipo == TipoHallazgo.GRUPO_REDUNDANTE
    assert hallazgo.columnas_involucradas == ["hb", "pcv", "exp_hb"]
    assert hallazgo.severidad == Severidad.MEDIA
    assert "no significa que no importen" in hallazgo.detalle
    assert all("eliminar" not in a.lower() for a in hallazgo.acciones_posibles)


def test_variables_independientes_no_forman_grupo():
    rng = np.random.default_rng(4)
    dataframe = pd.DataFrame(rng.normal(size=(300, 4)), columns=["a", "b", "c", "y"])

    assert ejecutar_con_objetivo(detectar_grupos_redundantes, dataframe, "y", TipoObjetivo.CONTINUO) == []


def test_objetivo_no_participa_y_pares_casi_perfectos_no_se_repiten():
    rng = np.random.default_rng(5)
    a = rng.normal(size=300)
    dataframe = pd.DataFrame(
        {"a": a, "a_cm": a * 100 + 0.001 * rng.normal(size=300), "y": a + rng.normal(0, 0.1, 300)}
    )

    assert ejecutar_con_objetivo(detectar_grupos_redundantes, dataframe, "y", TipoObjetivo.CONTINUO) == []


# --- A4. Tamaño efectivo ------------------------------------------------------------------------


def dataset_clases(minoritaria, mayoritaria, variables):
    rng = np.random.default_rng(6)
    n = minoritaria + mayoritaria
    datos = {f"x{i}": rng.normal(size=n) for i in range(variables)}
    datos["y"] = [1] * minoritaria + [0] * mayoritaria
    return pd.DataFrame(datos)


@pytest.mark.parametrize(
    "minoritaria, variables, motivo",
    [(30, 2, "tiene 30 casos"), (60, 10, "6.0 casos por cada una de las 10 variables")],
)
def test_tamano_efectivo_insuficiente(minoritaria, variables, motivo):
    dataframe = dataset_clases(minoritaria, 500, variables)

    [hallazgo] = ejecutar_con_objetivo(detectar_tamano_efectivo, dataframe, "y", TipoObjetivo.BINARIO)

    assert hallazgo.tipo == TipoHallazgo.TAMANO_EFECTIVO_INSUFICIENTE
    assert motivo in hallazgo.detalle
    assert "PC tendrá poca potencia" in hallazgo.detalle


def test_tamano_efectivo_suficiente():
    dataframe = dataset_clases(200, 300, 5)

    assert ejecutar_con_objetivo(detectar_tamano_efectivo, dataframe, "y", TipoObjetivo.BINARIO) == []


def test_tamano_efectivo_no_aplica_a_objetivo_continuo():
    dataframe = dataset_clases(10, 100, 5)

    assert ejecutar_con_objetivo(detectar_tamano_efectivo, dataframe, "y", TipoObjetivo.CONTINUO) == []


# --- Asimetría ---------------------------------------------------------------------------------------


def test_asimetria_fuerte_en_variable_positiva():
    valores = np.random.default_rng(7).lognormal(0, 1.2, 500)

    [hallazgo] = ejecutar(det.detectar_asimetria, pd.DataFrame({"ferritina": valores}))

    assert hallazgo.tipo == TipoHallazgo.ASIMETRIA_FUERTE
    assert hallazgo.evidencia["asimetria"] > CONFIG.umbral_asimetria


@pytest.mark.parametrize(
    "valores",
    [
        np.random.default_rng(8).normal(50, 5, 500),
        np.concatenate([[0.0], np.random.default_rng(9).lognormal(0, 1.2, 499)]),
    ],
    ids=["simetrica", "con_cero"],
)
def test_sin_asimetria_o_no_positiva(valores):
    assert ejecutar(det.detectar_asimetria, pd.DataFrame({"x": valores})) == []


# --- Integración e identificadores ---------------------------------------------------------------


def test_identificadores_de_hallazgos_unicos_y_deterministas():
    dataframe = dataset_faltantes()
    dataframe["y2"] = dataframe["grupo"]

    primero = revisar_dataset(dataframe, "grupo")
    segundo = revisar_dataset(dataframe, "grupo")

    identificadores = [h.identificador for h in primero.hallazgos]
    assert len(identificadores) == len(set(identificadores))
    assert identificadores == [h.identificador for h in segundo.hallazgos]
    assert "faltantes_dependientes_objetivo:ferritina|grupo" in identificadores
    json.dumps(a_diccionario_serializable(primero))


def test_identificador_por_defecto():
    hallazgo = Hallazgo("tipo_x", ["a", "b"], Severidad.BAJA, "detalle")

    assert hallazgo.identificador == "tipo_x:a|b"
    assert Hallazgo("t", [str(i) for i in range(9)], Severidad.BAJA, "d").identificador == "t"


def test_detectores_con_objetivo_no_modifican_el_dataframe():
    dataframe = dataset_faltantes()
    copia = dataframe.copy(deep=True)

    for detector in DETECTORES_CON_OBJETIVO:
        ejecutar_con_objetivo(detector, dataframe, "grupo", TipoObjetivo.BINARIO)

    pd.testing.assert_frame_equal(dataframe, copia)

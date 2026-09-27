"""Pruebas del perfilado de columnas y del informe de revisión."""

import json

import numpy as np
import pandas as pd
import pytest

from nucleo.modelos import Hallazgo, Severidad, TipoColumna, TipoObjetivo
from nucleo.perfilado import perfilar_columna, perfilar_columnas
from nucleo.revision import revisar_dataset
from nucleo.utilidades import a_diccionario_serializable

from .conftest import OBJETIVO, construir_dataset


def perfil(valores, nombre="columna"):
    return perfilar_columna(pd.Series(valores), nombre)


# --- Perfil de columnas ------------------------------------------------------


def test_perfil_numerico():
    resultado = perfil([3.5, 1, 7, np.nan, 7, 2, np.nan, 10, 4, 5])

    assert resultado.tipo_detectado == TipoColumna.NUMERICA
    assert resultado.faltantes == 2
    assert resultado.porcentaje_faltantes == 20.0
    assert resultado.valores_unicos == 7
    assert resultado.minimo == 1.0
    assert resultado.maximo == 10.0
    assert type(resultado.minimo) is float
    assert type(resultado.maximo) is float


def test_perfil_numerico_entero_devuelve_int_nativo():
    resultado = perfil(np.array([5, -2, 9], dtype=np.int64))

    assert (resultado.minimo, resultado.maximo) == (-2, 9)
    assert type(resultado.minimo) is int


def test_perfil_texto():
    valores = [f"comentario número {i}" for i in range(30)] + [None, None]

    resultado = perfil(valores)

    assert resultado.tipo_detectado == TipoColumna.TEXTO
    assert resultado.valores_unicos == 30
    assert resultado.faltantes == 2
    assert resultado.minimo is None and resultado.maximo is None


def test_perfil_categorica():
    resultado = perfil(["norte", "sur", "sur", "este", None])

    assert resultado.tipo_detectado == TipoColumna.CATEGORICA
    assert resultado.valores_unicos == 3


def test_perfil_categorica_por_dtype():
    resultado = perfil(pd.Categorical(["a", "b", "a"]))

    assert resultado.tipo_detectado == TipoColumna.CATEGORICA


@pytest.mark.parametrize(
    "valores",
    [[True, False, True], [True, None, False], pd.array([True, None, False], dtype="boolean")],
)
def test_perfil_booleana(valores):
    resultado = perfil(valores)

    assert resultado.tipo_detectado == TipoColumna.BOOLEANA
    assert resultado.valores_unicos == 2
    assert resultado.minimo is None and resultado.maximo is None


@pytest.mark.parametrize(
    "valores",
    [
        pd.to_datetime(["2024-01-05", "2024-02-10", None]),
        ["2024-01-05", "2024-02-10", None],
        ["05/01/2024", "10/02/2024 08:30"],
    ],
)
def test_perfil_fecha(valores):
    resultado = perfil(valores)

    assert resultado.tipo_detectado == TipoColumna.FECHA
    assert resultado.minimo is None and resultado.maximo is None


@pytest.mark.parametrize("valor_faltante", [np.nan, None])
def test_perfil_columna_totalmente_faltante(valor_faltante):
    resultado = perfil([valor_faltante] * 8)

    assert resultado.tipo_detectado == TipoColumna.VACIA
    assert resultado.faltantes == 8
    assert resultado.porcentaje_faltantes == 100.0
    assert resultado.valores_unicos == 0
    assert resultado.minimo is None
    assert resultado.maximo is None


@pytest.mark.parametrize(
    "valores",
    [
        [1, "a", 2.5, None, True, pd.Timestamp("2024-01-01")],
        [[1, 2], {"a": 1}, [1, 2], "texto"],
    ],
)
def test_perfil_mezcla_de_tipos_no_falla(valores):
    serie = pd.Series(valores, dtype=object)
    copia = serie.copy()

    resultado = perfilar_columna(serie, "mezcla")

    assert resultado.tipo_detectado in {TipoColumna.CATEGORICA, TipoColumna.TEXTO}
    assert resultado.minimo is None
    pd.testing.assert_series_equal(serie, copia)


def test_perfil_valores_unicos_con_repetidos():
    resultado = perfil(["a", "b", "a", "a", "c", "b", None])

    assert resultado.valores_unicos == 3


def test_faltantes_solo_reales():
    resultado = perfil(["NA", "N/A", "?", "-", "null", None])

    assert resultado.faltantes == 1
    assert resultado.valores_unicos == 5


def test_perfilar_columnas_con_nombres_repetidos():
    dataframe = pd.DataFrame([[1, "x"], [2, "y"]], columns=["edad", "edad"])

    perfiles = perfilar_columnas(dataframe)

    assert [(p.nombre, p.tipo_detectado) for p in perfiles] == [
        ("edad", TipoColumna.NUMERICA),
        ("edad", TipoColumna.CATEGORICA),
    ]


# --- Tipo del objetivo -------------------------------------------------------


def dataset_con_objetivo(valores):
    dataframe = construir_dataset(filas=len(valores))
    dataframe[OBJETIVO] = valores
    return dataframe


def test_objetivo_binario():
    informe = revisar_dataset(dataset_con_objetivo(["si", "no"] * 60), OBJETIVO)

    assert informe.resumen["tipo_objetivo"] == TipoObjetivo.BINARIO


def test_objetivo_multiclase():
    informe = revisar_dataset(dataset_con_objetivo(["bajo", "medio", "alto"] * 40), OBJETIVO)

    assert informe.resumen["tipo_objetivo"] == TipoObjetivo.MULTICLASE


def test_objetivo_numerico_con_pocas_clases_enteras_es_multiclase():
    informe = revisar_dataset(dataset_con_objetivo([1, 2, 3, 4] * 30), OBJETIVO)

    assert informe.resumen["tipo_objetivo"] == TipoObjetivo.MULTICLASE


def test_objetivo_continuo():
    valores = np.random.default_rng(1).normal(100, 15, size=120)

    informe = revisar_dataset(dataset_con_objetivo(valores), OBJETIVO)

    assert informe.resumen["tipo_objetivo"] == TipoObjetivo.CONTINUO


@pytest.mark.parametrize(
    "columnas, objetivo",
    [(["x0", "x1", "x2", OBJETIVO], "diabetes"), (["x0", "x1", OBJETIVO, OBJETIVO], OBJETIVO)],
)
def test_objetivo_invalido_no_lanza_excepcion(columnas, objetivo):
    dataframe = construir_dataset()
    dataframe.columns = columnas

    informe = revisar_dataset(dataframe, objetivo)

    assert informe.resumen["tipo_objetivo"] is None
    assert informe.informacion_objetivo["encontrado"] is False


def test_objetivo_constante_no_se_clasifica():
    informe = revisar_dataset(dataset_con_objetivo([1] * 120), OBJETIVO)

    assert informe.resumen["tipo_objetivo"] is None


# --- Informe de revisión -----------------------------------------------------


def dataset_mixto():
    filas = 120
    dataframe = construir_dataset(filas=filas)
    dataframe["ciudad"] = ["Lima", "Quito", "Bogotá"] * 40
    dataframe["fecha"] = pd.date_range("2024-01-01", periods=filas)
    dataframe["activo"] = [True, False] * 60
    dataframe.loc[:9, "x0"] = np.nan
    return dataframe


def test_informe_revision_resumen_y_perfiles():
    dataframe = dataset_mixto()

    informe = revisar_dataset(
        dataframe, OBJETIVO, detectores=(),
        detectores_objetivo=(),
        detectores_relaciones=(),
        detectores_con_objetivo=(),
    )

    assert informe.hallazgos == []
    assert [p.nombre for p in informe.perfiles_columnas] == list(dataframe.columns)
    assert informe.objetivo == OBJETIVO
    assert informe.resumen == {
        "filas": 120,
        "columnas": 7,
        "columnas_numericas": 4,
        "columnas_categoricas": 1,
        "columnas_texto": 0,
        "columnas_fecha": 1,
        "columnas_booleanas": 1,
        "columnas_vacias": 0,
        "total_faltantes": 10,
        "objetivo": OBJETIVO,
        "tipo_objetivo": TipoObjetivo.BINARIO,
    }


def test_revision_no_modifica_el_dataframe():
    dataframe = dataset_mixto()
    copia = dataframe.copy()

    revisar_dataset(dataframe, OBJETIVO)

    pd.testing.assert_frame_equal(dataframe, copia)


def test_informe_serializable_a_json():
    dataframe = dataset_mixto()
    dataframe["vacia"] = np.nan

    informe = revisar_dataset(dataframe, OBJETIVO)
    datos = json.loads(json.dumps(a_diccionario_serializable(informe), ensure_ascii=False))

    assert datos["resumen"]["tipo_objetivo"] == "binario"
    assert isinstance(datos["hallazgos"], list)
    assert datos["perfiles_columnas"][-1]["tipo_detectado"] == "vacia"


def test_revision_ejecuta_detectores_inyectados():
    recibido = {}

    def detector_de_prueba(dataframe, configuracion, perfiles):
        recibido["perfiles"] = perfiles
        return [
            Hallazgo(
                tipo="prueba",
                columnas_involucradas=["x0"],
                severidad=Severidad.BAJA,
                detalle="Hallazgo de prueba.",
            )
        ]

    informe = revisar_dataset(
        dataset_mixto(),
        OBJETIVO,
        detectores=[detector_de_prueba],
        detectores_objetivo=(),
        detectores_relaciones=(),
        detectores_con_objetivo=(),
    )

    assert [h.tipo for h in informe.hallazgos] == ["prueba"]
    assert recibido["perfiles"] is informe.perfiles_columnas


def test_hallazgo_serializable_con_tipos_variados():
    hallazgo = Hallazgo(
        tipo="ejemplo",
        columnas_involucradas=["a", "b"],
        severidad=Severidad.ALTA,
        detalle="Detalle.",
        evidencia={
            "texto": "valor",
            "lista": [1, 2.5, None],
            "anidado": {"activo": np.bool_(True), "conteo": np.int64(4)},
            "proporcion": np.float64(0.25),
            "ausente": None,
        },
        acciones_posibles=["Revisar la columna manualmente."],
        accion_sugerida=None,
    )

    datos = json.loads(json.dumps(a_diccionario_serializable(hallazgo)))

    assert datos["severidad"] == "alta"
    assert datos["evidencia"]["anidado"] == {"activo": True, "conteo": 4}
    assert datos["evidencia"]["proporcion"] == 0.25

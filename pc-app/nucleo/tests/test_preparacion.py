"""Pruebas de la preparación de datos, la receta y la plantilla de decisiones."""

import importlib
import json

import numpy as np
import pandas as pd
import pytest

# IterativeImputer es experimental: importar este módulo lo habilita.
importlib.import_module("sklearn.experimental.enable_iterative_imputer")
from sklearn.impute import IterativeImputer  # noqa: E402

from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.plantilla import generar_plantilla
from pcapp_nucleo.preparacion import (
    Codificacion,
    ConfiguracionSeparacion,
    ConversionUnidades,
    DecisionesUsuario,
    ErrorPreparacion,
    TratamientoColumna,
    ajustar_imputacion_iterativa,
    aplicar_imputacion_iterativa,
    aplicar_receta,
    decisiones_desde_diccionario,
    preparar,
    receta_a_diccionario,
    receta_desde_diccionario,
)
from pcapp_nucleo.utilidades import a_diccionario_serializable

from .datos_sinteticos import construir_dataset_prueba


def dataset_base(n=200, semilla=0):
    rng = np.random.default_rng(semilla)
    return pd.DataFrame(
        {
            "fecha": pd.date_range("2024-01-01", periods=n, freq="D").strftime("%d.%m.%y"),
            "edad": rng.integers(18, 80, n).astype(float),
            "temp": rng.normal(37, 0.5, n).round(2),
            "glucosa": rng.normal(100, 15, n).round(1),
            "sexo": rng.choice(["M", "F"], n),
            "nivel": rng.choice(["bajo", "medio", "alto"], n),
            "ciudad": rng.choice(["A", "B", "C"], n),
            "y": np.where(np.arange(n) % 3 == 0, "si", "no"),
        }
    )


def decisiones(**cambios):
    base = {
        "codificaciones": {
            "sexo": Codificacion("binaria", valor_positivo="F"),
            "nivel": Codificacion("ordinal", orden=["bajo", "medio", "alto"]),
            "ciudad": Codificacion("one_hot"),
        },
        "columnas_excluidas": ["fecha"],
    }
    base.update(cambios)
    return DecisionesUsuario(**base)


def ida_y_vuelta(receta):
    return receta_desde_diccionario(json.loads(json.dumps(receta_a_diccionario(receta))))


# --- B1/B2. Pasos antes de separar ---------------------------------------------------------


def test_codificaciones_y_objetivo():
    datos = preparar(dataset_base(), "y", decisiones())
    train = datos.train

    assert set(train["sexo"].unique()) <= {0, 1}
    assert set(train["nivel"].unique()) == {0.0, 0.5, 1.0}  # ordinal 0/1/2 normalizado
    assert [c for c in train.columns if c.startswith("ciudad")] == ["ciudad=B", "ciudad=C"]
    assert set(train["y"].unique()) == {0, 1}
    assert list(train.columns)[-1] == "y"
    tipos = {m.nombre: m.tipo_final for m in datos.columnas}
    assert tipos["sexo"] == "binaria" and tipos["nivel"] == "ordinal" and tipos["ciudad=B"] == "one_hot"
    assert tipos["y"] == "objetivo" and datos.tipo_objetivo == "binario"
    assert any("one-hot" in a for a in datos.receta.advertencias)


def test_agrupacion_de_clases_del_objetivo():
    fetal = pd.DataFrame({"x": np.arange(300.0), "fetal_health": [1.0, 2.0, 3.0] * 100})
    xapi = pd.DataFrame({"x": np.arange(300.0), "Class": ["L", "M", "H"] * 100})

    agrupado = preparar(fetal, "fetal_health", DecisionesUsuario(
        codificaciones={"fetal_health": Codificacion("agrupacion", grupos={"1": 0, "2": 1, "3": 1})}
    ))
    agrupado_xapi = preparar(xapi, "Class", DecisionesUsuario(
        codificaciones={"Class": Codificacion("agrupacion", grupos={"L": 0, "M": 1, "H": 1})}
    ))

    assert agrupado.train["fetal_health"].value_counts().to_dict() == {1: 140, 0: 70}
    assert agrupado.tipo_objetivo == "binario"
    assert set(agrupado_xapi.train["Class"].unique()) == {0, 1}


def test_valor_sin_correspondencia_es_error():
    dataframe = pd.DataFrame({"x": np.arange(30.0), "y": ["a", "b", "c"] * 10})

    with pytest.raises(ErrorPreparacion, match="sin correspondencia"):
        preparar(dataframe, "y", DecisionesUsuario(
            codificaciones={"y": Codificacion("agrupacion", grupos={"a": 0, "b": 1})}
        ))


def test_orden_de_pasos_previos():
    dataframe = dataset_base()
    dataframe.loc[[1, 2], "glucosa"] = 0.0
    dataframe.loc[5, "temp"] = 99.5  # en °F
    dataframe = pd.concat([dataframe, dataframe.iloc[[10, 11]]], ignore_index=True)

    datos = preparar(dataframe, "y", decisiones(
        eliminar_duplicados=True,
        conversiones=[ConversionUnidades("temp", ">", 50, restar=32, multiplicar=5 / 9)],
        faltantes={"glucosa": TratamientoColumna(ceros_como_faltantes=True, indicador_medido=True)},
        logaritmos=["edad"],
        normalizar=False,
    ))
    todo = pd.concat([datos.train, datos.test]).sort_index()

    assert datos.receta.parametros_previos["filas_duplicadas_eliminadas"] == 2
    assert len(todo) == 200
    assert todo.loc[5, "temp"] == pytest.approx((99.5 - 32) * 5 / 9)
    assert todo.loc[[1, 2], "glucosa_medido"].tolist() == [0, 0]
    assert todo.loc[[1, 2], "glucosa"].isna().all()
    assert todo.loc[0, "edad"] == pytest.approx(np.log(dataframe.loc[0, "edad"]))
    assert "fecha" not in todo.columns


def test_no_modifica_el_dataframe():
    dataframe = dataset_base()
    copia = dataframe.copy(deep=True)

    preparar(dataframe, "y", decisiones(faltantes={"glucosa": TratamientoColumna(imputacion="multivariada")}))

    pd.testing.assert_frame_equal(dataframe, copia)


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"columnas_excluidas": ["no_existe"]}, "no existen"),
        ({"columnas_excluidas": []}, "no son numéricas"),
        ({"columnas_excluidas": ["y", "fecha"]}, "objetivo no puede excluirse"),
        ({"logaritmos": ["sexo"]}, "no es numérica"),
        ({"faltantes": {"edad": TratamientoColumna(imputacion="media")}}, "Imputación no válida"),
    ],
)
def test_decisiones_no_aplicables(cambios, mensaje):
    with pytest.raises(ErrorPreparacion, match=mensaje):
        preparar(dataset_base(), "y", decisiones(**cambios))


# --- B2. Parámetros aprendidos solo con entrenamiento ---------------------------------------


def dataset_con_extremos_en_test():
    dataframe = dataset_base(100)
    dataframe["x"] = np.linspace(10, 20, 100)
    dataframe.loc[70:, "x"] = 1000.0  # extremos solo en el 30 % cronológico final
    dataframe.loc[[3, 72], "glucosa"] = np.nan
    return dataframe


def test_normalizacion_e_imputacion_solo_con_entrenamiento():
    dataframe = dataset_con_extremos_en_test()
    separacion = ConfiguracionSeparacion(tipo="temporal", columna_fecha="fecha")

    datos = preparar(dataframe, "y", decisiones(
        separacion=separacion, faltantes={"glucosa": TratamientoColumna(imputacion="mediana")}
    ))
    parametros = datos.receta.parametros_aprendidos
    train_original = dataframe.loc[datos.receta.indices_train]

    assert parametros["maximos"]["x"] < 1000
    assert parametros["maximos"]["x"] == pytest.approx(train_original["x"].max())
    assert datos.train["x"].max() == pytest.approx(1.0)
    assert datos.test["x"].max() > 1.0
    assert parametros["medianas"]["glucosa"] == pytest.approx(train_original["glucosa"].median())
    assert parametros["medianas"]["glucosa"] != pytest.approx(dataframe["glucosa"].median())


# --- B3. Separación ------------------------------------------------------------------------------


def test_separacion_temporal_con_corte():
    dataframe = dataset_base()
    separacion = ConfiguracionSeparacion(tipo="temporal", columna_fecha="fecha", corte="2024-05-01")

    datos = preparar(dataframe, "y", decisiones(separacion=separacion))
    fechas = pd.to_datetime(dataframe["fecha"], format="%d.%m.%y")

    assert (fechas[datos.receta.indices_train] < "2024-05-01").all()
    assert (fechas[datos.receta.indices_test] >= "2024-05-01").all()
    assert "fecha" not in datos.train.columns
    assert datos.receta.separacion_aplicada["formato_fecha"] == "%d.%m.%y"


def test_separacion_temporal_sin_corte_usa_el_primer_70_por_ciento():
    datos = preparar(dataset_base(), "y", decisiones(
        separacion=ConfiguracionSeparacion(tipo="temporal", columna_fecha="fecha")
    ))

    assert datos.receta.indices_train == list(range(140))
    assert datos.receta.indices_test == list(range(140, 200))


def test_separacion_estratificada_mantiene_proporciones():
    datos = preparar(dataset_base(300), "y", decisiones())

    assert len(datos.test) == 90
    assert datos.train["y"].mean() == pytest.approx(datos.test["y"].mean(), abs=0.02)
    assert datos.receta.separacion_aplicada["tipo"] == "estratificada"


def test_corte_que_vacia_un_conjunto_es_error():
    separacion = ConfiguracionSeparacion(tipo="temporal", columna_fecha="fecha", corte="2030-01-01")

    with pytest.raises(ErrorPreparacion, match="vacío"):
        preparar(dataset_base(), "y", decisiones(separacion=separacion))


# --- B4. Receta reproducible ------------------------------------------------------------------------


@pytest.mark.parametrize("tipo_separacion", ["estratificada", "temporal"])
def test_aplicar_receta_reproduce_exactamente(tipo_separacion):
    dataframe = dataset_base(300, semilla=3)
    dataframe.loc[dataframe.sample(frac=0.2, random_state=1).index, "glucosa"] = np.nan
    dataframe.loc[dataframe.sample(frac=0.1, random_state=2).index, "temp"] = np.nan
    dataframe.loc[[4, 9], "ciudad"] = "?"
    separacion = ConfiguracionSeparacion(
        tipo=tipo_separacion, columna_fecha="fecha" if tipo_separacion == "temporal" else None,
        semilla=11,
    )
    elegidas = decisiones(
        separacion=separacion,
        faltantes={
            "glucosa": TratamientoColumna(imputacion="multivariada", indicador_medido=True),
            "temp": TratamientoColumna(imputacion="mediana"),
            "ciudad": TratamientoColumna(imputacion="mediana"),
        },
        logaritmos=["edad"],
    )

    original = preparar(dataframe, "y", elegidas)
    reproducida = aplicar_receta(dataframe, ida_y_vuelta(original.receta))

    pd.testing.assert_frame_equal(original.train, reproducida.train, check_exact=True)
    pd.testing.assert_frame_equal(original.test, reproducida.test, check_exact=True)
    assert original.train.drop(columns="y").notna().all().all()


def test_receta_de_otros_datos_es_error():
    receta = preparar(dataset_base(), "y", decisiones()).receta

    with pytest.raises(ErrorPreparacion, match="no corresponde"):
        aplicar_receta(dataset_base(50), receta)


# --- Imputación iterativa propia ---------------------------------------------------------------------


def test_imputacion_iterativa_comparable_con_iterative_imputer():
    rng = np.random.default_rng(12)
    n = 500
    x1 = rng.normal(size=n)
    x2 = 2 * x1 + rng.normal(0, 0.3, n)
    x3 = -x1 + 0.5 * x2 + rng.normal(0, 0.3, n)
    completo = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    con_faltantes = completo.copy()
    faltante = rng.random(n) < 0.25
    con_faltantes.loc[faltante, "x2"] = np.nan

    parametros = ajustar_imputacion_iterativa(con_faltantes, ["x2"], rondas=10)
    propia = aplicar_imputacion_iterativa(con_faltantes, parametros)["x2"].to_numpy()
    sklearn = IterativeImputer(max_iter=10, random_state=0).fit_transform(con_faltantes)[:, 1]

    reales = completo["x2"].to_numpy()[faltante]
    error_propio = np.sqrt(np.mean((propia[faltante] - reales) ** 2))
    error_sklearn = np.sqrt(np.mean((sklearn[faltante] - reales) ** 2))
    assert np.corrcoef(propia[faltante], sklearn[faltante])[0, 1] > 0.999
    assert error_propio == pytest.approx(error_sklearn, rel=0.05)
    assert error_propio < 0.3 * reales.std()
    json.dumps(parametros)


def test_imputacion_iterativa_conserva_otras_columnas_con_faltantes():
    datos = pd.DataFrame({"a": [1.0, 2.0, np.nan, 4.0, 5.0], "b": [2.0, np.nan, 6.0, 8.0, np.nan]})

    parametros = ajustar_imputacion_iterativa(datos, ["a"], rondas=3)
    resultado = aplicar_imputacion_iterativa(datos, parametros)

    assert resultado["a"].notna().all()
    assert resultado["b"].isna().sum() == 2


# --- B1/B6. Decisiones como JSON y plantilla ----------------------------------------------------------


def test_decisiones_ida_y_vuelta_json():
    elegidas = decisiones(
        faltantes={"glucosa": TratamientoColumna(True, True, "mediana")},
        conversiones=[ConversionUnidades("temp", ">", 50, 32, 5 / 9, "°F → °C")],
        separacion=ConfiguracionSeparacion(tipo="temporal", columna_fecha="fecha"),
    )

    texto = json.dumps(a_diccionario_serializable(elegidas), ensure_ascii=False)

    assert decisiones_desde_diccionario(json.loads(texto)) == elegidas


def test_campo_desconocido_en_decisiones_es_error():
    with pytest.raises(ErrorPreparacion, match="campos desconocidos: imputar"):
        decisiones_desde_diccionario({"faltantes": {"x": {"imputar": "mediana"}}})


def test_plantilla_desde_informe():
    dataframe = construir_dataset_prueba()
    dataframe["peso"] = dataframe["peso"].astype(float)
    informe = analizar_dataset(dataframe, "objetivo").informe

    plantilla = generar_plantilla(informe)
    acciones = plantilla.acciones_hallazgos

    assert plantilla.eliminar_duplicados is True
    assert acciones["filas_duplicadas"].accion == "eliminar_duplicados"
    assert {"id", "observacion", "fecha", "ancho", "altura_m"} <= set(plantilla.columnas_excluidas)
    assert plantilla.columnas_fecha_disponibles == ["fecha"]
    assert plantilla.codificaciones["nivel"] == Codificacion("ordinal", orden=["bajo", "medio", "alto"])
    assert plantilla.codificaciones["sexo"].tipo == "binaria"
    assert plantilla.faltantes["peso"].imputacion == "mediana"
    ceros = acciones["ceros_sospechosos:minimo"]
    assert ceros.requiere_confirmacion is True and ceros.accion == "conservar"
    assert not acciones["filas_duplicadas"].requiere_confirmacion
    datos = preparar(dataframe, "objetivo", plantilla)
    assert datos.train.drop(columns="objetivo").notna().all().all()


def test_plantilla_confirmaciones_y_agrupacion():
    rng = np.random.default_rng(13)
    n = 400
    clase = np.repeat([1, 2, 3], [300, 60, 40])
    a = rng.normal(size=n)
    ferritina = rng.lognormal(5, 1, n)
    ferritina[rng.random(n) < np.where(clase == 1, 0.5, 0.05)] = np.nan
    dataframe = pd.DataFrame(
        {
            "hb": a,
            "pcv": 3 * a + rng.normal(0, 0.5, n),
            "temp": np.concatenate([rng.uniform(18, 34, 300), rng.uniform(60, 89, 100)]),
            "ferritina": ferritina,
            "clase": clase,
        }
    )
    informe = analizar_dataset(dataframe, "clase").informe

    plantilla = generar_plantilla(informe)
    confirmar = {k.split(":")[0] for k, a in plantilla.acciones_hallazgos.items() if a.requiere_confirmacion}

    assert {"posible_mezcla_unidades", "faltantes_dependientes_objetivo", "grupo_redundante"} <= confirmar
    assert plantilla.faltantes["ferritina"] == TratamientoColumna(indicador_medido=True, imputacion="mediana")
    distribucion = plantilla.acciones_hallazgos["distribucion_objetivo:clase"]
    assert "agrupar_clases" in distribucion.opciones
    assert "Al agruparlas" in distribucion.descripcion
    assert "ferritina" in plantilla.logaritmos

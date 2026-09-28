"""Pruebas de aplicar_elecciones: decisiones a partir de acciones elegidas por el usuario."""

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.plantilla import ErrorEleccion, aplicar_elecciones, generar_plantilla
from pcapp_nucleo.preparacion import Codificacion, TratamientoColumna, preparar

from .datos_sinteticos import construir_dataset_prueba


@pytest.fixture(scope="module")
def informe_sintetico():
    dataframe = construir_dataset_prueba()
    dataframe["peso"] = dataframe["peso"].astype(float)
    return analizar_dataset(dataframe, "objetivo").informe


@pytest.fixture(scope="module")
def informe_clinico():
    """Ceros sospechosos, faltantes dependientes del objetivo, grupo redundante,
    mezcla de unidades, objetivo multiclase y fecha."""
    rng = np.random.default_rng(13)
    n = 400
    clase = np.repeat([1, 2, 3], [300, 60, 40])
    a = rng.normal(size=n)
    ferritina = rng.lognormal(5, 1, n)
    ferritina[rng.random(n) < np.where(clase == 1, 0.5, 0.05)] = np.nan
    glucosa = rng.normal(100, 15, n).round(1)
    glucosa[rng.choice(n, 30, replace=False)] = 0
    dataframe = pd.DataFrame(
        {
            "fecha": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
            "hb": a,
            "pcv": 3 * a + rng.normal(0, 0.5, n),
            "temp": np.concatenate([rng.uniform(18, 34, 300), rng.uniform(60, 89, 100)]),
            "ferritina": ferritina,
            "glucosa": glucosa,
            "clase": clase,
        }
    )
    return analizar_dataset(dataframe, "clase").informe


def identificador(informe, tipo, columna=None):
    for hallazgo in informe.hallazgos:
        if hallazgo.tipo == tipo and (columna is None or columna in hallazgo.columnas_involucradas):
            return hallazgo.identificador
    raise AssertionError(f"No hay hallazgo {tipo} {columna}")


def test_sin_elecciones_es_la_plantilla(informe_sintetico, informe_clinico):
    for informe in (informe_sintetico, informe_clinico):
        assert aplicar_elecciones(informe, {}) == generar_plantilla(informe)


def test_excluir_en_vez_de_imputar_y_one_hot_en_vez_de_ordinal(informe_sintetico):
    elecciones = {
        identificador(informe_sintetico, "valores_faltantes", "peso"): "excluir_columna",
        identificador(informe_sintetico, "variable_categorica", "nivel"): "one_hot",
        identificador(informe_sintetico, "filas_duplicadas"): "conservar",
    }

    decisiones = aplicar_elecciones(informe_sintetico, elecciones)

    assert "peso" in decisiones.columnas_excluidas and "peso" not in decisiones.faltantes
    assert decisiones.codificaciones["nivel"] == Codificacion("one_hot")
    assert decisiones.eliminar_duplicados is False
    for clave, accion in elecciones.items():
        assert decisiones.acciones_hallazgos[clave].accion == accion


def test_conservar_lo_que_se_sugeria_excluir(informe_sintetico):
    elecciones = {
        identificador(informe_sintetico, "posible_identificador", "id"): "conservar",
        identificador(informe_sintetico, "columna_derivada", "ancho"): "conservar",
        identificador(informe_sintetico, "correlacion_casi_perfecta", "altura_m"): "conservar",
    }

    decisiones = aplicar_elecciones(informe_sintetico, elecciones)

    assert not {"id", "ancho", "altura_m"} & set(decisiones.columnas_excluidas)
    assert "observacion" in decisiones.columnas_excluidas  # lo no elegido sigue sugerido


def test_ordinal_sin_orden_y_ordinal_para_binaria(informe_sintetico):
    nivel = identificador(informe_sintetico, "posible_variable_ordinal", "nivel")
    sexo = identificador(informe_sintetico, "variable_categorica", "sexo")

    decisiones = aplicar_elecciones(informe_sintetico, {nivel: "sin_orden", sexo: "ordinal"})

    assert decisiones.codificaciones["nivel"] == Codificacion("one_hot")
    assert decisiones.codificaciones["sexo"] == Codificacion("ordinal", orden=["F", "M"])


def test_faltantes_de_varios_hallazgos_se_combinan(informe_clinico):
    ceros = identificador(informe_clinico, "ceros_sospechosos", "glucosa")
    dependiente = identificador(informe_clinico, "faltantes_dependientes_objetivo", "ferritina")

    decisiones = aplicar_elecciones(
        informe_clinico, {ceros: "ceros_como_faltantes", dependiente: "solo_casos_completos"}
    )
    imputando = aplicar_elecciones(informe_clinico, {ceros: "ceros_como_faltantes_imputar_mediana"})

    assert decisiones.faltantes["glucosa"] == TratamientoColumna(ceros_como_faltantes=True)
    assert decisiones.faltantes["ferritina"] == TratamientoColumna(imputacion="eliminar_filas")
    assert imputando.faltantes["glucosa"] == TratamientoColumna(ceros_como_faltantes=True, imputacion="mediana")


def test_acciones_con_valores_iniciales_editables(informe_clinico):
    elecciones = {
        identificador(informe_clinico, "posible_mezcla_unidades", "temp"): "convertir_unidades",
        identificador(informe_clinico, "distribucion_objetivo"): "agrupar_clases",
        identificador(informe_clinico, "grupo_redundante", "hb"): "excluir_variables",
        identificador(informe_clinico, "posible_fecha", "fecha"): "separacion_temporal",
    }

    decisiones = aplicar_elecciones(informe_clinico, elecciones)

    [conversion] = decisiones.conversiones
    assert (conversion.columna, conversion.condicion, conversion.restar, conversion.multiplicar) == ("temp", ">", 0.0, 1.0)
    assert 34 < conversion.umbral < 60
    assert decisiones.codificaciones["clase"] == Codificacion("agrupacion", grupos={"1": 0, "2": 1, "3": 1})
    assert "pcv" in decisiones.columnas_excluidas and "hb" not in decisiones.columnas_excluidas
    assert decisiones.separacion.tipo == "temporal" and decisiones.separacion.columna_fecha == "fecha"
    assert "fecha" not in decisiones.columnas_excluidas


def test_excluir_faltantes_dependientes_y_agrupar_clases(informe_clinico):
    decisiones = aplicar_elecciones(
        informe_clinico,
        {
            identificador(informe_clinico, "faltantes_dependientes_objetivo", "ferritina"): "excluir_columna",
            identificador(informe_clinico, "distribucion_objetivo"): "agrupar_clases",
        },
    )

    assert "ferritina" in decisiones.columnas_excluidas and "ferritina" not in decisiones.faltantes
    assert decisiones.codificaciones["clase"].tipo == "agrupacion"


def test_hallazgo_inexistente(informe_clinico):
    with pytest.raises(ErrorEleccion, match="No existe el hallazgo 'no_existe:x'") as error:
        aplicar_elecciones(informe_clinico, {"no_existe:x": "conservar"})

    assert error.value.identificador == "no_existe:x"


def test_accion_no_ofrecida(informe_clinico):
    ceros = identificador(informe_clinico, "ceros_sospechosos", "glucosa")

    with pytest.raises(ErrorEleccion, match="no es válida para este hallazgo; opciones: conservar") as error:
        aplicar_elecciones(informe_clinico, {ceros: "borrar"})

    assert error.value.identificador == ceros


def test_preparar_con_decisiones_elegidas():
    dataframe = construir_dataset_prueba()
    dataframe["peso"] = dataframe["peso"].astype(float)
    informe = analizar_dataset(dataframe, "objetivo").informe
    decisiones = aplicar_elecciones(
        informe,
        {
            identificador(informe, "valores_faltantes", "peso"): "imputar_multivariada",
            identificador(informe, "variable_categorica", "nivel"): "one_hot",
            identificador(informe, "posible_fecha", "fecha"): "separacion_temporal",
        },
    )

    datos = preparar(dataframe, "objetivo", decisiones)

    assert datos.receta.separacion_aplicada["tipo"] == "temporal"
    assert any(c.startswith("nivel=") for c in datos.train.columns)
    assert datos.train["peso"].notna().all()

"""Validación acumulada de la configuración de PC, nombres de niveles, límite de
columnas, distribución del objetivo, evaluación de la prueba elegida y aviso del
modo de ejecución."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo.caracterizacion import caracterizar
from pcapp_nucleo.exportacion import dibujar_grafo
from pcapp_nucleo.pc_bootstrap import AristaAgregada, GrafoAgregado, ejecutar_bootstrap
from pcapp_nucleo.pc_config import (
    ErrorConfiguracionPC,
    advertencias_configuracion,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    problemas_configuracion,
    validar_configuracion,
)
from pcapp_nucleo.preparacion import (
    COLUMNAS_PC_LENTO,
    COLUMNAS_PC_MAXIMO,
    DecisionesUsuario,
    MetadatosColumna,
    distribucion_objetivo,
    evaluar_columnas,
    preparar,
)
from pcapp_nucleo.seleccion_prueba import RecomendacionPrueba, evaluar_eleccion

VARIABLES = ["a", "b", "c", "y"]


def plantilla(**cambios):
    return replace(configuracion_por_defecto(VARIABLES, "y"), **cambios)


# --- Configuración: todos los problemas, con su campo --------------------------------------------


def test_problemas_se_acumulan_con_su_campo():
    conf = plantilla(
        alpha=2.0,
        max_k=-1,
        niveles=[["a", "b"], [], ["a", "x"]],
        nombres_niveles=["Demografía", " ", "Otro", "De más"],
        modificables=["y"],
    )

    problemas = problemas_configuracion(conf, VARIABLES, "y")
    campos = [p.campo for p in problemas]

    assert campos == [
        "alpha", "max_k", "niveles", "niveles", "niveles", "niveles", "niveles.1",
        "nombres_niveles", "nombres_niveles.1", "modificables",
    ]
    mensajes = " ".join(p.mensaje for p in problemas)
    assert "más de un nivel: a" in mensajes and "no están en los datos preparados: x" in mensajes
    assert "objetivo 'y' debe estar" in mensajes and "faltan: c" in mensajes
    assert "El nivel 2 está vacío" in mensajes


def test_validar_configuracion_lanza_el_primer_problema():
    with pytest.raises(ErrorConfiguracionPC, match="alpha"):
        validar_configuracion(plantilla(alpha=0, niveles=[["a"], ["y"]]), VARIABLES, "y")
    assert problemas_configuracion(plantilla(), VARIABLES, "y") == []


def test_advertencia_si_el_objetivo_no_esta_al_final():
    delante = plantilla(niveles=[["a"], ["y"], ["b", "c"]])

    [advertencia] = advertencias_configuracion(delante, "y")

    assert advertencia.campo == "niveles"
    assert "b, c no podrán ser causas del objetivo" in advertencia.mensaje
    assert advertencias_configuracion(plantilla(), "y") == []
    assert advertencias_configuracion(plantilla(niveles=[["a"], ["b", "c", "y"]]), "y") == []


def test_nombres_de_niveles_ida_y_vuelta_y_opcionales():
    conf = configuracion_desde_diccionario(
        {"niveles": [["a", "b", "c"], ["y"]], "nombres_niveles": ["Demografía", "Diagnóstico"]}
    )

    assert conf.nombres_niveles == ["Demografía", "Diagnóstico"]
    assert configuracion_desde_diccionario({"niveles": [["a", "b", "c"], ["y"]]}).nombres_niveles is None
    assert problemas_configuracion(conf, VARIABLES, "y") == []


def _grafo():
    arista = AristaAgregada("a", "y", "dirigida", 1.0, 1.0, 0.0, 0.0, 0.5, 1, None)
    return GrafoAgregado(VARIABLES, "y", 0.6, 10, [arista], [])


def _resultado():
    from pcapp_nucleo.pc_bootstrap import ResultadoBootstrap

    ceros = [[0] * 4 for _ in range(4)]
    return ResultadoBootstrap(VARIABLES, "y", 10, 10, 10, [], True, ceros, ceros, [], 1.0, {})


def _titulos(figura):
    return [t.get_text() for t in figura.axes[0].texts]


def test_grafo_usa_los_nombres_de_los_niveles():
    grafo = _grafo()
    caracterizacion = caracterizar(grafo, _resultado(), [])
    niveles = [["a", "b"], ["c"], ["y"]]

    con_nombres = _titulos(dibujar_grafo(grafo, caracterizacion, niveles, ["Demografía", "Síntomas", "Diagnóstico"]))
    sin_nombres = _titulos(dibujar_grafo(grafo, caracterizacion, niveles))

    assert {"Demografía", "Síntomas", "Diagnóstico"} <= set(con_nombres)
    assert {"Nivel 1", "Nivel 2", "Nivel 3"} <= set(sin_nombres)


# --- Límite de columnas y distribución del objetivo ----------------------------------------------------


def _columnas(n_continuas, one_hot=0):
    columnas = [MetadatosColumna(f"x{i}", "continua") for i in range(n_continuas)]
    columnas += [MetadatosColumna(f"ciudad={i}", "one_hot") for i in range(one_hot)]
    return columnas + [MetadatosColumna("y", "objetivo")]


def test_limite_de_columnas():
    ok = evaluar_columnas(_columnas(COLUMNAS_PC_LENTO - 1))
    lento = evaluar_columnas(_columnas(20, one_hot=15))
    bloqueado = evaluar_columnas(_columnas(COLUMNAS_PC_MAXIMO))

    assert (ok.estado, ok.columnas, ok.mensaje) == ("ok", COLUMNAS_PC_LENTO, None)
    assert lento.estado == "lento" and lento.columnas == 36
    assert "15 columnas (ciudad)" in lento.mensaje and "Vuelva a Decisiones" in lento.mensaje
    assert lento.columnas_one_hot == {"ciudad": 15}
    assert bloqueado.estado == "bloqueado" and f"el máximo para PC es {COLUMNAS_PC_MAXIMO}" in bloqueado.mensaje


def test_distribucion_objetivo_por_clases_y_continua():
    clases = distribucion_objetivo(pd.Series([0, 1, 1, 1, np.nan]), "binario")
    continua = distribucion_objetivo(pd.Series([1.0, 2.0, 3.0, 10.0]), "continuo")

    assert clases == {
        "tipo": "clases", "filas": 5,
        "clases": [{"valor": 0.0, "conteo": 1, "porcentaje": 25.0}, {"valor": 1.0, "conteo": 3, "porcentaje": 75.0}],
    }
    assert continua == {"tipo": "continuo", "filas": 4, "media": 4.0, "mediana": 2.5, "minimo": 1.0, "maximo": 10.0}


# --- Evaluación de la prueba elegida -----------------------------------------------------------------------


def recomendacion(**cambios):
    base = dict(
        prueba="fisherz", motivo="", discretizacion=None, variables_no_monotonas=[],
        faltantes_restantes={}, proporcion_categoricas=0.1, filas_train=800, variables=8,
        diagnosticos=[], alternativas=[], tiempo_por_ejecucion_s=0.2, tiempo_estimado_bootstrap_s=20.0,
    )
    return RecomendacionPrueba(**{**base, **cambios})


def codigos(evaluacion):
    return [a.codigo for a in evaluacion.advertencias]


def test_eleccion_coherente_sin_advertencias():
    evaluacion = evaluar_eleccion(recomendacion(), "fisherz", None)

    assert evaluacion.advertencias == [] and evaluacion.tiempo_estimado_s == 20.0


def test_fisherz_con_faltantes_sin_imputar():
    evaluacion = evaluar_eleccion(
        recomendacion(prueba="mv_fisherz", faltantes_restantes={"Insulin": 30}), "fisherz", None
    )

    [faltantes, tiempo] = evaluacion.advertencias
    assert (faltantes.codigo, faltantes.campo, faltantes.nivel) == ("FALTANTES_SIN_IMPUTAR", "prueba", "advertencia")
    assert "Insulin" in faltantes.mensaje
    assert (tiempo.codigo, tiempo.nivel) == ("TIEMPO_NO_ESTIMADO", "info")
    assert evaluacion.tiempo_estimado_s is None


def test_chisq_sin_max_k_con_un_tiempo_de_horas():
    lenta = recomendacion(
        prueba="chisq", tiempo_estimado_bootstrap_s=4 * 3600.0, max_k_sugerido=3,
        tiempo_estimado_bootstrap_max_k_s=600.0, variables_no_monotonas=["x"],
    )

    sin_max_k = evaluar_eleccion(lenta, "chisq", None)
    con_max_k = evaluar_eleccion(lenta, "chisq", 3)

    [aviso] = sin_max_k.advertencias
    assert (aviso.codigo, aviso.campo) == ("CHISQ_SIN_MAX_K", "max_k")
    assert "max_k = 3" in aviso.mensaje
    assert sin_max_k.tiempo_estimado_s == 4 * 3600.0
    assert con_max_k.advertencias == [] and con_max_k.tiempo_estimado_s == 600.0


def test_lineal_con_relaciones_en_u_y_otras_advertencias():
    en_u = recomendacion(prueba="chisq", variables_no_monotonas=["variabilidad"], proporcion_categoricas=0.7)

    assert codigos(evaluar_eleccion(en_u, "fisherz", None)) == [
        "RELACIONES_NO_MONOTONAS", "MAYORIA_CATEGORICAS", "TIEMPO_NO_ESTIMADO",
    ]
    assert codigos(evaluar_eleccion(recomendacion(), "mv_fisherz", None))[0] == "SIN_FALTANTES"
    assert "KCI_DEMASIADO_LENTA" in codigos(evaluar_eleccion(recomendacion(filas_train=2000), "kci", None))


# --- Aviso del modo de ejecución --------------------------------------------------------------------------


def _datos():
    rng = np.random.default_rng(4)
    a = rng.normal(size=600)
    dataframe = pd.DataFrame({"A": a, "B": a + rng.normal(size=600), "C": rng.normal(size=600)})
    return preparar(dataframe, "C", DecisionesUsuario(normalizar=False))


@pytest.mark.parametrize(
    "cambios, esperados",
    [
        ({"modo_ejecucion": "secuencial", "procesos": 2}, [("secuencial", 1)]),
        ({"modo_ejecucion": "adaptativo", "procesos": 2}, [("midiendo", 1), ("secuencial", 1)]),
    ],
)
def test_se_avisa_el_modo_de_ejecucion(cambios, esperados):
    datos = _datos()
    conf = replace(
        configuracion_por_defecto(list(datos.train.columns), "C"), corridas_bootstrap=4, **cambios
    )
    avisos = []

    ejecutar_bootstrap(datos, conf, al_decidir_modo=lambda modo, n: avisos.append((modo, n)))

    assert avisos == esperados

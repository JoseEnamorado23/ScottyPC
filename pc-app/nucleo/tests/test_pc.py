"""Pruebas de la configuración de PC, el bootstrap, la agregación, la
caracterización y la exportación."""

import json
import threading
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from nucleo.caracterizacion import (
    AMBIGUA,
    CAUSA_DIRECTA,
    CAUSA_INDIRECTA,
    CONSECUENCIA,
    SIN_CAMINO,
    caracterizar,
)
from nucleo.exportacion import exportar, matriz_frecuencias, matriz_mascara
from nucleo.pc_bootstrap import (
    AristaAgregada,
    GrafoAgregado,
    ResultadoBootstrap,
    agregar,
    ejecutar_bootstrap,
    frecuencia_par,
)
from nucleo.pc_config import (
    ErrorConfiguracionPC,
    OrientacionManual,
    configuracion_desde_diccionario,
    configuracion_por_defecto,
    validar_configuracion,
)
from nucleo.preparacion import DecisionesUsuario, preparar
from nucleo.utilidades import a_diccionario_serializable

N = 2000


def preparados(dataframe, objetivo):
    return preparar(dataframe, objetivo, DecisionesUsuario(normalizar=False))


def cadena():
    rng = np.random.default_rng(1)
    a = rng.normal(size=N)
    b = a + rng.normal(size=N)
    c = b + rng.normal(size=N)
    return pd.DataFrame({"A": a, "B": b, "C": c})


def horquilla():
    rng = np.random.default_rng(2)
    b = rng.normal(size=N)
    return pd.DataFrame({"A": b + rng.normal(size=N), "B": b, "C": b + rng.normal(size=N)})


def colisionador():
    rng = np.random.default_rng(3)
    a, c = rng.normal(size=N), rng.normal(size=N)
    b = a + c + rng.normal(0, 0.7, N)
    return pd.DataFrame({"A": a, "B": b, "C": c, "D": b + rng.normal(size=N)})


def configuracion(datos, **cambios):
    base = configuracion_por_defecto(list(datos.train.columns), datos.objetivo)
    return replace(base, **{"corridas_bootstrap": 8, "procesos": 1, **cambios})


def aristas(grafo):
    return {(a.origen, a.destino, a.tipo) for a in grafo.aristas}


def esqueleto(grafo):
    return {frozenset((a.origen, a.destino)) for a in grafo.aristas}


def correr(datos, **cambios):
    conf = configuracion(datos, **cambios)
    resultado = ejecutar_bootstrap(datos, conf)
    return resultado, agregar(resultado, datos, conf)


# --- Configuración ------------------------------------------------------------------------------


def test_configuracion_por_defecto():
    conf = configuracion_por_defecto(["a", "b", "y"], "y", "chisq", 3)

    assert conf.niveles == [["a", "b"], ["y"]]
    assert (conf.prueba, conf.max_k, conf.alpha, conf.corridas_bootstrap) == ("chisq", 3, 0.05, 100)
    assert conf.procesos >= 1


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"niveles": [["a", "b"], ["b", "y"]]}, "más de un nivel"),
        ({"niveles": [["a"], ["y"]]}, "faltan: b"),
        ({"niveles": [["a", "b", "x"], ["y"]]}, "no están en los datos"),
        ({"niveles": [["a", "b"]]}, "objetivo 'y' debe estar"),
        ({"modificables": ["y"]}, "distintas del objetivo"),
        ({"orientaciones_manuales": [OrientacionManual("y", "a")]}, "contradice los niveles"),
        ({"prueba": "gsq"}, "Prueba no válida"),
        ({"alpha": 1.5}, "alpha"),
        ({"umbral_frecuencia": 0}, "umbral_frecuencia"),
    ],
)
def test_configuracion_invalida(cambios, mensaje):
    conf = replace(configuracion_por_defecto(["a", "b", "y"], "y"), **cambios)

    with pytest.raises(ErrorConfiguracionPC, match=mensaje):
        validar_configuracion(conf, ["a", "b", "y"], "y")


def test_configuracion_ida_y_vuelta_json():
    conf = replace(
        configuracion_por_defecto(["a", "b", "y"], "y"),
        modificables=["a"], orientaciones_manuales=[OrientacionManual("a", "b", "conocimiento clínico")],
    )

    texto = json.dumps(a_diccionario_serializable(conf))

    assert configuracion_desde_diccionario(json.loads(texto)) == conf
    with pytest.raises(ErrorConfiguracionPC, match="campos desconocidos: umbral"):
        configuracion_desde_diccionario({"umbral": 0.5})


# --- DAG conocidos -------------------------------------------------------------------------------


def test_cadena_recupera_el_esqueleto():
    _, grafo = correr(preparados(cadena(), "C"))

    assert esqueleto(grafo) == {frozenset("AB"), frozenset("BC")}


def test_horquilla_recupera_el_esqueleto():
    _, grafo = correr(preparados(horquilla(), "C"))

    assert esqueleto(grafo) == {frozenset("AB"), frozenset("BC")}


def test_colisionador_se_orienta():
    resultado, grafo = correr(preparados(colisionador(), "D"))

    assert aristas(grafo) == {("A", "B", "dirigida"), ("C", "B", "dirigida"), ("B", "D", "dirigida")}
    assert all(a.frecuencia_total == 1.0 and a.signo == 1 for a in grafo.aristas)
    assert resultado.completo and resultado.corridas_validas == 8


def test_niveles_imponen_la_direccion_permitida():
    datos = preparados(colisionador(), "D")

    _, grafo = correr(datos, niveles=[["B"], ["A", "C"], ["D"]])

    assert ("B", "A", "dirigida") in aristas(grafo)
    assert ("B", "C", "dirigida") in aristas(grafo)
    assert not any(a.destino == "B" for a in grafo.aristas)


# --- Ejecución: paralelo, progreso, cancelación, puntos de control ------------------------------------


def test_paralelo_igual_a_secuencial():
    datos = preparados(colisionador(), "D")

    secuencial = ejecutar_bootstrap(datos, configuracion(datos, corridas_bootstrap=12, procesos=1))
    paralelo = ejecutar_bootstrap(datos, configuracion(datos, corridas_bootstrap=12, procesos=3))

    assert paralelo.dirigidas == secuencial.dirigidas
    assert paralelo.sin_orientar == secuencial.sin_orientar
    assert paralelo.corridas_fallidas == secuencial.corridas_fallidas


def test_progreso_una_vez_por_corrida():
    datos = preparados(cadena(), "C")
    llamadas = []

    ejecutar_bootstrap(datos, configuracion(datos), progreso=lambda *args: llamadas.append(args))

    assert [c[:2] for c in llamadas] == [(k, 8) for k in range(1, 9)]
    assert all(c[2] >= 0 for c in llamadas)


@pytest.mark.parametrize("procesos", [1, 2])
def test_cancelacion_devuelve_resultado_parcial(procesos):
    datos = preparados(cadena(), "C")
    cancelar = threading.Event()

    def progreso(completadas, total, segundos):
        if completadas >= 4:
            cancelar.set()

    resultado = ejecutar_bootstrap(
        datos, configuracion(datos, corridas_bootstrap=60, procesos=procesos), progreso, cancelar
    )

    assert resultado.completo is False
    assert 4 <= resultado.corridas_completadas < 60
    assert resultado.corridas_validas == resultado.corridas_completadas
    assert "Resultado parcial" in agregar(resultado, datos, configuracion(datos)).advertencias[0]


def test_reanudar_desde_punto_de_control_da_el_mismo_resultado(tmp_path):
    datos = preparados(colisionador(), "D")
    conf = configuracion(datos, corridas_bootstrap=12, punto_control_cada=3)
    punto = tmp_path / "punto_control.json"
    cancelar = threading.Event()

    parcial = ejecutar_bootstrap(
        datos, conf, lambda k, *_: cancelar.set() if k >= 5 else None, cancelar, punto
    )
    guardado = json.loads(punto.read_text(encoding="utf-8"))
    reanudado = ejecutar_bootstrap(datos, conf, punto_control=punto, reanudar=True)
    completo = ejecutar_bootstrap(datos, conf)

    assert parcial.completo is False and guardado["corridas_completadas"] == [0, 1, 2, 3, 4]
    assert reanudado.completo is True
    assert reanudado.dirigidas == completo.dirigidas
    assert reanudado.sin_orientar == completo.sin_orientar
    assert not punto.exists()


def test_punto_de_control_de_otra_configuracion_se_rechaza(tmp_path):
    datos = preparados(cadena(), "C")
    punto = tmp_path / "punto_control.json"
    cancelar = threading.Event()
    ejecutar_bootstrap(datos, configuracion(datos), lambda k, *_: cancelar.set(), cancelar, punto)

    with pytest.raises(ErrorConfiguracionPC, match="no corresponde"):
        ejecutar_bootstrap(datos, configuracion(datos, alpha=0.01), punto_control=punto, reanudar=True)


def test_corridas_fallidas_se_descartan():
    dataframe = cadena()
    dataframe["rara"] = 0.0
    dataframe.loc[[5, 900], "rara"] = 1.0  # en muchas submuestras queda constante
    datos = preparados(dataframe, "C")

    resultado = ejecutar_bootstrap(datos, configuracion(datos, corridas_bootstrap=20))

    assert resultado.corridas_fallidas
    assert resultado.corridas_validas + len(resultado.corridas_fallidas) == 20
    assert "constante" in resultado.corridas_fallidas[0].motivo
    assert "descartaron" in agregar(resultado, datos, configuracion(datos)).advertencias[0]


def test_faltantes_requieren_mv_fisherz():
    dataframe = cadena()
    dataframe.loc[::7, "A"] = np.nan
    datos = preparados(dataframe, "C")

    with pytest.raises(ErrorConfiguracionPC, match="no admite faltantes"):
        ejecutar_bootstrap(datos, configuracion(datos))
    _, grafo = correr(datos, prueba="mv_fisherz")
    assert esqueleto(grafo) == {frozenset("AB"), frozenset("BC")}


def test_chisq_guarda_limites_de_discretizacion():
    datos = preparados(colisionador(), "D")

    resultado, grafo = correr(datos, prueba="chisq", corridas_bootstrap=3)

    assert set(resultado.limites_discretizacion) == {"A", "B", "C", "D"}
    assert all(len(v) == 4 for v in resultado.limites_discretizacion.values())
    assert frozenset("AB") in esqueleto(grafo)


# --- Agregación a partir de cuentas construidas a mano --------------------------------------------


def resultado_a_mano(dirigidas, sin_orientar, validas=10, variables=("X", "Y", "Z", "W"), objetivo="Y"):
    return ResultadoBootstrap(
        variables=list(variables), objetivo=objetivo, corridas_totales=validas,
        corridas_completadas=validas, corridas_validas=validas, corridas_fallidas=[],
        completo=True, dirigidas=dirigidas, sin_orientar=sin_orientar, bidireccionales=0, tiempo_s=1.0,
    )


@pytest.fixture
def datos_xyzw():
    rng = np.random.default_rng(4)
    x = rng.normal(size=300)
    dataframe = pd.DataFrame({"X": x, "Y": x + rng.normal(size=300), "Z": -x + rng.normal(size=300),
                              "W": rng.normal(size=300)})
    return preparados(dataframe, "Y")


def test_agregacion_umbral_orientacion_y_manuales(datos_xyzw):
    #            X  Y  Z  W
    dirigidas = [[0, 7, 0, 0],   # X→Y 7
                 [2, 0, 0, 0],   # Y→X 2
                 [0, 0, 0, 0],
                 [0, 3, 0, 0]]   # W→Y 3 (bajo el umbral)
    sin_orientar = [[0, 1, 7, 0], [1, 0, 0, 0], [7, 0, 0, 0], [0, 0, 0, 0]]
    conf = replace(
        configuracion(datos_xyzw),
        niveles=[["X", "Z", "W"], ["Y"]],
        orientaciones_manuales=[OrientacionManual("Z", "X", "Z precede a X"), OrientacionManual("X", "Y")],
    )

    grafo = agregar(resultado_a_mano(dirigidas, sin_orientar), datos_xyzw, conf)
    por_par = {frozenset((a.origen, a.destino)): a for a in grafo.aristas}

    xy = por_par[frozenset("XY")]
    assert (xy.origen, xy.destino, xy.tipo) == ("X", "Y", "dirigida")
    assert (xy.frecuencia_total, xy.frecuencia_origen_destino, xy.frecuencia_destino_origen,
            xy.frecuencia_sin_orientar) == (1.0, 0.7, 0.2, 0.1)
    assert xy.signo == 1
    xz = por_par[frozenset("XZ")]
    assert (xz.origen, xz.destino, xz.tipo, xz.justificacion) == ("Z", "X", "manual", "Z precede a X")
    assert xz.signo == -1
    assert frozenset("WY") not in por_par
    assert any("PC ya orientó" in a for a in grafo.advertencias)


def test_empate_queda_sin_orientar(datos_xyzw):
    dirigidas = [[0, 4, 0, 0], [4, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    sin_orientar = [[0] * 4 for _ in range(4)]

    grafo = agregar(resultado_a_mano(dirigidas, sin_orientar), datos_xyzw, configuracion(datos_xyzw))

    assert [(a.tipo, a.frecuencia_total) for a in grafo.aristas] == [("sin_orientar", 0.8)]


def test_ciclos_se_reportan(datos_xyzw):
    dirigidas = [[0, 9, 0, 0], [0, 0, 9, 0], [9, 0, 0, 0], [0, 0, 0, 0]]  # X→Y→Z→X
    sin_orientar = [[0] * 4 for _ in range(4)]

    grafo = agregar(resultado_a_mano(dirigidas, sin_orientar), datos_xyzw, configuracion(datos_xyzw))

    assert len(grafo.ciclos) == 1 and set(grafo.ciclos[0]) == {"X", "Y", "Z"}
    assert any("ciclo" in a for a in grafo.advertencias)


def test_frecuencia_par():
    resultado = resultado_a_mano([[0, 3, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
                                 [[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])

    assert frecuencia_par(resultado, "X", "Y") == 0.5
    assert frecuencia_par(resultado, "Z", "W") == 0.0


# --- Caracterización sobre un grafo construido a mano ------------------------------------------------


def arista(origen, destino, tipo="dirigida"):
    return AristaAgregada(origen, destino, tipo, 0.9, 0.9, 0.0, 0.0, 0.5, 1)


VARIABLES = ["Y", "D", "M", "I", "C", "A", "B", "S", "F"]


def grafo_a_mano():
    return GrafoAgregado(
        variables=VARIABLES, objetivo="Y", umbral_frecuencia=0.6, corridas_validas=10,
        aristas=[
            arista("D", "Y"),                     # causa directa
            arista("M", "Y"), arista("I", "M"),   # I causa indirecta a través de M
            arista("Y", "C"),                     # consecuencia
            arista("A", "Y", "sin_orientar"),     # ambigua
            arista("B", "A", "sin_orientar"),     # ambigua a través de A
            arista("F", "C"),                     # F → C ← Y: sin camino
        ],
        ciclos=[],
    )


def resultado_para_caracterizar():
    n = len(VARIABLES)
    dirigidas = [[0] * n for _ in range(n)]
    dirigidas[VARIABLES.index("S")][0] = 4  # S–Y en el 40 %, bajo el umbral
    dirigidas[VARIABLES.index("D")][0] = 9
    return resultado_a_mano(dirigidas, [[0] * n for _ in range(n)], variables=tuple(VARIABLES))


def test_caracterizacion_de_cada_categoria():
    caracterizacion = caracterizar(grafo_a_mano(), resultado_para_caracterizar(), ["D", "I", "C"], [["M", "I"]])
    por_variable = {v.variable: v for v in caracterizacion.variables}

    assert {v: c.categoria for v, c in por_variable.items()} == {
        "D": CAUSA_DIRECTA, "M": CAUSA_DIRECTA, "I": CAUSA_INDIRECTA, "C": CONSECUENCIA,
        "A": AMBIGUA, "B": AMBIGUA, "S": SIN_CAMINO, "F": SIN_CAMINO,
    }
    assert por_variable["I"].a_traves_de == ["M"]
    assert por_variable["S"].frecuencia_con_objetivo == 0.4
    assert por_variable["D"].frecuencia_con_objetivo == 0.9
    assert por_variable["I"].grupo_redundante == ["M", "I"]
    assert caracterizacion.candidatas_prescriptivas == ["D", "I"]
    assert caracterizacion.mensaje == "Candidatas prescriptivas: D, I."


def test_caracterizacion_sin_modificables_o_sin_candidatas():
    resultado = resultado_para_caracterizar()

    sin_marcar = caracterizar(grafo_a_mano(), resultado, [])
    sin_candidatas = caracterizar(grafo_a_mano(), resultado, ["C", "S"])

    assert "márquelas" in sin_marcar.mensaje
    assert sin_candidatas.candidatas_prescriptivas == []
    assert "con estos datos no hay variables prescriptivas" in sin_candidatas.mensaje.lower()


def test_camino_indirecto_largo_indica_las_intermedias():
    grafo = GrafoAgregado(
        variables=["Y", "P", "Q", "R"], objetivo="Y", umbral_frecuencia=0.6, corridas_validas=10,
        aristas=[arista("P", "Q"), arista("Q", "R"), arista("R", "Y")], ciclos=[],
    )
    resultado = resultado_a_mano([[0] * 4 for _ in range(4)], [[0] * 4 for _ in range(4)],
                                 variables=("Y", "P", "Q", "R"))

    [p] = [v for v in caracterizar(grafo, resultado, []).variables if v.variable == "P"]

    assert (p.categoria, p.a_traves_de) == (CAUSA_INDIRECTA, ["Q", "R"])


# --- Exportación -------------------------------------------------------------------------------------


def test_exportacion(tmp_path):
    datos = preparados(colisionador(), "D")
    conf = replace(configuracion(datos), modificables=["A"])
    resultado = ejecutar_bootstrap(datos, conf)
    grafo = agregar(resultado, datos, conf)
    caracterizacion = caracterizar(grafo, resultado, conf.modificables)

    rutas = exportar(tmp_path, conf, datos.receta, resultado, grafo, caracterizacion)

    mascara = pd.read_csv(rutas["mascara.csv"], index_col=0)
    assert list(mascara.index) == list(mascara.columns) == ["A", "B", "C", "D"]
    assert mascara.loc["A", "B"] == 1 and mascara.loc["B", "A"] == 0
    assert mascara.to_numpy().sum() == 3
    frecuencias = pd.read_csv(rutas["matriz_frecuencias.csv"], index_col=0)
    assert frecuencias.loc["A", "B"] == 1.0 and frecuencias.loc["B", "A"] == 0.0
    tabla = pd.read_csv(rutas["aristas.csv"])
    assert list(tabla.columns[:4]) == ["origen", "destino", "tipo", "frecuencia_total"]
    contenido = json.loads(rutas["resultado.json"].read_text(encoding="utf-8"))
    assert contenido["corridas"]["validas"] == 8
    assert contenido["caracterizacion"]["candidatas_prescriptivas"] == ["A"]
    assert contenido["receta"]["sha256"] == datos.receta.origen.sha256
    assert rutas["grafo.png"].stat().st_size > 10_000


def test_mascara_sin_orientar_marca_ambas_direcciones():
    grafo = GrafoAgregado(["a", "b", "c"], "c", 0.6, 10,
                          [arista("a", "b", "sin_orientar"), arista("b", "c")], [])

    mascara = matriz_mascara(grafo)

    assert mascara.loc["a", "b"] == mascara.loc["b", "a"] == 1
    assert mascara.loc["b", "c"] == 1 and mascara.loc["c", "b"] == 0


def test_matriz_frecuencias_suma_dirigida_y_sin_orientar():
    resultado = resultado_a_mano([[0, 6, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
                                 [[0, 2, 0, 0], [2, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])

    matriz = matriz_frecuencias(resultado)

    assert matriz.loc["X", "Y"] == 0.8 and matriz.loc["Y", "X"] == 0.3


def test_grafo_con_muchas_variables_y_un_solo_nivel(tmp_path):
    from nucleo.exportacion import dibujar_grafo

    variables = [f"variable_con_nombre_largo_{i}" for i in range(25)] + ["y"]
    aristas_grafo = [arista(variables[i], variables[i + 1]) for i in range(24)] + [arista(variables[3], "y")]
    grafo = GrafoAgregado(variables, "y", 0.6, 10, aristas_grafo, [])
    resultado = resultado_a_mano([[0] * 26 for _ in range(26)], [[0] * 26 for _ in range(26)],
                                 variables=tuple(variables), objetivo="y")
    caracterizacion = caracterizar(grafo, resultado, [])

    figura = dibujar_grafo(grafo, caracterizacion, [variables])
    figura.savefig(tmp_path / "g.png")

    assert (tmp_path / "g.png").stat().st_size > 10_000


def test_etiquetas_se_parten_en_limites_naturales():
    from nucleo.exportacion import partir_etiqueta

    assert partir_etiqueta("DiabetesPedigreeFunction") == "DiabetesPedigree\nFunction"
    assert partir_etiqueta("total sulfur dioxide") == "total sulfur\ndioxide"
    assert all(len(l) <= 18 for l in partir_etiqueta("abnormal_short_term_variability_x").split("\n"))
    assert partir_etiqueta("Age") == "Age"

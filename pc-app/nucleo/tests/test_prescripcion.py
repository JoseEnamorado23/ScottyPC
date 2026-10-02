"""Optimizador de prescripciones: solución analítica, restricciones, discretas, calibración de μ,
determinismo, suavizado y datos nuevos preparados con la receta."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

from pcapp_nucleo.causal import caso_desde_test, construir_modelo, modelo_desde_diccionario
from pcapp_nucleo.causal.contrafactuales import contrafactual_preparado
from pcapp_nucleo.preparacion import Codificacion, DecisionesUsuario, preparar, preparar_nuevos
from pcapp_nucleo.prescripcion import (
    MENSAJE_SIN_PRESCRIPTIVAS,
    ConfiguracionAccion,
    Genetico,
    GradienteProximal,
    ObjetivoDeseado,
    ajustar_referencia,
    calibrar_mu,
    configuracion_por_defecto,
    confirmar_supuestos,
    evaluar_prescribibilidad,
    prescribir_caso,
)
from pcapp_nucleo.prescripcion import calibracion as modulo_calibracion
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion

N = 4000


def resultado(variables, aristas):
    return {
        "variables": variables,
        "aristas": [{"origen": o, "destino": d, "tipo": "dirigida"} for o, d in aristas],
        "corridas": {"completo": True},
    }


def construir(df, objetivo, aristas, configuracion_causal=None, **decisiones):
    datos = preparar(df, objetivo, DecisionesUsuario(**decisiones))
    variables = [c for c in datos.train.columns]
    modelo_json, _ = construir_modelo(resultado(variables, aristas), datos, configuracion=configuracion_causal)
    return datos, modelo_desde_diccionario(modelo_json)


def configuracion(modelo, modificables, direccion="bajar", valor=0.3, **acciones):
    c = configuracion_por_defecto(modelo, modificables)
    c = replace(c, objetivo=ObjetivoDeseado(direccion, valor))
    if acciones:
        c = replace(c, acciones={**c.acciones, **{v: replace(c.acciones[v], **a) for v, a in acciones.items()}})
    return confirmar_supuestos(c, list(c.acciones))


def sin_restricciones(c, *variables):
    return replace(c, acciones={
        v: replace(a, minimo=None, maximo=None, cambio_maximo=None) if v in variables else a for v, a in c.acciones.items()
    })


@pytest.fixture(scope="module")
def logistico():
    """Y ~ Bernoulli(σ(−4 + 0,4·X1 + 0,2·X2)), X1 y X2 raíces uniformes en [0, 10]."""
    rng = np.random.default_rng(1)
    x1, x2 = rng.uniform(0, 10, (2, N))
    y = (rng.uniform(size=N) < expit(-4 + 0.4 * x1 + 0.2 * x2)).astype(int)
    datos, modelo = construir(
        pd.DataFrame({"X1": x1, "X2": x2, "Y": y}), "Y", [("X1", "Y"), ("X2", "Y")],
    )
    assert modelo.mecanismos["Y"].familia == "logistica"
    return datos, modelo


def caso_en_riesgo(datos, modelo, minimo=0.5):
    for indice in datos.test.index:
        caso = caso_desde_test(modelo, datos.test, int(indice))
        if modelo.media("Y", {v: np.array([caso.valores[v]]) for v in modelo.padres["Y"]})[0] > minimo:
            return caso
    raise AssertionError("No hay casos en riesgo")


# --- Solución analítica ---------------------------------------------------------------------------


@pytest.mark.parametrize("costos, esperada", [((1.0, 1.0), "X1"), ((1.0, 0.3), "X2")])
def test_intervencion_minima_analitica(logistico, costos, esperada):
    """Con costos lineales, la intervención mínima usa solo la variable con mayor |β|/costo y
    mueve el logit exactamente hasta logit(p*)."""
    datos, modelo = logistico
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.3, X1={"costo": costos[0]}, X2={"costo": costos[1]})
    c = sin_restricciones(c, "X1", "X2")
    caso = caso_en_riesgo(datos, modelo)
    beta = dict(zip(modelo.mecanismos["Y"].padres, modelo.mecanismos["Y"].coeficientes))
    eta0 = modelo.mecanismos["Y"].intercepto + sum(beta[v] * caso.valores[v] for v in beta)
    delta_preparado = (logit(0.3) - eta0) / beta[esperada]
    for optimizador in (GradienteProximal.desde(c), Genetico.desde(c)):
        r = prescribir_caso(modelo, caso, c, 0.01, optimizador=optimizador)
        assert r.alcanzado and r.despues == pytest.approx(0.3, abs=1e-6)
        assert [a.variable for a in r.acciones] == [esperada], optimizador.nombre
        escala = modelo.unidades.a_original_numerico(esperada, 1.0) - modelo.unidades.a_original_numerico(esperada, 0.0)
        assert r.acciones[0].cambio == pytest.approx(delta_preparado * escala, rel=1e-3)


def test_caso_que_ya_cumple_no_recibe_cambios(logistico):
    datos, modelo = logistico
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.99)
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[0]))
    r = prescribir_caso(modelo, caso, c, 0.01)
    assert r.ya_cumple and r.alcanzado and r.acciones == [] and r.despues == r.antes
    assert "ya cumple" in r.explicacion


# --- Restricciones -----------------------------------------------------------------------------


def test_limites_cambio_maximo_y_direccion(logistico):
    datos, modelo = logistico
    caso = caso_en_riesgo(datos, modelo, 0.6)
    x1 = modelo.unidades.a_original_numerico("X1", caso.valores["X1"])
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.3, X1={"cambio_maximo": 1.0, "minimo": x1 - 0.5},
                      X2={"direccion": "subir"})
    r = prescribir_caso(modelo, caso, c, 0.01)
    cambios = {a.variable: a for a in r.acciones}
    if "X1" in cambios:
        assert -0.5 - 1e-9 <= cambios["X1"].cambio <= 1.0 + 1e-9
        assert cambios["X1"].despues_numerico >= x1 - 0.5 - 1e-9
    assert "X2" not in cambios or cambios["X2"].cambio >= 0  # solo subir (y subir empeora)
    assert not r.alcanzado
    restricciones = {(x.variable, x.restriccion) for x in r.restricciones_activas}
    assert ("X1", "limite") in restricciones
    assert ("X2", "direccion") in restricciones
    assert r.falta > 0 and "Lo impiden" in r.explicacion


def test_objetivo_no_alcanzable_devuelve_la_mejor_solucion(logistico):
    datos, modelo = logistico
    caso = caso_en_riesgo(datos, modelo, 0.7)
    c = configuracion(modelo, ["X1"], "bajar", 0.01, X1={"cambio_maximo": 2.0})
    r = prescribir_caso(modelo, caso, c, 0.01)
    assert not r.alcanzado and r.falta > 0
    assert len(r.acciones) == 1 and r.acciones[0].cambio == pytest.approx(-2.0, abs=1e-6)
    assert r.restricciones_activas[0].restriccion == "cambio_maximo"


# --- Binarias y categorías ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def discreto():
    """B binaria, «zona» (a, b, c) y «nivel» ordinal → Y; X continua."""
    rng = np.random.default_rng(2)
    b = rng.integers(0, 2, N)
    zona = rng.choice(["a", "b", "c"], N)
    x = rng.uniform(0, 10, N)
    efecto = {"a": 0.0, "b": -1.5, "c": 1.0}
    eta = -1 + 1.2 * b + np.array([efecto[z] for z in zona]) + 0.1 * x
    y = (rng.uniform(size=N) < expit(eta)).astype(int)
    df = pd.DataFrame({"B": b, "zona": zona, "X": x, "Y": y})
    datos = preparar(df, "Y", DecisionesUsuario(codificaciones={"zona": Codificacion("one_hot")}))
    modelo_json, _ = construir_modelo(
        resultado(list(datos.train.columns), [("B", "Y"), ("zona=b", "Y"), ("zona=c", "Y"), ("X", "Y")]), datos,
    )
    return datos, modelo_desde_diccionario(modelo_json)


def test_enumeracion_de_binarias_y_categorias_sin_estados_imposibles(discreto):
    datos, modelo = discreto
    c = configuracion(modelo, ["B", "zona=b", "zona=c"], "bajar", 0.15)
    problema_zona = None
    for indice in datos.test.index[:40]:
        caso = caso_desde_test(modelo, datos.test, int(indice))
        r = prescribir_caso(modelo, caso, c, 0.01)
        dummies = {v.variable: v.despues_numerico for v in r.valores if v.grupo == "zona"}
        assert sum(dummies.values()) <= 1 + 1e-9  # nunca dos categorías a la vez
        assert all(x in (0.0, 1.0) for x in dummies.values())
        b = next(v for v in r.valores if v.variable == "B")
        assert b.despues_numerico in (0.0, 1.0)
        problema_zona = problema_zona or ProblemaPrescripcion(modelo, caso, c, 0.01)
    assert problema_zona.combinaciones() is not None and len(problema_zona.combinaciones()) == 6
    # Bajar el riesgo: quitar B y pasar a la zona «b» (la de menor riesgo).
    caso = next(
        caso_desde_test(modelo, datos.test, int(i)) for i in datos.test.index
        if datos.test.loc[i, "B"] == 1 and datos.test.loc[i, "zona=c"] == 1
    )
    r = prescribir_caso(modelo, caso, c, 0.001)
    acciones = {a.variable: a for a in r.acciones}
    assert acciones["zona"].despues == "b"


def test_busqueda_por_coordenadas_con_mas_de_16_combinaciones(discreto):
    datos, modelo = discreto
    c = configuracion(modelo, ["B", "zona=b", "zona=c"], "bajar", 0.1)
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[0]))
    problema = ProblemaPrescripcion(modelo, caso, c, 0.01)
    import pcapp_nucleo.prescripcion.problema as modulo_problema

    original = modulo_problema.MAXIMO_COMBINACIONES
    try:
        modulo_problema.MAXIMO_COMBINACIONES = 2
        assert problema.combinaciones() is None
        r = prescribir_caso(modelo, caso, c, 0.01, problema=ProblemaPrescripcion(modelo, caso, c, 0.01))
        dummies = [v.despues_numerico for v in r.valores if v.grupo == "zona"]
        assert sum(dummies) <= 1
    finally:
        modulo_problema.MAXIMO_COMBINACIONES = original


# --- Determinismo, suavizado y condiciones ----------------------------------------------------------


def test_determinismo_de_ambos_optimizadores(logistico):
    datos, modelo = logistico
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.3)
    caso = caso_en_riesgo(datos, modelo)
    for optimizador in (GradienteProximal.desde(c), Genetico.desde(c)):
        a = prescribir_caso(modelo, caso, c, 0.01, optimizador=optimizador)
        b = prescribir_caso(modelo, caso, c, 0.01, optimizador=optimizador)
        assert [(x.variable, x.despues_numerico) for x in a.acciones] == [(x.variable, x.despues_numerico) for x in b.acciones]
        assert a.despues == b.despues


def test_el_exito_se_decide_con_el_motor_exacto_no_con_el_suavizado():
    """A → B (intermedia binaria) → Y: el optimizador usa la versión suave de B, pero el resultado
    (probabilidad y éxito) es el del motor de contrafactuales exacto."""
    rng = np.random.default_rng(3)
    a = rng.uniform(0, 10, N)
    b = (-3 + 0.6 * a + rng.logistic(size=N) > 0).astype(int)
    y = (rng.uniform(size=N) < expit(-1.5 + 2.5 * b + 0.05 * a)).astype(int)
    datos, modelo = construir(pd.DataFrame({"A": a, "B": b, "Y": y}), "Y", [("A", "B"), ("B", "Y"), ("A", "Y")])
    assert modelo.tipo("B") == "binaria"
    c = sin_restricciones(configuracion(modelo, ["A"], "bajar", 0.3), "A")
    comprobados = 0
    for indice in datos.test.index[:60]:
        caso = caso_desde_test(modelo, datos.test, int(indice))
        problema = ProblemaPrescripcion(modelo, caso, c, 0.01)
        r = prescribir_caso(modelo, caso, c, 0.01, problema=problema)
        if r.ya_cumple:
            continue
        fijadas = {x.variable: modelo.unidades.a_preparada(x.variable, x.despues_numerico) for x in r.acciones}
        exacto = contrafactual_preparado(modelo, caso, fijadas).despues
        assert r.despues == pytest.approx(exacto, abs=1e-9)
        assert r.alcanzado == (exacto <= 0.3 + 1e-12)
        assert r.aproximado
        d = np.array([(fijadas.get("A", problema.continuas[0].x0) - problema.continuas[0].x0) / problema.continuas[0].escala])
        suave = float(problema.p([d], [()], suave=True)[0])
        comprobados += suave != pytest.approx(exacto, abs=1e-9)
    assert comprobados > 0  # el suavizado sí difiere del motor exacto en algunos casos


def test_condiciones_para_prescribir(logistico):
    datos, modelo = logistico
    sin_modificables = configuracion_por_defecto(modelo, [])
    problema = next(p for p in evaluar_prescribibilidad(modelo, sin_modificables) if p.codigo == "SIN_PRESCRIPTIVAS")
    assert problema.severidad == "bloqueante" and problema.mensaje.startswith(MENSAJE_SIN_PRESCRIPTIVAS)
    assert "ninguna variable marcada como modificable" in problema.mensaje
    c = configuracion_por_defecto(modelo, ["X1"])
    codigos = {p.codigo for p in evaluar_prescribibilidad(modelo, c)}
    assert "SUPUESTOS_SIN_CONFIRMAR" in codigos
    assert "SUPUESTOS_SIN_CONFIRMAR" not in {p.codigo for p in evaluar_prescribibilidad(modelo, confirmar_supuestos(c, ["X1"]))}
    assert {p.codigo for p in evaluar_prescribibilidad(modelo, c, vigente=False)} >= {"MODELO_NO_VIGENTE"}


def test_modificable_sin_camino_se_ignora_y_advierte():
    rng = np.random.default_rng(4)
    x, z = rng.normal(size=(2, 1500))
    y = (rng.uniform(size=1500) < expit(x)).astype(int)
    datos, modelo = construir(pd.DataFrame({"X": x, "Z": z, "Y": y}), "Y", [("X", "Y")])
    c = confirmar_supuestos(configuracion_por_defecto(modelo, ["X", "Z"]), ["X"])
    advertencia = next(p for p in evaluar_prescribibilidad(modelo, c) if p.codigo == "MODIFICABLES_SIN_CAMINO")
    assert advertencia.variables == ["Z"] and advertencia.severidad == "advertencia"
    assert list(c.acciones) == ["X"]
    solo_z = configuracion_por_defecto(modelo, ["Z"])
    bloqueo = next(p for p in evaluar_prescribibilidad(modelo, solo_z) if p.codigo == "SIN_PRESCRIPTIVAS")
    assert "no tienen camino" in bloqueo.mensaje


# --- Calibración de μ y datos nuevos ------------------------------------------------------------------


def test_calibracion_de_mu_solo_lee_train(logistico, monkeypatch):
    datos, modelo = logistico
    c = replace(configuracion(modelo, ["X1", "X2"], "bajar", 0.3), rejilla_mu=[0.001, 0.01, 0.1])
    vistos = []
    original = modulo_calibracion.caso_desde_test

    def registrar(m, filas, indice):
        vistos.append(indice)
        return original(m, filas, indice)

    monkeypatch.setattr(modulo_calibracion, "caso_desde_test", registrar)
    r = calibrar_mu(modelo, datos.train.iloc[:150], c)
    assert vistos and set(vistos) <= set(datos.train.index)
    assert not set(vistos) & set(datos.test.index)
    assert r.mu in (0.001, 0.01, 0.1) and len(r.rejilla) == 3
    assert r.casos == r.alcanzables + r.no_alcanzables
    assert "un solo arranque" in r.nota and "multiarranque" in r.nota


def test_csv_nuevo_da_el_mismo_resultado_que_la_fila_de_test(logistico):
    datos, modelo = logistico
    c = configuracion(modelo, ["X1", "X2"], "bajar", 0.3)
    # Filas originales (antes de preparar) de algunos casos de test.
    rng = np.random.default_rng(1)
    x1, x2 = rng.uniform(0, 10, (2, N))
    originales = pd.DataFrame({"X1": x1, "X2": x2})
    indices = datos.test.index[:15]
    nuevos = preparar_nuevos(originales.loc[indices].reset_index(drop=True), datos.receta)
    assert nuevos.problemas == []
    referencia = ajustar_referencia(datos.train, "Y", True)
    for posicion, indice in enumerate(indices):
        de_test = prescribir_caso(modelo, caso_desde_test(modelo, datos.test, int(indice)), c, 0.01, referencia,
                                  datos.test.loc[[indice]].drop(columns="Y"))
        caso_nuevo = caso_desde_test(modelo, nuevos.datos, posicion)
        caso_nuevo = replace(caso_nuevo, indice=int(indice))  # misma semilla que la fila de test
        nuevo = prescribir_caso(modelo, caso_nuevo, c, 0.01, referencia, nuevos.datos.loc[[posicion]])
        assert nuevo.despues == de_test.despues and nuevo.requiere_revision == de_test.requiere_revision
        assert [(a.variable, a.despues_numerico) for a in nuevo.acciones] == [(a.variable, a.despues_numerico) for a in de_test.acciones]


def test_csv_nuevo_informa_filas_y_columnas_con_problemas():
    rng = np.random.default_rng(5)
    df = pd.DataFrame({"x": rng.normal(size=200), "zona": rng.choice(["a", "b"], 200), "Y": rng.integers(0, 2, 200)})
    datos = preparar(df, "Y", DecisionesUsuario(codificaciones={"zona": Codificacion("binaria")}))
    nuevos = preparar_nuevos(pd.DataFrame({"x": [0.1, 0.2], "zona": ["a", "z"], "extra": [1, 2]}), datos.receta)
    assert [p.fila for p in nuevos.problemas] == [1] and "zona" in nuevos.problemas[0].mensaje
    assert list(nuevos.datos.index) == [0] and nuevos.columnas_ignoradas == ["extra"]
    from pcapp_nucleo.preparacion import ErrorPreparacion

    with pytest.raises(ErrorPreparacion, match="Faltan columnas"):
        preparar_nuevos(pd.DataFrame({"x": [0.1]}), datos.receta)

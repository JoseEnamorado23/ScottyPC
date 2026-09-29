"""Modelo causal estructural: aplicabilidad, mecanismos, contrafactuales y persistencia.

Usa SCM sintéticos con coeficientes conocidos (n = 3000) preparados con ``preparar`` (con
normalización, para comprobar que entrada y salida están en unidades originales).
"""

import json
import math

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from pcapp_nucleo.causal import (
    ConfiguracionModeloCausal,
    ErrorContrafactual,
    ErrorModeloCausal,
    Intervencion,
    caso_desde_test,
    caso_desde_valores,
    construir_modelo,
    contrafactual,
    descripcion_variables,
    evaluar_aplicabilidad,
    modelo_desde_diccionario,
)
from pcapp_nucleo.causal import mecanismos as modulo_mecanismos
from pcapp_nucleo.causal.unidades import Unidades
from pcapp_nucleo.preparacion import Codificacion, DecisionesUsuario, preparar

N = 3000


def resultado(variables, aristas, completo=True):
    """Contenido mínimo de un resultado.json: aristas como (origen, destino[, tipo])."""
    return {
        "variables": variables,
        "aristas": [
            {"origen": a[0], "destino": a[1], "tipo": a[2] if len(a) > 2 else "dirigida"} for a in aristas
        ],
        "corridas": {"completo": completo},
    }


def preparar_df(df, objetivo, **decisiones):
    return preparar(df, objetivo, DecisionesUsuario(**decisiones))


def codigos(problemas):
    return {p.codigo for p in problemas}


# --- SCM sintéticos -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cadena():
    """A → B → Y (lineal): B = 1 + 2A + e, Y = 3 − 1.5B + e."""
    rng = np.random.default_rng(1)
    a = rng.normal(10, 2, N)
    b = 1 + 2 * a + rng.normal(0, 0.5, N)
    y = 3 - 1.5 * b + rng.normal(0, 0.5, N)
    d = rng.normal(0, 1, N)  # sin relación con el resto
    datos = preparar_df(pd.DataFrame({"A": a, "B": b, "D": d, "Y": y}), "Y")
    res = resultado(["A", "B", "D", "Y"], [("A", "B"), ("B", "Y")])
    modelo_json, evaluacion = construir_modelo(res, datos)
    return datos, res, modelo_json, evaluacion


@pytest.fixture(scope="module")
def bifurcacion():
    """A → B, A → Y, B → Y: B = 2A + e, Y = 1 + 0.8A + 1.2B + e."""
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, N)
    b = 2 * a + rng.normal(0, 0.5, N)
    y = 1 + 0.8 * a + 1.2 * b + rng.normal(0, 0.5, N)
    datos = preparar_df(pd.DataFrame({"A": a, "B": b, "Y": y}), "Y")
    res = resultado(["A", "B", "Y"], [("A", "B"), ("A", "Y"), ("B", "Y")])
    return datos, construir_modelo(res, datos)[0]


def pendiente_original(modelo, variable, padre):
    """Coeficiente del mecanismo lineal expresado en unidades originales."""
    mecanismo = modelo.mecanismos[variable]
    i = mecanismo.padres.index(padre)
    u = modelo.unidades
    escala_y = u.a_original_numerico(variable, 1.0) - u.a_original_numerico(variable, 0.0)
    escala_x = u.a_original_numerico(padre, 1.0) - u.a_original_numerico(padre, 0.0)
    return mecanismo.coeficientes[i] * escala_y / escala_x


def test_cadena_recupera_coeficientes(cadena):
    datos, _, modelo_json, _ = cadena
    modelo = modelo_desde_diccionario(modelo_json, datos.train)
    assert modelo.mecanismos["B"].familia == "lineal"
    assert modelo.mecanismos["Y"].familia == "lineal"
    assert pendiente_original(modelo, "B", "A") == pytest.approx(2.0, abs=0.03)
    assert pendiente_original(modelo, "Y", "B") == pytest.approx(-1.5, abs=0.03)
    assert modelo_json["subgrafo"]["fuera"] == ["D"]


def test_cadena_contrafactual_coincide_con_el_analitico(cadena):
    datos, _, modelo_json, _ = cadena
    modelo = modelo_desde_diccionario(modelo_json)
    indice = int(datos.test.index[0])
    caso = caso_desde_test(modelo, datos.test, indice)
    r = contrafactual(modelo, caso, [Intervencion("A", "desplazar", 1.0)])
    # Con el residuo de B: B' = B + 2 → Y' − Y = −1.5 · 2 = −3.
    assert r.cambio == pytest.approx(-3.0, abs=0.08)
    b = next(v for v in r.valores if v.variable == "B")
    assert b.cambio == pytest.approx(2.0, abs=0.03)
    # Exacto con los coeficientes estimados.
    esperado = pendiente_original(modelo, "Y", "B") * pendiente_original(modelo, "B", "A")
    assert r.cambio == pytest.approx(esperado, rel=1e-9)
    # El valor factual de B (unidades originales) es el observado.
    assert b.antes == pytest.approx(modelo.unidades.a_original_numerico("B", float(datos.test.loc[indice, "B"])))
    assert [p.variable for p in r.traza] == ["A", "B", "Y"]


def test_fijar_en_unidades_originales(cadena):
    datos, _, modelo_json, _ = cadena
    modelo = modelo_desde_diccionario(modelo_json)
    caso = caso_desde_valores(modelo, {"A": 10.0, "B": 21.0})
    r = contrafactual(modelo, caso, [Intervencion("B", "fijar", 25.0)])
    assert r.cambio == pytest.approx(-1.5 * 4, abs=0.1)
    assert not r.extrapolacion


def test_bifurcacion_propagacion_y_traza(bifurcacion):
    datos, modelo_json = bifurcacion
    modelo = modelo_desde_diccionario(modelo_json)
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[3]))
    r = contrafactual(modelo, caso, [Intervencion("A", "desplazar", 1.0)])
    assert r.cambio == pytest.approx(0.8 + 1.2 * 2, abs=0.1)
    paso_y = next(p for p in r.traza if p.variable == "Y")
    contribuciones = {c.padre: c.contribucion for c in paso_y.por_padre}
    assert contribuciones["A"] == pytest.approx(0.8, abs=0.08)
    assert contribuciones["B"] == pytest.approx(2.4, abs=0.1)


def test_intervenir_sin_camino_al_objetivo_no_cambia_nada(cadena):
    datos, _, modelo_json, _ = cadena
    modelo = modelo_desde_diccionario(modelo_json)
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[0]))
    r = contrafactual(modelo, caso, [Intervencion("D", "fijar", 5.0)])
    assert r.cambio == 0.0
    assert all(v.cambio == 0.0 for v in r.valores)
    assert "SIN_EFECTO" in {a.codigo for a in r.avisos}


def test_no_se_interviene_el_objetivo_ni_sus_consecuencias():
    rng = np.random.default_rng(3)
    a = rng.normal(size=500)
    y = a + rng.normal(size=500)
    z = y + rng.normal(size=500)
    datos = preparar_df(pd.DataFrame({"A": a, "Y": y, "Z": z}), "Y")
    res = resultado(["A", "Y", "Z"], [("A", "Y"), ("Y", "Z")])
    modelo = modelo_desde_diccionario(construir_modelo(res, datos)[0])
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[0]))
    with pytest.raises(ErrorContrafactual, match="objetivo"):
        contrafactual(modelo, caso, [Intervencion("Y", "fijar", 0.0)])
    with pytest.raises(ErrorContrafactual, match="consecuencia"):
        contrafactual(modelo, caso, [Intervencion("Z", "fijar", 0.0)])


def test_extrapolacion_se_calcula_y_se_marca(cadena):
    datos, _, modelo_json, _ = cadena
    modelo = modelo_desde_diccionario(modelo_json)
    caso = caso_desde_test(modelo, datos.test, int(datos.test.index[0]))
    r = contrafactual(modelo, caso, [Intervencion("A", "fijar", 100.0)])
    assert r.extrapolacion
    assert "EXTRAPOLACION" in {a.codigo for a in r.avisos}
    assert next(v for v in r.valores if v.variable == "A").extrapolacion
    assert math.isfinite(r.despues)


# --- Intermedia binaria ------------------------------------------------------------------------


def test_intermedia_binaria_aproxima_el_contrafactual_verdadero():
    """B = 1[−0.5 + 2A + U > 0] (U logística), Y = 1 + 3B + 0.5A + e.

    Caso A = 0, B = 0; do(A = 1): P(B' = 1 | B = 0) = (σ(0.5) − σ(−1.5)) / σ(0.5).
    """
    rng = np.random.default_rng(4)
    a = rng.normal(0, 1, N)
    u = rng.logistic(size=N)
    b = (-0.5 + 2 * a + u > 0).astype(int)
    y = 1 + 3 * b + 0.5 * a + rng.normal(0, 0.3, N)
    datos = preparar_df(pd.DataFrame({"A": a, "B": b, "Y": y}), "Y")
    res = resultado(["A", "B", "Y"], [("A", "B"), ("A", "Y"), ("B", "Y")])
    modelo_json, _ = construir_modelo(res, datos)
    modelo = modelo_desde_diccionario(modelo_json)
    assert modelo.tipo("B") == "binaria"

    caso = caso_desde_valores(modelo, {"A": 0.0, "B": 0})
    r = contrafactual(modelo, caso, [Intervencion("A", "fijar", 1.0)])
    p = (expit(0.5) - expit(-1.5)) / expit(0.5)
    verdadero = 1 + 3 * p + 0.5 * 1.0
    assert r.aproximado and r.muestras == 200
    assert r.antes == pytest.approx(1.0, abs=0.1)
    assert r.despues == pytest.approx(verdadero, abs=0.3)
    b_despues = next(v for v in r.valores if v.variable == "B").despues
    assert b_despues == pytest.approx(p, abs=0.1)
    # Reproducible: misma semilla, mismo resultado.
    assert contrafactual(modelo, caso, [Intervencion("A", "fijar", 1.0)]).despues == r.despues


# --- Aplicabilidad -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def datos_basicos():
    rng = np.random.default_rng(5)
    a, b, c = rng.normal(size=(3, 600))
    y = (a + b + rng.logistic(size=600) > 0).astype(int)
    return preparar_df(pd.DataFrame({"A": a, "B": b, "C": c, "Y": y}), "Y")


def test_bloqueante_sin_causas(datos_basicos):
    problemas = evaluar_aplicabilidad(resultado(["A", "B", "C", "Y"], [("A", "B")]), datos_basicos)
    assert "SIN_CAUSAS" in codigos(problemas)


def test_bloqueante_arista_sin_orientar_en_el_subgrafo(datos_basicos):
    res = resultado(["A", "B", "C", "Y"], [("A", "B", "sin_orientar"), ("B", "Y"), ("C", "A")])
    problemas = evaluar_aplicabilidad(res, datos_basicos)
    arista = next(p for p in problemas if p.codigo == "ARISTA_SIN_ORIENTAR")
    assert arista.severidad == "bloqueante" and arista.destino == "resultados"
    assert "Oriente la arista A — B en Resultados" in arista.accion
    # Una arista sin orientar fuera del subgrafo no bloquea.
    fuera = resultado(["A", "B", "C", "Y"], [("B", "Y"), ("A", "C", "sin_orientar")])
    assert "ARISTA_SIN_ORIENTAR" not in codigos(evaluar_aplicabilidad(fuera, datos_basicos))


def test_bloqueante_ciclo(datos_basicos):
    res = resultado(["A", "B", "C", "Y"], [("A", "B"), ("B", "A"), ("B", "Y")])
    assert "CICLO" in codigos(evaluar_aplicabilidad(res, datos_basicos))


def test_bloqueante_multiclase():
    rng = np.random.default_rng(6)
    a = rng.normal(size=600)
    y = np.digitize(a + rng.normal(size=600), [-0.5, 0.5])
    datos = preparar_df(pd.DataFrame({"A": a, "Y": y}), "Y")
    problema = next(p for p in evaluar_aplicabilidad(resultado(["A", "Y"], [("A", "Y")]), datos)
                    if p.codigo == "OBJETIVO_MULTICLASE")
    assert problema.destino == "decisiones" and "Agrupe" in problema.accion


def test_bloqueante_datos_insuficientes():
    rng = np.random.default_rng(7)
    df = pd.DataFrame(rng.normal(size=(40, 4)), columns=["A", "B", "C", "Y"])
    datos = preparar_df(df, "Y")
    res = resultado(["A", "B", "C", "Y"], [("A", "Y"), ("B", "Y"), ("C", "Y")])
    assert "DATOS_INSUFICIENTES" in codigos(evaluar_aplicabilidad(res, datos))


def test_bloqueante_clase_minoritaria_insuficiente():
    rng = np.random.default_rng(8)
    a, b = rng.normal(size=(2, 400))
    y = np.zeros(400, dtype=int)
    y[:20] = 1
    datos = preparar_df(pd.DataFrame({"A": a, "B": b, "Y": y}), "Y")
    res = resultado(["A", "B", "Y"], [("A", "Y"), ("B", "Y")])
    assert "MINORITARIA_INSUFICIENTE" in codigos(evaluar_aplicabilidad(res, datos))


def test_bloqueante_resultado_incompleto_o_desactualizado(datos_basicos):
    res = resultado(["A", "B", "C", "Y"], [("A", "Y")], completo=False)
    assert "RESULTADO_INCOMPLETO" in codigos(evaluar_aplicabilidad(res, datos_basicos))
    res = resultado(["A", "B", "C", "Y"], [("A", "Y")])
    assert "RESULTADO_DESACTUALIZADO" in codigos(evaluar_aplicabilidad(res, datos_basicos, desactualizado=True))


def test_construir_con_bloqueantes_falla(datos_basicos):
    with pytest.raises(ErrorModeloCausal) as error:
        construir_modelo(resultado(["A", "B", "C", "Y"], []), datos_basicos)
    assert "SIN_CAUSAS" in codigos(error.value.problemas)


def test_advertencias_faltantes_intermedias_binarias_y_fuera():
    rng = np.random.default_rng(9)
    a = rng.normal(size=800)
    b = (a + rng.logistic(size=800) > 0).astype(float)
    c = rng.normal(size=800)
    y = (a + 2 * b + rng.logistic(size=800) > 1).astype(int)
    a[:30] = np.nan
    datos = preparar_df(pd.DataFrame({"A": a, "B": b, "C": c, "Y": y}), "Y")
    res = resultado(["A", "B", "C", "Y"], [("A", "B"), ("A", "Y"), ("B", "Y")])
    problemas = evaluar_aplicabilidad(res, datos)
    assert {"FALTANTES_SIN_IMPUTAR", "INTERMEDIAS_BINARIAS", "FUERA_DEL_SUBGRAFO"} <= codigos(problemas)
    assert all(p.severidad == "advertencia" for p in problemas)
    modelo_json, _ = construir_modelo(res, datos)
    assert modelo_json["imputadas_en_modelo"] == ["A"]


# --- Objetivo binario: calibración, umbral, monotonía y persistencia ---------------------------


@pytest.fixture(scope="module")
def binario():
    """X1 (monótona), X2 (en U) → Y binaria desbalanceada (≈ 20 % de positivos)."""
    rng = np.random.default_rng(10)
    x1 = rng.uniform(0, 10, N)
    x2 = rng.uniform(-3, 3, N)
    y = (rng.uniform(size=N) < expit(-3.2 + 0.3 * x1 + 0.5 * x2 ** 2)).astype(int)
    datos = preparar_df(pd.DataFrame({"X1": x1, "X2": x2, "Y": y}), "Y")
    res = resultado(["X1", "X2", "Y"], [("X1", "Y"), ("X2", "Y")])
    diagnosticos = [
        {"nombre": "X1", "monotona": True, "spearman": 0.3},
        {"nombre": "X2", "monotona": False, "spearman": 0.01, "motivo": "La relación sube y baja."},
    ]
    return datos, res, diagnosticos


def test_objetivo_binario_calibrado_con_umbral_en_cv(binario):
    datos, res, diagnosticos = binario
    modelo_json, evaluacion = construir_modelo(res, datos, diagnosticos)
    objetivo = evaluacion["evaluacion_objetivo"]
    assert modelo_json["pesos_clase"] is False
    assert modelo_json["mecanismos"]["Y"]["familia"] == "gam_logistico"  # la U exige el GAM
    assert 0.05 < objetivo["umbral_decision"] < 0.5
    assert objetivo["cv"]["brier"] < 0.2 and objetivo["test"]["auc"] > 0.7
    # Calibración: la probabilidad media se parece a la frecuencia observada.
    for punto in objetivo["calibracion"]["cv"]:
        assert abs(punto["probabilidad_media"] - punto["frecuencia_observada"]) < 0.12
    monotonia = {d["padre"]: d for d in modelo_json["monotonia"]}
    assert monotonia["X1"]["restriccion"] == "creciente" and monotonia["X1"]["origen"] == "automatico"
    assert monotonia["X2"]["restriccion"] is None
    efectos = {e["padre"]: e for e in next(m for m in evaluacion["mecanismos"] if m["variable"] == "Y")["efectos"]}
    assert efectos["X1"]["signo"] == 1
    assert efectos["X2"]["signo"] == 0  # sube y baja
    assert "histograma" in efectos["X1"]


def test_pesos_de_clase_como_override_advierten(binario):
    datos, res, diagnosticos = binario
    configuracion = ConfiguracionModeloCausal(pesos_clase=True, mecanismos={"Y": "simple"})
    modelo_json, _ = construir_modelo(res, datos, diagnosticos, configuracion)
    assert modelo_json["pesos_clase"] is True
    assert "PROBABILIDADES_NO_CALIBRADAS" in {a["codigo"] for a in modelo_json["advertencias"]}
    assert modelo_json["mecanismos"]["Y"]["seleccion"]["origen"] == "manual"


def test_monotonia_manual(binario):
    datos, res, diagnosticos = binario
    configuracion = ConfiguracionModeloCausal(monotonia={"X1": "ninguna"})
    modelo_json, _ = construir_modelo(res, datos, diagnosticos, configuracion)
    x1 = next(d for d in modelo_json["monotonia"] if d["padre"] == "X1")
    assert x1["restriccion"] is None and x1["origen"] == "manual"


def test_guardar_y_cargar_da_las_mismas_predicciones(binario):
    datos, res, diagnosticos = binario
    modelo_json, _ = construir_modelo(res, datos, diagnosticos)
    original = modelo_desde_diccionario(modelo_json)
    cargado = modelo_desde_diccionario(json.loads(json.dumps(modelo_json)), datos.train)
    for variable in original.mecanismos:
        assert np.array_equal(original.media(variable, datos.test), cargado.media(variable, datos.test))
    caso = caso_desde_test(cargado, datos.test, int(datos.test.index[0]))
    intervencion = [Intervencion("X1", "desplazar", 2.0)]
    assert contrafactual(original, caso, intervencion) == contrafactual(cargado, caso, intervencion)


def test_cargar_con_otro_train_falla(binario):
    datos, res, diagnosticos = binario
    modelo_json, _ = construir_modelo(res, datos, diagnosticos, ConfiguracionModeloCausal(mecanismos={"Y": "simple"}))
    with pytest.raises(ErrorModeloCausal, match="entrenamiento"):
        modelo_desde_diccionario(modelo_json, datos.train.iloc[:-1])


def test_rescate_si_pygam_no_converge(binario, monkeypatch):
    datos, res, diagnosticos = binario
    original = modulo_mecanismos._ajuste_pygam
    llamadas = {"n": 0}

    def primero_falla(*args, **kwargs):
        llamadas["n"] += 1
        gam, problema = original(*args, **kwargs)
        return (gam, "no convergió") if llamadas["n"] == 1 else (gam, problema)

    monkeypatch.setattr(modulo_mecanismos, "_ajuste_pygam", primero_falla)
    configuracion = ConfiguracionModeloCausal(mecanismos={"Y": "complejo"}, pliegues=2)
    X = datos.train[["X1", "X2"]].to_numpy()
    y = datos.train["Y"].to_numpy(dtype=float)
    mecanismo, rescate, _ = modulo_mecanismos.ajustar_gam(
        "Y", ["X1", "X2"], X, y, True, [True, True], [None, None], configuracion
    )
    assert mecanismo.familia == "gam_logistico"
    assert any("no convergió" in r for r in rescate) and any("aumentó" in r for r in rescate)


def test_eleccion_manual_del_mecanismo(cadena):
    datos, res, _, _ = cadena
    modelo_json, _ = construir_modelo(res, datos, configuracion=ConfiguracionModeloCausal(mecanismos={"B": "complejo"}))
    seleccion = modelo_json["mecanismos"]["B"]["seleccion"]
    assert modelo_json["mecanismos"]["B"]["familia"] == "splines_ridge"
    assert seleccion["origen"] == "manual" and seleccion["elegido"] == "complejo"


def test_referencia_muestra_el_costo_de_la_parsimonia():
    """Y depende de A (causa en el grafo) y de C (no está en el grafo): la referencia gana."""
    rng = np.random.default_rng(11)
    a, c = rng.normal(size=(2, N))
    y = (rng.uniform(size=N) < expit(0.8 * a + 2.0 * c)).astype(int)
    datos = preparar_df(pd.DataFrame({"A": a, "C": c, "Y": y}), "Y")
    modelo_json, evaluacion = construir_modelo(resultado(["A", "C", "Y"], [("A", "Y")]), datos)
    assert evaluacion["referencia"]["advertencia"]
    assert "COSTO_PARSIMONIA" in {a["codigo"] for a in modelo_json["advertencias"]}


# --- Unidades y categorías ---------------------------------------------------------------------


def test_unidades_ida_y_vuelta_con_logaritmo_y_codificaciones():
    rng = np.random.default_rng(12)
    df = pd.DataFrame({
        "ingreso": rng.lognormal(3, 1, 300),
        "nivel": rng.choice(["bajo", "medio", "alto"], 300),
        "zona": rng.choice(["norte", "sur", "este"], 300),
        "Y": rng.integers(0, 2, 300),
    })
    datos = preparar_df(
        df, "Y", logaritmos=["ingreso"],
        codificaciones={
            "nivel": Codificacion("ordinal", orden=["bajo", "medio", "alto"]),
            "zona": Codificacion("one_hot"),
        },
    )
    u = Unidades(datos.columnas)
    for valor in (1.5, 20.0, 400.0):
        assert u.a_original_numerico("ingreso", u.a_preparada("ingreso", valor)) == pytest.approx(valor)
    assert u.a_original("nivel", u.a_preparada("nivel", "medio")) == "medio"
    assert set(u.grupos) == {"zona"}
    grupo = u.grupos["zona"]
    assert grupo.referencia == "este" and grupo.categorias == ["este", "norte", "sur"]
    assert u.dummies_de_categoria("zona", "sur") == {"zona=norte": 0.0, "zona=sur": 1.0}
    assert u.dummies_de_categoria("zona", "este") == {"zona=norte": 0.0, "zona=sur": 0.0}


def test_categoria_one_hot_se_interviene_como_grupo():
    rng = np.random.default_rng(13)
    zona = rng.choice(["a", "b", "c"], N)
    x = rng.normal(size=N)
    efecto = {"a": 0.0, "b": 1.0, "c": -1.0}
    y = 2 * x + np.array([efecto[z] for z in zona]) + rng.normal(0, 0.3, N)
    datos = preparar_df(pd.DataFrame({"zona": zona, "X": x, "Y": y}), "Y", codificaciones={"zona": Codificacion("one_hot")})
    res = resultado(["zona=b", "zona=c", "X", "Y"], [("zona=b", "Y"), ("zona=c", "Y"), ("X", "Y")])
    modelo = modelo_desde_diccionario(construir_modelo(res, datos)[0])
    controles = {c["nombre"]: c for c in descripcion_variables(modelo)}
    assert controles["zona"]["control"] == "grupo_one_hot"
    assert controles["zona"]["categorias"] == ["a", "b", "c"]

    caso = caso_desde_valores(modelo, {"zona": "a", "X": 0.0})
    r = contrafactual(modelo, caso, [Intervencion("zona", "fijar", "b")])
    assert r.cambio == pytest.approx(1.0, abs=0.1)
    r = contrafactual(modelo, caso, [Intervencion("zona", "fijar", "c")])
    assert r.cambio == pytest.approx(-1.0, abs=0.1)
    dummies = {v.variable: v.despues for v in r.valores if v.grupo == "zona"}
    assert dummies == {"zona=b": 0, "zona=c": 1}
    with pytest.raises(ErrorContrafactual, match="dummy"):
        contrafactual(modelo, caso, [Intervencion("zona=b", "fijar", 1)])
    with pytest.raises(ErrorContrafactual, match="solo se puede fijar"):
        contrafactual(modelo, caso, [Intervencion("zona", "desplazar", 1)])
    with pytest.raises(ErrorContrafactual, match="categoría"):
        contrafactual(modelo, caso, [Intervencion("zona", "fijar", "z")])

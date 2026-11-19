"""Evidencia de vecinos y comparador de métodos, sobre datos con la verdad causal conocida.

Generador: X → M → Y, con Y ~ Bernoulli(σ(−5 + 1,0·M)), M = X + ruido y una consecuencia C de Y
(C no es causa: el modelo de referencia la usa, el causal no). La única acción es X: el
prescriptor causal sabe que mover X mueve M; el método sin causalidad (referencia, sin propagar)
cree que mover X apenas cambia Y porque casi todo el efecto lo explica M.
"""

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from pcapp_nucleo.causal import caso_desde_test
from pcapp_nucleo.prescripcion import ajustar_referencia, evaluar_prescriptor, prescribir_caso
from pcapp_nucleo.prescripcion.comparador import (
    ALEATORIA, IMITAR, METODOS, PRESCRIPTOR, SIN_CAUSALIDAD, SIN_INTERVENCION, ProblemaSinCausalidad,
)
from pcapp_nucleo.prescripcion.evidencia import construir_indice, evidencia_caso
from pcapp_nucleo.prescripcion.lotes import prescribir_lote, que_no_cumplen
from pcapp_nucleo.utilidades import a_diccionario_serializable

from .test_prescripcion import construir, configuracion

N = 3000


@pytest.fixture(scope="module")
def mediado():
    rng = np.random.default_rng(5)
    x = rng.uniform(0, 10, N)
    m = x + rng.normal(0, 0.5, N)
    y = (rng.uniform(size=N) < expit(-5 + 1.0 * m)).astype(int)
    c = y + rng.normal(0, 0.3, N)
    datos, modelo = construir(
        pd.DataFrame({"X": x, "M": m, "Y": y, "C": c}), "Y", [("X", "M"), ("M", "Y"), ("Y", "C")],
    )
    return datos, modelo


def test_el_indice_busca_por_el_perfil_y_las_acciones_no_por_las_mediadoras(mediado):
    datos, modelo = mediado
    indice = construir_indice(modelo, datos.train, configuracion(modelo, ["X"]))
    assert indice.columnas_accion == ["X"]
    assert "M" not in indice.columnas_perfil  # depende de la acción
    assert indice.k == 20 and indice.umbral_respaldo > 0


def test_indice_sin_datos_suficientes_o_sin_acciones(mediado):
    datos, modelo = mediado
    assert construir_indice(modelo, datos.train.head(8), configuracion(modelo, ["X"])) is None
    assert construir_indice(modelo, datos.train, configuracion(modelo, [])) is None


def test_los_vecinos_de_la_prescripcion_tienen_mejor_resultado_observado(mediado):
    datos, modelo = mediado
    c = configuracion(modelo, ["X"], valor=0.3, X={"cambio_maximo": None})
    indice = construir_indice(modelo, datos.train, c)
    caso = _caso_alto(datos, modelo)
    r = prescribir_caso(modelo, caso, c, 0.01, vecinos=indice)
    assert r.alcanzado and r.evidencia is not None
    e = r.evidencia
    assert e.prescrita.valor < e.actual.valor  # bajar Y: los vecinos con X más bajo tienen menos Y=1
    assert e.mejora > 0 and e.prescrita.con_respaldo
    assert "parecidos" in e.texto
    # Sin índice no hay evidencia (y el resto del resultado no cambia).
    sin = prescribir_caso(modelo, caso, c, 0.01)
    assert sin.evidencia is None and sin.despues == pytest.approx(r.despues)


def test_sin_cambios_los_dos_grupos_son_el_mismo(mediado):
    datos, modelo = mediado
    c = configuracion(modelo, ["X"])
    indice = construir_indice(modelo, datos.train, c)
    e = evidencia_caso(indice, {"X": 0.2, "M": 0.2}, {}, "Y", 1)
    assert e.prescrita == e.actual and e.mejora == 0


def _caso_alto(datos, modelo):
    """Caso de test con X en el percentil 90 (riesgo alto, pero con vecinos alrededor)."""
    x = datos.test["X"]
    indice = (x - x.quantile(0.9)).abs().idxmin()
    return caso_desde_test(modelo, datos.test, int(indice))


def test_el_problema_sin_causalidad_conserva_su_clase_al_cambiar_mu(mediado):
    datos, modelo = mediado
    c = configuracion(modelo, ["X"])
    referencia = ajustar_referencia(datos.train, "Y", True)
    caso = _caso_alto(datos, modelo)
    fila = datos.test.loc[[caso.indice]].drop(columns=["Y"])
    problema = ProblemaSinCausalidad(modelo, caso, c, 0.01, referencia, fila)
    assert isinstance(problema.con_mu(0.0), ProblemaSinCausalidad)
    # Sin intervenir, coincide con la predicción de la referencia sobre la fila.
    p0 = problema.p(np.zeros((1, problema.k)), [problema.actual])[0]
    assert p0 == pytest.approx(referencia.predecir(fila)[0])


@pytest.fixture(scope="module")
def evaluacion(mediado):
    datos, modelo = mediado
    c = configuracion(modelo, ["X"], valor=0.3)
    referencia = ajustar_referencia(datos.train, "Y", True)
    test = datos.test.loc[que_no_cumplen(modelo, datos.test.drop(columns=["Y"]), c).index[:40]]
    return evaluar_prescriptor(modelo, test, c, 0.01, referencia, train=datos.train)


def test_el_comparador_juzga_todos_los_metodos_en_los_mismos_casos(evaluacion):
    metodos = {m.metodo: m for m in evaluacion.comparador}
    assert list(metodos) == list(METODOS)
    assert all(m.casos == evaluacion.casos for m in metodos.values())
    assert metodos[SIN_INTERVENCION].tasa_exito_causal == 0
    assert metodos[SIN_INTERVENCION].costo_medio == 0 and metodos[SIN_INTERVENCION].mejora_vecinos_media == 0
    assert metodos[PRESCRIPTOR].tasa_exito_causal == pytest.approx(evaluacion.tasa_exito)
    for otro in (SIN_CAUSALIDAD, IMITAR, ALEATORIA):
        assert metodos[PRESCRIPTOR].tasa_exito_causal >= metodos[otro].tasa_exito_causal
        assert metodos[otro].p_valor_frente_prescriptor is not None
    assert metodos[PRESCRIPTOR].p_valor_frente_prescriptor is None


def test_los_vecinos_confirman_al_prescriptor_y_no_al_metodo_sin_causalidad(evaluacion):
    metodos = {m.metodo: m for m in evaluacion.comparador}
    prescriptor, sin_causalidad = metodos[PRESCRIPTOR], metodos[SIN_CAUSALIDAD]
    # El efecto de X pasa por M: sin propagar, la referencia subestima el efecto de X y se queda corta.
    assert prescriptor.valor_vecinos_medio < sin_causalidad.valor_vecinos_medio
    assert prescriptor.mejora_vecinos_media > 0
    e = evaluacion.evidencia_vecinos
    assert e.medida == "proporcion" and e.casos == evaluacion.casos
    assert e.porcentaje_con_respaldo > 50
    assert e.mejora_media > 0 and e.intervalo_mejora[0] > 0 and e.p_valor < 0.05
    assert e.valor_prescrita_medio < e.valor_actual_medio
    assert e.coincidencia_modelo > 50


def test_evaluacion_sin_train_no_tiene_evidencia_y_se_serializa(mediado, evaluacion):
    datos, modelo = mediado
    c = configuracion(modelo, ["X"], valor=0.3)
    test = datos.test.loc[que_no_cumplen(modelo, datos.test.drop(columns=["Y"]), c).index[:5]]
    sin = evaluar_prescriptor(modelo, test, c, 0.01, None)
    assert sin.evidencia_vecinos is None
    assert {m.metodo for m in sin.comparador} == {PRESCRIPTOR, ALEATORIA, SIN_INTERVENCION}
    serializada = a_diccionario_serializable(evaluacion)
    assert serializada["evidencia_vecinos"]["k"] == 20 and len(serializada["comparador"]) == len(METODOS)


def test_el_lote_con_train_trae_la_evidencia_de_cada_caso(mediado):
    datos, modelo = mediado
    c = configuracion(modelo, ["X"], valor=0.3)
    filas = datos.test.head(3)
    con = prescribir_lote(modelo, filas, c, 0.01, None, train=datos.train)
    sin = prescribir_lote(modelo, filas, c, 0.01, None)
    assert all(r["evidencia"] is not None for r in con) and all(r["evidencia"] is None for r in sin)
    assert [r["despues"] for r in con] == [r["despues"] for r in sin]

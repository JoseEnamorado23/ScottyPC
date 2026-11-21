"""Rejilla de valores permitidos (``paso``): enteras, ordinales con muchos niveles, paso 0,5,
ordinales discretas y binarias; y el aviso «alcanzable solo con cambios intermedios»."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from pcapp_nucleo.causal import caso_desde_test
from pcapp_nucleo.prescripcion import ConfiguracionAccion, GradienteProximal, prescribir_caso
from pcapp_nucleo.prescripcion.configuracion import paso_por_defecto
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion
from pcapp_nucleo.prescripcion.rejilla import ErrorRejilla, comprobar_rejilla
from pcapp_nucleo.preparacion import Codificacion

from .test_prescripcion import caso_en_riesgo, configuracion, construir, sin_restricciones

N = 4000
ORDEN15 = list(range(20, 35))  # etiquetas 20..34 (códigos 0..14): no coinciden con sus códigos
ORDEN5 = [1, 2, 3, 4, 5]


@pytest.fixture(scope="module")
def mundo():
    """Y ~ Bernoulli(σ(−4,5 + 0,45·ENT + 0,2·CONT + 0,25·ORD15 + 0,3·ORD5 + 1,2·B))."""
    rng = np.random.default_rng(5)
    ent = rng.integers(0, 11, N)
    cont = rng.uniform(0, 10, N)
    ord15 = rng.choice(ORDEN15, N)
    ord5 = rng.choice(ORDEN5, N)
    b = rng.integers(0, 2, N)
    eta = -4.5 + 0.45 * ent + 0.2 * cont + 0.25 * (ord15 - 20) + 0.3 * (ord5 - 1) + 1.2 * b
    y = (rng.uniform(size=N) < expit(eta)).astype(int)
    df = pd.DataFrame({"ENT": ent, "CONT": cont, "ORD15": ord15, "ORD5": ord5, "B": b, "Y": y})
    aristas = [(v, "Y") for v in ("ENT", "CONT", "ORD15", "ORD5", "B")]
    datos, modelo = construir(
        df, "Y", aristas,
        codificaciones={"ORD15": Codificacion("ordinal", orden=ORDEN15), "ORD5": Codificacion("ordinal", orden=ORDEN5)},
    )
    return datos, modelo


def prescribir(mundo, c, caso=None):
    datos, modelo = mundo
    caso = caso or caso_en_riesgo(datos, modelo, 0.7)
    return prescribir_caso(modelo, caso, c, 0.0 + 1e-3, optimizador=GradienteProximal(), semilla_por_valores=True), caso


def acciones(r):
    return {a.variable: a for a in r.acciones}


def test_paso_por_defecto(mundo):
    _, modelo = mundo
    assert paso_por_defecto(modelo, "ENT") == 1.0        # solo enteros en train
    assert paso_por_defecto(modelo, "CONT") is None       # continua libre
    assert paso_por_defecto(modelo, "ORD15") == 1.0       # un nivel
    assert paso_por_defecto(modelo, "ORD5") == 1.0
    assert paso_por_defecto(modelo, "B") is None          # binaria: no tiene paso
    c = configuracion(modelo, ["ENT", "CONT", "ORD15", "ORD5", "B"])
    assert {v: a.paso for v, a in c.acciones.items()} == {"ENT": 1.0, "CONT": None, "ORD15": 1.0, "ORD5": 1.0, "B": None}


def test_entera_solo_propone_enteros(mundo):
    _, modelo = mundo
    c = sin_restricciones(configuracion(modelo, ["ENT", "CONT"], "bajar", 0.3), "ENT", "CONT")
    r, _ = prescribir(mundo, c)
    a = acciones(r)
    assert r.alcanzado
    assert float(a["ENT"].despues) == round(float(a["ENT"].despues))
    assert not r.solo_con_cambios_intermedios


def test_sin_paso_la_continua_queda_libre(mundo):
    _, modelo = mundo
    c = sin_restricciones(configuracion(modelo, ["ENT"], "bajar", 0.3), "ENT")
    libre = replace(c, acciones={"ENT": replace(c.acciones["ENT"], paso=None)})
    r, _ = prescribir(mundo, libre)
    despues = float(acciones(r)["ENT"].despues)
    assert abs(despues - round(despues)) > 1e-6  # el valor intermedio de siempre


def test_paso_medio_en_continua(mundo):
    _, modelo = mundo
    c = sin_restricciones(configuracion(modelo, ["CONT"], "bajar", 0.45, CONT={"paso": 0.5}), "CONT")
    r, _ = prescribir(mundo, c)
    despues = float(acciones(r)["CONT"].despues)
    assert (despues / 0.5) == pytest.approx(round(despues / 0.5), abs=1e-6)


def test_ordinal_con_muchos_niveles_propone_niveles_existentes(mundo):
    datos, modelo = mundo
    assert len(modelo.unidades.mapeo("ORD15")) == 15
    c = sin_restricciones(configuracion(modelo, ["ORD15"], "bajar", 0.3), "ORD15")
    r, caso = prescribir(mundo, c)
    despues = acciones(r)["ORD15"].despues
    assert acciones(r)["ORD15"].tipo == "continua"  # >10 niveles: relajación continua + rejilla
    assert despues in ORDEN15  # una etiqueta real, no un valor intermedio


def test_ordinal_hasta_diez_niveles_sigue_siendo_discreta(mundo):
    _, modelo = mundo
    c = sin_restricciones(configuracion(modelo, ["ORD5"], "bajar", 0.3), "ORD5")
    r, _ = prescribir(mundo, c)
    assert acciones(r)["ORD5"].tipo == "discreta"
    assert acciones(r)["ORD5"].despues in ORDEN5


def test_binaria_sin_cambios(mundo):
    datos, modelo = mundo
    c = configuracion(modelo, ["B"], "bajar", 0.3)
    assert c.acciones["B"].paso is None
    vistas = 0
    for indice in list(datos.test.index)[:60]:
        r, _ = prescribir(mundo, c, caso_desde_test(modelo, datos.test, int(indice)))
        for a in r.acciones:
            assert a.tipo == "discreta" and a.despues in (0, 1)
            vistas += 1
    assert vistas > 0


def test_combinadas_nunca_salen_de_su_rejilla(mundo):
    datos, modelo = mundo
    c = sin_restricciones(
        configuracion(modelo, ["ENT", "CONT", "ORD15", "ORD5", "B"], "bajar", 0.25, CONT={"paso": 0.5}),
        "ENT", "CONT", "ORD15", "ORD5",
    )
    revisados = 0
    for indice in list(datos.test.index)[:25]:
        caso = caso_desde_test(modelo, datos.test, int(indice))
        r, _ = prescribir(mundo, c, caso)
        for a in r.acciones:
            if a.variable == "ENT":
                assert float(a.despues) == round(float(a.despues))
            if a.variable == "CONT":
                assert float(a.despues) / 0.5 == pytest.approx(round(float(a.despues) / 0.5), abs=1e-6)
            if a.variable == "ORD15":
                assert a.despues in ORDEN15
            if a.variable == "ORD5":
                assert a.despues in ORDEN5
            revisados += 1
    assert revisados > 10


def test_alcanzable_solo_con_cambios_intermedios(mundo):
    """Con un máximo no entero, la relajación alcanza el objetivo pero la rejilla de pasos enteros no."""
    datos, modelo = mundo
    caso = caso_en_riesgo(datos, modelo, 0.6)
    base = sin_restricciones(configuracion(modelo, ["ENT"], "bajar", 0.3), "ENT")
    problema = ProblemaPrescripcion(modelo, caso, base, 1e-3)
    a = problema.continuas[0]
    x0 = a.a_original(a.x0)

    def p_en(valor_original):
        d = (a.a_preparada(valor_original) - a.x0) / a.escala
        return float(problema.p([np.array([d])], [()])[0])

    # Objetivo entre lo que da bajar 1 punto entero y lo que da bajar 1,4 puntos.
    deseado = (p_en(np.floor(x0 - 0.001)) + p_en(x0 - 1.4)) / 2
    c = replace(
        base,
        objetivo=replace(base.objetivo, valor=float(deseado)),
        acciones={"ENT": replace(base.acciones["ENT"], minimo=x0 - 1.5, maximo=None, paso=1.0)},
    )
    entera, _ = prescribir(mundo, c, caso)
    libre = replace(c, acciones={"ENT": replace(c.acciones["ENT"], paso=None)})
    intermedia, _ = prescribir(mundo, libre, caso)

    assert intermedia.alcanzado and not intermedia.solo_con_cambios_intermedios
    assert not entera.alcanzado and entera.solo_con_cambios_intermedios
    assert "cambios intermedios" in entera.explicacion
    despues = float(acciones(entera)["ENT"].despues)
    assert despues == round(despues)


def test_la_comprobacion_final_falla_fuera_de_la_rejilla(mundo):
    datos, modelo = mundo
    caso = caso_en_riesgo(datos, modelo, 0.6)
    c = sin_restricciones(configuracion(modelo, ["ENT"], "bajar", 0.3), "ENT")
    problema = ProblemaPrescripcion(modelo, caso, c, 1e-3)
    a = problema.continuas[0]
    x0 = a.a_original(a.x0)
    fuera = (a.a_preparada(x0 - 0.37) - a.x0) / a.escala
    dentro = (a.a_preparada(round(x0) - 1) - a.x0) / a.escala
    comprobar_rejilla(problema, np.array([dentro]))
    with pytest.raises(ErrorRejilla):
        comprobar_rejilla(problema, np.array([fuera]))

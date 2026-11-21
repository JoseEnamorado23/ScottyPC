"""Límites de las ordinales en valores originales (no en códigos) y migración de las configuraciones
guardadas con límites en códigos."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from pcapp_nucleo.causal import caso_desde_test
from pcapp_nucleo.prescripcion import configuracion_desde_diccionario, migrar_limites
from pcapp_nucleo.prescripcion.configuracion import ConfiguracionAccion, problemas_configuracion, rango_original
from pcapp_nucleo.preparacion import Codificacion
from pcapp_nucleo.utilidades import a_diccionario_serializable

from .test_prescripcion import caso_en_riesgo, configuracion, construir, sin_restricciones
from .test_rejilla import ORDEN5, ORDEN15, acciones, mundo, prescribir  # noqa: F401  (fixture)

N = 3000


@pytest.fixture(scope="module")
def mundo_desigual():
    """Y depende de TAM (niveles 10, 20, 50, 100: no igualmente espaciados), DESC (orden descendente
    5..1) y BAJO (texto: sus límites se cuentan en niveles)."""
    rng = np.random.default_rng(11)
    tam = rng.choice([10, 20, 50, 100], N)
    desc = rng.choice([1, 2, 3, 4, 5], N)
    bajo = rng.choice(["bajo", "medio", "alto"], N)
    eta = -2.0 + 0.02 * tam + 0.4 * desc + 0.5 * pd.Series(bajo).map({"bajo": 0, "medio": 1, "alto": 2}).to_numpy()
    y = (rng.uniform(size=N) < expit(eta)).astype(int)
    df = pd.DataFrame({"TAM": tam, "DESC": desc, "BAJO": bajo, "Y": y})
    return construir(
        df, "Y", [(v, "Y") for v in ("TAM", "DESC", "BAJO")],
        codificaciones={
            "TAM": Codificacion("ordinal", orden=[10, 20, 50, 100]),
            "DESC": Codificacion("ordinal", orden=[5, 4, 3, 2, 1]),
            "BAJO": Codificacion("ordinal", orden=["bajo", "medio", "alto"]),
        },
    )


def test_valor_original_frente_a_codigo(mundo):
    """Con orden [1..5], el valor 3 es el tercer nivel (código 2): sin ambigüedad con el código 3."""
    _, modelo = mundo
    u = modelo.unidades
    assert u.niveles_ordinal("ORD5") == [(1.0, 0.0), (2.0, 1.0), (3.0, 2.0), (4.0, 3.0), (5.0, 4.0)]
    assert u.niveles_permitidos("ORD5", minimo=3) == [2.0, 3.0, 4.0]       # 3, 4 y 5
    assert u.niveles_permitidos("ORD5", maximo=3) == [0.0, 1.0, 2.0]       # 1, 2 y 3
    assert u.niveles_permitidos("ORD5", centro=2.0, radio=1) == [1.0, 2.0, 3.0]  # a un valor del 3
    assert rango_original(modelo, "ORD5") == (1.0, 5.0)
    assert rango_original(modelo, "ORD15") == (20.0, 34.0)
    por_defecto = configuracion(modelo, ["ORD15"]).acciones["ORD15"]
    assert (por_defecto.minimo, por_defecto.maximo) == (20.0, 34.0)       # valores, no 0 y 14
    assert por_defecto.cambio_maximo == pytest.approx(0.25 * 14)


def test_minimo_y_cambio_maximo_en_valores_discreta(mundo):
    datos, modelo = mundo
    c = sin_restricciones(configuracion(modelo, ["ORD5"], "bajar", 0.3), "ORD5")
    libre = {"minimo": None, "maximo": None, "cambio_maximo": None}
    c = replace(c, acciones={"ORD5": replace(c.acciones["ORD5"], **{**libre, "minimo": 3.0, "cambio_maximo": 1.0})})
    vistas = 0
    for indice in list(datos.test.index)[:40]:
        r, _ = prescribir(mundo, c, caso_desde_test(modelo, datos.test, int(indice)))
        for a in r.acciones:
            vistas += 1
            assert a.despues >= 3          # el límite es el valor 3 (no el código 3, que sería el valor 4)
            assert abs(a.despues - a.antes) <= 1
    assert vistas > 0


def test_minimo_y_cambio_maximo_en_valores_continua(mundo):
    datos, modelo = mundo
    base = sin_restricciones(configuracion(modelo, ["ORD15"], "bajar", 0.3), "ORD15")
    c = replace(base, acciones={"ORD15": replace(base.acciones["ORD15"], minimo=27.0, cambio_maximo=3.0)})
    vistas = 0
    for indice in list(datos.test.index)[:40]:
        r, _ = prescribir(mundo, c, caso_desde_test(modelo, datos.test, int(indice)))
        for a in r.acciones:
            vistas += 1
            assert a.despues in ORDEN15 and a.despues >= 27
            assert abs(a.despues - a.antes) <= 3 + 1e-9
            # el cambio y los valores numéricos se informan en valores originales, no en códigos
            assert a.despues_numerico == pytest.approx(a.despues)
            assert a.cambio == pytest.approx(a.despues - a.antes)
    assert vistas > 0


def test_ningun_nivel_en_el_rango_es_un_error_de_validacion(mundo):
    _, modelo = mundo
    c = configuracion(modelo, ["ORD5"], "bajar", 0.3)
    mala = replace(c, acciones={"ORD5": replace(c.acciones["ORD5"], minimo=7.0, maximo=9.0)})
    assert [p.campo for p in problemas_configuracion(modelo, mala)] == ["acciones.ORD5.minimo"]
    assert not problemas_configuracion(modelo, c)


def _antigua(c, **cambios_por_variable):
    """La configuración como se guardaba antes: sin ``unidades_limites`` y con límites en códigos."""
    datos = a_diccionario_serializable(c)
    del datos["unidades_limites"]
    for variable, cambios in cambios_por_variable.items():
        datos["acciones"][variable].update(cambios)
    return configuracion_desde_diccionario(datos)


def test_migracion_conserva_el_significado(mundo):
    datos, modelo = mundo
    nueva = configuracion(modelo, ["ORD5", "ORD15"], "bajar", 0.3)
    # códigos: ORD5 niveles 1..3 (valores 2..4) y cambio de 1,25 niveles; ORD15 desde el nivel 4
    antigua = _antigua(nueva, ORD5={"minimo": 1.0, "maximo": 3.0, "cambio_maximo": 1.25}, ORD15={"minimo": 4.0, "maximo": None})
    assert antigua.unidades_limites == "codigo"
    migrada, avisos = migrar_limites(modelo, antigua)
    assert migrada.unidades_limites == "original"
    assert (migrada.acciones["ORD5"].minimo, migrada.acciones["ORD5"].maximo) == (2.0, 4.0)
    assert migrada.acciones["ORD5"].cambio_maximo == pytest.approx(1.25)
    assert (migrada.acciones["ORD15"].minimo, migrada.acciones["ORD15"].maximo) == (24.0, None)
    assert avisos and not any(a.distinta for a in avisos)  # se reexpresó, no cambió
    assert migrar_limites(modelo, migrada) == (migrada, [])  # idempotente

    # y da las mismas prescripciones que la configuración ya migrada
    for indice in list(datos.test.index)[:15]:
        caso = caso_desde_test(modelo, datos.test, int(indice))
        a, _ = prescribir(mundo, antigua, caso)
        b, _ = prescribir(mundo, migrada, caso)
        assert [(x.variable, x.despues) for x in a.acciones] == [(x.variable, x.despues) for x in b.acciones]


def test_migracion_sin_cambio_si_valor_y_codigo_coinciden(mundo_desigual):
    _, modelo = mundo_desigual
    c = configuracion(modelo, ["BAJO"], "bajar", 0.3)  # etiquetas de texto: el valor es la posición
    migrada, avisos = migrar_limites(modelo, _antigua(c, BAJO={"minimo": 1.0, "maximo": 2.0, "cambio_maximo": 1.0}))
    assert avisos == []
    assert (migrada.acciones["BAJO"].minimo, migrada.acciones["BAJO"].maximo, migrada.acciones["BAJO"].cambio_maximo) == (1.0, 2.0, 1.0)
    assert modelo.unidades.etiquetas_numericas("BAJO") is False


def test_migracion_avisa_si_el_espaciado_es_desigual(mundo_desigual):
    _, modelo = mundo_desigual
    c = configuracion(modelo, ["TAM"], "bajar", 0.3)
    migrada, avisos = migrar_limites(modelo, _antigua(c, TAM={"minimo": 1.0, "maximo": 3.0, "cambio_maximo": 1.0}))
    assert (migrada.acciones["TAM"].minimo, migrada.acciones["TAM"].maximo) == (20.0, 100.0)  # niveles 1 y 3 → 20 y 100
    (aviso,) = avisos
    assert aviso.distinta and "igualmente espaciados" in aviso.mensaje


def test_migracion_invierte_la_direccion_si_el_orden_baja_en_valor(mundo_desigual):
    _, modelo = mundo_desigual
    c = configuracion(modelo, ["DESC"], "bajar", 0.3)
    antigua = _antigua(c, DESC={"direccion": "subir", "minimo": 1.0, "maximo": 3.0})
    migrada, avisos = migrar_limites(modelo, antigua)
    accion = migrada.acciones["DESC"]
    assert accion.direccion == "bajar"                      # subir de nivel = bajar de valor (5, 4, 3, 2, 1)
    assert (accion.minimo, accion.maximo) == (2.0, 4.0)     # niveles 1..3 = valores 4, 3, 2
    assert avisos and not avisos[0].distinta
    assert "dirección" in avisos[0].mensaje


def test_configuracion_nueva_no_se_migra(mundo):
    _, modelo = mundo
    c = configuracion(modelo, ["ORD5"], "bajar", 0.3)
    assert c.unidades_limites == "original"
    assert migrar_limites(modelo, c) == (c, [])

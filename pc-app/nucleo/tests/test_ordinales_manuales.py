"""Marcar variables como ordinales: por el hallazgo sugerido y a mano (sin hallazgo)."""

import numpy as np
import pandas as pd
import pytest

from pcapp_nucleo.analisis import analizar_dataset
from pcapp_nucleo.plantilla import (
    ErrorEleccion,
    aplicar_elecciones,
    aplicar_marcas_ordinales,
    generar_plantilla,
    separar_marcas_ordinales,
)
from pcapp_nucleo.preparacion import Codificacion, preparar, separacion_sugerida


@pytest.fixture(scope="module")
def datos():
    rng = np.random.default_rng(3)
    n = 600
    estrato = rng.choice([1, 2, 3, 4, 5, 6], n, p=[0.3, 0.3, 0.2, 0.1, 0.06, 0.04])
    creditos = rng.integers(8, 23, n)  # 15 niveles: no hay hallazgo ordinal
    x = rng.normal(size=n)
    y = (x + 0.2 * estrato - 0.05 * creditos + rng.normal(size=n) > 0).astype(int)
    return pd.DataFrame({"estrato": estrato, "creditos": creditos, "x": x, "y": y})


@pytest.fixture(scope="module")
def informe(datos):
    return analizar_dataset(datos, "y").informe


def _tipo_final(datos, decisiones, columna):
    prep = preparar(datos, "y", decisiones, separacion=separacion_sugerida(decisiones))
    return next(c.tipo_final for c in prep.receta.columnas if c.nombre == columna)


def test_aceptar_el_orden_sugerido_crea_la_ordinal(datos, informe):
    ids = [h.identificador for h in informe.hallazgos if h.tipo == "posible_variable_ordinal"]
    assert any(i.endswith(":estrato") for i in ids)
    decisiones = generar_plantilla(informe)
    assert decisiones.codificaciones["estrato"].tipo == "ordinal"
    assert decisiones.codificaciones["estrato"].orden == [1, 2, 3, 4, 5, 6]
    assert _tipo_final(datos, decisiones, "estrato") == "ordinal"


def test_sin_orden_la_deja_numerica(datos, informe):
    ident = next(h.identificador for h in informe.hallazgos
                 if h.tipo == "posible_variable_ordinal" and h.columnas_involucradas == ["estrato"])
    decisiones = aplicar_elecciones(informe, {ident: "sin_orden"})
    assert "estrato" not in decisiones.codificaciones or decisiones.codificaciones["estrato"].tipo != "ordinal"


def test_marcar_a_mano_una_columna_sin_hallazgo(datos, informe):
    base = generar_plantilla(informe)
    assert "creditos" not in base.codificaciones
    hallazgos, marcas = separar_marcas_ordinales({"ordinal_manual:creditos": "marcar"})
    assert hallazgos == {} and marcas == {"creditos": "marcar"}
    decisiones = aplicar_marcas_ordinales(base, datos, marcas)
    assert decisiones.codificaciones["creditos"] == Codificacion("ordinal", orden=list(range(8, 23)))
    assert _tipo_final(datos, decisiones, "creditos") == "ordinal"
    # no cambia nada más
    assert {k: v for k, v in decisiones.codificaciones.items() if k != "creditos"} == base.codificaciones


def test_quitar_la_marca_devuelve_la_numerica(datos, informe):
    base = aplicar_marcas_ordinales(generar_plantilla(informe), datos, {"creditos": "marcar", "estrato": "quitar"})
    assert "estrato" not in base.codificaciones
    assert _tipo_final(datos, base, "estrato") == "continua"
    otra = aplicar_marcas_ordinales(base, datos, {"creditos": "quitar"})
    assert "creditos" not in otra.codificaciones


def test_marcar_una_ya_ordinal_conserva_su_orden(datos, informe):
    base = generar_plantilla(informe)
    assert aplicar_marcas_ordinales(base, datos, {"estrato": "marcar"}).codificaciones == base.codificaciones


def test_marcas_invalidas(datos, informe):
    base = generar_plantilla(informe)
    for marcas in ({"no_existe": "marcar"}, {"creditos": "borrar"}, {"y": "marcar"}):
        if marcas == {"y": "marcar"}:
            continue
        with pytest.raises(ErrorEleccion):
            aplicar_marcas_ordinales(base, datos, marcas)
    texto = datos.assign(t=["a", "b"] * (len(datos) // 2))
    with pytest.raises(ErrorEleccion, match="no es numérica"):
        aplicar_marcas_ordinales(base, texto, {"t": "marcar"})

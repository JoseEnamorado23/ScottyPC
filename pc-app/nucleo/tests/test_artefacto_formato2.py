"""Artefactos reales de formato 2 (exportados con v0.5): siguen cargándose y su golden se verifica idéntico.

En el formato 1 y 2 el `paso` de controles.json es solo informativo (el golden trae valores como Asistencia 2,4975) y
la prescripción se comporta como antes: sin paso, salvo lo que diga su propia configuración. La comprobación de rejilla
y de ``valores_permitidos`` de ``verificar_golden`` aplica solo desde el formato 3.
"""
from pathlib import Path

import pytest

from pcapp_nucleo.artefacto import cargar_artefacto, verificar_golden

DATOS = Path(__file__).parent / "datos_formato2"
ARTEFACTOS = sorted(DATOS.glob("*.scotty"))


def test_hay_artefactos_de_formato_2():
    assert len(ARTEFACTOS) == 2


@pytest.mark.parametrize("ruta", ARTEFACTOS, ids=lambda r: r.name)
def test_el_golden_de_un_artefacto_de_formato_2_se_verifica_identico(ruta):
    art = cargar_artefacto(ruta)
    assert art.manifest.version_formato == 2
    informe = verificar_golden(art)
    assert informe.correcto, informe.diferencias[:3]
    assert (informe.casos, informe.casos_identicos, informe.casos_equivalentes, informe.casos_fallidos) == (20, 20, 0, 0)
    assert informe.maxima_diferencia == 0.0


def test_el_golden_de_formato_2_trae_valores_fuera_de_la_rejilla_del_paso_informativo():
    """La razón de la regla: lo que se exportó con v0.5 ya traía valores intermedios aunque `paso` valga 1."""
    art = cargar_artefacto(next(r for r in ARTEFACTOS if r.name.startswith("Factores")))
    assert art.controles.control("Asistencia").paso == 1
    valores = [a["despues"] for c in art.golden["casos"] for a in c["prescribir"]["acciones"] if a["variable"] == "Asistencia"]
    assert any(abs(v - round(v)) > 1e-3 for v in valores)

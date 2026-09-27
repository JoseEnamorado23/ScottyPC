"""Prueba mínima de infraestructura: importación y serialización de contratos."""

import json

import numpy as np

from nucleo import (
    Hallazgo,
    InformeRevision,
    NivelProblema,
    PerfilColumna,
    ProblemaValidacion,
    ResultadoValidacion,
    Severidad,
)
from nucleo.utilidades import a_diccionario_serializable


def test_contratos_se_serializan_a_json():
    resultado = ResultadoValidacion(
        valido=False,
        errores=[
            ProblemaValidacion(
                nivel=NivelProblema.ERROR,
                codigo="codigo_prueba",
                mensaje="Mensaje de prueba.",
                columnas=["a"],
                evidencia={"conteo": np.int64(3), "proporcion": np.float64(0.5)},
            )
        ],
    )
    informe = InformeRevision(
        resumen={"filas": np.int64(10), "vacio": np.bool_(False)},
        hallazgos=[
            Hallazgo(
                tipo="tipo_prueba",
                columnas_involucradas=["a", "b"],
                severidad=Severidad.MEDIA,
                detalle="Detalle de prueba.",
                evidencia={"valores": np.array([1, 2])},
            )
        ],
        perfiles_columnas=[
            PerfilColumna(
                nombre="a",
                tipo_detectado="numerico",
                faltantes=0,
                porcentaje_faltantes=0.0,
                valores_unicos=2,
                minimo=np.float64(np.nan),
            )
        ],
    )

    datos_resultado = a_diccionario_serializable(resultado)
    datos_informe = a_diccionario_serializable(informe)
    json.dumps(datos_resultado)
    json.dumps(datos_informe)

    assert datos_resultado["errores"][0]["nivel"] == "error"
    assert datos_resultado["errores"][0]["evidencia"] == {"conteo": 3, "proporcion": 0.5}
    assert datos_informe["resumen"] == {"filas": 10, "vacio": False}
    assert datos_informe["hallazgos"][0]["severidad"] == "media"
    assert datos_informe["hallazgos"][0]["evidencia"]["valores"] == [1, 2]
    assert datos_informe["perfiles_columnas"][0]["minimo"] is None

"""Endpoints de solo lectura (revisión guardada, datos por hoja, distribución)
y previsualización de decisiones a partir de elecciones."""

import json

import pandas as pd

from conftest import CEROS, crear_proyecto, ok


def test_revision_guardada(cliente, diabetes):
    proyecto = crear_proyecto(cliente, diabetes)
    sin_revision = cliente.get(f"/proyectos/{proyecto}/revision")
    assert sin_revision.status_code == 409

    revisada = ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "Outcome"}))
    guardada = ok(cliente.get(f"/proyectos/{proyecto}/revision"))

    assert guardada == revisada
    acciones = ok(cliente.get(f"/proyectos/{proyecto}/decisiones/plantilla"))["acciones_hallazgos"]
    pendientes = [a for a in acciones.values() if a["requiere_confirmacion"]]
    assert (len(guardada["hallazgos"]), len(pendientes)) == (7, 6)


def test_datos_por_hoja(cliente, tmp_path):
    ruta = tmp_path / "libro.xlsx"
    with pd.ExcelWriter(ruta) as escritor:
        pd.DataFrame({"x": range(150), "y": [0, 1] * 75}).to_excel(escritor, sheet_name="datos", index=False)
        pd.DataFrame({"a": [1, 2]}).to_excel(escritor, sheet_name="notas", index=False)
    proyecto = crear_proyecto(cliente, ruta)

    primera = ok(cliente.get(f"/proyectos/{proyecto}/datos"))
    notas = ok(cliente.get(f"/proyectos/{proyecto}/datos", params={"hoja": "notas"}))
    inexistente = cliente.get(f"/proyectos/{proyecto}/datos", params={"hoja": "otra"})

    assert (primera["hoja"], primera["hojas"], primera["filas"]) == ("datos", ["datos", "notas"], 150)
    assert primera["columnas"] == ["x", "y"] and len(primera["vista_previa"]) == 20
    assert (notas["hoja"], notas["filas"], notas["vista_previa"]) == ("notas", 2, [{"a": 1}, {"a": 2}])
    assert inexistente.status_code == 422
    assert inexistente.json()["error"]["detalles"][0]["campo"] == "hoja"


def test_datos_csv_sin_hojas(cliente, diabetes):
    datos = ok(cliente.get(f"/proyectos/{crear_proyecto(cliente, diabetes)}/datos"))

    assert (datos["hoja"], datos["hojas"], datos["filas"]) == (None, None, 768)


def test_distribucion_categorias_e_histograma(cliente, diabetes):
    proyecto = crear_proyecto(cliente, diabetes)

    objetivo = ok(cliente.get(f"/proyectos/{proyecto}/distribucion", params={"columna": "Outcome"}))
    glucosa = ok(cliente.get(f"/proyectos/{proyecto}/distribucion", params={"columna": "Glucose"}))
    inexistente = cliente.get(f"/proyectos/{proyecto}/distribucion", params={"columna": "Nada"})

    assert objetivo["tipo"] == "categorias" and objetivo["total"] == 768
    assert {c["valor"]: c["conteo"] for c in objetivo["categorias"]} == {0: 500, 1: 268}
    assert round(sum(c["porcentaje"] for c in objetivo["categorias"])) == 100
    assert glucosa["tipo"] == "histograma" and glucosa["categorias"] == []
    assert len(glucosa["histograma"]["limites"]) == len(glucosa["histograma"]["conteos"]) + 1 == 21
    assert sum(glucosa["histograma"]["conteos"]) == 768
    assert inexistente.status_code == 422
    assert inexistente.json()["error"]["detalles"][0]["campo"] == "columna"


def test_distribucion_agrupa_otros(cliente, tmp_path):
    ruta = tmp_path / "muchas.csv"
    pd.DataFrame({"c": [f"v{i % 30}" for i in range(300)], "y": [0, 1] * 150}).to_csv(ruta, index=False)
    proyecto = crear_proyecto(cliente, ruta)

    distribucion = ok(cliente.get(f"/proyectos/{proyecto}/distribucion", params={"columna": "c"}))

    assert len(distribucion["categorias"]) == 21 and distribucion["valores_distintos"] == 30
    assert distribucion["categorias"][-1] == {"valor": "otros", "conteo": 100, "porcentaje": 33.33}


def test_previsualizar_decisiones(cliente, diabetes):
    proyecto = crear_proyecto(cliente, diabetes)
    ruta = f"/proyectos/{proyecto}/decisiones/previsualizar"
    assert cliente.post(ruta, json={"elecciones": {}}).status_code == 409
    informe = ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "Outcome"}))
    ceros = {h["columnas_involucradas"][0]: h["identificador"]
             for h in informe["hallazgos"] if h["tipo"] == "ceros_sospechosos"}

    plantilla = ok(cliente.get(f"/proyectos/{proyecto}/decisiones/plantilla"))
    sin_elecciones = ok(cliente.post(ruta, json={"elecciones": {}}))
    elegidas = ok(cliente.post(ruta, json={"elecciones": {ceros[c]: "ceros_como_faltantes_imputar_mediana"
                                                          for c in CEROS}}))

    assert sin_elecciones == plantilla
    for columna in CEROS:
        assert elegidas["faltantes"][columna] == {"ceros_como_faltantes": True, "indicador_medido": False,
                                                  "imputacion": "mediana"}
        assert elegidas["acciones_hallazgos"][ceros[columna]]["accion"] == "ceros_como_faltantes_imputar_mediana"
    # Previsualizar no guarda nada.
    assert cliente.get(f"/proyectos/{proyecto}/decisiones").status_code == 409
    # Guardar lo previsualizado se acepta tal cual.
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=elegidas))


def test_previsualizar_eleccion_no_valida(cliente, diabetes):
    proyecto = crear_proyecto(cliente, diabetes)
    informe = ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "Outcome"}))
    identificador = informe["hallazgos"][0]["identificador"]
    ruta = f"/proyectos/{proyecto}/decisiones/previsualizar"

    accion = cliente.post(ruta, json={"elecciones": {identificador: "borrar"}})
    hallazgo = cliente.post(ruta, json={"elecciones": {"no_existe": "conservar"}})
    tipo = cliente.post(ruta, json={"elecciones": {identificador: 3}})

    assert accion.status_code == hallazgo.status_code == tipo.status_code == 422
    assert accion.json()["error"]["codigo"] == "ELECCION_NO_VALIDA"
    assert accion.json()["error"]["detalles"][0]["campo"] == f"elecciones.{identificador}"
    assert hallazgo.json()["error"]["detalles"][0]["campo"] == "elecciones.no_existe"
    assert tipo.json()["error"]["detalles"][0]["campo"] == f"elecciones.{identificador}"


def test_decisiones_de_la_app_coinciden_con_las_de_la_terminal(cliente, diabetes):
    """Criterio de aceptación: confirmar los ceros como faltantes en la app da las mismas
    decisiones que datasets_prueba/diabetes_decisiones.json (plantilla editada en la terminal).
    Solo difiere ``acciones_hallazgos``: en la terminal se editó ``faltantes`` a mano. El
    archivo es anterior a que la separación pasara a la receta: su ``separacion`` es la
    antigua (estratificada por defecto) y se lee solo como valor inicial."""
    terminal = json.loads((diabetes.parent / "diabetes_decisiones.json").read_text(encoding="utf-8"))
    proyecto = crear_proyecto(cliente, diabetes)
    informe = ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "Outcome"}))
    elecciones = {
        h["identificador"]: "ceros_como_faltantes" if h["columnas_involucradas"] != ["Pregnancies"] else "conservar"
        for h in informe["hallazgos"] if h["tipo"] == "ceros_sospechosos"
    }

    previsualizadas = ok(cliente.post(f"/proyectos/{proyecto}/decisiones/previsualizar", json={"elecciones": elecciones}))
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=previsualizadas))
    guardadas = ok(cliente.get(f"/proyectos/{proyecto}/decisiones"))

    assert {k: v for k, v in guardadas.items() if k != "acciones_hallazgos"} == {
        k: v for k, v in terminal.items() if k not in ("acciones_hallazgos", "separacion")
    }
    assert terminal["separacion"]["tipo"] == "estratificada"

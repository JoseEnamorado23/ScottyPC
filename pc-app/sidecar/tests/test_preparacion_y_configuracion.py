"""Preparación con separación (solo en la receta), límite de columnas, evaluación de la
prueba elegida, plantilla y validación de la configuración de PC sin guardarla."""

import json

import numpy as np
import pandas as pd
import pytest

from conftest import (
    CEROS,
    NIVELES_DIABETES,
    crear_proyecto,
    esperar_trabajo,
    hasta_configuracion,
    hasta_decisiones,
    ok,
)


def estados(cliente, proyecto):
    return ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]


# --- Preparación --------------------------------------------------------------------------------


def test_preparar_sin_cuerpo_usa_la_separacion_sugerida_y_guarda_el_resumen(cliente, diabetes):
    proyecto = hasta_decisiones(cliente, diabetes)
    antes = ok(cliente.get(f"/proyectos/{proyecto}/preparacion"))
    assert antes["vigente"] is False and antes["resumen"] is None
    assert antes["separacion"]["tipo"] == "estratificada" and antes["columnas_fecha_disponibles"] == []

    resumen = ok(cliente.post(f"/proyectos/{proyecto}/preparar"))
    despues = ok(cliente.get(f"/proyectos/{proyecto}/preparacion"))

    assert despues["vigente"] is True and despues["resumen"] == resumen
    assert resumen["separacion_configurada"] == antes["separacion"]
    train, test = resumen["distribucion_objetivo"]["train"], resumen["distribucion_objetivo"]["test"]
    assert (train["filas"], test["filas"]) == (resumen["filas_train"], resumen["filas_test"])
    assert sum(c["conteo"] for c in train["clases"]) + sum(c["conteo"] for c in test["clases"]) == 768
    assert {c["valor"] for c in train["clases"]} == {0, 1}
    assert resumen["limite_columnas"] == {"estado": "ok", "columnas": 9, "mensaje": None, "columnas_one_hot": {}}
    receta = json.loads((cliente.app.state.servicios.archivos.carpeta(proyecto) / "receta.json").read_text(encoding="utf-8"))
    assert receta["version"] == 2 and receta["separacion"] == resumen["separacion_configurada"]
    assert "separacion" not in receta["decisiones"]


def test_preparar_con_otra_separacion_y_rehacer_invalida_solo_lo_posterior(cliente, diabetes):
    proyecto = hasta_configuracion(cliente, diabetes, corridas_bootstrap=4)
    ok(cliente.post(f"/proyectos/{proyecto}/recomendacion?estimar_tiempo=false"), 202)
    trabajo = ok(cliente.get(f"/proyectos/{proyecto}"))["ultimo_trabajo"]
    esperar_trabajo(cliente, trabajo["id"])
    configuracion = ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc"))["configuracion"]
    configuracion.update(niveles=NIVELES_DIABETES, corridas_bootstrap=4, procesos=1)
    ok(cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json=configuracion))
    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
    assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
    assert set(estados(cliente, proyecto).values()) == {"vigente"}

    separacion = {"tipo": "estratificada", "proporcion_test": 0.25, "semilla": 7}
    resumen = ok(cliente.post(f"/proyectos/{proyecto}/preparar", json={"separacion": separacion}))

    assert resumen["filas_test"] == 192 and resumen["separacion_configurada"]["semilla"] == 7
    assert estados(cliente, proyecto) == {
        "revision": "vigente", "decisiones": "vigente", "preparacion": "vigente",
        "recomendacion": "desactualizada", "configuracion_pc": "desactualizada", "analisis": "desactualizada",
    }
    # Cambiar las decisiones archiva la receta, pero su separación sigue siendo el valor inicial.
    decisiones = ok(cliente.get(f"/proyectos/{proyecto}/decisiones"))
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones))
    estado = ok(cliente.get(f"/proyectos/{proyecto}/preparacion"))
    assert estado["vigente"] is False
    assert estado["separacion"] == {**separacion, "columna_fecha": None, "corte": None}


@pytest.fixture
def con_fecha(tmp_path):
    rng = np.random.default_rng(5)
    n = 300
    x = rng.normal(size=n)
    dataframe = pd.DataFrame({
        "fecha": pd.date_range("2024-01-01", periods=n).strftime("%Y-%m-%d"),
        "x": x,
        "z": x + rng.normal(size=n),
        "y": (x + rng.normal(size=n) > 0).astype(int),
    })
    ruta = tmp_path / "con fecha.csv"
    dataframe.to_csv(ruta, index=False)
    return ruta


def _decisiones_con_fecha_reservada(cliente, ruta):
    proyecto = crear_proyecto(cliente, ruta)
    informe = ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "y"}))
    fecha = next(h["identificador"] for h in informe["hallazgos"] if h["tipo"] == "posible_fecha")
    decisiones = ok(cliente.post(
        f"/proyectos/{proyecto}/decisiones/previsualizar", json={"elecciones": {fecha: "separacion_temporal"}}
    ))
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones))
    return proyecto


def test_separacion_temporal_con_corte_y_errores_por_campo(cliente, con_fecha):
    proyecto = _decisiones_con_fecha_reservada(cliente, con_fecha)
    estado = ok(cliente.get(f"/proyectos/{proyecto}/preparacion"))
    assert estado["columnas_fecha_disponibles"] == ["fecha"]
    assert estado["separacion"]["tipo"] == "temporal" and estado["separacion"]["columna_fecha"] == "fecha"

    def preparar(**separacion):
        return cliente.post(f"/proyectos/{proyecto}/preparar", json={"separacion": {"tipo": "temporal", **separacion}})

    def campo(respuesta):
        assert respuesta.status_code == 422, respuesta.text
        return respuesta.json()["error"]["detalles"][0]["campo"]

    assert campo(preparar(columna_fecha="x")) == "separacion.columna_fecha"
    assert campo(preparar(columna_fecha=None)) == "separacion.columna_fecha"
    assert campo(preparar(columna_fecha="fecha", corte="01/05/2024")) == "separacion.corte"
    assert campo(preparar(columna_fecha="fecha", corte="")) == "separacion.corte"
    assert campo(preparar(columna_fecha="fecha", corte="2030-01-01")) == "separacion.corte"

    resumen = ok(preparar(columna_fecha="fecha", corte="2024-08-01"))
    assert resumen["separacion"]["tipo"] == "temporal" and resumen["separacion"]["corte"] == "2024-08-01"
    assert resumen["filas_train"] == 213 and "fecha" not in [c["nombre"] for c in resumen["columnas"]]

    cronologica = ok(preparar(columna_fecha="fecha", proporcion_test=0.2))
    assert (cronologica["filas_train"], cronologica["filas_test"]) == (240, 60)
    # Con la fecha reservada pero separación estratificada, la fecha tampoco es variable.
    estratificada = ok(cliente.post(f"/proyectos/{proyecto}/preparar", json={"separacion": {"tipo": "estratificada"}}))
    assert "fecha" not in [c["nombre"] for c in estratificada["columnas"]]


# --- Límite de columnas -------------------------------------------------------------------------


def test_mas_de_50_columnas_bloquea_recomendacion_y_analisis(cliente, tmp_path):
    # 20 numéricas y dos categóricas de 18 categorías en one-hot: 20 + 2 * 17 + objetivo = 55.
    rng = np.random.default_rng(6)
    n = 400
    dataframe = pd.DataFrame(rng.normal(size=(n, 20)), columns=[f"v{i}" for i in range(20)])
    for nombre in ("ciudad", "oficio"):
        dataframe[nombre] = [f"{nombre}_{i % 18}" for i in rng.permutation(n)]
    dataframe["y"] = (dataframe["v0"] + rng.normal(size=n) > 0).astype(int)
    ruta = tmp_path / "ancho.csv"
    dataframe.to_csv(ruta, index=False)
    proyecto = crear_proyecto(cliente, ruta)
    informe = ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "y"}))
    elecciones = {
        h["identificador"]: "one_hot" for h in informe["hallazgos"]
        if h["tipo"] == "variable_categorica" and h["columnas_involucradas"][0] in ("ciudad", "oficio")
    }
    assert len(elecciones) == 2
    decisiones = ok(cliente.post(f"/proyectos/{proyecto}/decisiones/previsualizar", json={"elecciones": elecciones}))
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones))

    limite = ok(cliente.post(f"/proyectos/{proyecto}/preparar"))["limite_columnas"]
    recomendacion = cliente.post(f"/proyectos/{proyecto}/recomendacion?estimar_tiempo=false")
    ok(cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json=ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc/plantilla"))))
    analisis = cliente.post(f"/proyectos/{proyecto}/pc")

    assert limite["estado"] == "bloqueado" and limite["columnas"] == 55
    assert limite["columnas_one_hot"] == {"ciudad": 17, "oficio": 17}
    for respuesta in (recomendacion, analisis):
        assert respuesta.status_code == 409
        assert respuesta.json()["error"]["codigo"] == "DEMASIADAS_COLUMNAS"
        assert respuesta.json()["error"]["mensaje"] == limite["mensaje"]


# --- Evaluación de la prueba elegida ---------------------------------------------------------------


def test_evaluar_la_prueba_elegida(cliente, diabetes):
    proyecto = hasta_decisiones(cliente, diabetes)
    ok(cliente.post(f"/proyectos/{proyecto}/preparar"))
    ruta = f"/proyectos/{proyecto}/recomendacion/evaluar"
    assert cliente.post(ruta, json={"prueba": "fisherz"}).status_code == 409
    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/recomendacion?estimar_tiempo=false"), 202)
    esperar_trabajo(cliente, trabajo["id"])
    recomendada = ok(cliente.get(f"/proyectos/{proyecto}/recomendacion"))["prueba"]

    coherente = ok(cliente.post(ruta, json={"prueba": recomendada}))
    innecesaria = ok(cliente.post(ruta, json={"prueba": "mv_fisherz", "max_k": 2}))

    assert coherente["advertencias"] == [] and coherente["prueba"] == recomendada
    assert innecesaria["advertencias"][0]["codigo"] == "SIN_FALTANTES"
    assert innecesaria["advertencias"][0]["nivel"] == "info" and innecesaria["max_k"] == 2
    invalida = cliente.post(ruta, json={"prueba": "gsq"})
    assert invalida.status_code == 422 and invalida.json()["error"]["detalles"][0]["campo"] == "prueba"


# --- Configuración de PC -----------------------------------------------------------------------------


def test_plantilla_y_validacion_sin_guardar(cliente, diabetes):
    proyecto = hasta_decisiones(cliente, diabetes)
    ok(cliente.post(f"/proyectos/{proyecto}/preparar"))
    plantilla = ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc/plantilla"))
    assert plantilla["niveles"][-1] == ["Outcome"] and plantilla["nombres_niveles"] is None
    validar = f"/proyectos/{proyecto}/configuracion-pc/validar"

    valida = ok(cliente.post(validar, json=plantilla))
    delante = ok(cliente.post(validar, json={**plantilla, "niveles": [["Outcome"], plantilla["niveles"][0]]}))
    rota = ok(cliente.post(validar, json={
        **plantilla, "niveles": [["Age", "Age"], [], ["Outcome"]], "nombres_niveles": ["A", "B"],
        "modificables": ["Outcome"],
    }))

    assert valida == {"valida": True, "errores": [], "advertencias": []}
    assert delante["valida"] is True and delante["advertencias"][0]["campo"] == "niveles"
    assert rota["valida"] is False
    assert [e["campo"] for e in rota["errores"]] == ["niveles", "niveles", "niveles.1", "nombres_niveles", "modificables"]
    # Validar no guarda nada.
    assert ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc"))["guardada"] is False


def test_guardar_configuracion_con_errores_por_campo_y_nombres_de_niveles(cliente, diabetes):
    proyecto = hasta_decisiones(cliente, diabetes)
    ok(cliente.post(f"/proyectos/{proyecto}/preparar"))
    plantilla = ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc/plantilla"))

    rechazada = cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json={
        **plantilla, "niveles": [["Age"], ["Outcome"]], "modificables": ["Outcome"],
    })
    nombres = ["Demografía", "Medidas", "Laboratorio", "Diagnóstico"]
    guardada = ok(cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json={
        **plantilla, "niveles": NIVELES_DIABETES, "nombres_niveles": nombres, "modificables": ["BMI", "Glucose"],
    }))

    assert rechazada.status_code == 422
    assert [d["campo"] for d in rechazada.json()["error"]["detalles"]] == ["niveles", "modificables"]
    assert guardada["configuracion"]["nombres_niveles"] == nombres
    pc = cliente.app.state.servicios.archivos.carpeta(proyecto) / "pc.json"
    assert json.loads(pc.read_text(encoding="utf-8"))["nombres_niveles"] == nombres
    assert set(CEROS) >= {"BMI", "Glucose"}

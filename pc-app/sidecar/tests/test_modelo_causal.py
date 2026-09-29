"""Modelo causal por la API: aplicabilidad, construcción (trabajo), consulta, casos,
contrafactuales e invalidación al cambiar la versión del resultado de PC."""

import sqlite3

import pytest

from conftest import DIABETES, NIVELES_DIABETES, crear_cliente, esperar_trabajo, hasta_configuracion, ok

from pcapp_servidor.almacenamiento.base_datos import VERSION_ESQUEMA, BaseDatos

NIVEL = {v: i for i, nivel in enumerate(NIVELES_DIABETES) for v in nivel}


@pytest.fixture(scope="module")
def analizado(tmp_path_factory):
    if not DIABETES.is_file():
        pytest.skip("Falta datasets_prueba/diabetes.csv.")
    with crear_cliente(tmp_path_factory.mktemp("modelo_causal") / "datos") as cliente:
        proyecto = hasta_configuracion(cliente, DIABETES, umbral_frecuencia=0.6)
        trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
        assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
        yield cliente, proyecto


def orientar_bloqueantes(cliente, proyecto) -> dict:
    """Orienta (respetando los niveles) las aristas sin orientar que bloquean; devuelve la aplicabilidad."""
    orientaciones = []
    for _ in range(5):
        aplicabilidad = ok(cliente.post(f"/proyectos/{proyecto}/modelo-causal/aplicabilidad"))
        pendientes = [p for p in aplicabilidad["problemas"] if p["codigo"] == "ARISTA_SIN_ORIENTAR"]
        if not pendientes:
            return aplicabilidad
        for problema in pendientes:
            origen, destino = problema["variables"]
            if NIVEL[origen] > NIVEL[destino]:
                origen, destino = destino, origen
            orientaciones.append({"origen": origen, "destino": destino, "justificacion": "Prueba"})
        umbral = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))["agregacion"]["umbral_frecuencia"]
        ok(cliente.post(
            f"/proyectos/{proyecto}/resultado/versiones",
            json={"umbral_frecuencia": umbral, "orientaciones_manuales": orientaciones},
        ), 201)
    raise AssertionError("No se pudieron orientar las aristas del subgrafo.")


@pytest.fixture(scope="module")
def construido(analizado):
    cliente, proyecto = analizado
    aplicabilidad = orientar_bloqueantes(cliente, proyecto)
    if aplicabilidad["bloqueado"]:
        pytest.skip(f"El análisis corto no permite el modelo: {aplicabilidad['problemas']}")
    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/modelo-causal", json={}), 202)
    assert trabajo["tipo"] == "modelo_causal"
    terminado = esperar_trabajo(cliente, trabajo["id"])
    assert terminado["estado"] == "completado", terminado
    return cliente, proyecto


def test_aplicabilidad_no_construye_nada(analizado):
    cliente, proyecto = analizado
    aplicabilidad = ok(cliente.post(f"/proyectos/{proyecto}/modelo-causal/aplicabilidad", json={}))
    assert aplicabilidad["subgrafo"]["objetivo"] == "Outcome"
    for problema in aplicabilidad["problemas"]:
        assert problema["severidad"] in ("bloqueante", "advertencia") and problema["accion"]
        if problema["codigo"] == "ARISTA_SIN_ORIENTAR":
            assert problema["destino"] == "resultados"
    assert "modelo_causal" not in ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]


def test_con_bloqueantes_responde_409_con_los_problemas(analizado):
    cliente, proyecto = analizado
    aplicabilidad = ok(cliente.post(f"/proyectos/{proyecto}/modelo-causal/aplicabilidad"))
    if not aplicabilidad["bloqueado"]:
        pytest.skip("Este análisis no tiene bloqueantes.")
    respuesta = cliente.post(f"/proyectos/{proyecto}/modelo-causal")
    assert respuesta.status_code == 409
    error = respuesta.json()["error"]
    assert error["codigo"] == "MODELO_NO_APLICABLE"
    assert any(p["severidad"] == "bloqueante" for p in error["detalles"]["problemas"])


def test_configuracion_no_valida(analizado):
    cliente, proyecto = analizado
    respuesta = cliente.post(f"/proyectos/{proyecto}/modelo-causal/aplicabilidad", json={"monotonia": {"BMI": "rara"}})
    assert respuesta.status_code == 422


def test_modelo_construido_y_consultable(construido):
    cliente, proyecto = construido
    assert ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]["modelo_causal"] == "vigente"
    vista = ok(cliente.get(f"/proyectos/{proyecto}/modelo-causal"))
    assert vista["vigente"] and vista["motivo_desactualizado"] is None
    modelo, evaluacion = vista["modelo"], vista["evaluacion"]
    assert modelo["objetivo"] == "Outcome" and modelo["subgrafo"]["variables"][-1] == "Outcome"
    assert modelo["resultado_pc"]["version"] >= 1 and len(modelo["huella"]) == 64
    objetivo = evaluacion["evaluacion_objetivo"]
    assert objetivo["umbral_decision"] is not None and objetivo["pesos_clase"] is False
    assert {"exactitud_balanceada", "auc", "brier"} <= set(objetivo["test"])
    assert evaluacion["referencia"]["comparacion"]
    padres = modelo["subgrafo"]["padres"]["Outcome"]
    mecanismo = next(m for m in evaluacion["mecanismos"] if m["variable"] == "Outcome")
    assert [e["padre"] for e in mecanismo["efectos"]] == padres
    assert all(e["histograma"] for e in mecanismo["efectos"])
    assert {c["nombre"] for c in vista["controles"]} == set(modelo["subgrafo"]["variables"][:-1])


def test_casos_y_contrafactual(construido):
    cliente, proyecto = construido
    casos = ok(cliente.get(f"/proyectos/{proyecto}/modelo-causal/casos"))
    assert casos["total"] > 0 and len(casos["filas"]) <= casos["por_pagina"]
    indice = casos["filas"][0]["indice"]
    vista = ok(cliente.get(f"/proyectos/{proyecto}/modelo-causal"))
    padre = vista["modelo"]["subgrafo"]["padres"]["Outcome"][0]

    sin_cambio = ok(cliente.post(
        f"/proyectos/{proyecto}/modelo-causal/contrafactual", json={"caso": {"indice_test": indice}},
    ))
    assert sin_cambio["cambio"] == 0.0 and sin_cambio["medida"] == "probabilidad"

    resultado = ok(cliente.post(
        f"/proyectos/{proyecto}/modelo-causal/contrafactual",
        json={"caso": {"indice_test": indice}, "intervenciones": [{"variable": padre, "tipo": "desplazar", "valor": 5}]},
    ))
    assert resultado["cambio"] != 0.0
    assert resultado["traza"][0] == {**resultado["traza"][0], "variable": padre, "causa": "intervencion"}

    fuera = vista["modelo"]["subgrafo"]["fuera"]
    if fuera and fuera[0] in NIVEL:
        sin_efecto = ok(cliente.post(
            f"/proyectos/{proyecto}/modelo-causal/contrafactual",
            json={"caso": {"indice_test": indice}, "intervenciones": [{"variable": fuera[0], "tipo": "desplazar", "valor": 1}]},
        ))
        assert sin_efecto["cambio"] == 0.0
        assert "SIN_EFECTO" in {a["codigo"] for a in sin_efecto["avisos"]}

    propio = ok(cliente.post(
        f"/proyectos/{proyecto}/modelo-causal/contrafactual",
        json={"caso": {"valores": {padre: casos["filas"][0]["valores"][padre]}}},
    ))
    assert propio["caso"]["origen"] == "usuario"


def test_contrafactual_no_valido(construido):
    cliente, proyecto = construido
    url = f"/proyectos/{proyecto}/modelo-causal/contrafactual"
    casos = ok(cliente.get(f"/proyectos/{proyecto}/modelo-causal/casos"))
    indice = casos["filas"][0]["indice"]
    objetivo = cliente.post(url, json={"caso": {"indice_test": indice}, "intervenciones": [
        {"variable": "Outcome", "tipo": "fijar", "valor": 1}]})
    assert objetivo.status_code == 422 and objetivo.json()["error"]["codigo"] == "CONTRAFACTUAL_NO_VALIDO"
    assert objetivo.json()["error"]["detalles"][0]["campo"] == "intervenciones.0.variable"
    assert cliente.post(url, json={"caso": {}}).status_code == 422
    assert cliente.post(url, json={"caso": {"indice_test": -99}}).status_code == 422
    texto = cliente.post(url, json={"caso": {"valores": {"Age": "mucho"}}})
    assert texto.status_code == 422 and texto.json()["error"]["detalles"][0]["campo"] == "caso.valores.Age"


def test_cambiar_la_version_del_resultado_lo_desactualiza(construido):
    cliente, proyecto = construido
    versiones = ok(cliente.get(f"/proyectos/{proyecto}/resultado/versiones"))
    otra = next(v["version"] for v in versiones["versiones"] if v["version"] != versiones["version_actual"])
    ok(cliente.put(f"/proyectos/{proyecto}/resultado/version-actual", json={"version": otra}))
    assert ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]["modelo_causal"] == "desactualizada"
    respuesta = cliente.get(f"/proyectos/{proyecto}/modelo-causal")
    assert respuesta.status_code == 409 and respuesta.json()["error"]["codigo"] == "ETAPA_REQUERIDA"


def test_migracion_del_esquema_conserva_los_trabajos(tmp_path):
    ruta = tmp_path / "app.db"
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE proyectos (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, archivo_original TEXT NOT NULL,
            archivo TEXT NOT NULL, hoja TEXT, sha256 TEXT NOT NULL, objetivo TEXT, etapa_actual TEXT,
            creado_en TEXT NOT NULL, actualizado_en TEXT NOT NULL);
        CREATE TABLE etapas (proyecto_id TEXT NOT NULL, etapa TEXT NOT NULL, estado TEXT NOT NULL,
            actualizada_en TEXT NOT NULL, PRIMARY KEY (proyecto_id, etapa));
        CREATE TABLE trabajos (id TEXT PRIMARY KEY, proyecto_id TEXT NOT NULL REFERENCES proyectos(id),
            tipo TEXT NOT NULL CHECK (tipo IN ('recomendacion', 'pc')), estado TEXT NOT NULL,
            completadas INTEGER NOT NULL DEFAULT 0, total INTEGER, fallidas INTEGER NOT NULL DEFAULT 0,
            segundos REAL NOT NULL DEFAULT 0, mensaje TEXT, parametros TEXT NOT NULL DEFAULT '{}',
            inicio TEXT, fin TEXT, error TEXT, actualizado_en TEXT NOT NULL);
        INSERT INTO proyectos VALUES ('p', 'n', 'a', 'a', NULL, 's', NULL, NULL, 't', 't');
        INSERT INTO trabajos (id, proyecto_id, tipo, estado, actualizado_en) VALUES ('t1', 'p', 'pc', 'completado', 't');
        PRAGMA user_version = 1;
    """)
    con.close()

    base = BaseDatos(ruta)

    with base.conexion() as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] == VERSION_ESQUEMA
        assert conexion.execute("SELECT tipo FROM trabajos WHERE id = 't1'").fetchone()[0] == "pc"
        conexion.execute(
            "INSERT INTO trabajos (id, proyecto_id, tipo, estado, actualizado_en) "
            "VALUES ('t2', 'p', 'modelo_causal', 'en_curso', 't')"
        )

"""Prescripción por la API: configuración, condiciones, candidatas en Resultados, calibración de μ,
caso, lotes (test y CSV nuevo), evaluación, exportación e invalidación."""

import sqlite3

import pandas as pd
import pytest

from conftest import DIABETES, crear_cliente, esperar_trabajo, hasta_configuracion, ok
from test_modelo_causal import orientar_bloqueantes

from pcapp_servidor.almacenamiento.base_datos import BaseDatos


@pytest.fixture(scope="module")
def con_modelo(tmp_path_factory):
    if not DIABETES.is_file():
        pytest.skip("Falta datasets_prueba/diabetes.csv.")
    with crear_cliente(tmp_path_factory.mktemp("prescripcion") / "datos") as cliente:
        proyecto = hasta_configuracion(cliente, DIABETES, umbral_frecuencia=0.6)
        assert esperar_trabajo(cliente, ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)["id"])["estado"] == "completado"
        if orientar_bloqueantes(cliente, proyecto)["bloqueado"]:
            pytest.skip("El análisis corto no permite el modelo causal.")
        trabajo = ok(cliente.post(f"/proyectos/{proyecto}/modelo-causal", json={}), 202)
        assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
        yield cliente, proyecto


def url(proyecto, ruta=""):
    return f"/proyectos/{proyecto}/prescripcion{ruta}"


def confirmada(vista, **cambios):
    configuracion = vista["configuracion"]
    for variable in vista["prescriptivas"]:
        configuracion["supuestos"][variable] = {
            "modificable_por_decision": True, "medida_antes_del_resultado": True, "no_define_el_objetivo": True,
            "confirmado_en": "2026-09-29T10:00:00",
        }
    configuracion.update(cambios)
    return configuracion


@pytest.fixture(scope="module")
def guardada(con_modelo):
    cliente, proyecto = con_modelo
    vista = ok(cliente.get(url(proyecto, "/configuracion")))
    if not vista["prescriptivas"]:
        pytest.skip("El grafo de este análisis no deja variables prescriptivas.")
    configuracion = confirmada(vista, mu=0.01, objetivo={"direccion": "bajar", "valor": 0.85}, rejilla_mu=[0.01, 0.1])
    ok(cliente.put(url(proyecto, "/configuracion"), json=configuracion))
    return cliente, proyecto


def test_configuracion_sugerida_y_condiciones(con_modelo):
    cliente, proyecto = con_modelo
    vista = ok(cliente.get(url(proyecto, "/configuracion")))
    assert vista["guardada"] is False
    assert vista["configuracion"]["modificables"] == vista["modificables_pc"] == ["BMI", "Glucose"]
    assert set(vista["prescriptivas"]) <= {"BMI", "Glucose"} and vista["aviso"].startswith("Recomendaciones basadas")
    condiciones = ok(cliente.post(url(proyecto, "/condiciones")))
    codigos = {p["codigo"] for p in condiciones["problemas"]}
    assert condiciones["bloqueado"] and ("SUPUESTOS_SIN_CONFIRMAR" in codigos or "SIN_PRESCRIPTIVAS" in codigos)


def test_sin_prescriptivas_bloquea_con_el_mensaje(con_modelo):
    cliente, proyecto = con_modelo
    vista = ok(cliente.get(url(proyecto, "/configuracion")))
    configuracion = {**vista["configuracion"], "modificables": []}
    condiciones = ok(cliente.post(url(proyecto, "/condiciones"), json=configuracion))
    problema = next(p for p in condiciones["problemas"] if p["codigo"] == "SIN_PRESCRIPTIVAS")
    assert problema["mensaje"].startswith("Con estos datos no hay variables prescriptivas")
    assert problema["destino"] == "prescripcion"


def test_validar_no_guarda_y_devuelve_errores_por_campo(con_modelo):
    cliente, proyecto = con_modelo
    vista = ok(cliente.get(url(proyecto, "/configuracion")))
    configuracion = vista["configuracion"]
    variable = vista["prescriptivas"][0] if vista["prescriptivas"] else None
    if variable is None:
        pytest.skip("Sin prescriptivas.")
    configuracion["acciones"][variable]["costo"] = -1
    validacion = ok(cliente.post(url(proyecto, "/configuracion/validar"), json=configuracion))
    assert not validacion["valida"] and validacion["errores"][0]["campo"] == f"acciones.{variable}.costo"
    respuesta = cliente.put(url(proyecto, "/configuracion"), json=configuracion)
    assert respuesta.status_code == 422
    assert "prescripcion" not in ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]


def test_guardar_caso_y_candidatas_en_resultados(guardada):
    cliente, proyecto = guardada
    assert ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]["prescripcion"] == "vigente"
    resultado = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))
    assert resultado["origen_candidatas"] == "prescripcion" and "prescripción" in resultado["nota_candidatas"]
    casos = ok(cliente.get(f"/proyectos/{proyecto}/modelo-causal/casos"))
    r = ok(cliente.post(url(proyecto, "/caso"), json={"caso": {"indice_test": casos["filas"][0]["indice"]}}))
    assert r["medida"] == "probabilidad" and r["explicacion"]
    assert {a["variable"] for a in r["acciones"]} <= {"BMI", "Glucose"}
    assert r["mu"] == 0.01


def test_mu_automatico_sin_calibrar_y_calibracion(guardada):
    cliente, proyecto = guardada
    vista = ok(cliente.get(url(proyecto, "/configuracion")))
    ok(cliente.put(url(proyecto, "/configuracion"), json={**vista["configuracion"], "mu": "automatico"}))
    casos = ok(cliente.get(f"/proyectos/{proyecto}/modelo-causal/casos"))
    respuesta = cliente.post(url(proyecto, "/caso"), json={"caso": {"indice_test": casos["filas"][0]["indice"]}})
    assert respuesta.status_code == 409 and respuesta.json()["error"]["codigo"] == "MU_SIN_CALIBRAR"
    trabajo = ok(cliente.post(url(proyecto, "/calibrar-mu")), 202)
    assert trabajo["tipo"] == "calibracion_mu"
    assert esperar_trabajo(cliente, trabajo["id"], 600)["estado"] == "completado"
    vista = ok(cliente.get(url(proyecto, "/configuracion")))
    assert vista["calibracion"]["mu"] in (0.01, 0.1) and vista["mu_efectivo"] == vista["calibracion"]["mu"]
    assert "un solo arranque" in vista["calibracion"]["nota"]
    ok(cliente.post(url(proyecto, "/caso"), json={"caso": {"indice_test": casos["filas"][0]["indice"]}}))


def test_lotes_de_test_y_de_csv_nuevo(guardada, tmp_path):
    cliente, proyecto = guardada
    trabajo = ok(cliente.post(url(proyecto, "/lote"), json={"origen": "test"}), 202)
    assert esperar_trabajo(cliente, trabajo["id"], 600)["estado"] == "completado"
    lotes = ok(cliente.get(url(proyecto, "/lotes")))
    numero = lotes[-1]["numero"]
    pagina = ok(cliente.get(url(proyecto, f"/lotes/{numero}")))
    assert pagina["total"] == lotes[-1]["casos"]
    if pagina["total"] == 0:
        pytest.skip("Ningún caso de test incumple el objetivo exigente.")
    filtrada = ok(cliente.get(url(proyecto, f"/lotes/{numero}?filtro=no_alcanzable")))
    assert all(not r["alcanzado"] for r in filtrada["filas"])
    assert cliente.get(url(proyecto, f"/lotes/{numero}?filtro=raro")).status_code == 422

    # CSV nuevo con las columnas originales de esas mismas filas: mismo resultado.
    indices = [r["caso"]["indice"] for r in pagina["filas"][:5]]
    originales = pd.read_csv(DIABETES).loc[indices].drop(columns="Outcome")
    ruta = tmp_path / "nuevos.csv"
    originales.to_csv(ruta, index=False)
    trabajo = ok(cliente.post(url(proyecto, "/lote"), json={"origen": "csv", "ruta_csv": str(ruta)}), 202)
    assert esperar_trabajo(cliente, trabajo["id"], 600)["estado"] == "completado"
    lote_csv = ok(cliente.get(url(proyecto, "/lotes")))[-1]
    assert lote_csv["origen"] == "csv" and lote_csv["filas_con_problemas"] == []
    filas_csv = ok(cliente.get(url(proyecto, f"/lotes/{lote_csv['numero']}")))["filas"]
    for de_test, nuevo in zip(pagina["filas"][:5], filas_csv):
        assert nuevo["antes"] == de_test["antes"]
        assert nuevo["alcanzado"] == de_test["alcanzado"]
    faltan = cliente.post(url(proyecto, "/lote"), json={"origen": "csv", "ruta_csv": str(tmp_path / "no.csv")})
    assert faltan.status_code == 422


def test_evaluacion_y_exportacion(guardada, tmp_path):
    cliente, proyecto = guardada
    trabajo = ok(cliente.post(url(proyecto, "/evaluacion")), 202)
    assert esperar_trabajo(cliente, trabajo["id"], 900)["estado"] == "completado"
    numero = ok(cliente.get(url(proyecto, "/evaluaciones")))[-1]["numero"]
    informe = ok(cliente.get(url(proyecto, f"/evaluaciones/{numero}")))["evaluacion"]
    assert "INTERNA" in informe["texto"]
    assert [c["optimizador"] for c in informe["comparacion_optimizadores"]] == ["gradiente_proximal", "genetico"]
    assert [s["fraccion_rango"] for s in informe["sensibilidad_cambio_maximo"]] == [0.1, 0.25, 0.4]
    lotes = ok(cliente.get(url(proyecto, "/lotes")))
    exportado = ok(cliente.post(url(proyecto, "/exportar"), json={
        "carpeta_destino": str(tmp_path), "evaluacion": numero, "lote": lotes[0]["numero"] if lotes else None,
    }))
    html = (tmp_path / exportado["carpeta"].split("\\")[-1].split("/")[-1] / "informe_prescripcion.html").read_text("utf-8")
    assert "Recomendaciones basadas en datos observacionales" in html and "Declaración de supuestos" in html


def test_reconstruir_el_modelo_desactualiza_la_prescripcion(guardada):
    cliente, proyecto = guardada
    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/modelo-causal", json={}), 202)
    assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
    assert ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"]["prescripcion"] == "desactualizada"
    respuesta = cliente.post(url(proyecto, "/caso"), json={"caso": {"indice_test": 0}})
    assert respuesta.status_code == 409


def test_migracion_del_esquema_a_la_version_3(tmp_path):
    ruta = tmp_path / "app.db"
    BaseDatos(ruta)
    with sqlite3.connect(ruta) as con:
        con.execute("INSERT INTO proyectos VALUES ('p', 'n', 'a', 'a', NULL, 's', NULL, NULL, 't', 't')")
        for tipo in ("calibracion_mu", "lote_prescripcion", "evaluacion_prescripcion"):
            con.execute(
                "INSERT INTO trabajos (id, proyecto_id, tipo, estado, actualizado_en) VALUES (?, 'p', ?, 'completado', 't')",
                (tipo, tipo),
            )

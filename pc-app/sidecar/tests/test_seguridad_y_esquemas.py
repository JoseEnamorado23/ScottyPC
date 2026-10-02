"""Token, CORS, rutas seguras, errores internos y coherencia de los esquemas."""

import dataclasses

import pytest
from fastapi.testclient import TestClient

from conftest import TOKEN, crear_cliente, esperar_trabajo, hasta_configuracion, ok

from pcapp_nucleo.causal import aplicabilidad as causal_aplicabilidad
from pcapp_nucleo.causal import contrafactuales as causal_contrafactual
from pcapp_nucleo.causal import mecanismos as causal_mecanismos
from pcapp_nucleo.prescripcion import calibracion as p_calibracion
from pcapp_nucleo.prescripcion import configuracion as p_configuracion
from pcapp_nucleo.prescripcion import lotes as p_lotes
from pcapp_nucleo.prescripcion import prescriptor as p_prescriptor
from pcapp_nucleo import (
    caracterizacion,
    informe,
    modelos,
    pc_bootstrap,
    pc_config,
    preparacion,
    reagregacion,
    seleccion_prueba,
)
from pcapp_servidor import esquemas


# --- Token y CORS -----------------------------------------------------------------------------


def test_peticiones_sin_token_o_con_token_incorrecto(cliente):
    sin_token = TestClient(cliente.app)

    for respuesta in (sin_token.get("/salud"), sin_token.get("/proyectos", headers={"X-Token": "otro"}),
                      sin_token.get("/openapi.json")):
        assert respuesta.status_code == 401
        assert respuesta.json() == {"error": {
            "codigo": "NO_AUTORIZADO", "mensaje": "Falta el encabezado X-Token o no es válido.", "detalles": None,
        }}
    assert cliente.get("/salud").status_code == 200


def test_cors_solo_para_origenes_de_tauri_y_vite(cliente):
    anonimo = TestClient(cliente.app)
    preflight = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-Token"}

    permitido = anonimo.options("/salud", headers={"Origin": "http://localhost:5173", **preflight})
    tauri = anonimo.get("/salud", headers={"Origin": "http://tauri.localhost"})
    ajeno = anonimo.options("/salud", headers={"Origin": "http://sitio-malicioso.com", **preflight})

    assert permitido.status_code == 200
    assert permitido.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert tauri.status_code == 401 and tauri.headers["access-control-allow-origin"] == "http://tauri.localhost"
    assert "access-control-allow-origin" not in ajeno.headers


def test_modo_desarrollo_sin_token(tmp_path):
    with crear_cliente(tmp_path / "datos", token=None) as cliente:
        assert TestClient(cliente.app).get("/salud").status_code == 200


# --- Rutas seguras --------------------------------------------------------------------------------


# Un ".." literal lo normaliza el propio cliente HTTP antes de enviarlo; los intentos
# reales llegan codificados (%2F, %5C) y son los que el servidor debe rechazar.
@pytest.mark.parametrize("nombre", ["..%2F..%2Fapp.db", "..%5C..%5Capp.db", "receta.json", "punto_control.json"])
def test_archivos_solo_de_la_carpeta_de_resultados(cliente, diabetes, nombre):
    proyecto = hasta_configuracion(cliente, diabetes, corridas_bootstrap=3)
    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
    esperar_trabajo(cliente, trabajo["id"])

    respuesta = cliente.get(f"/proyectos/{proyecto}/archivos/{nombre}")

    assert respuesta.status_code == 404
    assert "error" in respuesta.json()


@pytest.mark.parametrize("identificador", ["..%2F..%2Fapp.db", "..", "abc", "0" * 31 + "Z"])
def test_identificadores_de_proyecto_no_validos(cliente, identificador):
    assert cliente.get(f"/proyectos/{identificador}").status_code == 404
    assert cliente.delete(f"/proyectos/{identificador}").status_code in (404, 405)


def test_errores_internos_no_llegan_al_cliente(cliente, tmp_path, monkeypatch):
    def fallar(*_):
        raise RuntimeError("detalle técnico secreto")

    monkeypatch.setattr(cliente.app.state.servicios, "listar", fallar)
    cliente_sin_excepciones = TestClient(cliente.app, headers={"X-Token": TOKEN}, raise_server_exceptions=False)

    respuesta = cliente_sin_excepciones.get("/proyectos")

    assert respuesta.status_code == 500
    error = respuesta.json()["error"]
    assert error["codigo"] == "ERROR_INTERNO" and "secreto" not in respuesta.text
    registro = (tmp_path / "datos" / "logs" / "servidor.log")
    if registro.exists():  # el registro solo se configura al arrancar el proceso real
        assert error["detalles"]["referencia"] in registro.read_text(encoding="utf-8")


def test_error_interno_desde_origen_permitido_lleva_cors(cliente, tmp_path, monkeypatch):
    def fallar(*_):
        raise RuntimeError("detalle técnico secreto")

    monkeypatch.setattr(cliente.app.state.servicios, "listar", fallar)
    navegador = TestClient(cliente.app, raise_server_exceptions=False)

    respuesta = navegador.get("/proyectos", headers={"X-Token": TOKEN, "Origin": "http://tauri.localhost"})

    assert respuesta.status_code == 500
    assert respuesta.headers["access-control-allow-origin"] == "http://tauri.localhost"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"error"}
    assert cuerpo["error"]["codigo"] == "ERROR_INTERNO"
    referencia = cuerpo["error"]["detalles"]["referencia"]
    assert len(referencia) == 12 and referencia in cuerpo["error"]["mensaje"]
    assert "secreto" not in respuesta.text


# --- Esquemas ---------------------------------------------------------------------------------------

PARES = [
    (esquemas.ProblemaValidacion, modelos.ProblemaValidacion),
    (esquemas.ResultadoValidacion, modelos.ResultadoValidacion),
    (esquemas.Hallazgo, modelos.Hallazgo),
    (esquemas.PerfilColumna, modelos.PerfilColumna),
    (esquemas.TratamientoColumna, preparacion.TratamientoColumna),
    (esquemas.Codificacion, preparacion.Codificacion),
    (esquemas.ConversionUnidades, preparacion.ConversionUnidades),
    (esquemas.ConfiguracionSeparacion, preparacion.ConfiguracionSeparacion),
    (esquemas.AccionHallazgo, preparacion.AccionHallazgo),
    (esquemas.DecisionesUsuario, preparacion.DecisionesUsuario),
    (esquemas.MetadatosColumna, preparacion.MetadatosColumna),
    (esquemas.LimiteColumnas, preparacion.LimiteColumnas),
    (esquemas.DiagnosticoVariable, seleccion_prueba.DiagnosticoVariable),
    (esquemas.AlternativaPrueba, seleccion_prueba.AlternativaPrueba),
    (esquemas.RecomendacionPrueba, seleccion_prueba.RecomendacionPrueba),
    (esquemas.AdvertenciaEleccion, seleccion_prueba.AdvertenciaEleccion),
    (esquemas.EvaluacionEleccion, seleccion_prueba.EvaluacionEleccion),
    (esquemas.OrientacionManual, pc_config.OrientacionManual),
    (esquemas.ConfiguracionPC, pc_config.ConfiguracionPC),
    (esquemas.ProblemaConfiguracion, pc_config.ProblemaConfiguracion),
    (esquemas.CorridaFallida, pc_bootstrap.CorridaFallida),
    (esquemas.EjecucionBootstrap, pc_bootstrap.EjecucionBootstrap),
    (esquemas.AristaAgregada, pc_bootstrap.AristaAgregada),
    (esquemas.CaracterizacionVariable, caracterizacion.CaracterizacionVariable),
    (esquemas.Caracterizacion, caracterizacion.Caracterizacion),
    (esquemas.ParVariables, reagregacion.ParVariables),
    (esquemas.AvisoResultado, reagregacion.AvisoResultado),
    (esquemas.LineaResumen, informe.LineaResumen),
    (esquemas.ProblemaAplicabilidad, causal_aplicabilidad.ProblemaAplicabilidad),
    (esquemas.AvisoContrafactual, causal_contrafactual.AvisoContrafactual),
    (esquemas.ValorContrafactual, causal_contrafactual.ValorContrafactual),
    (esquemas.ContribucionPadre, causal_contrafactual.ContribucionPadre),
    (esquemas.PasoTraza, causal_contrafactual.PasoTraza),
    (esquemas.ResultadoContrafactual, causal_contrafactual.ResultadoContrafactual),
    (esquemas.ObjetivoDeseado, p_configuracion.ObjetivoDeseado),
    (esquemas.ConfiguracionAccion, p_configuracion.ConfiguracionAccion),
    (esquemas.Supuestos, p_configuracion.Supuestos),
    (esquemas.ConfiguracionPrescripcion, p_configuracion.ConfiguracionPrescripcion),
    (esquemas.PuntoRejilla, p_calibracion.PuntoRejilla),
    (esquemas.AccionPrescrita, p_prescriptor.AccionPrescrita),
    (esquemas.RestriccionActiva, p_prescriptor.RestriccionActiva),
    (esquemas.ResultadoPrescripcion, p_prescriptor.ResultadoPrescripcion),
    (esquemas.ComparacionOptimizadores, p_lotes.ComparacionOptimizadores),
    (esquemas.EvaluacionPrescriptor, p_lotes.EvaluacionPrescriptor),
]


@pytest.mark.parametrize("modelo, clase", PARES, ids=lambda x: x.__name__)
def test_modelos_pydantic_reflejan_las_dataclasses(modelo, clase):
    assert list(modelo.model_fields) == [f.name for f in dataclasses.fields(clase)]


def test_openapi_completo(cliente):
    esquema = ok(cliente.get("/openapi.json"))

    rutas = set(esquema["paths"])
    assert {
        "/salud", "/apagar", "/proyectos", "/proyectos/{proyecto_id}", "/proyectos/{proyecto_id}/revision",
        "/proyectos/{proyecto_id}/decisiones/plantilla", "/proyectos/{proyecto_id}/decisiones",
        "/proyectos/{proyecto_id}/decisiones/previsualizar", "/proyectos/{proyecto_id}/datos",
        "/proyectos/{proyecto_id}/distribucion",
        "/proyectos/{proyecto_id}/preparacion", "/proyectos/{proyecto_id}/recomendacion/evaluar",
        "/proyectos/{proyecto_id}/configuracion-pc/plantilla", "/proyectos/{proyecto_id}/configuracion-pc/validar",
        "/proyectos/{proyecto_id}/preparar", "/proyectos/{proyecto_id}/recomendacion",
        "/proyectos/{proyecto_id}/configuracion-pc", "/proyectos/{proyecto_id}/pc",
        "/proyectos/{proyecto_id}/resultado", "/proyectos/{proyecto_id}/archivos/{nombre}",
        "/proyectos/{proyecto_id}/exportar", "/proyectos/{proyecto_id}/resultado/versiones",
        "/proyectos/{proyecto_id}/resultado/reagregar", "/proyectos/{proyecto_id}/resultado/version-actual",
        "/proyectos/{proyecto_id}/resultado/procedencia", "/trabajos/{trabajo_id}", "/trabajos/{trabajo_id}/cancelar",
        "/trabajos/{trabajo_id}/reanudar", "/proyectos/{proyecto_id}/modelo-causal",
        "/proyectos/{proyecto_id}/modelo-causal/aplicabilidad", "/proyectos/{proyecto_id}/modelo-causal/casos",
        "/proyectos/{proyecto_id}/modelo-causal/contrafactual",
        "/proyectos/{proyecto_id}/prescripcion/configuracion", "/proyectos/{proyecto_id}/prescripcion/configuracion/validar",
        "/proyectos/{proyecto_id}/prescripcion/condiciones", "/proyectos/{proyecto_id}/prescripcion/calibrar-mu",
        "/proyectos/{proyecto_id}/prescripcion/caso", "/proyectos/{proyecto_id}/prescripcion/lote",
        "/proyectos/{proyecto_id}/prescripcion/lotes/{numero}", "/proyectos/{proyecto_id}/prescripcion/evaluacion",
        "/proyectos/{proyecto_id}/prescripcion/evaluaciones/{numero}", "/proyectos/{proyecto_id}/prescripcion/exportar",
    } <= rutas
    componentes = set(esquema["components"]["schemas"])
    assert {"Revision", "DecisionesUsuario", "ResumenPreparacion", "RecomendacionPrueba", "ConfiguracionPC",
            "Trabajo", "ResultadoPC", "RespuestaError", "ProyectoCreado", "DatosHoja", "Distribucion"} <= componentes
    respuestas = esquema["paths"]["/proyectos/{proyecto_id}/preparar"]["post"]["responses"]
    assert {"200", "404", "409", "422"} <= set(respuestas)

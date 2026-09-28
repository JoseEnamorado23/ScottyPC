"""Invalidación de etapas, requisitos y trabajos en segundo plano."""

import time

from conftest import crear_cliente, esperar_trabajo, hasta_configuracion, hasta_decisiones, ok

from pcapp_servidor.almacenamiento.base_datos import ahora
from pcapp_servidor.almacenamiento.repositorio import Trabajo


def test_requisitos_de_cada_etapa(cliente, diabetes):
    proyecto = ok(cliente.post("/proyectos", json={"ruta_archivo": str(diabetes)}), 201)["id"]

    for metodo, ruta, etapa in [
        ("get", "decisiones/plantilla", "revision"),
        ("post", "preparar", "decisiones"),
        ("get", "configuracion-pc", "preparacion"),
        ("post", "pc", "configuracion_pc"),
        ("get", "resultado", "analisis"),
    ]:
        respuesta = getattr(cliente, metodo)(f"/proyectos/{proyecto}/{ruta}")
        assert respuesta.status_code == 409, ruta
        error = respuesta.json()["error"]
        assert error["codigo"] == "ETAPA_REQUERIDA" and error["detalles"]["requiere"] == etapa
        assert "primero se necesita" in error["mensaje"] or "No hay" in error["mensaje"]


def test_modificar_decisiones_invalida_las_etapas_posteriores(cliente, diabetes, tmp_path):
    proyecto = hasta_configuracion(cliente, diabetes)
    carpeta = tmp_path / "datos" / "proyectos" / proyecto
    assert (carpeta / "receta.json").exists() and (carpeta / "pc.json").exists()

    decisiones = ok(cliente.get(f"/proyectos/{proyecto}/decisiones"))
    decisiones["eliminar_duplicados"] = not decisiones["eliminar_duplicados"]
    ok(cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones))

    estado = ok(cliente.get(f"/proyectos/{proyecto}"))
    assert estado["etapas"] == {
        "revision": "vigente", "decisiones": "vigente",
        "preparacion": "desactualizada", "configuracion_pc": "desactualizada",
    }
    assert estado["etapa_actual"] == "decisiones"
    for nombre in ("receta.json", "train.csv", "test.csv", "pc.json"):
        assert not (carpeta / nombre).exists()
    archivados = [p.name for p in (carpeta / "anteriores").rglob("*") if p.is_file()]
    assert {"receta.json", "train.csv", "test.csv", "pc.json", "decisiones.json"} <= set(archivados)
    assert cliente.post(f"/proyectos/{proyecto}/pc").status_code == 409
    assert cliente.get(f"/proyectos/{proyecto}/configuracion-pc").status_code == 409

    ok(cliente.post(f"/proyectos/{proyecto}/preparar"))
    assert ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc"))["guardada"] is False


def test_rehacer_la_revision_invalida_todo(cliente, diabetes):
    proyecto = hasta_decisiones(cliente, diabetes)

    ok(cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "Outcome"}))

    assert ok(cliente.get(f"/proyectos/{proyecto}"))["etapas"] == {
        "revision": "vigente", "decisiones": "desactualizada"
    }
    assert cliente.post(f"/proyectos/{proyecto}/preparar").status_code == 409


def test_progreso_cancelacion_y_reanudacion(cliente, diabetes):
    proyecto = hasta_configuracion(cliente, diabetes, corridas_bootstrap=150, modo_ejecucion="secuencial")
    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)

    intermedio = None
    for _ in range(600):
        estado = ok(cliente.get(f"/trabajos/{trabajo['id']}"))
        if 5 <= estado["completadas"] < 150:
            intermedio = estado
            break
        time.sleep(0.05)
    assert intermedio is not None and intermedio["estado"] == "en_curso"
    assert intermedio["total"] == 150 and intermedio["segundos_restantes_estimados"] is not None
    assert intermedio["segundos_transcurridos"] > 0
    assert intermedio["detalles"] == {"modo": "secuencial", "procesos": 1}
    en_curso = ok(cliente.get(f"/proyectos/{proyecto}"))
    assert en_curso["trabajo_activo"] == trabajo["id"]
    assert en_curso["ultimo_trabajo"]["estado"] == "en_curso" and not en_curso["ultimo_trabajo"]["reanudable"]

    assert cliente.post(f"/proyectos/{proyecto}/recomendacion").status_code == 409  # un trabajo a la vez
    decisiones = ok(cliente.get(f"/proyectos/{proyecto}/decisiones"))
    assert cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones).status_code == 409
    assert cliente.delete(f"/proyectos/{proyecto}").status_code == 409

    ok(cliente.post(f"/trabajos/{trabajo['id']}/cancelar"))
    cancelado = esperar_trabajo(cliente, trabajo["id"])
    assert cancelado["estado"] == "cancelado" and cancelado["completadas"] < 150
    assert cliente.post(f"/trabajos/{trabajo['id']}/cancelar").status_code == 409
    assert cliente.get(f"/proyectos/{proyecto}/resultado").status_code == 409
    assert cancelado["detalles"] is None
    ultimo = ok(cliente.get(f"/proyectos/{proyecto}"))["ultimo_trabajo"]
    assert (ultimo["id"], ultimo["tipo"], ultimo["estado"], ultimo["reanudable"]) == (trabajo["id"], "pc", "cancelado", True)

    ok(cliente.post(f"/trabajos/{trabajo['id']}/reanudar"), 202)
    final = esperar_trabajo(cliente, trabajo["id"])
    assert final["estado"] == "completado" and final["completadas"] == 150
    assert ok(cliente.get(f"/proyectos/{proyecto}/resultado"))["corridas"]["validas"] == 150


def test_trabajo_interrumpido_por_reinicio_se_reanuda(diabetes, tmp_path):
    datos = tmp_path / "datos"
    with crear_cliente(datos) as cliente:
        proyecto = hasta_configuracion(cliente, diabetes)
        servicios = cliente.app.state.servicios
        servicios.trabajos.repositorio.crear(Trabajo(
            id="a" * 32, proyecto_id=proyecto, tipo="pc", estado="en_curso", completadas=3, total=10,
            fallidas=0, segundos=1.0, mensaje=None, parametros={}, inicio=ahora(), fin=None, error=None,
            actualizado_en=ahora(),
        ))

    with crear_cliente(datos) as cliente:  # "reinicio" del servidor
        interrumpido = ok(cliente.get(f"/trabajos/{'a' * 32}"))
        assert interrumpido["estado"] == "interrumpido"
        [listado] = ok(cliente.get("/proyectos"))
        assert listado["ultimo_trabajo"]["estado"] == "interrumpido" and listado["ultimo_trabajo"]["reanudable"]
        ok(cliente.post(f"/trabajos/{'a' * 32}/reanudar"), 202)
        assert esperar_trabajo(cliente, "a" * 32)["estado"] == "completado"
        assert ok(cliente.get(f"/proyectos/{proyecto}/resultado"))["corridas"]["validas"] == 10


def test_grupo_de_procesos_reutilizado_con_el_mismo_resultado(cliente, diabetes):
    secuencial = hasta_configuracion(cliente, diabetes, corridas_bootstrap=6, modo_ejecucion="secuencial")
    paralelo = hasta_configuracion(cliente, diabetes, corridas_bootstrap=6, modo_ejecucion="paralelo", procesos=2)
    assert ok(cliente.get("/salud"))["grupo_procesos_creado"] is False

    resultados = {}
    for nombre, proyecto in (("secuencial", secuencial), ("paralelo", paralelo), ("paralelo_2", paralelo)):
        trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
        assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
        resultados[nombre] = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))

    assert ok(cliente.get("/salud"))["grupo_procesos_creado"] is True
    assert resultados["paralelo"]["ejecucion"]["modo_usado"] == "paralelo"
    assert resultados["paralelo"]["aristas"] == resultados["secuencial"]["aristas"]
    assert resultados["paralelo_2"]["aristas"] == resultados["secuencial"]["aristas"]


def test_tiempo_de_un_trabajo_sin_progreso_se_mide(cliente, diabetes):
    proyecto = hasta_configuracion(cliente, diabetes)

    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/recomendacion?estimar_tiempo=true"), 202)
    final = esperar_trabajo(cliente, trabajo["id"])

    assert final["estado"] == "completado"
    assert final["segundos_transcurridos"] > 0.5  # la estimación arranca procesos de PC

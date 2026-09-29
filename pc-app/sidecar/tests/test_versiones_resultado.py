"""Versiones del resultado: previsualizar un ajuste no escribe nada, guardarlo crea una versión
nueva sin tocar las anteriores, migración de resultados antiguos y exportación con informe."""

import hashlib
import json
from pathlib import Path

import pytest

from conftest import DIABETES, NIVELES_DIABETES, crear_cliente, esperar_trabajo, hasta_configuracion, ok

NIVEL = {v: i for i, nivel in enumerate(NIVELES_DIABETES) for v in nivel}


@pytest.fixture(scope="module")
def diabetes():
    if not DIABETES.is_file():
        pytest.skip("Falta datasets_prueba/diabetes.csv.")
    return DIABETES


@pytest.fixture(scope="module")
def analizado(tmp_path_factory, diabetes):
    """Cliente y proyecto de diabetes con el análisis terminado (compartido por el módulo)."""
    with crear_cliente(tmp_path_factory.mktemp("versiones") / "datos") as cliente:
        proyecto = hasta_configuracion(cliente, diabetes, umbral_frecuencia=0.6)
        trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
        assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
        yield cliente, proyecto, cliente.app.state.servicios.archivos.carpeta(proyecto)


def huellas(carpeta: Path) -> dict[str, str]:
    return {
        str(ruta.relative_to(carpeta)): hashlib.sha256(ruta.read_bytes()).hexdigest()
        for ruta in sorted(carpeta.rglob("*")) if ruta.is_file()
    }


def orientacion_valida(resultado: dict) -> dict:
    """Una orientación compatible con los niveles para una arista sin orientar."""
    arista = next((a for a in resultado["aristas"] if a["tipo"] == "sin_orientar"), None)
    if arista is None:
        pytest.skip("El análisis no dejó aristas sin orientar.")
    origen, destino = arista["origen"], arista["destino"]
    if NIVEL[origen] > NIVEL[destino]:
        origen, destino = destino, origen
    return {"origen": origen, "destino": destino, "justificacion": "Se mide antes"}


def test_version_original(analizado):
    cliente, proyecto, _ = analizado

    versiones = ok(cliente.get(f"/proyectos/{proyecto}/resultado/versiones"))

    primera = versiones["versiones"][0]
    assert (primera["version"], primera["base"], primera["migrada"], primera["etiqueta"]) == (1, None, False, "Original")
    assert versiones["umbral_original"] == primera["umbral_frecuencia"] == 0.6
    resultado = ok(cliente.get(f"/proyectos/{proyecto}/resultado?version=1"))
    assert (resultado["version"], resultado["etiqueta"]) == (1, "Original")
    assert "cuentas" not in resultado and "spearman" not in resultado
    assert [c["titulo"] for c in resultado["disposicion"]] == [f"Nivel {i + 1}" for i in range(4)]
    procedencia = ok(cliente.get(f"/proyectos/{proyecto}/resultado/procedencia"))
    assert procedencia["configuracion"]["umbral_frecuencia"] == 0.6
    assert procedencia["archivo"] == "diabetes.csv"  # el del usuario, no la copia del proyecto
    assert procedencia["decisiones"] and procedencia["separacion"][0] == {"concepto": "Tipo", "detalle": "estratificada"}


def test_previsualizar_no_modifica_los_archivos(analizado):
    cliente, proyecto, carpeta = analizado
    original = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))
    ok(cliente.get(f"/proyectos/{proyecto}/resultado/versiones"))  # la migración, si hubiera, ya pasó
    antes = huellas(carpeta)

    vista = ok(cliente.post(f"/proyectos/{proyecto}/resultado/reagregar", json={"umbral_frecuencia": 0.3}))
    rechazo = cliente.post(
        f"/proyectos/{proyecto}/resultado/reagregar",
        json={"umbral_frecuencia": 0.6, "orientaciones_manuales": [
            {"origen": "Outcome", "destino": "Glucose", "justificacion": "al revés"}]},
    )

    assert huellas(carpeta) == antes
    assert vista["version"] is None and vista["etiqueta"] == "Ajustada: umbral 0,3, original 0,6"
    assert vista["agregacion"]["umbral_frecuencia"] == 0.3
    assert vista["configuracion"] == original["configuracion"]
    assert len(vista["aristas"]) >= len(original["aristas"])
    assert rechazo.status_code == 422
    error = rechazo.json()["error"]
    assert error["codigo"] == "AJUSTE_NO_VALIDO"
    assert error["detalles"][0]["campo"] == "orientaciones_manuales.0"
    assert "contradice los niveles" in error["detalles"][0]["mensaje"]


def test_guardar_crea_una_version_sin_borrar_las_anteriores(analizado):
    cliente, proyecto, carpeta = analizado
    ok(cliente.put(f"/proyectos/{proyecto}/resultado/version-actual", json={"version": 1}))
    original = ok(cliente.get(f"/proyectos/{proyecto}/resultado?version=1"))
    pc_json = (carpeta / "pc.json").read_bytes()
    antes = huellas(carpeta / "pc")
    orientacion = orientacion_valida(original)
    previa = ok(cliente.get(f"/proyectos/{proyecto}/resultado/versiones"))["versiones"]

    versiones = ok(cliente.post(
        f"/proyectos/{proyecto}/resultado/versiones",
        json={"umbral_frecuencia": 0.5, "orientaciones_manuales": [orientacion], "version_base": 1},
    ), 201)

    nueva = versiones["versiones"][-1]
    numero = nueva["version"]
    assert numero == len(previa) + 1 and versiones["version_actual"] == numero
    assert (nueva["base"], nueva["umbral_frecuencia"], nueva["migrada"]) == (1, 0.5, False)
    assert nueva["orientaciones_manuales"] == [orientacion]
    assert nueva["etiqueta"].startswith("Ajustada: umbral 0,5, original 0,6")
    # Nada de lo anterior cambia: ni los archivos de las versiones previas ni pc.json.
    despues = huellas(carpeta / "pc")
    assert all(despues[k] == v for k, v in antes.items() if k != "versiones.json")
    assert {Path(k).parent for k in set(despues) - set(antes)} == {Path("versiones") / str(numero)}
    assert (carpeta / "pc.json").read_bytes() == pc_json
    assert ok(cliente.get(f"/proyectos/{proyecto}/resultado?version=1")) == original

    actual = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))
    assert actual["version"] == numero and actual["agregacion"]["orientaciones_manuales"] == [orientacion]
    manual = [a for a in actual["aristas"] if a["tipo"] == "manual"]
    assert [(a["origen"], a["destino"], a["justificacion"]) for a in manual] == [
        (orientacion["origen"], orientacion["destino"], "Se mide antes")
    ]
    imagen = cliente.get(f"/proyectos/{proyecto}/archivos/grafo.png?version={numero}")
    assert imagen.status_code == 200 and imagen.content != cliente.get(
        f"/proyectos/{proyecto}/archivos/grafo.png?version=1").content

    # Volver a la original y de nuevo a la ajustada: todo se conserva.
    ok(cliente.put(f"/proyectos/{proyecto}/resultado/version-actual", json={"version": 1}))
    assert ok(cliente.get(f"/proyectos/{proyecto}/resultado")) == original
    ok(cliente.put(f"/proyectos/{proyecto}/resultado/version-actual", json={"version": numero}))
    assert ok(cliente.get(f"/proyectos/{proyecto}/resultado")) == actual


def test_version_inexistente(analizado):
    cliente, proyecto, _ = analizado

    assert cliente.get(f"/proyectos/{proyecto}/resultado?version=99").status_code == 404
    respuesta = cliente.put(f"/proyectos/{proyecto}/resultado/version-actual", json={"version": 99})
    assert respuesta.status_code == 404 and respuesta.json()["error"]["codigo"] == "VERSION_NO_ENCONTRADA"


def test_exportar_la_version_vista_con_informe(analizado, tmp_path):
    cliente, proyecto, _ = analizado
    versiones = ok(cliente.get(f"/proyectos/{proyecto}/resultado/versiones"))
    if len(versiones["versiones"]) == 1:
        ok(cliente.post(f"/proyectos/{proyecto}/resultado/versiones", json={"umbral_frecuencia": 0.5}), 201)
    ok(cliente.put(f"/proyectos/{proyecto}/resultado/version-actual", json={"version": 1}))

    exportado = ok(cliente.post(
        f"/proyectos/{proyecto}/exportar", json={"carpeta_destino": str(tmp_path), "version": 2}
    ))

    carpeta = Path(exportado["carpeta"])
    assert exportado["version"] == 2 and "_v2_" in carpeta.name
    assert {p.name for p in carpeta.iterdir()} == set(exportado["archivos"]) >= {"informe.html", "grafo.png", "receta.json"}
    assert json.loads((carpeta / "resultado.json").read_text(encoding="utf-8"))["agregacion"]["umbral_frecuencia"] == 0.5
    informe = (carpeta / "informe.html").read_text(encoding="utf-8")
    assert "Historial de versiones" in informe and "2 (exportada)" in informe
    assert "data:image/png;base64," in informe and "https://" not in informe
    assert "Umbral original" in informe
    assert "diabetes.csv" in informe and "original.csv" not in informe


def test_migrar_un_resultado_de_la_fase_6(tmp_path, diabetes):
    """Un resultado sin cuentas ni versiones.json (fase 6) se migra al consultarlo y, con su
    umbral original, la reagregación lo reproduce."""
    with crear_cliente(tmp_path / "datos") as cliente:
        proyecto = hasta_configuracion(cliente, diabetes)
        trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
        assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
        carpeta = cliente.app.state.servicios.archivos.carpeta(proyecto) / "pc"
        ruta = carpeta / "resultado.json"
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        antiguo = {k: v for k, v in contenido.items() if k not in ("cuentas", "spearman", "agregacion")}
        ruta.write_text(json.dumps(antiguo), encoding="utf-8")
        (carpeta / "versiones.json").unlink()

        versiones = ok(cliente.get(f"/proyectos/{proyecto}/resultado/versiones"))
        migrado = json.loads(ruta.read_text(encoding="utf-8"))
        vista = ok(cliente.post(
            f"/proyectos/{proyecto}/resultado/reagregar",
            json={"umbral_frecuencia": contenido["configuracion"]["umbral_frecuencia"]},
        ))

    assert versiones["versiones"][0]["migrada"] is True
    assert migrado["cuentas"] == contenido["cuentas"]
    for clave in ("aristas", "caracterizacion", "ciclos", "advertencias"):
        assert vista[clave] == contenido[clave], clave

"""Flujo completo por la API y errores de cada etapa."""

import hashlib
from pathlib import Path

import pandas as pd

from conftest import esperar_trabajo, hasta_configuracion, hasta_decisiones, ok


def test_flujo_completo_diabetes(cliente, diabetes, tmp_path):
    proyecto = hasta_configuracion(cliente, diabetes)

    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/recomendacion?estimar_tiempo=false"), 202)
    assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
    assert ok(cliente.get(f"/proyectos/{proyecto}/recomendacion"))["prueba"] in ("fisherz", "chisq")
    # La recomendación invalida la configuración: se vuelve a guardar.
    configuracion = ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc"))
    assert configuracion["guardada"] is False
    configuracion = configuracion["configuracion"]
    configuracion.update({"niveles": [["Age", "Pregnancies", "DiabetesPedigreeFunction"],
                                      ["BMI", "SkinThickness", "BloodPressure"], ["Glucose", "Insulin"],
                                      ["Outcome"]], "corridas_bootstrap": 10, "procesos": 1})
    ok(cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json=configuracion))

    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
    final = esperar_trabajo(cliente, trabajo["id"])
    assert final["estado"] == "completado", final
    assert (final["completadas"], final["total"]) == (10, 10)

    resultado = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))
    assert resultado["corridas"]["validas"] == 10
    assert resultado["ejecucion"]["modo_usado"] == "secuencial"
    assert {v["variable"] for v in resultado["caracterizacion"]["variables"]} >= {"Glucose", "BMI"}

    imagen = cliente.get(f"/proyectos/{proyecto}/archivos/grafo.png")
    assert imagen.status_code == 200 and imagen.headers["content-type"] == "image/png"
    assert imagen.content.startswith(b"\x89PNG")
    mascara = cliente.get(f"/proyectos/{proyecto}/archivos/mascara.csv")
    assert mascara.headers["content-type"].startswith("text/csv")
    assert cliente.get(f"/proyectos/{proyecto}/archivos/resultado.json").headers["content-type"] == "application/json"

    destino = tmp_path / "exportados"
    destino.mkdir()
    exportado = ok(cliente.post(f"/proyectos/{proyecto}/exportar", json={"carpeta_destino": str(destino)}))
    carpeta = Path(exportado["carpeta"])
    assert carpeta.parent == destino
    assert {p.name for p in carpeta.iterdir()} == set(exportado["archivos"]) >= {"grafo.png", "receta.json"}

    detalle = ok(cliente.get(f"/proyectos/{proyecto}"))
    assert detalle["etapa_actual"] == "analisis"
    assert set(detalle["etapas"].values()) == {"vigente"}


def test_proyecto_excel_con_hojas(cliente, tmp_path):
    ruta = tmp_path / "libro.xlsx"
    with pd.ExcelWriter(ruta) as escritor:
        pd.DataFrame({"x": range(150), "y": [0, 1] * 75}).to_excel(escritor, sheet_name="datos", index=False)
        pd.DataFrame({"a": [1]}).to_excel(escritor, sheet_name="notas", index=False)

    proyecto = ok(cliente.post("/proyectos", json={"ruta_archivo": str(ruta), "nombre": "Libro"}), 201)

    assert proyecto["hojas"] == ["datos", "notas"] and proyecto["hoja_vista"] == "datos"
    assert proyecto["filas"] == 150 and len(proyecto["vista_previa"]) == 20
    respuesta = cliente.post(f"/proyectos/{proyecto['id']}/revision", json={"objetivo": "y", "hoja": "otra"})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["detalles"][0]["campo"] == "hoja"
    revision = ok(cliente.post(f"/proyectos/{proyecto['id']}/revision", json={"objetivo": "y", "hoja": "datos"}))
    assert revision["valido"] is True
    assert ok(cliente.get(f"/proyectos/{proyecto['id']}"))["hoja"] == "datos"


def test_errores_al_crear_proyecto(cliente, tmp_path):
    texto = tmp_path / "datos.txt"
    texto.write_text("a,b\n1,2\n", encoding="utf-8")

    inexistente = cliente.post("/proyectos", json={"ruta_archivo": str(tmp_path / "no.csv")})
    formato = cliente.post("/proyectos", json={"ruta_archivo": str(texto)})
    vacio = tmp_path / "vacio.csv"
    vacio.write_text("", encoding="utf-8")
    ilegible = cliente.post("/proyectos", json={"ruta_archivo": str(vacio)})

    assert inexistente.status_code == formato.status_code == ilegible.status_code == 422
    assert inexistente.json()["error"]["codigo"] == "ARCHIVO_NO_ENCONTRADO"
    assert formato.json()["error"]["codigo"] == "FORMATO_NO_SOPORTADO"
    assert ilegible.json()["error"]["codigo"] == "ARCHIVO_VACIO"
    assert ok(cliente.get("/proyectos")) == []
    assert list((tmp_path / "datos" / "proyectos").iterdir()) == []


def test_revision_de_dataset_no_valido(cliente, diabetes):
    proyecto = ok(cliente.post("/proyectos", json={"ruta_archivo": str(diabetes)}), 201)["id"]

    respuesta = cliente.post(f"/proyectos/{proyecto}/revision", json={"objetivo": "NoExiste"})

    assert respuesta.status_code == 422
    error = respuesta.json()["error"]
    assert error["codigo"] == "DATASET_NO_VALIDO"
    assert error["detalles"][0]["codigo"] == "OBJETIVO_INEXISTENTE"


def test_decisiones_con_errores_por_campo(cliente, diabetes):
    proyecto = hasta_decisiones(cliente, diabetes)
    decisiones = ok(cliente.get(f"/proyectos/{proyecto}/decisiones"))

    decisiones["faltantes"]["NoExiste"] = {"imputacion": "mediana"}
    decisiones["codificaciones"]["Age"] = {"tipo": "ordinal"}
    decisiones["columnas_excluidas"] = ["Outcome"]
    semanticos = cliente.put(f"/proyectos/{proyecto}/decisiones", json=decisiones)
    tipos = cliente.put(
        f"/proyectos/{proyecto}/decisiones",
        json={"faltantes": {"Glucose": {"imputacion": "media"}}, "desconocido": 1},
    )

    assert semanticos.status_code == tipos.status_code == 422
    campos = {d["campo"]: d["mensaje"] for d in semanticos.json()["error"]["detalles"]}
    assert set(campos) == {"faltantes.NoExiste", "codificaciones.Age.orden", "columnas_excluidas.0"}
    assert "no puede excluirse" in campos["columnas_excluidas.0"]
    campos = {d["campo"]: d["mensaje"] for d in tipos.json()["error"]["detalles"]}
    assert campos["faltantes.Glucose.imputacion"].startswith("Valor no permitido")
    assert campos["desconocido"] == "Campo desconocido."


def test_configuracion_pc_no_valida(cliente, diabetes):
    proyecto = hasta_configuracion(cliente, diabetes)
    configuracion = ok(cliente.get(f"/proyectos/{proyecto}/configuracion-pc"))["configuracion"]
    configuracion["niveles"] = [["Age"], ["Outcome"]]

    respuesta = cliente.put(f"/proyectos/{proyecto}/configuracion-pc", json=configuracion)

    assert respuesta.status_code == 422
    detalle = respuesta.json()["error"]["detalles"][0]
    assert detalle["campo"] == "niveles" and "faltan" in detalle["mensaje"]


def test_eliminar_proyecto_no_toca_el_original(cliente, diabetes, tmp_path):
    copia_usuario = tmp_path / "mis_datos.csv"
    copia_usuario.write_bytes(diabetes.read_bytes())
    huella = hashlib.sha256(copia_usuario.read_bytes()).hexdigest()
    proyecto = ok(cliente.post("/proyectos", json={"ruta_archivo": str(copia_usuario)}), 201)["id"]
    carpeta = tmp_path / "datos" / "proyectos" / proyecto
    assert carpeta.is_dir()

    assert cliente.delete(f"/proyectos/{proyecto}").status_code == 204

    assert not carpeta.exists()
    assert hashlib.sha256(copia_usuario.read_bytes()).hexdigest() == huella
    assert cliente.get(f"/proyectos/{proyecto}").status_code == 404

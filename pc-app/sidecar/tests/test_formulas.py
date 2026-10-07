"""Explorador de fórmulas por la API."""

from conftest import esperar_trabajo, hasta_configuracion, ok


def test_traza_de_seleccion_de_prueba(cliente, diabetes):
    proyecto = hasta_configuracion(cliente, diabetes)
    ruta = f"/proyectos/{proyecto}/formulas/seleccion-prueba"
    # Sin recomendación vigente.
    assert cliente.post(ruta).status_code == 409

    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/recomendacion?estimar_tiempo=false"), 202)
    assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
    recomendada = ok(cliente.get(f"/proyectos/{proyecto}/recomendacion"))["prueba"]

    traza = ok(cliente.post(ruta))
    assert traza["prueba"] == traza["prueba_original"] == recomendada and not traza["cambia"]
    assert sum(r["estado"] == "decide" for r in traza["reglas"]) == 1
    assert traza["variables"] and traza["formulas_prueba"]

    otra = ok(cliente.post(ruta, json={"umbrales": {"proporcion_maxima_categoricas": 0.0}, "k": 2}))
    assert otra["k"] == 2 and otra["prueba_original"] == recomendada
    assert ok(cliente.get(f"/proyectos/{proyecto}/recomendacion"))["prueba"] == recomendada

    error = cliente.post(ruta, json={"umbrales": {"spearman_debil": 7}})
    assert error.status_code == 422 and error.json()["error"]["codigo"] == "UMBRAL_INVALIDO"
    assert cliente.post(ruta, json={"umbrales": {"inventado": 1}}).status_code == 422


def test_traza_del_analisis_de_pc(cliente, diabetes):
    proyecto = hasta_configuracion(cliente, diabetes)
    ruta = f"/proyectos/{proyecto}/formulas/analisis-pc"
    assert cliente.post(ruta).status_code == 409  # sin análisis vigente

    trabajo = ok(cliente.post(f"/proyectos/{proyecto}/pc"), 202)
    assert esperar_trabajo(cliente, trabajo["id"])["estado"] == "completado"
    resultado = ok(cliente.get(f"/proyectos/{proyecto}/resultado"))

    traza = ok(cliente.post(ruta))
    assert traza["version"] == resultado["version"] and traza["cambios"] == []
    aceptadas = {frozenset((p["a"], p["b"])) for p in traza["pares"] if p["estado"] == "aceptada"}
    assert aceptadas == {frozenset((a["origen"], a["destino"])) for a in resultado["aristas"]}

    bajo = ok(cliente.post(ruta, json={"umbral": 0.1}))
    assert bajo["umbral"] == 0.1 and bajo["umbral_guardado"] == traza["umbral_guardado"]
    assert all(c["cambio"] == "nueva" for c in bajo["cambios"])
    # No se guardó nada: el resultado sigue igual.
    assert ok(cliente.get(f"/proyectos/{proyecto}/resultado"))["aristas"] == resultado["aristas"]

    assert cliente.post(ruta, json={"umbral": 3}).status_code == 422
    assert cliente.post(ruta, json={"version": 99}).status_code == 404

"""Esquemas del artefacto: manifest, esquema de entrada y controles."""

import copy
import json

import pytest

from pcapp_nucleo.artefacto.formato import (
    ARCHIVOS_CONTENIDO,
    ErrorFormatoArtefacto,
    controles_desde_diccionario,
    esquema_entrada_desde_diccionario,
    json_canonico,
    manifest_desde_diccionario,
    nombre_visible,
    sha256_bytes,
)

SHA = "a" * 64


def manifest_valido() -> dict:
    return {
        "formato": "scotty-artefacto",
        "version_formato": 1,
        "creado_en": "2026-10-20T10:30:00",
        "version_nucleo": "0.1.0",
        "versiones_librerias": {"pygam": "0.12.0", "scikit-learn": "1.9.1", "numpy": "2.5.3", "scipy": "1.16.3"},
        "proyecto": {"id": "abc", "nombre": "Factores", "archivo_original": "f.csv", "sha256_dataset": SHA},
        "objetivo": {
            "columna": "Clase", "tipo": "binario", "clase_positiva": ["Alta"], "clase_objetivo": 1,
            "medida": "probabilidad", "direccion": "subir", "deseado": 0.5, "umbral_decision": 0.39,
        },
        "prescripcion": {"mu": 0.003162, "mu_origen": "automatico", "optimizador": "gradiente_proximal"},
        "modelo": {"huella": SHA, "train_sha256": SHA, "version_resultado_pc": 2},
        "variables_prescriptivas": ["Asistencia"],
        "supuestos_confirmados": {"Asistencia": "2026-10-01T21:09:46"},
        "resumen_evaluacion": {
            "exactitud_balanceada_test": 0.7, "auc_test": 0.8, "brier_test": 0.2, "r2_test": None, "rmse_test": None,
            "tasa_exito_prescriptor": 0.9, "filas_evaluadas": 100,
        },
        "aviso": "Evaluación interna.",
        "advertencias": [{"codigo": "SIN_EVALUACION", "mensaje": "No hay evaluación."}],
        "archivos": {nombre: SHA for nombre in ARCHIVOS_CONTENIDO},
        "golden_sha256": SHA,
    }


def esquema_valido() -> dict:
    return {
        "version_formato": 1,
        "columnas": [
            {
                "nombre": "Daytime/evening attendance\t", "nombre_visible": "Daytime/evening attendance",
                "tipo": "binaria", "categorias": [0, 1], "minimo": None, "maximo": None, "rol": "prescriptiva",
                "admite_faltantes": True, "imputacion": "ninguna", "detalle_imputacion": "Sin imputación.",
                "conversion": None,
            },
            {
                "nombre": "Edad", "nombre_visible": "Edad", "tipo": "continua", "categorias": None,
                "minimo": 17.0, "maximo": 70.0, "rol": "ancestro_objetivo", "admite_faltantes": False,
                "imputacion": "eliminar_filas", "detalle_imputacion": "La fila se descarta.", "conversion": None,
            },
            {
                "nombre": "Curso", "nombre_visible": "Curso", "tipo": "categorica", "categorias": ["A", "B", "C"],
                "minimo": None, "maximo": None, "rol": "fuera_del_subgrafo", "admite_faltantes": True,
                "imputacion": "mediana", "detalle_imputacion": "Mediana de train.", "conversion": None,
            },
        ],
    }


def controles_validos() -> dict:
    return {
        "version_formato": 1,
        "controles": [
            {
                "variable": "Asistencia", "nombre_visible": "Asistencia", "tipo": "continua", "direccion": "subir",
                "permitida": True, "minimo": 0.0, "maximo": 100.0, "cambio_maximo": 25.0, "costo": 1.0,
                "estados_permitidos": None, "paso": 1, "valores_permitidos": None,
            },
            {
                "variable": "Curso", "nombre_visible": "Curso", "tipo": "categorica", "direccion": "ambas",
                "permitida": False, "minimo": None, "maximo": None, "cambio_maximo": None, "costo": 2.0,
                "estados_permitidos": ["A", "B"], "paso": None, "valores_permitidos": None,
            },
        ],
    }


def controles_v3() -> dict:
    """Controles del formato 3: una continua con paso 0,5 y una ordinal con sus valores permitidos."""
    datos = controles_validos()
    datos["version_formato"] = 3
    datos["controles"][0]["paso"] = 0.5
    datos["controles"].append({
        "variable": "Nivel", "nombre_visible": "Nivel", "tipo": "ordinal", "direccion": "ambas", "permitida": True,
        "minimo": 14.0, "maximo": 16.0, "cambio_maximo": 2.0, "costo": 1.0, "estados_permitidos": [14, 15, 16], "paso": None,
        "valores_permitidos": [{"valor": 14.0, "etiqueta": None}, {"valor": 15.0, "etiqueta": None}, {"valor": 16.0, "etiqueta": None}],
    })
    return datos


def problemas_de(funcion, datos) -> dict[str, str]:
    with pytest.raises(ErrorFormatoArtefacto) as error:
        funcion(datos)
    return {p.campo: p.mensaje for p in error.value.problemas}


# --- Manifest ------------------------------------------------------------------------------------


def test_manifest_valido_ida_y_vuelta():
    datos = manifest_valido()
    manifest = manifest_desde_diccionario(datos)
    assert manifest.objetivo.deseado == 0.5
    assert manifest.a_diccionario() == datos
    assert json.loads(json.dumps(manifest.a_diccionario())) == datos


def test_manifest_golden_provisional_es_valido():
    datos = manifest_valido()
    datos["golden_sha256"] = None
    del datos["archivos"]["golden.json"]
    assert manifest_desde_diccionario(datos).golden_sha256 is None


@pytest.mark.parametrize(
    "cambio, campo",
    [
        (lambda d: d.update(formato="otro"), "formato"),
        (lambda d: d.update(version_formato=4), "version_formato"),
        (lambda d: d.update(creado_en="ayer"), "creado_en"),
        (lambda d: d.pop("version_nucleo"), "version_nucleo"),
        (lambda d: d["versiones_librerias"].update(pygam=""), "versiones_librerias.pygam"),
        (lambda d: d["proyecto"].update(sha256_dataset="xyz"), "proyecto.sha256_dataset"),
        (lambda d: d["objetivo"].update(tipo="multiclase"), "objetivo.tipo"),
        (lambda d: d["objetivo"].update(medida="valor"), "objetivo.medida"),
        (lambda d: d["objetivo"].update(direccion="ambas"), "objetivo.direccion"),
        (lambda d: d["objetivo"].update(deseado=float("nan")), "objetivo.deseado"),
        (lambda d: d["objetivo"].update(deseado=True), "objetivo.deseado"),
        (lambda d: d["objetivo"].update(clase_objetivo=2), "objetivo.clase_objetivo"),
        (lambda d: d["prescripcion"].update(mu_origen="a_ojo"), "prescripcion.mu_origen"),
        (lambda d: d["prescripcion"].update(mu=-1), "prescripcion.mu"),
        (lambda d: d["modelo"].update(huella="1234"), "modelo.huella"),
        (lambda d: d["supuestos_confirmados"].clear(), "supuestos_confirmados"),
        (lambda d: d["resumen_evaluacion"].update(auc_test="alto"), "resumen_evaluacion.auc_test"),
        (lambda d: d["resumen_evaluacion"].update(filas_evaluadas=1.5), "resumen_evaluacion.filas_evaluadas"),
        (lambda d: d["archivos"].update({"otro.txt": SHA}), "archivos.otro.txt"),
        (lambda d: d["archivos"].update({"receta.json": "corto"}), "archivos.receta.json"),
        (lambda d: d.update(golden_sha256="corto"), "golden_sha256"),
        (lambda d: d.update(inesperado=1), "inesperado"),
        (lambda d: d["advertencias"][0].pop("codigo"), "advertencias.0.codigo"),
    ],
)
def test_manifest_invalido(cambio, campo):
    datos = copy.deepcopy(manifest_valido())
    cambio(datos)
    assert campo in problemas_de(manifest_desde_diccionario, datos)


def test_manifest_acumula_todos_los_problemas():
    datos = manifest_valido()
    datos["formato"] = "otro"
    datos["objetivo"]["direccion"] = "ambas"
    datos["modelo"]["huella"] = "x"
    assert {"formato", "objetivo.direccion", "modelo.huella"} <= set(problemas_de(manifest_desde_diccionario, datos))


def test_manifest_objetivo_continuo_se_mide_como_valor():
    datos = manifest_valido()
    datos["objetivo"].update(tipo="continuo", medida="probabilidad", clase_positiva=None, clase_objetivo=None)
    assert "objetivo.medida" in problemas_de(manifest_desde_diccionario, datos)
    datos["objetivo"].update(medida="valor", umbral_decision=None)
    assert manifest_desde_diccionario(datos).objetivo.medida == "valor"


def test_manifest_no_objeto():
    assert "" in problemas_de(manifest_desde_diccionario, [])


# --- Esquema de entrada ----------------------------------------------------------------------------


def test_esquema_valido_ida_y_vuelta_y_respeta_el_nombre_exacto():
    datos = esquema_valido()
    esquema = esquema_entrada_desde_diccionario(datos)
    assert esquema.a_diccionario() == datos
    columna = esquema.columna("Daytime/evening attendance\t")
    assert columna is not None and columna.nombre_visible == "Daytime/evening attendance"
    assert esquema.columna("Daytime/evening attendance") is None


@pytest.mark.parametrize(
    "cambio, campo",
    [
        (lambda d: d.update(columnas=[]), "columnas"),
        (lambda d: d["columnas"][1].update(nombre="Daytime/evening attendance\t"), "columnas.1.nombre"),
        (lambda d: d["columnas"][0].update(nombre_visible="Daytime/evening attendance\t"), "columnas.0.nombre_visible"),
        (lambda d: d["columnas"][0].update(nombre_visible=" Edad"), "columnas.0.nombre_visible"),
        (lambda d: d["columnas"][1].update(tipo="texto"), "columnas.1.tipo"),
        (lambda d: d["columnas"][1].update(minimo=None), "columnas.1.minimo"),
        (lambda d: d["columnas"][1].update(minimo=80.0), "columnas.1.minimo"),
        (lambda d: d["columnas"][1].update(categorias=[1, 2]), "columnas.1.categorias"),
        (lambda d: d["columnas"][2].update(categorias=None), "columnas.2.categorias"),
        (lambda d: d["columnas"][2].update(categorias=["A", "A"]), "columnas.2.categorias"),
        (lambda d: d["columnas"][2].update(minimo=1.0), "columnas.2.minimo"),
        (lambda d: d["columnas"][0].update(categorias=[0, 1, 2]), "columnas.0.categorias"),
        (lambda d: d["columnas"][1].update(rol="causa"), "columnas.1.rol"),
        (lambda d: d["columnas"][1].update(admite_faltantes=True), "columnas.1.admite_faltantes"),
        (lambda d: d["columnas"][2].update(admite_faltantes=False), "columnas.2.admite_faltantes"),
        (lambda d: d["columnas"][2].update(imputacion="media"), "columnas.2.imputacion"),
        (lambda d: d["columnas"][2].pop("detalle_imputacion"), "columnas.2.detalle_imputacion"),
        (lambda d: d.update(version_formato=4), "version_formato"),
        (lambda d: d["columnas"][0].update(extra=1), "columnas.0.extra"),
    ],
)
def test_esquema_invalido(cambio, campo):
    datos = copy.deepcopy(esquema_valido())
    cambio(datos)
    assert campo in problemas_de(esquema_entrada_desde_diccionario, datos)


def test_esquema_admite_rol_id():
    datos = esquema_valido()
    datos["columnas"][2]["rol"] = "id"
    assert esquema_entrada_desde_diccionario(datos).columnas[2].rol == "id"


# --- Controles --------------------------------------------------------------------------------------


def test_controles_validos_ida_y_vuelta():
    datos = controles_validos()
    controles = controles_desde_diccionario(datos)
    assert controles.a_diccionario() == datos
    assert controles.control("Asistencia").paso == 1
    assert controles.control("Curso").permitida is False
    assert controles.control("No existe") is None


def test_controles_formato_3_ida_y_vuelta_con_ordinal_y_paso_real():
    datos = controles_v3()
    controles = controles_desde_diccionario(datos)
    assert controles.a_diccionario() == datos
    assert controles.control("Asistencia").paso == 0.5
    assert [p["valor"] for p in controles.control("Nivel").valores_permitidos] == [14.0, 15.0, 16.0]


def test_controles_formato_3_ordinal_de_texto_lleva_la_etiqueta():
    datos = controles_v3()
    datos["controles"][2].update(
        estados_permitidos=["bajo", "alto"], minimo=0.0, maximo=2.0, cambio_maximo=1.0,
        valores_permitidos=[{"valor": 0.0, "etiqueta": "bajo"}, {"valor": 2.0, "etiqueta": "alto"}],
    )
    assert controles_desde_diccionario(datos).control("Nivel").valores_permitidos[1] == {"valor": 2.0, "etiqueta": "alto"}


@pytest.mark.parametrize("version", [1, 2])
def test_los_formatos_1_y_2_se_siguen_leyendo_sin_valores_permitidos(version):
    datos = controles_validos()
    datos["version_formato"] = version
    for c in datos["controles"]:
        c.pop("valores_permitidos")
    datos["controles"].append({
        "variable": "Nivel", "nombre_visible": "Nivel", "tipo": "ordinal", "direccion": "ambas", "permitida": True,
        "minimo": 0.0, "maximo": 2.0, "cambio_maximo": 1.0, "costo": 1.0, "estados_permitidos": [14, 15, 16], "paso": None,
    })
    leidos = controles_desde_diccionario(datos)
    assert leidos.version_formato == version and leidos.control("Nivel").valores_permitidos is None
    assert leidos.control("Asistencia").paso == 1


@pytest.mark.parametrize(
    "cambio, campo",
    [
        (lambda d: d["controles"][0].update(tipo="numerica"), "controles.0.tipo"),
        (lambda d: d["controles"][0].update(direccion="arriba"), "controles.0.direccion"),
        (lambda d: d["controles"][0].update(costo=0), "controles.0.costo"),
        (lambda d: d["controles"][0].update(cambio_maximo=-1), "controles.0.cambio_maximo"),
        (lambda d: d["controles"][0].update(paso=0), "controles.0.paso"),
        (lambda d: d["controles"][0].update(paso="x"), "controles.0.paso"),
        (lambda d: d["controles"][0].update(valores_permitidos=[{"valor": 1.0, "etiqueta": None}]), "controles.0.valores_permitidos"),
        (lambda d: d["controles"][2].update(valores_permitidos=[]), "controles.2.valores_permitidos"),
        (lambda d: d["controles"][2].update(valores_permitidos=None), "controles.2.valores_permitidos"),
        (lambda d: d["controles"][2].update(paso=1.0), "controles.2.paso"),
        (lambda d: d["controles"][2]["valores_permitidos"][0].update(extra=1), "controles.2.valores_permitidos.0.extra"),
        (lambda d: d["controles"][2]["valores_permitidos"][0].pop("etiqueta"), "controles.2.valores_permitidos.0.etiqueta"),
        (lambda d: d["controles"][0].update(minimo=200.0), "controles.0.minimo"),
        (lambda d: d["controles"][0].update(estados_permitidos=["a"]), "controles.0.estados_permitidos"),
        (lambda d: d["controles"][1].update(estados_permitidos=[]), "controles.1.estados_permitidos"),
        (lambda d: d["controles"][1].update(estados_permitidos=None), "controles.1.estados_permitidos"),
        (lambda d: d["controles"][1].update(maximo=3.0), "controles.1.minimo"),
        (lambda d: d["controles"][1].update(paso=1), "controles.1.paso"),
        (lambda d: d["controles"][1].update(variable="Asistencia"), "controles.1.variable"),
        (lambda d: d["controles"][0].update(permitida="si"), "controles.0.permitida"),
        (lambda d: d["controles"][0].pop("nombre_visible"), "controles.0.nombre_visible"),
    ],
)
def test_controles_invalidos(cambio, campo):
    datos = copy.deepcopy(controles_v3())
    cambio(datos)
    assert campo in problemas_de(controles_desde_diccionario, datos)


# --- Utilidades ---------------------------------------------------------------------------------------


def test_nombre_visible_quita_invisibles_y_espacios_sobrantes():
    assert nombre_visible("Daytime/evening attendance\t") == "Daytime/evening attendance"
    assert nombre_visible("  A​  B \n") == "A B"
    assert nombre_visible("Edad") == "Edad"


def test_json_canonico_es_estable_e_independiente_del_orden():
    a = {"b": 1, "a": [1.0, None], "ñ": "é"}
    b = {"ñ": "é", "a": [1.0, None], "b": 1}
    assert json_canonico(a) == json_canonico(b) == '{"a":[1.0,null],"b":1,"ñ":"é"}'.encode()
    assert sha256_bytes(json_canonico(a)) == sha256_bytes(json_canonico(b))
    assert json_canonico({"x": float("nan")}) == b'{"x":null}'

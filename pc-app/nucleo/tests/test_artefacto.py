"""Artefacto .scotty: exportación, carga, API (predecir, prescribir, contrafactual, lote) y golden.

Un proyecto sintético con una columna cuyo nombre lleva un tabulador, una binaria prescriptiva, una
categórica one-hot, una intermedia y distintos tratamientos de faltantes se exporta una vez y se
carga desde el archivo, sin carpeta de proyecto ni dataset original.
"""

import copy
import io
import json
import re
import zipfile
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from pcapp_nucleo.artefacto import formato as f
from pcapp_nucleo.artefacto import golden as g
from pcapp_nucleo.artefacto.cargar import Artefacto, ErrorArtefacto, ErrorSolicitud, cargar_artefacto
from pcapp_nucleo.artefacto.exportar import (
    ErrorExportacion, ExportacionCancelada, ProyectoParaExportar, _evaluacion_vigente, _resumen_evaluacion,
    exportar_artefacto, exportar_artefacto_completo,
)
from pcapp_nucleo.causal import caso_desde_test, construir_modelo, modelo_desde_diccionario, sha256_train
from pcapp_nucleo.preparacion import Codificacion, DecisionesUsuario, TratamientoColumna, preparar, receta_a_diccionario
from pcapp_nucleo.prescripcion import (
    LoteCancelado, ObjetivoDeseado, ajustar_referencia, configuracion_por_defecto, confirmar_supuestos,
)
from pcapp_nucleo.prescripcion.prescriptor import semilla_de_caso
from pcapp_nucleo.utilidades import a_diccionario_serializable

TAB = "Horas\t"


def dataset(n: int = 1500) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    horas = rng.integers(0, 21, n).astype(float)
    tutoria = rng.integers(0, 2, n)
    sede = rng.choice(["A", "B", "C"], n)
    edad = rng.normal(22, 3, n).round(1)
    ruido = rng.normal(size=n).round(3)  # con pocos decimales, el CSV conserva exactamente los valores
    nota = (40 + 2.0 * horas + 8 * tutoria + rng.normal(0, 5, n)).round(2)
    p = expit(-8 + 0.12 * nota + 0.6 * (sede == "B") - 0.05 * (edad - 22))
    y = np.where(rng.uniform(size=n) < p, "Si", "No")
    edad[rng.choice(n, 60, replace=False)] = np.nan
    ruido[rng.choice(n, 25, replace=False)] = np.nan
    return pd.DataFrame({TAB: horas, "Tutoria": tutoria, "Sede": sede, "Edad": edad, "Ruido": ruido, "Nota": nota, "Y": y})


def construir_proyecto(**cambios) -> ProyectoParaExportar:
    df = dataset()
    datos = preparar(df, "Y", DecisionesUsuario(
        codificaciones={"Sede": Codificacion("one_hot")},
        faltantes={"Edad": TratamientoColumna(imputacion="mediana"), "Ruido": TratamientoColumna(imputacion="eliminar_filas")},
    ))
    variables = list(datos.train.columns)
    aristas = [(TAB, "Nota"), ("Tutoria", "Nota"), ("Nota", "Y"), ("Sede=B", "Y"), ("Sede=C", "Y"), ("Edad", "Y")]
    resultado_pc = {
        "variables": variables, "aristas": [{"origen": o, "destino": d, "tipo": "dirigida"} for o, d in aristas],
        "corridas": {"completo": True},
    }
    modelo_json, evaluacion = construir_modelo(resultado_pc, datos)
    modelo = modelo_desde_diccionario(modelo_json, datos.train)
    configuracion = configuracion_por_defecto(modelo, [TAB, "Tutoria", "Ruido"])
    configuracion = replace(configuracion, objetivo=ObjetivoDeseado("subir", 0.8), mu=0.01)
    configuracion = confirmar_supuestos(configuracion, list(configuracion.acciones))
    prescripcion = {
        "configuracion": a_diccionario_serializable(configuracion),
        "modelo_causal": {"huella": modelo_json["huella"], "version_resultado": 1},
        "referencia": a_diccionario_serializable(ajustar_referencia(datos.train, "Y", True)),
        "calibracion": None, "semilla": modelo.semilla,
    }
    modelo_json["resultado_pc"] = {"version": 1, "sha256": "b" * 64}
    receta = receta_a_diccionario(datos.receta)
    receta["origen"]["sha256"] = "c" * 64
    proyecto = ProyectoParaExportar(
        id="a" * 32, nombre="Proyecto de prueba", archivo_original="prueba.csv", receta=receta,
        modelo_causal=modelo_json, evaluacion_modelo=evaluacion, prescripcion=prescripcion, original=df,
    )
    return replace(proyecto, **cambios) if cambios else proyecto


@pytest.fixture(scope="module")
def proyecto() -> ProyectoParaExportar:
    return construir_proyecto()


@pytest.fixture(scope="module")
def exportado(proyecto, tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("scotty")
    resultado = exportar_artefacto_completo(proyecto, carpeta)
    return resultado, carpeta


@pytest.fixture(scope="module")
def art(exportado) -> Artefacto:
    return cargar_artefacto(exportado[0].ruta)


def modificado(proyecto, **cambios) -> ProyectoParaExportar:
    copia = replace(proyecto, **{k: copy.deepcopy(getattr(proyecto, k)) for k in ("receta", "modelo_causal", "prescripcion")})
    for campo, funcion in cambios.items():
        funcion(getattr(copia, campo))
    return copia


def reempaquetar(ruta, manifest=None, archivos=None, quitar=()) -> bytes:
    """Zip del artefacto con cambios (sin recalcular los sha256 del manifest, salvo que se pidan)."""
    salida = io.BytesIO()
    with zipfile.ZipFile(ruta) as origen, zipfile.ZipFile(salida, "w") as destino:
        for nombre in origen.namelist():
            if nombre in quitar:
                continue
            contenido = origen.read(nombre)
            if nombre == f.MANIFEST and manifest:
                datos = json.loads(contenido)
                manifest(datos)
                contenido = json.dumps(datos).encode()
            if archivos and nombre in archivos:
                contenido = archivos[nombre](contenido)
            destino.writestr(nombre, contenido)
    return salida.getvalue()


# --- Exportación -----------------------------------------------------------------------------------------------


def test_nombre_y_contenido_del_archivo(exportado):
    resultado, carpeta = exportado
    assert re.fullmatch(r"Proyecto_de_prueba_v1_\d{8}-\d{6}\.scotty", resultado.ruta.name)
    assert resultado.ruta.parent == carpeta
    with zipfile.ZipFile(resultado.ruta) as z:
        assert z.namelist()[0] == f.MANIFEST and set(z.namelist()) == {f.MANIFEST, *f.ARCHIVOS_CONTENIDO}
        manifest = json.loads(z.read(f.MANIFEST))
        assert set(manifest["archivos"]) == set(f.ARCHIVOS_CONTENIDO)
        for nombre, huella in manifest["archivos"].items():
            assert f.sha256_bytes(z.read(nombre)) == huella


def test_el_manifest_resume_el_proyecto(art, proyecto):
    m = art.manifest
    assert m.formato == "scotty-artefacto" and m.version_formato == 1
    assert m.objetivo.columna == "Y" and m.objetivo.tipo == "binario" and m.objetivo.medida == "probabilidad"
    assert m.objetivo.clase_positiva == ["Si"] and m.objetivo.clase_objetivo == 1
    assert (m.objetivo.direccion, m.objetivo.deseado) == ("subir", 0.8)
    assert m.objetivo.umbral_decision == proyecto.modelo_causal["umbral_decision"]
    assert (m.prescripcion.mu, m.prescripcion.mu_origen) == (0.01, "manual")
    assert m.variables_prescriptivas == [TAB, "Tutoria"]
    assert set(m.supuestos_confirmados) == {TAB, "Tutoria"}
    assert m.modelo.huella == proyecto.modelo_causal["huella"] and m.modelo.train_sha256 == proyecto.modelo_causal["train_sha256"]
    assert m.versiones_librerias == proyecto.modelo_causal["versiones"]
    assert m.proyecto.sha256_dataset == "c" * 64
    assert m.aviso.startswith("Recomendaciones basadas en datos observacionales")
    assert "SIN_EVALUACION_PRESCRIPTOR" in {a.codigo for a in m.advertencias}
    assert m.resumen_evaluacion.auc_test is not None and m.resumen_evaluacion.tasa_exito_prescriptor is None
    assert m.golden_sha256 == g.sha256_golden(art.golden)


def test_los_json_copiados_son_los_del_proyecto(exportado, proyecto):
    with zipfile.ZipFile(exportado[0].ruta) as z:
        assert json.loads(z.read(f.RECETA)) == proyecto.receta
        assert json.loads(z.read(f.MODELO_CAUSAL)) == proyecto.modelo_causal
        assert json.loads(z.read(f.PRESCRIPCION)) == proyecto.prescripcion
        evaluacion = json.loads(z.read(f.EVALUACION))
    assert evaluacion["modelo_causal"] == a_diccionario_serializable(proyecto.evaluacion_modelo)
    assert evaluacion["prescriptor"] is None


def test_el_train_del_parquet_conserva_la_huella(exportado, proyecto):
    """Prueba obligatoria: sha256_train del train leído del artefacto = el del modelo, y la huella se comprueba."""
    with zipfile.ZipFile(exportado[0].ruta) as z:
        train = pd.read_parquet(io.BytesIO(z.read(f.TRAIN)))
        modelo_json = json.loads(z.read(f.MODELO_CAUSAL))
    assert sha256_train(train) == modelo_json["train_sha256"]
    modelo_desde_diccionario(modelo_json, train)  # lanza si la huella de las predicciones no coincide
    assert str(train.index.dtype) == "int64" and any(c == "Sede=B" for c in train.columns)


def test_esquema_de_entrada(art):
    columnas = {c.nombre: c for c in art.esquema_entrada.columnas}
    assert list(columnas) == [TAB, "Tutoria", "Sede", "Edad", "Ruido", "Nota"]
    assert columnas[TAB].nombre_visible == "Horas" and TAB in columnas
    assert (columnas[TAB].tipo, columnas[TAB].rol, columnas[TAB].minimo, columnas[TAB].maximo) == ("continua", "prescriptiva", 0.0, 20.0)
    assert (columnas["Tutoria"].tipo, columnas["Tutoria"].categorias, columnas["Tutoria"].rol) == ("binaria", [0, 1], "prescriptiva")
    assert (columnas["Sede"].tipo, columnas["Sede"].categorias, columnas["Sede"].rol) == ("categorica", ["A", "B", "C"], "ancestro_objetivo")
    assert columnas["Edad"].rol == "ancestro_objetivo" and columnas["Edad"].imputacion == "mediana" and columnas["Edad"].admite_faltantes
    assert columnas["Ruido"].rol == "fuera_del_subgrafo"
    assert (columnas["Ruido"].imputacion, columnas["Ruido"].admite_faltantes) == ("eliminar_filas", False)
    assert columnas["Nota"].rol == "ancestro_objetivo" and "predicción de su mecanismo" in columnas["Nota"].detalle_imputacion
    assert "Y" not in columnas
    f.esquema_entrada_desde_diccionario(art.esquema_entrada.a_diccionario())


def test_controles(art):
    horas, tutoria = art.controles.control(TAB), art.controles.control("Tutoria")
    assert (horas.tipo, horas.nombre_visible, horas.permitida, horas.paso) == ("continua", "Horas", True, 1)
    assert (horas.minimo, horas.maximo, horas.cambio_maximo, horas.costo, horas.estados_permitidos) == (0.0, 20.0, 5.0, 1.0, None)
    assert (tutoria.tipo, tutoria.estados_permitidos, tutoria.paso, tutoria.cambio_maximo) == ("binaria", [0, 1], None, None)
    assert [c.variable for c in art.controles.controles] == art.manifest.variables_prescriptivas


@pytest.mark.parametrize(
    "campo, cambio, texto",
    [
        ("prescripcion", lambda p: p["modelo_causal"].update(huella="x" * 64), "no está vigente"),
        ("prescripcion", lambda p: p["configuracion"].update(mu="automatico"), "no se calibró"),
        ("prescripcion", lambda p: p["configuracion"]["supuestos"][TAB].update(confirmado_en=None), "confirmar la declaración de supuestos"),
        ("prescripcion", lambda p: p["configuracion"].update(modificables=[], acciones={}, supuestos={}), "no hay variables prescriptivas"),
        ("modelo_causal", lambda m: m["versiones"].update(pygam="0.0.1"), "pygam 0.0.1"),
    ],
)
def test_no_se_exporta_si_no_se_cumplen_las_condiciones(proyecto, tmp_path, campo, cambio, texto):
    copia = modificado(proyecto, **{campo: cambio})
    with pytest.raises(ErrorExportacion, match=texto):
        exportar_artefacto(copia, tmp_path)
    assert not list(tmp_path.glob("*"))


def test_mu_automatico_calibrado_se_exporta_como_automatico(proyecto):
    copia = modificado(proyecto, prescripcion=lambda p: (p["configuracion"].update(mu="automatico"), p.update(calibracion={"mu": 0.02})))
    from pcapp_nucleo.artefacto.cargar import mu_efectivo

    assert mu_efectivo(copia.prescripcion) == (0.02, "automatico")


def test_sin_prescripcion_guardada(proyecto, tmp_path):
    with pytest.raises(ErrorExportacion, match="no tiene prescripción guardada"):
        exportar_artefacto(replace(proyecto, prescripcion=None), tmp_path)


def test_destino_explicito_y_nunca_sobrescribe(proyecto, tmp_path):
    ruta = tmp_path / "x" / "mi.scotty"
    ruta.parent.mkdir()
    ruta.write_bytes(b"previo")
    nueva = exportar_artefacto(proyecto, ruta)
    assert nueva.name == "mi_2.scotty" and ruta.read_bytes() == b"previo"
    assert cargar_artefacto(nueva).manifest.proyecto.nombre == "Proyecto de prueba"


def test_exportacion_cancelada(proyecto, tmp_path):
    class Cancelada:
        def is_set(self):
            return True

    with pytest.raises(ExportacionCancelada):
        exportar_artefacto(proyecto, tmp_path, cancelacion=Cancelada())
    assert not list(tmp_path.glob("*"))


def test_evaluacion_del_prescriptor_solo_si_corresponde_al_modelo_y_a_mu(proyecto):
    from pcapp_nucleo.artefacto.exportar import _validar

    v = _validar(proyecto)
    meta = {"numero": 1, "casos": 44, "mu": 0.01, "tasa_exito": 0.9, "huella_modelo": proyecto.modelo_causal["huella"]}
    vigente, avisos = _evaluacion_vigente(replace(proyecto, evaluaciones=[(meta, {"x": 1})]), v)
    assert vigente is not None and avisos == []
    resumen = _resumen_evaluacion(proyecto.evaluacion_modelo, vigente)
    assert (resumen.tasa_exito_prescriptor, resumen.filas_evaluadas) == (0.9, 44)
    for obsoleta in ({**meta, "mu": 0.5}, {**meta, "huella_modelo": "z"}):
        vigente, avisos = _evaluacion_vigente(replace(proyecto, evaluaciones=[(obsoleta, {})]), v)
        assert vigente is None and avisos[0].codigo == "EVALUACION_PRESCRIPTOR_OBSOLETA"


# --- Carga ------------------------------------------------------------------------------------------------------


def test_se_carga_desde_ruta_y_desde_bytes(exportado, art):
    de_bytes = cargar_artefacto(exportado[0].ruta.read_bytes())
    assert de_bytes.manifest == art.manifest and de_bytes.avisos_carga == []


def test_un_archivo_alterado_no_se_carga(exportado):
    ruta = exportado[0].ruta
    alterado = reempaquetar(ruta, archivos={f.MODELO_CAUSAL: lambda c: c.replace(b'"semilla"', b'"semilla" ')})
    with pytest.raises(ErrorArtefacto, match="modelo_causal.json no coincide con su sha256") as error:
        cargar_artefacto(alterado)
    assert error.value.codigo == "INTEGRIDAD"


def test_formato_no_valido(exportado, tmp_path):
    ruta = exportado[0].ruta
    with pytest.raises(ErrorArtefacto, match="no es un zip"):
        cargar_artefacto(b"no soy un zip")
    with pytest.raises(ErrorArtefacto, match="Falta manifest.json"):
        cargar_artefacto(reempaquetar(ruta, quitar=(f.MANIFEST,)))
    with pytest.raises(ErrorArtefacto, match="Faltan archivos"):
        cargar_artefacto(reempaquetar(ruta, quitar=(f.CONTROLES,)))
    with pytest.raises(ErrorArtefacto, match="version_formato"):
        cargar_artefacto(reempaquetar(ruta, manifest=lambda m: m.update(version_formato=2)))
    with pytest.raises(ErrorArtefacto, match="formato"):
        cargar_artefacto(reempaquetar(ruta, manifest=lambda m: m.update(formato="otro")))
    destino = io.BytesIO()
    with zipfile.ZipFile(ruta) as origen, zipfile.ZipFile(destino, "w") as z:
        for n in origen.namelist():
            z.writestr(n, origen.read(n))
        z.writestr("sobra.txt", b"x")
    with pytest.raises(ErrorArtefacto, match="desconocidos"):
        cargar_artefacto(destino.getvalue())


def test_una_libreria_distinta_impide_cargar(exportado):
    cambiado = reempaquetar(exportado[0].ruta, manifest=lambda m: m["versiones_librerias"].update(pygam="0.11.9"))
    with pytest.raises(ErrorArtefacto, match=r"pygam 0\.11\.9 \(instalada: 0\.12\.0\)") as error:
        cargar_artefacto(cambiado)
    assert error.value.codigo == "VERSIONES"


def test_otra_version_del_nucleo_solo_avisa(exportado):
    cambiado = reempaquetar(exportado[0].ruta, manifest=lambda m: m.update(version_nucleo="0.0.1"))
    assert "pcapp_nucleo 0.0.1" in cargar_artefacto(cambiado).avisos_carga[0]


def test_el_golden_es_obligatorio_salvo_al_exportar(exportado):
    sin_golden = reempaquetar(exportado[0].ruta, quitar=(f.GOLDEN,), manifest=lambda m: (m["archivos"].pop("golden.json"), m.update(golden_sha256=None)))
    with pytest.raises(ErrorArtefacto):
        cargar_artefacto(sin_golden)
    assert cargar_artefacto(sin_golden, permitir_sin_golden=True).golden is None


# --- Semilla por valores -------------------------------------------------------------------------------------------


def test_la_semilla_por_valores_ignora_el_indice_y_la_de_siempre_lo_usa(art):
    a = caso_desde_test(art.modelo, art.train, int(art.train.index[0]))
    b = replace(a, indice=57)
    assert semilla_de_caso(art.modelo, a).entropy == semilla_de_caso(art.modelo, a).entropy
    assert semilla_de_caso(art.modelo, a).spawn_key == semilla_de_caso(art.modelo, a).spawn_key
    assert semilla_de_caso(art.modelo, a).generate_state(4).tolist() != semilla_de_caso(art.modelo, b).generate_state(4).tolist()
    assert (
        semilla_de_caso(art.modelo, a, por_valores=True).generate_state(4).tolist()
        == semilla_de_caso(art.modelo, b, por_valores=True).generate_state(4).tolist()
    )
    # El comportamiento de Scotty PC no cambia: sin índice, siempre fue por valores.
    sin_indice = replace(a, indice=None)
    assert semilla_de_caso(art.modelo, sin_indice).generate_state(4).tolist() == semilla_de_caso(art.modelo, a, por_valores=True).generate_state(4).tolist()


def sin_tiempo(resultado):
    resultado = copy.deepcopy(resultado)
    resultado.pop("segundos", None)
    resultado["caso"]["indice"] = None
    return resultado


def test_la_misma_fila_en_la_posicion_0_y_en_la_57_da_el_mismo_resultado(art):
    filas = [g.fila_original(art, dataset(), i) for i in (3, 10, 15, 40)]
    csv = pd.DataFrame([filas[(i % 3) + 1] for i in range(60)])
    csv.iloc[0] = pd.Series(filas[0])
    csv.iloc[57] = pd.Series(filas[0])
    lote = art.prescribir_lote(csv)
    por_fila = {r["fila"]: r["prescripcion"] for r in lote.resultados}
    assert lote.filas == 60 and len(por_fila) == 60 and not lote.no_preparadas
    assert por_fila[0]["caso"]["indice"] == 0 and por_fila[57]["caso"]["indice"] == 57
    assert sin_tiempo(por_fila[0]) == sin_tiempo(por_fila[57])
    assert sin_tiempo(por_fila[0]) == sin_tiempo(art.prescribir(filas[0]))
    assert sin_tiempo(por_fila[1]) == sin_tiempo(por_fila[4])


# --- API --------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fila_en_riesgo(art):
    original = dataset()
    for i in range(len(original)):
        fila = g.fila_original(art, original, i)
        if not art.predecir(fila)["cumple_objetivo"]:
            return fila
    raise AssertionError("no hay filas que no cumplan")


def test_predecir(art, fila_en_riesgo):
    r = art.predecir(fila_en_riesgo)
    assert set(r) == {
        "objetivo", "medida", "probabilidad", "umbral_decision", "clase", "clase_etiqueta", "probabilidad_clase_objetivo",
        "cumple_objetivo", "causas", "extrapolacion", "avisos",
    }
    assert 0 <= r["probabilidad"] <= 1 and r["clase"] == int(r["probabilidad"] >= art.modelo.umbral_decision)
    assert r["clase_etiqueta"] in ("Si", "No") and r["cumple_objetivo"] is False and r["extrapolacion"] is False
    causas = {c["variable"]: c for c in r["causas"]}
    assert set(causas) == {TAB, "Tutoria", "Sede", "Edad", "Nota"}
    assert causas["Nota"]["categoria"] == "directa" and causas[TAB]["categoria"] == "indirecta"
    assert causas["Sede"]["categoria"] == "directa" and causas[TAB]["prescriptiva"] and not causas["Edad"]["prescriptiva"]
    assert [abs(c["contribucion"]) for c in r["causas"]] == sorted((abs(c["contribucion"]) for c in r["causas"]), reverse=True)
    assert causas["Sede"]["valor"] in ("A", "B", "C") and causas["Sede"]["valor_tipico"] in ("A", "B", "C")
    json.dumps(r)


def test_predecir_avisa_de_extrapolacion_y_faltantes(art, fila_en_riesgo):
    r = art.predecir({**fila_en_riesgo, TAB: 90.0, "Nota": None})
    codigos = {a["codigo"] for a in r["avisos"]}
    assert r["extrapolacion"] and {"VALOR_FUERA_DE_RANGO", "CASO_FUERA_DE_RANGO", "INTERMEDIAS_PREDICHAS"} <= codigos
    assert "Edad" not in {a["variables"][0] for a in r["avisos"] if a["codigo"] == "RAICES_IMPUTADAS"}  # su mediana la pone la receta


def test_prescribir_formato_y_resultado(art, fila_en_riesgo):
    r = art.prescribir(fila_en_riesgo)
    assert r["objetivo"] == "Y" and r["medida"] == "probabilidad" and r["deseado"] == 0.8 and r["mu"] == 0.01
    assert r["caso"] == {"origen": "usuario", "indice": 0}
    assert r["acciones"] and r["alcanzado"] and not r["ya_cumple"] and r["despues"] >= 0.8 - 1e-9 > r["antes"]
    assert r["referencia"].keys() == {"despues", "alcanzado"} and isinstance(r["requiere_revision"], bool)
    assert r["evidencia"]["k"] > 0 and {"prescrita", "actual", "mejora", "texto"} <= r["evidencia"].keys()
    assert {"variable", "tipo", "antes", "despues", "contribucion"} <= r["acciones"][0].keys()
    assert art.prescribir(fila_en_riesgo)["acciones"] == r["acciones"]
    json.dumps(r)


def test_resultado_identico_en_una_instancia_nueva(exportado, art, fila_en_riesgo):
    otra = cargar_artefacto(exportado[0].ruta.read_bytes())
    assert sin_tiempo(otra.prescribir(fila_en_riesgo)) == sin_tiempo(art.prescribir(fila_en_riesgo))
    assert otra.predecir(fila_en_riesgo) == art.predecir(fila_en_riesgo)


def test_contrafactual(art, fila_en_riesgo):
    fijar = art.contrafactual(fila_en_riesgo, [{"variable": TAB, "tipo": "fijar", "valor": 20}])
    desplazar = art.contrafactual(fila_en_riesgo, [{"variable": TAB, "tipo": "desplazar", "valor": 3}])
    categoria = art.contrafactual(fila_en_riesgo, [{"variable": "Sede", "tipo": "fijar", "valor": "B"}])
    assert fijar["medida"] == "probabilidad" and fijar["despues"] > fijar["antes"] and fijar["clase_despues"] in (0, 1)
    assert 0 < desplazar["despues"] - desplazar["antes"] <= fijar["despues"] - fijar["antes"] + 1e-12
    assert categoria["caso"]["origen"] == "usuario"
    assert art.contrafactual(fila_en_riesgo, []) ["cambio"] == 0


@pytest.mark.parametrize(
    "intervenciones, campo",
    [
        ([{"variable": "Y", "tipo": "fijar", "valor": 1}], "intervenciones.0.variable"),
        ([{"variable": "Sede", "tipo": "fijar", "valor": "Z"}], "intervenciones.0.valor"),
        ([{"variable": TAB, "tipo": "girar", "valor": 1}], "intervenciones.0.tipo"),
        ([{"variable": TAB}], "intervenciones"),
    ],
)
def test_contrafactual_invalido(art, fila_en_riesgo, intervenciones, campo):
    with pytest.raises(ErrorSolicitud) as error:
        art.contrafactual(fila_en_riesgo, intervenciones)
    assert error.value.campo == campo


def test_filas_no_validas(art, fila_en_riesgo):
    sin_columna = {k: v for k, v in fila_en_riesgo.items() if k != "Edad"}
    with pytest.raises(ErrorSolicitud, match="Faltan columnas en la fila: 'Edad'") as error:
        art.prescribir(sin_columna)
    assert error.value.campo == "Edad"
    with pytest.raises(ErrorSolicitud, match="'Z' no es un valor conocido de 'Sede'") as error:
        art.predecir({**fila_en_riesgo, "Sede": "Z"})
    assert error.value.campo == "Sede"
    with pytest.raises(ErrorSolicitud, match="debe ser un número") as error:
        art.predecir({**fila_en_riesgo, TAB: "mucho"})
    assert error.value.campo == TAB
    with pytest.raises(ErrorSolicitud, match="Falta 'Ruido'"):
        art.predecir({**fila_en_riesgo, "Ruido": None})
    assert art.predecir({**fila_en_riesgo, "Edad": "?", "Extra": 1})["probabilidad"] > 0  # "?" es faltante y lo sobrante se ignora


def test_validar_filas(art, fila_en_riesgo):
    csv = pd.DataFrame([
        fila_en_riesgo, {**fila_en_riesgo, "Sede": "Z"}, {**fila_en_riesgo, TAB: 99.0}, {**fila_en_riesgo, "Ruido": None},
        {**fila_en_riesgo, TAB: "x"}, {**fila_en_riesgo, "Sede": "C"},
    ])
    csv["Sobrante"] = 1
    informe = art.validar_filas(csv)
    assert (informe.filas, informe.filas_preparables, informe.correcto) == (6, 3, False)
    assert informe.columnas_ignoradas == ["Sobrante"]
    assert informe.categorias_no_vistas == {"Sede": ["Z"]}
    assert informe.fuera_de_rango == {TAB: {"filas": [2], "minimo": 0.0, "maximo": 20.0}}
    assert [(p.fila, p.columna, p.tipo) for p in informe.problemas] == [
        (1, "Sede", "categoria_no_vista"), (3, None, "no_preparable"), (4, TAB, "no_numerico"),
    ]
    assert informe.a_diccionario()["correcto"] is False
    json.dumps(informe.a_diccionario())


def test_una_celda_mala_no_arruina_las_demas_filas_ni_los_vacios_la_columna(art, fila_en_riesgo):
    vacia = {**fila_en_riesgo, "Edad": None}  # una sola fila con None: la columna sería «object»
    assert art.predecir(vacia)["probabilidad"] > 0
    csv = pd.DataFrame([{**fila_en_riesgo, TAB: "x"}, *[fila_en_riesgo] * 3, {**fila_en_riesgo, "Tutoria": 7}])
    informe = art.validar_filas(csv)
    assert informe.filas_preparables == 3 and [(p.fila, p.tipo) for p in informe.problemas] == [(0, "no_numerico"), (4, "categoria_no_vista")]
    lote = art.prescribir_lote(csv, tamano_bloque=2)
    assert [r["fila"] for r in lote.resultados] == [1, 2, 3] and [p.fila for p in lote.no_preparadas] == [0, 4]


def test_validar_filas_columnas_faltantes_con_pista_del_nombre_exacto(art, fila_en_riesgo):
    csv = pd.DataFrame([fila_en_riesgo]).rename(columns={TAB: "Horas"})
    informe = art.validar_filas(csv)
    assert informe.columnas_faltantes == [TAB] and not informe.correcto
    assert "el archivo trae 'Horas'" in informe.problemas[0].mensaje
    with pytest.raises(ErrorSolicitud, match="Faltan columnas"):
        art.prescribir_lote(csv)


# --- Lote -----------------------------------------------------------------------------------------------------------------


def test_lote_por_bloques_en_secuencia(art, fila_en_riesgo):
    csv = pd.DataFrame([{**fila_en_riesgo, TAB: float(i % 21)} for i in range(25)] + [{**fila_en_riesgo, "Sede": "Z"}])
    avances = []
    bloques = list(art.iterar_lote(csv, progreso=lambda h, t: avances.append((h, t)), tamano_bloque=10))
    assert [len(b.resultados) for b in bloques] == [10, 10, 5] and avances == [(10, 26), (20, 26), (26, 26)]
    assert [(p.fila, p.tipo) for b in bloques for p in b.no_preparadas] == [(25, "categoria_no_vista")]
    lote = art.prescribir_lote(csv, tamano_bloque=10)
    assert [r["fila"] for r in lote.resultados] == list(range(25)) and lote.filas == 26
    assert [(p.fila, p.columna) for p in lote.no_preparadas] == [(25, "Sede")]
    assert sin_tiempo(lote.resultados[7]["prescripcion"]) == sin_tiempo(art.prescribir(csv.iloc[7].to_dict()))
    assert json.dumps(lote.a_diccionario())


def test_lote_cancelado(art, fila_en_riesgo):
    class Cancelar:
        def __init__(self):
            self.llamadas = 0

        def is_set(self):
            self.llamadas += 1
            return self.llamadas > 1

    csv = pd.DataFrame([fila_en_riesgo] * 40)
    with pytest.raises(LoteCancelado):
        art.prescribir_lote(csv, cancelacion=Cancelar(), tamano_bloque=10)


def test_lote_en_procesos_da_lo_mismo(art, fila_en_riesgo):
    csv = pd.DataFrame([{**fila_en_riesgo, TAB: float(i)} for i in range(6)])
    en_secuencia = art.prescribir_lote(csv, tamano_bloque=2)
    en_paralelo = art.prescribir_lote(csv, procesos=2, tamano_bloque=2)
    assert [sin_tiempo(r["prescripcion"]) for r in en_paralelo.resultados] == [sin_tiempo(r["prescripcion"]) for r in en_secuencia.resultados]


# --- Golden ------------------------------------------------------------------------------------------------------------------


def test_golden_generado_y_verificado(art):
    casos = art.golden["casos"]
    assert 1 <= len(casos) <= 20
    assert {"indice_test", "fila_original", "predecir", "prescribir", "contrafactual"} <= casos[0].keys()
    assert "segundos" not in json.dumps(casos)
    assert casos[0]["contrafactual"]["intervenciones"] == [{"variable": TAB, "tipo": "fijar", "valor": 20.0}]
    informe = g.verificar_golden(art)
    assert informe.correcto and informe.casos == len(casos) and informe.diferencias == [] and informe.maxima_diferencia <= 1e-9


def test_seleccion_de_casos_del_golden(art, proyecto):
    from pcapp_nucleo.artefacto.exportar import _validar

    v = _validar(proyecto)
    indices = g.seleccionar_indices(art, v.test)
    sin_objetivo = v.test.drop(columns=["Y"])
    from pcapp_nucleo.prescripcion import que_no_cumplen

    no_cumplen = set(que_no_cumplen(art.modelo, sin_objetivo, art.configuracion).index)
    cumplen = set(sin_objetivo.index) - no_cumplen
    assert len(indices) == 20 and indices == sorted(indices)
    assert sum(1 for i in indices if i in no_cumplen) == min(len(no_cumplen), 15 + max(0, 5 - len(cumplen)))
    assert sum(1 for i in indices if i in cumplen) == min(len(cumplen), 5 + max(0, 15 - len(no_cumplen)))


def test_verificar_golden_detecta_cambios(art):
    alterado = copy.copy(art)
    alterado.golden = copy.deepcopy(art.golden)
    alterado.golden["casos"][0]["prescribir"]["alcanzado"] = not alterado.golden["casos"][0]["prescribir"]["alcanzado"]
    informe = g.verificar_golden(alterado)
    assert not informe.correcto and informe.casos_distintos == [art.golden["casos"][0]["indice_test"]]
    assert any("alcanzado" in d for d in informe.diferencias) and any("sha256 del golden" in d for d in informe.diferencias)
    sin = copy.copy(art)
    sin.golden = None
    assert not g.verificar_golden(sin).correcto


@pytest.mark.parametrize(
    "esperado, obtenido, correcto",
    [
        (1.0, 1.0 + 1e-10, True), (1.0, 1.0 + 1e-8, False), (1, 1.0, True), (True, False, False), (True, 1, False),
        ("a", "b", False), (None, 0.0, False), ({"a": [1, 2]}, {"a": [1, 2]}, True), ({"a": [1, 2]}, {"a": [1]}, False),
        ({"a": 1}, {"b": 1}, False), ([{"x": "p"}], [{"x": "q"}], False), (0.0, float("inf"), False),
    ],
)
def test_comparacion_exacta_en_lo_discreto_y_tolerante_en_lo_numerico(esperado, obtenido, correcto):
    diferencias: list[str] = []
    g._comparar(esperado, obtenido, "x", diferencias, [0.0])
    assert (not diferencias) is correcto


def test_comparacion_con_scotty_pc(exportado, art):
    c = exportado[0].comparacion
    assert c["casos"] == len(art.golden["casos"])
    assert 0 <= c["acuerdo_alcanzado"] <= 1 and c["diferencia_media_despues"] >= 0
    assert c["filas_con_preparacion_distinta"] == []


# --- CLI y proyecto en disco ---------------------------------------------------------------------------------------


def escribir_proyecto(raiz, proyecto):
    carpeta = raiz / "proyectos" / proyecto.id
    (carpeta / "modelo_causal").mkdir(parents=True)
    (carpeta / "prescripcion").mkdir()
    proyecto.original.to_csv(carpeta / "prueba.csv", index=False)
    receta = copy.deepcopy(proyecto.receta)
    receta["origen"]["archivo"] = "prueba.csv"
    receta["origen"].pop("hoja", None)
    for nombre, datos in (
        ("receta.json", receta), ("modelo_causal/modelo_causal.json", proyecto.modelo_causal),
        ("modelo_causal/evaluacion.json", a_diccionario_serializable(proyecto.evaluacion_modelo)),
        ("prescripcion/prescripcion.json", proyecto.prescripcion),
    ):
        (carpeta / nombre).write_text(json.dumps(datos), encoding="utf-8")
    return carpeta


def test_cli_exportar_artefacto_desde_la_carpeta_del_proyecto(proyecto, tmp_path, capsys):
    from pcapp_nucleo.cli import SALIDA_CORRECTA, SALIDA_ERROR, main

    carpeta = escribir_proyecto(tmp_path, proyecto)
    salida = tmp_path / "salida"
    salida.mkdir()
    assert main(["exportar-artefacto", str(carpeta), str(salida)]) == SALIDA_CORRECTA
    texto = capsys.readouterr()
    [archivo] = salida.glob("*.scotty")
    assert "EXPORTACIÓN COMPLETADA" in texto.out and str(archivo) in texto.out
    art = cargar_artefacto(archivo)
    assert art.manifest.proyecto.id == proyecto.id and g.verificar_golden(art).correcto
    # Con una carpeta que no es un proyecto, falla con un mensaje claro y sin escribir nada.
    assert main(["exportar-artefacto", str(tmp_path / "no_existe"), str(salida)]) == SALIDA_ERROR
    assert "no existe" in capsys.readouterr().err and len(list(salida.glob("*"))) == 1
    sin_prescripcion = tmp_path / "otro"
    (sin_prescripcion / "proyectos").mkdir(parents=True)
    (sin_prescripcion / "proyectos" / "p").mkdir()
    assert main(["exportar-artefacto", str(sin_prescripcion / "proyectos" / "p"), str(salida)]) == SALIDA_ERROR
    assert "no tiene receta" in capsys.readouterr().err


def test_la_api_publica_se_importa_desde_el_paquete():
    import pcapp_nucleo.artefacto as paquete

    for nombre in ("cargar_artefacto", "Artefacto", "verificar_golden", "exportar_artefacto", "ErrorExportacion", "ErrorSolicitud"):
        assert getattr(paquete, nombre) is getattr(__import__(f"pcapp_nucleo.artefacto.{'golden' if 'golden' in nombre else 'exportar' if 'xport' in nombre else 'cargar'}", fromlist=[nombre]), nombre)
    with pytest.raises(AttributeError):
        paquete.no_existe


def test_servir_un_artefacto_no_necesita_causal_learn(exportado):
    """Un servidor que solo carga artefactos no debe arrastrar las dependencias de entrenamiento."""
    import subprocess
    import sys

    codigo = (
        "import sys\n"
        "class Bloqueo:\n"
        "    def find_spec(self, nombre, ruta=None, destino=None):\n"
        "        if nombre.split('.')[0] == 'causallearn':\n"
        "            raise ImportError('causal-learn no debe importarse al servir')\n"
        "sys.meta_path.insert(0, Bloqueo())\n"
        "from pcapp_nucleo.artefacto import cargar_artefacto, verificar_golden\n"
        "art = cargar_artefacto(sys.argv[1])\n"
        "assert verificar_golden(art).correcto\n"
        "print('ok')\n"
    )
    resultado = subprocess.run([sys.executable, "-c", codigo, str(exportado[0].ruta)], capture_output=True, text=True)
    assert resultado.returncode == 0 and resultado.stdout.strip() == "ok", resultado.stderr

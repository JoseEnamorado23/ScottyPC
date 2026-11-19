"""Casos golden: resultados de referencia que el artefacto debe reproducir al cargarse en cualquier máquina.

Al exportar se eligen hasta 20 filas de test (15 que NO cumplen el objetivo y 5 que sí), se pasan a
unidades originales y se procesan con la API del propio artefacto (``predecir``, ``prescribir`` y un
contrafactual que fija la primera variable prescriptiva a su máximo permitido). ``verificar_golden``
recalcula esos casos. ``predecir`` y el contrafactual exigen igualdad exacta en lo discreto y una diferencia
≤ 1e-9 en los números. ``prescribir`` se verifica por **resultado equivalente**: el optimizador parte de arranques
aleatorios y, si alguno no converge (llega al tope de iteraciones en un valle plano), 1 ULP de diferencia entre
plataformas se amplifica y el mínimo entre arranques puede elegir otro ganador igual de válido. Se exige igualdad
exacta de ``alcanzado``, ``ya_cumple``, ``requiere_revision``, ``extrapolacion``, ``aproximado`` y del conjunto de
variables con cambio; tolerancia en el costo total, en ``despues`` y en el cambio de cada acción; y que la solución
recalculada sea válida (límites, cambio máximo, dirección, estados permitidos y ``alcanzado`` con el motor exacto).
No se comparan la traza, la evidencia, ``referencia.despues`` ni la explicación. El tiempo (``segundos``) no se
guarda: cambia en cada ejecución.

``comparar_con_scotty_pc`` es solo informativa: contrasta con lo que da el flujo de Scotty PC sobre
las mismas filas (por su índice de test). Como la semilla del optimizador depende aquí de los
valores y en Scotty PC del índice, las prescripciones pueden diferir un poco.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo.artefacto import formato as f
from pcapp_nucleo.artefacto.cargar import Artefacto
from pcapp_nucleo.causal import caso_desde_test
from pcapp_nucleo.prescripcion import prescribir_caso, que_no_cumplen
from pcapp_nucleo.prescripcion.configuracion import rango_original
from pcapp_nucleo.prescripcion.problema import ProblemaPrescripcion
from pcapp_nucleo.utilidades import a_diccionario_serializable

MAXIMO_CASOS = 20
CASOS_NO_CUMPLEN = 15
CASOS_CUMPLEN = 5
TOLERANCIA = 1e-9
MAXIMO_DIFERENCIAS = 50
# Tolerancias por defecto de la prescripción equivalente (parámetros de ``verificar_golden``).
COSTO_RELATIVO = 0.02  # |Δ costo_total| / costo_total
DESPUES_ABSOLUTO = 0.01  # |Δ despues| (y |Δ falta|), en unidades del objetivo
CAMBIO_RELATIVO_RANGO = 0.015  # |Δ cambio| de cada acción / rango de train de su variable
# Se exigen iguales (con 1e-9 en los números): lo que no depende del camino del optimizador.
CAMPOS_EXACTOS = ("alcanzado", "ya_cumple", "requiere_revision", "extrapolacion", "aproximado")
CAMPOS_INVARIANTES = ("caso", "objetivo", "medida", "direccion", "clase_positiva", "deseado", "antes", "optimizador", "mu")
IDENTICA, EQUIVALENTE, FALLIDA = "identica", "equivalente", "fallida"
# Campos que cambian en cada ejecución: no forman parte del golden.
VOLATILES = ("segundos",)


class ErrorGolden(Exception):
    pass


def sha256_golden(golden: dict[str, Any]) -> str:
    """sha256 del JSON canónico de los casos (``golden["casos"]``): no depende del formato del archivo."""
    return f.sha256_bytes(f.json_canonico(golden["casos"]))


# --- Selección y generación -------------------------------------------------------------------------------


def seleccionar_indices(art: Artefacto, test: pd.DataFrame) -> list[int]:
    """Índices de test del golden: hasta 15 que no cumplen el objetivo y hasta 5 que sí (los primeros de cada grupo);
    si un grupo no llega a su cupo, el otro lo completa hasta 20."""
    modelo = art.modelo
    sin_objetivo = test.drop(columns=[modelo.objetivo], errors="ignore")
    no_cumplen = [int(i) for i in que_no_cumplen(modelo, sin_objetivo, art.configuracion).index]
    cumplen = [int(i) for i in sin_objetivo.index if int(i) not in set(no_cumplen)]
    primeros_no, primeros_si = no_cumplen[:CASOS_NO_CUMPLEN], cumplen[:CASOS_CUMPLEN]
    faltan = MAXIMO_CASOS - len(primeros_no) - len(primeros_si)
    if faltan > 0:
        primeros_no = no_cumplen[:CASOS_NO_CUMPLEN + faltan] if len(no_cumplen) > len(primeros_no) else primeros_no
        faltan = MAXIMO_CASOS - len(primeros_no) - len(primeros_si)
        if faltan > 0:
            primeros_si = cumplen[:CASOS_CUMPLEN + faltan]
    return sorted([*primeros_no, *primeros_si])


def fila_original(art: Artefacto, original: pd.DataFrame, posicion: int) -> dict[str, Any]:
    """Fila del dataset original (por su posición) con exactamente las columnas del esquema de entrada."""
    fila = original.iloc[posicion]
    valores: dict[str, Any] = {}
    for columna in art.esquema_entrada.columnas:
        valor = fila[columna.nombre]
        valores[columna.nombre] = None if pd.isna(valor) else (valor.item() if isinstance(valor, np.generic) else valor)
    return valores


def valor_maximo(control: f.ControlVariable, art: Artefacto) -> Any:
    """Máximo permitido de un control: el tope de una continua o la última categoría permitida (en orden de código)."""
    if control.tipo == f.CONTINUA:
        return control.maximo
    descripcion = next(d for d in _descripciones(art) if d["nombre"] == control.variable)
    orden = [c for c in descripcion["categorias"] if any(_igual(c, e) for e in control.estados_permitidos)]
    return orden[-1] if orden else control.estados_permitidos[-1]


def _descripciones(art: Artefacto) -> list[dict[str, Any]]:
    return list(art._controles.values())


def _igual(a: Any, b: Any) -> bool:
    from pcapp_nucleo.preparacion import _mismo_valor

    return _mismo_valor(a, b)


def intervencion_golden(art: Artefacto) -> list[dict[str, Any]]:
    """Contrafactual del golden: fijar la primera variable prescriptiva a su máximo permitido."""
    control = art.controles.control(art.manifest.variables_prescriptivas[0])
    return [{"variable": control.variable, "tipo": "fijar", "valor": valor_maximo(control, art)}]


def _sin_volatiles(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: _sin_volatiles(v) for k, v in valor.items() if k not in VOLATILES}
    if isinstance(valor, list):
        return [_sin_volatiles(v) for v in valor]
    return valor


def calcular_caso(art: Artefacto, fila: dict[str, Any]) -> dict[str, Any]:
    """Los tres resultados del golden de una fila, con la API pública del artefacto."""
    intervenciones = intervencion_golden(art)
    return {
        "predecir": a_diccionario_serializable(art.predecir(fila)),
        "prescribir": _sin_volatiles(a_diccionario_serializable(art.prescribir(fila))),
        "contrafactual": {
            "intervenciones": intervenciones,
            "resultado": a_diccionario_serializable(art.contrafactual(fila, intervenciones)),
        },
    }


def generar_golden(
    art: Artefacto, original: pd.DataFrame, test: pd.DataFrame,
    progreso: Callable[[int, int], None] | None = None, cancelacion: Any = None,
) -> dict[str, Any]:
    """Casos golden de ``art`` a partir del dataset original y de las filas de test (preparadas)."""
    indices = seleccionar_indices(art, test)
    if not indices:
        raise ErrorGolden("No hay filas de test para armar los casos de verificación.")
    casos = []
    for hechos, indice in enumerate(indices):
        if cancelacion is not None and cancelacion.is_set():
            from pcapp_nucleo.artefacto.exportar import ExportacionCancelada

            raise ExportacionCancelada()
        fila = fila_original(art, original, indice)
        casos.append({"indice_test": indice, "fila_original": fila, **calcular_caso(art, fila)})
        if progreso:
            progreso(hechos + 1, len(indices))
    return a_diccionario_serializable({"version_formato": f.VERSION_FORMATO, "casos": casos})


# --- Verificación --------------------------------------------------------------------------------------------


@dataclass
class InformeGolden:
    """``casos_identicos``, ``casos_equivalentes`` (misma prescripción válida pero otra trayectoria del optimizador) y
    ``casos_fallidos`` suman ``casos``. ``campos_fallidos``: campo → índices de test de los casos que fallan en él.
    ``trayectorias``: por caso, ``resultado`` y las diferencias máximas de ``prescribir`` (``costo_relativo``,
    ``despues_absoluto``, ``cambio_relativo_rango``)."""

    correcto: bool
    casos: int
    casos_distintos: list[int] = field(default_factory=list)
    diferencias: list[str] = field(default_factory=list)
    maxima_diferencia: float = 0.0
    casos_identicos: int = 0
    casos_equivalentes: int = 0
    casos_fallidos: int = 0
    campos_fallidos: dict[str, list[int]] = field(default_factory=dict)
    trayectorias: list[dict[str, Any]] = field(default_factory=list)

    def a_diccionario(self) -> dict[str, Any]:
        return a_diccionario_serializable(self)


def _comparar(esperado: Any, obtenido: Any, ruta: str, diferencias: list[str], maximo: list[float]) -> None:
    """Igualdad exacta en lo discreto y |a − b| ≤ 1e-9 en los números."""
    if len(diferencias) >= MAXIMO_DIFERENCIAS:
        return
    numeros = (
        isinstance(esperado, (int, float)) and not isinstance(esperado, bool)
        and isinstance(obtenido, (int, float)) and not isinstance(obtenido, bool)
    )
    if numeros:
        diferencia = abs(float(esperado) - float(obtenido))
        if not math.isfinite(diferencia):
            diferencia = math.inf
        maximo[0] = max(maximo[0], diferencia if math.isfinite(diferencia) else 0.0)
        if diferencia > TOLERANCIA:
            diferencias.append(f"{ruta}: esperado {esperado!r}, obtenido {obtenido!r} (diferencia {diferencia:.3g})")
        return
    if isinstance(esperado, dict) and isinstance(obtenido, dict):
        for clave in sorted(set(esperado) | set(obtenido)):
            if clave not in esperado or clave not in obtenido:
                diferencias.append(f"{ruta}.{clave}: {'falta en lo esperado' if clave not in esperado else 'falta en lo obtenido'}")
            else:
                _comparar(esperado[clave], obtenido[clave], f"{ruta}.{clave}", diferencias, maximo)
        return
    if isinstance(esperado, list) and isinstance(obtenido, list):
        if len(esperado) != len(obtenido):
            diferencias.append(f"{ruta}: esperados {len(esperado)} elementos, obtenidos {len(obtenido)}")
            return
        for i, (a, b) in enumerate(zip(esperado, obtenido)):
            _comparar(a, b, f"{ruta}[{i}]", diferencias, maximo)
        return
    if esperado != obtenido or type(esperado) is not type(obtenido):
        diferencias.append(f"{ruta}: esperado {esperado!r}, obtenido {obtenido!r}")


def _cambio(accion: dict[str, Any]) -> float | None:
    cambio = accion.get("cambio")
    return None if cambio is None else float(cambio)


def _por_variable(prescripcion: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["variable"]: a for a in prescripcion.get("acciones", [])}


def _alcanzado_exacto(art: Artefacto, fila: dict[str, Any], obtenido: dict[str, Any]) -> bool:
    """¿La solución de ``obtenido`` alcanza el objetivo según el motor exacto (``ProblemaPrescripcion.p``)?"""
    caso, _, _ = art._caso(fila)
    problema = ProblemaPrescripcion(art.modelo, caso, art.configuracion, art.mu)
    acciones = _por_variable(obtenido)
    D = np.zeros(problema.k)
    for i, a in enumerate(problema.continuas):
        accion = acciones.get(a.nombre)
        if accion is not None and accion.get("despues_numerico") is not None:
            D[i] = (art.modelo.unidades.a_preparada(a.columna, accion["despues_numerico"]) - a.x0) / a.escala
    estados = list(problema.actual)
    for j, a in enumerate(problema.discretas):
        accion = acciones.get(a.nombre)
        if accion is not None:
            estados[j] = next(i for i, e in enumerate(a.etiquetas) if _igual(e, accion["despues"]))
    p = float(problema.p([D], [estados])[0])
    return float(problema.brecha(np.array([p]))[0]) <= 1e-9


def _validar_solucion(art: Artefacto, fila: dict[str, Any], obtenido: dict[str, Any], ruta: str, diferencias: list[str]) -> None:
    """La solución recalculada respeta límites, cambio máximo, dirección y estados permitidos, y alcanza el objetivo."""
    for accion in obtenido.get("acciones", []):
        control = art.controles.control(accion["variable"])
        if control is None:
            continue
        nombre = f"{ruta}.acciones[{accion['variable']}]"
        despues, cambio = accion.get("despues_numerico"), _cambio(accion)
        if despues is not None:
            holgura = lambda x: 1e-9 * max(1.0, abs(x))  # noqa: E731
            if (control.minimo is not None and despues < control.minimo - holgura(control.minimo)) or (
                control.maximo is not None and despues > control.maximo + holgura(control.maximo)
            ):
                diferencias.append(f"{nombre}.despues: {despues!r} fuera de los límites [{control.minimo}, {control.maximo}]")
        if cambio is not None:
            if control.cambio_maximo is not None and abs(cambio) > control.cambio_maximo + 1e-9 * max(1.0, control.cambio_maximo):
                diferencias.append(f"{nombre}.cambio: |{cambio:.6g}| supera el cambio máximo {control.cambio_maximo:g}")
            if (control.direccion == "subir" and cambio < -1e-9) or (control.direccion == "bajar" and cambio > 1e-9):
                diferencias.append(f"{nombre}.cambio: {cambio:.6g} va contra la dirección permitida ('{control.direccion}')")
        if accion.get("tipo") == "discreta" and control.estados_permitidos is not None:
            if not any(_igual(accion["despues"], e) for e in control.estados_permitidos):
                diferencias.append(f"{nombre}.despues: {accion['despues']!r} no es un estado permitido")
    try:
        recalculado = _alcanzado_exacto(art, fila, obtenido)
    except Exception as error:  # una solución que no se puede evaluar no es válida
        diferencias.append(f"{ruta}.alcanzado: no se pudo recalcular con el motor exacto ({type(error).__name__}: {error})")
        return
    if obtenido["alcanzado"] and not obtenido["ya_cumple"] and not recalculado:
        diferencias.append(f"{ruta}.alcanzado: la solución recalculada no alcanza el objetivo con el motor exacto")


def _comparar_prescripcion(
    art: Artefacto, fila: dict[str, Any], esperado: dict[str, Any], obtenido: dict[str, Any], ruta: str,
    diferencias: list[str], resumen: dict[str, float], costo_relativo: float, despues_absoluto: float, cambio_relativo_rango: float,
) -> None:
    """Equivalencia de dos prescripciones: ver el docstring del módulo. ``resumen`` recibe las diferencias máximas."""
    for campo in CAMPOS_EXACTOS:
        if esperado.get(campo) != obtenido.get(campo):
            diferencias.append(f"{ruta}.{campo}: esperado {esperado.get(campo)!r}, obtenido {obtenido.get(campo)!r}")
    for campo in CAMPOS_INVARIANTES:
        if campo in esperado or campo in obtenido:
            _comparar(esperado.get(campo), obtenido.get(campo), f"{ruta}.{campo}", diferencias, [0.0])
    a, b = _por_variable(esperado), _por_variable(obtenido)
    if set(a) != set(b):
        diferencias.append(f"{ruta}.acciones: variables con cambio esperadas {sorted(a)}, obtenidas {sorted(b)}")
    costo_a, costo_b = float(esperado["costo_total"]), float(obtenido["costo_total"])
    base = max(abs(costo_a), abs(costo_b))
    relativo = abs(costo_a - costo_b) / base if base > 1e-12 else 0.0
    resumen["costo_relativo"] = relativo
    if relativo > costo_relativo:
        diferencias.append(f"{ruta}.costo_total: esperado {costo_a!r}, obtenido {costo_b!r} (diferencia relativa {relativo:.3g})")
    for campo in ("despues", "falta"):
        diferencia = abs(float(esperado[campo]) - float(obtenido[campo]))
        resumen["despues_absoluto"] = max(resumen.get("despues_absoluto", 0.0), diferencia)
        if diferencia > despues_absoluto:
            diferencias.append(f"{ruta}.{campo}: esperado {esperado[campo]!r}, obtenido {obtenido[campo]!r} (diferencia {diferencia:.3g})")
    for variable in sorted(set(a) & set(b)):
        cambio_a, cambio_b = _cambio(a[variable]), _cambio(b[variable])
        if cambio_a is None or cambio_b is None:
            continue
        rango = rango_original(art.modelo, variable)
        amplitud = (rango[1] - rango[0]) if rango else 0.0
        diferencia = abs(cambio_a - cambio_b) / amplitud if amplitud > 0 else (0.0 if abs(cambio_a - cambio_b) <= 1e-9 else math.inf)
        resumen["cambio_relativo_rango"] = max(resumen.get("cambio_relativo_rango", 0.0), diferencia)
        if diferencia > cambio_relativo_rango:
            diferencias.append(
                f"{ruta}.acciones[{variable}].cambio: esperado {cambio_a!r}, obtenido {cambio_b!r} "
                f"(diferencia {diferencia:.3g} del rango de train)"
            )
    _validar_solucion(art, fila, obtenido, ruta, diferencias)


_CAMPO = re.compile(r"^caso \d+\.(.*?)(?:: |$)")


def _campo_de(diferencia: str) -> str:
    """Campo de una diferencia (``caso 7.prescribir.acciones[Asistencia].cambio: …`` → ``prescribir.acciones[].cambio``)."""
    coincidencia = _CAMPO.match(diferencia)
    return re.sub(r"\[[^\]]*\]", "[]", coincidencia.group(1)) if coincidencia else "error"


def verificar_golden(
    art: Artefacto, *, costo_relativo: float = COSTO_RELATIVO, despues_absoluto: float = DESPUES_ABSOLUTO,
    cambio_relativo_rango: float = CAMBIO_RELATIVO_RANGO,
) -> InformeGolden:
    """Recalcula los casos golden con la API del artefacto y los compara con lo guardado.

    ``predecir`` y ``contrafactual``: exacto en lo discreto y 1e-9 en los números. ``prescribir``: idéntico (como
    antes) o equivalente dentro de las tolerancias (``costo_relativo``, ``despues_absoluto``,
    ``cambio_relativo_rango``) con una solución recalculada válida; ver el docstring del módulo.
    """
    golden = art.golden
    if golden is None or not golden.get("casos"):
        return InformeGolden(False, 0, diferencias=["El artefacto no trae casos golden."])
    diferencias: list[str] = []
    if art.manifest.golden_sha256 != sha256_golden(golden):
        diferencias.append("El sha256 del golden no coincide con el del manifest.")
    maximo = [0.0]
    distintos, trayectorias, campos = [], [], {}
    identicos = equivalentes = 0
    for caso in golden["casos"]:
        indice = caso["indice_test"]
        antes = len(diferencias)
        resumen: dict[str, float] = {}
        resultado = IDENTICA
        try:
            obtenido = calcular_caso(art, caso["fila_original"])
        except Exception as error:  # un caso que falla es una diferencia, no un fallo de la verificación
            diferencias.append(f"caso {indice}: {type(error).__name__}: {error}")
            distintos.append(indice)
            campos.setdefault("error", []).append(indice)
            trayectorias.append({"indice_test": indice, "resultado": FALLIDA})
            continue
        for parte in ("predecir", "contrafactual"):
            _comparar(caso[parte], obtenido[parte], f"caso {indice}.{parte}", diferencias, maximo)
        ruta = f"caso {indice}.prescribir"
        estricta, maximo_estricta = [], [0.0]
        _comparar(caso["prescribir"], obtenido["prescribir"], ruta, estricta, maximo_estricta)
        if estricta:
            resultado = EQUIVALENTE
            equivalencia: list[str] = []
            _comparar_prescripcion(
                art, caso["fila_original"], caso["prescribir"], obtenido["prescribir"], ruta, equivalencia, resumen,
                costo_relativo, despues_absoluto, cambio_relativo_rango,
            )
            diferencias.extend(equivalencia)
        else:
            maximo[0] = max(maximo[0], maximo_estricta[0])
        if len(diferencias) > antes:
            resultado = FALLIDA
            distintos.append(indice)
            for campo in {_campo_de(d) for d in diferencias[antes:]}:
                campos.setdefault(campo, []).append(indice)
        elif resultado == IDENTICA:
            identicos += 1
        else:
            equivalentes += 1
        trayectorias.append({"indice_test": indice, "resultado": resultado, **resumen})
    return InformeGolden(
        not diferencias, len(golden["casos"]), distintos, diferencias, maximo[0], identicos, equivalentes, len(distintos),
        campos, trayectorias,
    )


# --- Comparación informativa con Scotty PC -----------------------------------------------------------------------


def comparar_con_scotty_pc(art: Artefacto, test: pd.DataFrame, golden: dict[str, Any]) -> dict[str, Any]:
    """Para las mismas filas, compara la prescripción del artefacto con la del flujo de Scotty PC (por índice de test).

    Informa el acuerdo en ``alcanzado``, en las acciones elegidas y en ``requiere_revision``, y la diferencia media
    (en valor absoluto) de ``despues``. Y si la fila original, preparada con la receta, coincide con la de test.
    """
    modelo = art.modelo
    sin_objetivo = test.drop(columns=[modelo.objetivo], errors="ignore")
    acuerdo_alcanzado, acuerdo_acciones, acuerdo_revision, diferencias, preparacion_distinta = [], [], [], [], []
    for caso in golden["casos"]:
        indice = int(caso["indice_test"])
        scotty = a_diccionario_serializable(prescribir_caso(
            modelo, caso_desde_test(modelo, test, indice), art.configuracion, art.mu, art.referencia,
            sin_objetivo.loc[[indice]], vecinos=art.indice,
        ))
        propio = caso["prescribir"]
        acuerdo_alcanzado.append(propio["alcanzado"] == scotty["alcanzado"])
        acuerdo_acciones.append(
            sorted(a["variable"] for a in propio["acciones"]) == sorted(a["variable"] for a in scotty["acciones"])
        )
        acuerdo_revision.append(propio["requiere_revision"] == scotty["requiere_revision"])
        diferencias.append(abs(propio["despues"] - scotty["despues"]))
        informe, nuevos = art._preparar(pd.DataFrame([caso["fila_original"]]))
        if nuevos is None or nuevos.datos.empty:
            preparacion_distinta.append(indice)
            continue
        propia = nuevos.datos.iloc[0].reindex(sin_objetivo.columns).to_numpy(dtype=float)
        de_test = sin_objetivo.loc[indice].to_numpy(dtype=float)
        if not np.allclose(propia, de_test, rtol=0, atol=1e-9, equal_nan=True):
            preparacion_distinta.append(indice)
    n = max(len(diferencias), 1)
    return {
        "casos": len(diferencias),
        "acuerdo_alcanzado": sum(acuerdo_alcanzado) / n,
        "acuerdo_acciones": sum(acuerdo_acciones) / n,
        "acuerdo_requiere_revision": sum(acuerdo_revision) / n,
        "diferencia_media_despues": float(np.mean(diferencias)) if diferencias else 0.0,
        "diferencia_maxima_despues": float(np.max(diferencias)) if diferencias else 0.0,
        "filas_con_preparacion_distinta": preparacion_distinta,
        "nota": (
            "Informativa. La semilla del optimizador depende en el artefacto de los valores del caso y en Scotty PC "
            "de su índice de test, por lo que pueden diferir algunas prescripciones."
        ),
    }

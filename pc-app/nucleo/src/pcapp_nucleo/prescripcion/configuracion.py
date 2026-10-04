"""Configuración de la prescripción (serializable) y variables prescriptivas.

Una variable es **prescriptiva** si es a la vez ancestro del objetivo en el modelo causal y
modificable según la lista de la prescripción (que empieza con las modificables de la
configuración de PC). Las dummies one-hot se tratan como su categoría (grupo).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from datetime import datetime
from typing import Any

import numpy as np

from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.causal.unidades import CATEGORICA, GRUPO, NUMERICA, ORDINAL
from pcapp_nucleo.pc_config import ProblemaConfiguracion

SUBIR, BAJAR, AMBAS = "subir", "bajar", "ambas"
DIRECCIONES_OBJETIVO = (SUBIR, BAJAR)
CLASES_POSITIVAS = (0, 1)
DIRECCIONES_ACCION = (SUBIR, BAJAR, AMBAS)
GRADIENTE, GENETICO = "gradiente_proximal", "genetico"
OPTIMIZADORES = (GRADIENTE, GENETICO)
AUTOMATICO = "automatico"
REJILLA_MU = tuple(float(v) for v in np.round(np.logspace(-3, -1, 9), 6))
MARGEN_OBJETIVO = 0.1
FRACCION_CAMBIO_MAXIMO = 0.25
# Una ordinal con más niveles se optimiza como continua.
MAXIMO_NIVELES_DISCRETOS = 10


@dataclass(frozen=True)
class ObjetivoDeseado:
    """``valor``: probabilidad de ``clase_positiva`` (objetivo binario) o valor en unidades originales.

    La dirección y la clase de interés las decide el usuario; ``objetivo_por_defecto`` solo
    las sugiere. ``clase_positiva`` (0 o 1) solo se usa con objetivo binario.
    """

    direccion: str
    valor: float
    clase_positiva: int = 1


@dataclass(frozen=True)
class ConfiguracionAccion:
    """Restricciones de una variable prescriptiva (unidades originales).

    ``estados_permitidos`` (binarias, ordinales discretas y categorías): valores a los que se
    permite pasar; ``None`` = todos. La dirección solo se aplica a las numéricas, ordinales y
    binarias (subir = pasar a un código mayor).
    """

    variable: str
    permitida: bool = True
    direccion: str = AMBAS
    minimo: float | None = None
    maximo: float | None = None
    cambio_maximo: float | None = None
    costo: float = 1.0
    estados_permitidos: list[Any] | None = None


@dataclass(frozen=True)
class Supuestos:
    """Declaración que el usuario confirma para cada variable prescriptiva."""

    modificable_por_decision: bool = False
    medida_antes_del_resultado: bool = False
    no_define_el_objetivo: bool = False
    confirmado_en: str | None = None

    @property
    def confirmados(self) -> bool:
        return (
            self.modificable_por_decision and self.medida_antes_del_resultado and self.no_define_el_objetivo
            and bool(self.confirmado_en)
        )


@dataclass(frozen=True)
class ConfiguracionPrescripcion:
    modificables: list[str]
    objetivo: ObjetivoDeseado
    acciones: dict[str, ConfiguracionAccion]
    supuestos: dict[str, Supuestos] = field(default_factory=dict)
    mu: Any = AUTOMATICO
    optimizador: str = GRADIENTE
    rejilla_mu: list[float] = field(default_factory=lambda: list(REJILLA_MU))
    exito_calibracion: float = 0.95
    arranques_aleatorios: int = 4
    iteraciones_maximas: int = 300
    tolerancia: float = 1e-8
    tau_suavizado: float = 0.25
    poblacion: int = 40
    generaciones: int = 60
    alfa_blx: float = 0.5
    probabilidad_mutacion: float = 0.2
    elite: int = 2


@dataclass(frozen=True)
class VariablesPrescriptivas:
    prescriptivas: list[str]
    sin_camino: list[str]
    desconocidas: list[str]


def nombre_control(modelo: ModeloCausal, variable: str) -> str:
    """Nombre del control de una columna (la categoría si es una dummy one-hot)."""
    return modelo.unidades.grupo_de.get(variable, variable)


def variables_prescriptivas(modelo: ModeloCausal, modificables: list[str]) -> VariablesPrescriptivas:
    ancestros = {nombre_control(modelo, v) for v in modelo.ancestros}
    conocidas = {nombre_control(modelo, v) for v in [*modelo.variables, *modelo.fuera, *modelo.descendientes_objetivo]}
    prescriptivas, sin_camino, desconocidas = [], [], []
    for variable in dict.fromkeys(nombre_control(modelo, m) for m in modificables):
        if variable == modelo.objetivo:
            sin_camino.append(variable)
        elif variable in ancestros:
            prescriptivas.append(variable)
        elif variable in conocidas or variable in modelo.unidades.grupos:
            sin_camino.append(variable)
        else:
            desconocidas.append(variable)
    orden = {nombre_control(modelo, v): i for i, v in enumerate(modelo.variables)}
    return VariablesPrescriptivas(sorted(prescriptivas, key=lambda v: orden.get(v, 0)), sin_camino, desconocidas)


def columnas_de(modelo: ModeloCausal, variable: str) -> list[str]:
    """Columnas del modelo que controla una variable prescriptiva."""
    if variable in modelo.unidades.grupos:
        return [c for c in modelo.unidades.grupos[variable].columnas if c in modelo.info_variables]
    return [variable]


def rango_original(modelo: ModeloCausal, variable: str) -> tuple[float, float] | None:
    """Rango de train en unidades originales (numéricas y ordinales)."""
    if variable not in modelo.info_variables or modelo.unidades.control(variable) not in (NUMERICA, ORDINAL):
        return None
    info = modelo.info_variables[variable]
    return (
        modelo.unidades.a_original_numerico(variable, info["minimo"]),
        modelo.unidades.a_original_numerico(variable, info["maximo"]),
    )


def accion_por_defecto(modelo: ModeloCausal, variable: str) -> ConfiguracionAccion:
    rango = rango_original(modelo, variable)
    if rango is None:
        return ConfiguracionAccion(variable)
    bajo, alto = rango
    return ConfiguracionAccion(
        variable, minimo=bajo, maximo=alto, cambio_maximo=round(FRACCION_CAMBIO_MAXIMO * (alto - bajo), 10),
    )


def objetivo_por_defecto(modelo: ModeloCausal) -> ObjetivoDeseado:
    """Valor inicial SUGERIDO (el usuario lo confirma o lo cambia; nada lo fuerza).

    Binario: la clase de interés es la 1; la dirección sugerida es bajar su probabilidad si es
    la minoritaria (suele ser el evento adverso) y subirla si no, con el umbral de decisión ± 0,1.
    La distribución de clases no dice qué es deseable (p. ej. «aprobado» minoritario se quiere
    subir), por eso es solo una sugerencia."""
    if modelo.binario:
        # La mediana de un objetivo 0/1 es 0 si la clase 1 es la minoritaria.
        minoritaria = modelo.info_variables[modelo.objetivo]["mediana"] < 0.5
        direccion = BAJAR if minoritaria else SUBIR
        umbral = modelo.umbral_decision if modelo.umbral_decision is not None else 0.5
        valor = umbral - MARGEN_OBJETIVO if direccion == BAJAR else umbral + MARGEN_OBJETIVO
        return ObjetivoDeseado(direccion, float(np.clip(round(valor, 6), 0.01, 0.99)))
    info = modelo.info_variables[modelo.objetivo]
    mediana = modelo.unidades.a_original_numerico(modelo.objetivo, info["mediana"])
    rango = modelo.unidades.a_original_numerico(modelo.objetivo, info["maximo"]) - modelo.unidades.a_original_numerico(
        modelo.objetivo, info["minimo"]
    )
    return ObjetivoDeseado(SUBIR, float(mediana + MARGEN_OBJETIVO * rango))


def configuracion_por_defecto(modelo: ModeloCausal, modificables: list[str]) -> ConfiguracionPrescripcion:
    variables = variables_prescriptivas(modelo, modificables)
    return ConfiguracionPrescripcion(
        modificables=list(modificables),
        objetivo=objetivo_por_defecto(modelo),
        acciones={v: accion_por_defecto(modelo, v) for v in variables.prescriptivas},
        supuestos={v: Supuestos() for v in variables.prescriptivas},
    )


def completar(modelo: ModeloCausal, configuracion: ConfiguracionPrescripcion) -> ConfiguracionPrescripcion:
    """Añade acciones y supuestos por defecto a las prescriptivas que no los tengan (p. ej. al
    cambiar la lista de modificables) y quita los de variables que ya no lo son."""
    prescriptivas = variables_prescriptivas(modelo, configuracion.modificables).prescriptivas
    acciones = {v: configuracion.acciones.get(v) or accion_por_defecto(modelo, v) for v in prescriptivas}
    supuestos = {v: configuracion.supuestos.get(v) or Supuestos() for v in prescriptivas}
    return replace(configuracion, acciones=acciones, supuestos=supuestos)


def confirmar_supuestos(configuracion: ConfiguracionPrescripcion, variables: list[str]) -> ConfiguracionPrescripcion:
    """Marca como confirmada la declaración de ``variables`` con la fecha actual."""
    fecha = datetime.now().isoformat(timespec="seconds")
    supuestos = dict(configuracion.supuestos)
    for v in variables:
        supuestos[v] = Supuestos(True, True, True, fecha)
    return replace(configuracion, supuestos=supuestos)


# --- Serialización y validación ---------------------------------------------------------------


class ErrorConfiguracionPrescripcion(ValueError):
    def __init__(self, problemas: list[ProblemaConfiguracion]) -> None:
        super().__init__("; ".join(p.mensaje for p in problemas))
        self.problemas = problemas


def _construir(clase, datos: Any, campo: str, problemas: list[ProblemaConfiguracion]):
    if not isinstance(datos, dict):
        problemas.append(ProblemaConfiguracion(campo, "Debe ser un objeto."))
        return None
    nombres = {f.name for f in fields(clase)}
    desconocidos = sorted(set(datos) - nombres)
    if desconocidos:
        problemas.append(ProblemaConfiguracion(f"{campo}.{desconocidos[0]}" if campo else desconocidos[0], "Campo desconocido."))
        return None
    try:
        return clase(**datos)
    except TypeError as error:
        problemas.append(ProblemaConfiguracion(campo, f"Datos incompletos: {error}."))
        return None


def configuracion_desde_diccionario(datos: dict[str, Any]) -> ConfiguracionPrescripcion:
    """Raises: ErrorConfiguracionPrescripcion con todos los problemas de forma."""
    problemas: list[ProblemaConfiguracion] = []
    datos = dict(datos or {})
    objetivo = _construir(ObjetivoDeseado, datos.get("objetivo"), "objetivo", problemas)
    acciones = {
        v: _construir(ConfiguracionAccion, {"variable": v, **(a or {})}, f"acciones.{v}", problemas)
        for v, a in (datos.get("acciones") or {}).items()
    }
    supuestos = {
        v: _construir(Supuestos, s or {}, f"supuestos.{v}", problemas) for v, s in (datos.get("supuestos") or {}).items()
    }
    resto = {k: v for k, v in datos.items() if k not in ("objetivo", "acciones", "supuestos")}
    if problemas:
        raise ErrorConfiguracionPrescripcion(problemas)
    configuracion = _construir(
        ConfiguracionPrescripcion,
        {**resto, "objetivo": objetivo, "acciones": acciones, "supuestos": supuestos}, "", problemas,
    )
    if problemas:
        raise ErrorConfiguracionPrescripcion(problemas)
    return configuracion


def problemas_configuracion(modelo: ModeloCausal, c: ConfiguracionPrescripcion) -> list[ProblemaConfiguracion]:
    """Errores de contenido (cada uno con su campo)."""
    problemas: list[ProblemaConfiguracion] = []
    if c.objetivo.direccion not in DIRECCIONES_OBJETIVO:
        problemas.append(ProblemaConfiguracion("objetivo.direccion", "Debe ser 'subir' o 'bajar'."))
    if modelo.binario and c.objetivo.clase_positiva not in CLASES_POSITIVAS:
        problemas.append(ProblemaConfiguracion("objetivo.clase_positiva", "Debe ser 0 o 1."))
    if modelo.binario and not 0 < c.objetivo.valor < 1:
        problemas.append(ProblemaConfiguracion("objetivo.valor", "La probabilidad deseada debe estar entre 0 y 1."))
    if c.optimizador not in OPTIMIZADORES:
        problemas.append(ProblemaConfiguracion("optimizador", "Debe ser 'gradiente_proximal' o 'genetico'."))
    if c.mu != AUTOMATICO and (not isinstance(c.mu, (int, float)) or isinstance(c.mu, bool) or c.mu < 0):
        problemas.append(ProblemaConfiguracion("mu", "μ debe ser 'automatico' o un número mayor o igual que 0."))
    if not c.rejilla_mu or any(m <= 0 for m in c.rejilla_mu):
        problemas.append(ProblemaConfiguracion("rejilla_mu", "La rejilla de μ necesita valores positivos."))
    if not 0 < c.exito_calibracion <= 1:
        problemas.append(ProblemaConfiguracion("exito_calibracion", "Debe estar entre 0 y 1."))
    prescriptivas = set(variables_prescriptivas(modelo, c.modificables).prescriptivas)
    for v, a in c.acciones.items():
        campo = f"acciones.{v}"
        if v not in prescriptivas:
            problemas.append(ProblemaConfiguracion(campo, f"'{v}' no es una variable prescriptiva."))
            continue
        if a.direccion not in DIRECCIONES_ACCION:
            problemas.append(ProblemaConfiguracion(f"{campo}.direccion", "Debe ser 'subir', 'bajar' o 'ambas'."))
        if a.costo is None or a.costo <= 0:
            problemas.append(ProblemaConfiguracion(f"{campo}.costo", "El costo debe ser mayor que 0."))
        if a.minimo is not None and a.maximo is not None and a.minimo > a.maximo:
            problemas.append(ProblemaConfiguracion(f"{campo}.minimo", "El mínimo es mayor que el máximo."))
        if a.cambio_maximo is not None and a.cambio_maximo <= 0:
            problemas.append(ProblemaConfiguracion(f"{campo}.cambio_maximo", "El cambio máximo debe ser mayor que 0."))
        control = modelo.unidades.control(modelo.unidades.grupos[v].columnas[0]) if v in modelo.unidades.grupos else modelo.unidades.control(v)
        if a.estados_permitidos is not None and control in (CATEGORICA, GRUPO, ORDINAL):
            validos = _estados_validos(modelo, v)
            malos = [e for e in a.estados_permitidos if not any(_igual(e, x) for x in validos)]
            if malos:
                problemas.append(ProblemaConfiguracion(
                    f"{campo}.estados_permitidos", f"Valores no válidos: {', '.join(map(str, malos))}.",
                ))
    return problemas


def _igual(a: Any, b: Any) -> bool:
    from pcapp_nucleo.preparacion import _mismo_valor

    return _mismo_valor(a, b)


def _estados_validos(modelo: ModeloCausal, variable: str) -> list[Any]:
    if variable in modelo.unidades.grupos:
        return list(modelo.unidades.grupos[variable].categorias)
    return list(modelo.unidades.describir(variable).categorias)

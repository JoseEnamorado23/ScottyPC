"""Contrafactuales por abducción–acción–predicción sobre el modelo causal.

- Abducción: para cada intermedia continua se guarda el residuo aditivo del caso
  (x_obs − f(padres_obs)). Una intermedia binaria se modela como X = 1[η(padres) + U > 0]
  con U logística; se toman ``muestras_abduccion`` valores de U compatibles con el valor
  observado (logística truncada, semilla fija). Es una aproximación de Monte Carlo.
- Acción: «fijar» asigna un valor; «desplazar» suma una cantidad en unidades originales.
  Las dummies one-hot solo se intervienen como categoría (todas a la vez).
- Predicción: se recorre el subgrafo en orden topológico. El objetivo es su probabilidad
  (o valor esperado), sin residuo.

Entrada y salida en unidades originales (se usa la receta para convertir).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit, logit

from pcapp_nucleo.causal.modelo import BINARIA, INTERMEDIA, OBJETIVO, RAIZ, ModeloCausal
from pcapp_nucleo.causal.unidades import CATEGORICA, GRUPO, NUMERICA, ORDINAL, ErrorUnidades

DESPLAZAR, FIJAR = "desplazar", "fijar"
_TOLERANCIA = 1e-9


class ErrorContrafactual(ValueError):
    """Caso o intervención no válidos; ``campo`` indica cuál."""

    def __init__(self, mensaje: str, campo: str | None = None) -> None:
        super().__init__(mensaje)
        self.campo = campo


@dataclass(frozen=True)
class Intervencion:
    variable: str
    tipo: str
    valor: Any


@dataclass(frozen=True)
class AvisoContrafactual:
    codigo: str
    mensaje: str
    variables: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Caso:
    """Valores del subgrafo en unidades preparadas; NaN en una intermedia = no observada."""

    valores: dict[str, float]
    origen: str
    indice: int | None = None
    observado_objetivo: Any = None
    avisos: list[AvisoContrafactual] = field(default_factory=list)


@dataclass(frozen=True)
class ValorContrafactual:
    variable: str
    rol: str
    tipo: str
    grupo: str | None
    antes: Any
    despues: Any
    antes_numerico: float | None
    despues_numerico: float | None
    cambio: float
    intervenida: bool
    extrapolacion: bool
    observado: bool


@dataclass(frozen=True)
class ContribucionPadre:
    padre: str
    contribucion: float


@dataclass(frozen=True)
class PasoTraza:
    variable: str
    causa: str  # "intervencion" | "propagacion"
    antes: float | None
    despues: float | None
    cambio: float
    por_padre: list[ContribucionPadre] = field(default_factory=list)


@dataclass(frozen=True)
class ResultadoContrafactual:
    objetivo: str
    medida: str  # "probabilidad" | "valor"
    antes: float
    despues: float
    cambio: float
    umbral_decision: float | None
    clase_antes: int | None
    clase_despues: int | None
    valores: list[ValorContrafactual]
    traza: list[PasoTraza]
    avisos: list[AvisoContrafactual]
    aproximado: bool
    muestras: int
    extrapolacion: bool
    caso: dict[str, Any]


# --- Casos ------------------------------------------------------------------------------------


def _en_rango(modelo: ModeloCausal, variable: str, valor: float) -> bool:
    info = modelo.info_variables[variable]
    escala = max(info["maximo"] - info["minimo"], 1.0)
    return info["minimo"] - _TOLERANCIA * escala <= valor <= info["maximo"] + _TOLERANCIA * escala


def _completar(modelo: ModeloCausal, valores: dict[str, float], avisos: list[AvisoContrafactual], origen: str) -> None:
    """Raíces faltantes → mediana de train; intermedias faltantes → se predicen sin residuo."""
    raices = [v for v in modelo.ancestros if modelo.info_variables[v]["rol"] == RAIZ and math.isnan(valores.get(v, math.nan))]
    for v in raices:
        valores[v] = modelo.info_variables[v]["mediana"]
    if raices:
        motivo = "El caso no tiene valor en" if origen == "test" else "No se indicó"
        avisos.append(AvisoContrafactual(
            "RAICES_IMPUTADAS", f"{motivo} {', '.join(raices)}: se usa la mediana de entrenamiento.", raices,
        ))
    intermedias = [
        v for v in modelo.ancestros
        if modelo.info_variables[v]["rol"] == INTERMEDIA and math.isnan(valores.get(v, math.nan))
    ]
    for v in intermedias:
        valores[v] = math.nan
    if intermedias:
        avisos.append(AvisoContrafactual(
            "INTERMEDIAS_PREDICHAS",
            f"Sin valor observado para {', '.join(intermedias)}: se usa la predicción de su mecanismo "
            "(sin residuo propio del caso).",
            intermedias,
        ))


def caso_desde_test(modelo: ModeloCausal, test: pd.DataFrame, indice: int) -> Caso:
    """Fila de test por su índice (posición de la fila en los datos originales)."""
    if indice not in test.index:
        raise ErrorContrafactual(f"No hay ninguna fila de test con índice {indice}.", "caso.indice")
    fila = test.loc[indice]
    valores = {v: float(fila[v]) if pd.notna(fila[v]) else math.nan for v in modelo.ancestros}
    avisos: list[AvisoContrafactual] = []
    _completar(modelo, valores, avisos, "test")
    observado = fila[modelo.objetivo]
    return Caso(
        valores, "test", int(indice),
        modelo.unidades.a_original(modelo.objetivo, float(observado)) if pd.notna(observado) else None, avisos,
    )


def caso_desde_valores(modelo: ModeloCausal, valores_originales: dict[str, Any]) -> Caso:
    """Valores escritos por el usuario (unidades originales; categorías por su nombre de grupo)."""
    valores: dict[str, float] = {}
    avisos: list[AvisoContrafactual] = []
    ignoradas, extrapoladas = [], []
    for nombre, valor in valores_originales.items():
        campo = f"caso.valores.{nombre}"
        if valor is None:
            continue
        if nombre == modelo.objetivo:
            continue
        if nombre in modelo.unidades.grupos:
            try:
                dummies = modelo.unidades.dummies_de_categoria(nombre, valor)
            except ErrorUnidades as error:
                raise ErrorContrafactual(str(error), campo) from error
            valores.update({c: x for c, x in dummies.items() if c in modelo.info_variables})
            continue
        if nombre in modelo.unidades.grupo_de:
            raise ErrorContrafactual(
                f"'{nombre}' es una dummy de '{modelo.unidades.grupo_de[nombre]}': indique la categoría del grupo.",
                campo,
            )
        if nombre not in modelo.info_variables:
            if nombre in modelo.fuera or nombre in modelo.descendientes_objetivo:
                ignoradas.append(nombre)
                continue
            raise ErrorContrafactual(f"'{nombre}' no es una variable del modelo.", campo)
        try:
            preparado = modelo.unidades.a_preparada(nombre, valor)
        except ErrorUnidades as error:
            raise ErrorContrafactual(str(error), campo) from error
        if modelo.info_variables[nombre]["tipo"] == BINARIA and preparado not in (
            modelo.info_variables[nombre]["minimo"], modelo.info_variables[nombre]["maximo"]
        ):
            raise ErrorContrafactual(f"'{nombre}' es binaria: use uno de sus dos valores.", campo)
        if not _en_rango(modelo, nombre, preparado):
            extrapoladas.append(nombre)
        valores[nombre] = preparado
    if ignoradas:
        avisos.append(AvisoContrafactual(
            "VARIABLES_IGNORADAS", f"No forman parte del modelo y se ignoran: {', '.join(ignoradas)}.", ignoradas,
        ))
    if extrapoladas:
        avisos.append(AvisoContrafactual(
            "CASO_FUERA_DE_RANGO",
            f"Valores fuera del rango de entrenamiento en {', '.join(extrapoladas)}: el resultado es una extrapolación.",
            extrapoladas,
        ))
    _completar(modelo, valores, avisos, "usuario")
    return Caso(valores, "usuario", None, None, avisos)


# --- Intervenciones ---------------------------------------------------------------------------


@dataclass
class _Accion:
    columnas: dict[str, Any]  # columna → ("fijar", preparado) | ("desplazar", delta original)
    nombre: str
    extrapolada: bool = False


def _resolver(
    modelo: ModeloCausal, intervenciones: list[Intervencion], avisos: list[AvisoContrafactual]
) -> list[_Accion]:
    acciones: list[_Accion] = []
    vistas: set[str] = set()
    sin_efecto: list[str] = []
    for i, intervencion in enumerate(intervenciones):
        campo = f"intervenciones.{i}"
        nombre, tipo = intervencion.variable, intervencion.tipo
        if tipo not in (DESPLAZAR, FIJAR):
            raise ErrorContrafactual("El tipo de intervención debe ser 'desplazar' o 'fijar'.", f"{campo}.tipo")
        if nombre in vistas:
            raise ErrorContrafactual(f"'{nombre}' se interviene más de una vez.", f"{campo}.variable")
        vistas.add(nombre)
        if nombre == modelo.objetivo:
            raise ErrorContrafactual("No se puede intervenir el objetivo.", f"{campo}.variable")
        if nombre in modelo.descendientes_objetivo:
            raise ErrorContrafactual(
                f"'{nombre}' es una consecuencia del objetivo: no se puede intervenir.", f"{campo}.variable"
            )
        if nombre in modelo.unidades.grupo_de:
            raise ErrorContrafactual(
                f"'{nombre}' es una dummy de '{modelo.unidades.grupo_de[nombre]}': intervenga la categoría.",
                f"{campo}.variable",
            )
        if nombre in modelo.unidades.grupos:
            if tipo != FIJAR:
                raise ErrorContrafactual("Una categoría solo se puede fijar.", f"{campo}.tipo")
            try:
                dummies = modelo.unidades.dummies_de_categoria(nombre, intervencion.valor)
            except ErrorUnidades as error:
                raise ErrorContrafactual(str(error), f"{campo}.valor") from error
            en_modelo = {c: (FIJAR, x) for c, x in dummies.items() if c in modelo.info_variables}
            if not en_modelo:
                sin_efecto.append(nombre)
                continue
            acciones.append(_Accion(en_modelo, nombre))
            continue
        if nombre not in modelo.info_variables:
            if nombre in modelo.fuera:
                sin_efecto.append(nombre)
                continue
            raise ErrorContrafactual(f"'{nombre}' no es una variable del grafo.", f"{campo}.variable")
        control = modelo.unidades.control(nombre)
        if tipo == DESPLAZAR:
            if control not in (NUMERICA, ORDINAL):
                raise ErrorContrafactual(f"'{nombre}' es categórica: solo se puede fijar.", f"{campo}.tipo")
            try:
                delta = float(intervencion.valor)
            except (TypeError, ValueError) as error:
                raise ErrorContrafactual("El desplazamiento debe ser un número.", f"{campo}.valor") from error
            if not math.isfinite(delta):
                raise ErrorContrafactual("El desplazamiento debe ser un número finito.", f"{campo}.valor")
            acciones.append(_Accion({nombre: (DESPLAZAR, delta)}, nombre))
            continue
        try:
            preparado = modelo.unidades.a_preparada(nombre, intervencion.valor)
        except ErrorUnidades as error:
            raise ErrorContrafactual(str(error), f"{campo}.valor") from error
        if control == CATEGORICA and modelo.info_variables[nombre]["tipo"] == BINARIA and preparado not in (
            modelo.info_variables[nombre]["minimo"], modelo.info_variables[nombre]["maximo"]
        ):
            raise ErrorContrafactual(f"'{nombre}' es binaria: use uno de sus dos valores.", f"{campo}.valor")
        acciones.append(_Accion({nombre: (FIJAR, preparado)}, nombre))
    if sin_efecto:
        avisos.append(AvisoContrafactual(
            "SIN_EFECTO",
            f"{', '.join(sin_efecto)} no {'es ancestro' if len(sin_efecto) == 1 else 'son ancestros'} del "
            "objetivo: intervenir no tiene efecto sobre él (cambio cero).",
            sin_efecto,
        ))
    return acciones


def _desplazar(modelo: ModeloCausal, variable: str, base: np.ndarray, delta: float, campo: str) -> np.ndarray:
    unidades = modelo.unidades
    try:
        return np.array([unidades.a_preparada(variable, unidades.a_original_numerico(variable, x) + delta) for x in base])
    except ErrorUnidades as error:
        raise ErrorContrafactual(str(error), campo) from error


# --- Motor ------------------------------------------------------------------------------------


def _muestras_ruido(eta: np.ndarray, observado: float, rng: np.random.Generator) -> np.ndarray:
    """U logística compatible con X = observado (truncada), o sin truncar si no se observó."""
    r = rng.uniform(size=eta.shape)
    if math.isnan(observado):
        p = r
    else:
        corte = expit(-eta)  # P(U <= -η)
        p = corte + r * (1 - corte) if observado >= 0.5 else r * corte
    return logit(np.clip(p, 1e-15, 1 - 1e-15))


def _resumen(modelo: ModeloCausal, variable: str, vector: np.ndarray) -> tuple[Any, float]:
    """(valor para mostrar, valor numérico) en unidades originales."""
    if variable == modelo.objetivo and modelo.binario:
        valor = float(np.mean(vector))
        return valor, valor
    if modelo.tipo(variable) == BINARIA:
        media = float(np.mean(vector))
        if np.all(vector == vector[0]):
            return modelo.unidades.a_original(variable, float(vector[0])), modelo.unidades.a_original_numerico(variable, float(vector[0]))
        return media, modelo.unidades.a_original_numerico(variable, media)
    numericos = np.array([modelo.unidades.a_original_numerico(variable, float(x)) for x in vector])
    if np.all(vector == vector[0]):
        return modelo.unidades.a_original(variable, float(vector[0])), float(numericos[0])
    return float(numericos.mean()), float(numericos.mean())


def contrafactual(modelo: ModeloCausal, caso: Caso, intervenciones: list[Intervencion]) -> ResultadoContrafactual:
    avisos = list(caso.avisos)
    acciones = _resolver(modelo, intervenciones, avisos)
    binarias_intermedias = [
        v for v in modelo.variables if modelo.info_variables[v]["rol"] == INTERMEDIA and modelo.tipo(v) == BINARIA
    ]
    muestras = modelo.muestras_abduccion if binarias_intermedias else 1
    rng = np.random.default_rng(modelo.semilla)
    objetivo = modelo.objetivo

    # Abducción: valores factuales (vectores de muestras) y ruido de cada intermedia.
    antes: dict[str, np.ndarray] = {}
    residuos: dict[str, np.ndarray] = {}
    observado: dict[str, bool] = {}
    for v in modelo.variables:
        rol = modelo.info_variables[v]["rol"]
        if rol == RAIZ:
            antes[v] = np.full(muestras, caso.valores[v])
            observado[v] = True
            continue
        mecanismo = modelo.mecanismos[v]
        eta = mecanismo.eta(np.column_stack([antes[p] for p in modelo.padres[v]]))
        if rol == OBJETIVO:
            antes[v] = mecanismo.media(np.column_stack([antes[p] for p in modelo.padres[v]]))
            observado[v] = False
            continue
        x = caso.valores.get(v, math.nan)
        observado[v] = not math.isnan(x)
        if modelo.tipo(v) == BINARIA:
            residuos[v] = _muestras_ruido(eta, x, rng)
            antes[v] = (eta + residuos[v] > 0).astype(float)
        else:
            residuos[v] = (x - eta) if observado[v] else np.zeros(muestras)
            antes[v] = eta + residuos[v]

    # Acción.
    fijadas: dict[str, np.ndarray] = {}
    intervenidas: dict[str, str] = {}
    extrapoladas: list[str] = []
    for accion in acciones:
        for columna, (tipo, valor) in accion.columnas.items():
            if tipo == FIJAR:
                vector = np.full(muestras, float(valor))
            else:
                vector = _desplazar(modelo, columna, antes[columna], valor, f"intervenciones.{accion.nombre}")
            fijadas[columna] = vector
            intervenidas[columna] = accion.nombre
            if not all(_en_rango(modelo, columna, float(x)) for x in vector):
                extrapoladas.append(columna)

    # Predicción.
    despues: dict[str, np.ndarray] = {}

    def valor_con(v: str, padres_valores: dict[str, np.ndarray]) -> np.ndarray:
        mecanismo = modelo.mecanismos[v]
        X = np.column_stack([padres_valores[p] for p in modelo.padres[v]])
        if v == objetivo:
            return mecanismo.media(X)
        eta = mecanismo.eta(X)
        if modelo.tipo(v) == BINARIA:
            return (eta + residuos[v] > 0).astype(float)
        return eta + residuos[v]

    for v in modelo.variables:
        if v in fijadas:
            despues[v] = fijadas[v]
        elif modelo.info_variables[v]["rol"] == RAIZ:
            despues[v] = antes[v]
        else:
            despues[v] = valor_con(v, despues)

    # Resultados en unidades originales.
    valores, traza = [], []
    propagadas_fuera = []
    for v in modelo.variables:
        rol = modelo.info_variables[v]["rol"]
        valor_antes, numero_antes = _resumen(modelo, v, antes[v])
        valor_despues, numero_despues = _resumen(modelo, v, despues[v])
        cambio = numero_despues - numero_antes
        escala = max(abs(numero_antes), 1.0)
        cambio = 0.0 if abs(cambio) <= 1e-12 * escala else cambio
        extrapolada = v in extrapoladas
        if (
            v not in fijadas and rol == INTERMEDIA and modelo.tipo(v) != BINARIA and cambio != 0.0
            and not _en_rango(modelo, v, float(np.mean(despues[v])))
        ):
            extrapolada = True
            propagadas_fuera.append(v)
        valores.append(ValorContrafactual(
            variable=v, rol=rol, tipo=modelo.tipo(v), grupo=modelo.unidades.grupo_de.get(v),
            antes=valor_antes, despues=valor_despues, antes_numerico=numero_antes, despues_numerico=numero_despues,
            cambio=cambio, intervenida=v in fijadas, extrapolacion=extrapolada, observado=observado[v],
        ))
        if v in fijadas:
            traza.append(PasoTraza(v, "intervencion", numero_antes, numero_despues, cambio))
            continue
        if rol == RAIZ or cambio == 0.0:
            continue
        por_padre = []
        base = valor_con(v, antes) if rol != OBJETIVO else antes[v]
        for p in modelo.padres[v]:
            if np.array_equal(antes[p], despues[p]):
                continue
            mezcla = {**antes, p: despues[p]}
            solo_p = valor_con(v, mezcla)
            _, numero_solo = _resumen(modelo, v, solo_p)
            _, numero_base = _resumen(modelo, v, base)
            por_padre.append(ContribucionPadre(p, numero_solo - numero_base))
        traza.append(PasoTraza(v, "propagacion", numero_antes, numero_despues, cambio, por_padre))

    if extrapoladas:
        nombres = sorted({intervenidas[c] for c in extrapoladas})
        avisos.append(AvisoContrafactual(
            "EXTRAPOLACION",
            f"La intervención en {', '.join(nombres)} sale del rango observado en entrenamiento: el resultado "
            "es una extrapolación.",
            nombres,
        ))
    if propagadas_fuera:
        avisos.append(AvisoContrafactual(
            "EXTRAPOLACION_PROPAGADA",
            f"Tras la propagación, {', '.join(propagadas_fuera)} queda fuera del rango de entrenamiento.",
            propagadas_fuera,
        ))
    if binarias_intermedias:
        avisos.append(AvisoContrafactual(
            "APROXIMADO",
            f"Hay intermedias binarias ({', '.join(binarias_intermedias)}): el contrafactual promedia "
            f"{muestras} muestras del ruido compatible con el caso (aproximación de Monte Carlo, semilla fija).",
            binarias_intermedias,
        ))

    antes_obj, despues_obj = float(np.mean(antes[objetivo])), float(np.mean(despues[objetivo]))
    if not modelo.binario:
        antes_obj = modelo.unidades.a_original_numerico(objetivo, antes_obj)
        despues_obj = modelo.unidades.a_original_numerico(objetivo, despues_obj)
    umbral = modelo.umbral_decision
    cambio_obj = despues_obj - antes_obj
    return ResultadoContrafactual(
        objetivo=objetivo,
        medida="probabilidad" if modelo.binario else "valor",
        antes=antes_obj,
        despues=despues_obj,
        cambio=0.0 if abs(cambio_obj) <= 1e-12 else cambio_obj,
        umbral_decision=umbral,
        clase_antes=int(antes_obj >= umbral) if umbral is not None else None,
        clase_despues=int(despues_obj >= umbral) if umbral is not None else None,
        valores=valores,
        traza=traza,
        avisos=avisos,
        aproximado=bool(binarias_intermedias),
        muestras=muestras,
        extrapolacion=bool(extrapoladas or propagadas_fuera),
        caso={"origen": caso.origen, "indice": caso.indice, "observado_objetivo": caso.observado_objetivo},
    )

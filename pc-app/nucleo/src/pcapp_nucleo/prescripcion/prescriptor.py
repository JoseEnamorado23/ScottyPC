"""Prescripción de un caso: acciones, logro, contribuciones, marcas y explicación.

Si el objetivo no se puede alcanzar con las restricciones, se devuelve la mejor solución posible
(la que más se acerca, sin penalizar el costo), cuánto falta y qué restricciones lo impiden.
Un caso que ya cumple el objetivo no recibe ninguna acción.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pcapp_nucleo.causal.configuracion import decimal
from pcapp_nucleo.causal.contrafactuales import (
    AvisoContrafactual, Caso, PasoTraza, ValorContrafactual, contrafactual_preparado,
)
from pcapp_nucleo.causal.modelo import INTERMEDIA, ModeloCausal
from pcapp_nucleo.prescripcion.configuracion import BAJAR, ConfiguracionPrescripcion, SUBIR
from pcapp_nucleo.prescripcion.optimizadores import Optimizador, Solucion, crear_optimizador, optimizar_caso
from pcapp_nucleo.prescripcion.problema import CAMBIO_MAXIMO, DIRECCION, LIMITE, ProblemaPrescripcion
from pcapp_nucleo.prescripcion.referencia import ModeloReferencia

PASO_RELAJACION = 0.05
# Cambio (en la escala normalizada) por debajo del cual fijar una intermedia es «mantenerla».
UMBRAL_MANTENER = 1e-4
ESTADOS_PERMITIDOS = "estados_permitidos"
MENSAJES_RESTRICCION = {
    LIMITE: "está en su límite absoluto",
    CAMBIO_MAXIMO: "está en su cambio máximo",
    DIRECCION: "solo se permite moverla en la otra dirección",
    ESTADOS_PERMITIDOS: "el valor que ayudaría no está entre los permitidos",
}


@dataclass(frozen=True)
class AccionPrescrita:
    variable: str
    tipo: str  # "continua" | "discreta"
    antes: Any
    despues: Any
    antes_numerico: float | None
    despues_numerico: float | None
    cambio: float | None
    contribucion: float
    restriccion_activa: str | None = None
    extrapolacion: bool = False
    # Intervenir una intermedia con un cambio despreciable equivale a mantenerla constante:
    # corta el efecto que le llegaría de las demás acciones.
    mantener: bool = False


@dataclass(frozen=True)
class RestriccionActiva:
    variable: str
    restriccion: str
    mensaje: str


@dataclass(frozen=True)
class ResultadoPrescripcion:
    caso: dict[str, Any]
    objetivo: str
    medida: str
    direccion: str
    clase_positiva: int
    deseado: float
    antes: float
    despues: float
    alcanzado: bool
    ya_cumple: bool
    falta: float
    acciones: list[AccionPrescrita]
    sin_cambio: list[str]
    restricciones_activas: list[RestriccionActiva]
    extrapolacion: bool
    aproximado: bool
    requiere_revision: bool
    referencia: dict[str, Any]
    explicacion: str
    costo_total: float
    optimizador: str
    mu: float
    segundos: float
    traza: list[PasoTraza] = field(default_factory=list)
    valores: list[ValorContrafactual] = field(default_factory=list)
    avisos: list[AvisoContrafactual] = field(default_factory=list)


def semilla_de_caso(modelo: ModeloCausal, caso: Caso) -> np.random.SeedSequence:
    """Semilla derivada de la del modelo y del caso (índice de la fila o sus valores)."""
    if caso.indice is not None:
        clave = int(caso.indice)
    else:
        texto = json.dumps({k: (None if v != v else round(v, 12)) for k, v in sorted(caso.valores.items())})
        clave = zlib.crc32(texto.encode("utf-8"))
    return np.random.SeedSequence([int(modelo.semilla), clave])


# --- Formato -----------------------------------------------------------------------------------


def numero(valor: float) -> str:
    if valor is None:
        return "—"
    absoluto = abs(valor)
    if 0 < absoluto < 0.01:  # cambios pequeños: dos cifras significativas en vez de «0»
        return decimal(valor, ".2g")
    decimales = 0 if absoluto >= 100 else 1 if absoluto >= 10 else 2
    texto = decimal(valor, f".{decimales}f")
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


def _etiqueta(valor: Any) -> str:
    return numero(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else str(valor)


def _lista(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def _frase_accion(a: AccionPrescrita) -> str:
    if a.mantener:
        return f"Mantener {a.variable} en {_etiqueta(a.antes)} (sin que cambie por las demás acciones)"
    if a.tipo == "continua" and a.cambio is not None:
        verbo = "Aumentar" if a.cambio > 0 else "Reducir"
        signo = "+" if a.cambio > 0 else "−"
        return f"{verbo} {a.variable} de {_etiqueta(a.antes)} a {_etiqueta(a.despues)} ({signo}{numero(abs(a.cambio))})"
    return f"Cambiar {a.variable} de {_etiqueta(a.antes)} a {_etiqueta(a.despues)}"


def explicar(r: ResultadoPrescripcion) -> str:
    cantidad = f"la probabilidad de {r.objetivo}={r.clase_positiva}" if r.medida == "probabilidad" else f"el valor esperado de {r.objetivo}"
    formato = (lambda x: decimal(x, ".2f")) if r.medida == "probabilidad" else numero
    comparador = "≤" if r.direccion == BAJAR else "≥"
    if r.ya_cumple:
        return (
            f"El caso ya cumple el objetivo ({cantidad} es {formato(r.antes)} {comparador} {formato(r.deseado)}): "
            "no se prescribe ningún cambio."
        )
    if not r.acciones:
        texto = f"Ninguna acción permitida mejora {cantidad} ({formato(r.antes)}); el objetivo ({formato(r.deseado)}) no es alcanzable."
    else:
        frases = [_frase_accion(a) for a in r.acciones]
        primera = frases[0]
        resto = [f[0].lower() + f[1:] for f in frases[1:]]
        verbo = "baja" if r.despues < r.antes else "sube"
        texto = f"{_lista([primera, *resto])}. Con esto, {cantidad} {verbo} de {formato(r.antes)} a {formato(r.despues)}."
        if not r.alcanzado:
            texto += f" No alcanza el objetivo ({formato(r.deseado)}): faltan {formato(r.falta)}."
    if not r.alcanzado and r.restricciones_activas:
        texto += " Lo impiden: " + "; ".join(f"{x.variable} {x.mensaje}" for x in r.restricciones_activas) + "."
    return texto


# --- Prescripción --------------------------------------------------------------------------------


def _fijadas(problema: ProblemaPrescripcion, s: Solucion) -> tuple[dict[str, float], dict[str, str]]:
    fijadas, nombres = {}, {}
    for i, a in enumerate(problema.continuas):
        if s.d[i] != 0:
            fijadas[a.columna] = a.x0 + s.d[i] * a.escala
            nombres[a.columna] = a.nombre
    for j, a in enumerate(problema.discretas):
        if s.estado[j] != a.actual:
            for c in a.columnas:
                fijadas[c] = a.estados[s.estado[j]][c]
                nombres[c] = a.nombre
    return fijadas, nombres


def _exacta(problema: ProblemaPrescripcion, s: Solucion) -> float:
    return float(problema.p([s.d], [s.estado])[0])


def _logro(problema: ProblemaPrescripcion, p: np.ndarray) -> np.ndarray:
    return p if problema.direccion == SUBIR else -p


def _a_medida(modelo: ModeloCausal, p: float) -> float:
    return p if modelo.binario else modelo.unidades.a_original_numerico(modelo.objetivo, p)


def _restricciones_activas(problema: ProblemaPrescripcion, s: Solucion) -> list[RestriccionActiva]:
    """Restricciones que, relajadas un poco, acercarían el caso al objetivo."""
    base = float(problema.brecha(np.array([_exacta(problema, s)]))[0])
    activas: list[RestriccionActiva] = []
    candidatos, motivos = [], []
    for i, a in enumerate(problema.continuas):
        for lado, tope, motivo in ((1, a.hi, a.motivo_hi), (-1, a.lo, a.motivo_lo)):
            if motivo and abs(s.d[i] - tope) < 1e-9:
                d = s.d.copy()
                d[i] = tope + lado * PASO_RELAJACION
                candidatos.append((d, s.estado, None))
                motivos.append((a.nombre, motivo))
    D, E = problema.matrices([c[0] for c in candidatos], [c[1] for c in candidatos])
    if len(D):
        brechas = problema.brecha(problema.p(D, E))
        for (nombre, motivo), brecha in zip(motivos, brechas):
            if brecha < base - 1e-9:
                activas.append(RestriccionActiva(nombre, motivo, MENSAJES_RESTRICCION[motivo]))
    fijadas_base, _ = _fijadas(problema, s)
    for a in problema.discretas:
        for excluido in a.excluidos:
            fijadas = {**fijadas_base, **excluido}
            valores = {c: (np.array([v]), np.array([True])) for c, v in fijadas.items()}
            p = problema.a_clase(problema.evaluador.objetivo(valores, 1))
            if float(problema.brecha(p)[0]) < base - 1e-9:
                activas.append(RestriccionActiva(a.nombre, ESTADOS_PERMITIDOS, MENSAJES_RESTRICCION[ESTADOS_PERMITIDOS]))
                break
    vistas, unicas = set(), []
    for r in activas:
        if (r.variable, r.restriccion) not in vistas:
            vistas.add((r.variable, r.restriccion))
            unicas.append(r)
    return unicas


def _contribuciones(problema: ProblemaPrescripcion, s: Solucion) -> dict[str, float]:
    """Cuánto baja el logro si se quita solo esa acción (con las demás aplicadas)."""
    filas, nombres = [], []
    for i, a in enumerate(problema.continuas):
        if s.d[i] != 0:
            d = s.d.copy()
            d[i] = 0.0
            filas.append((d, s.estado))
            nombres.append(a.nombre)
    for j, a in enumerate(problema.discretas):
        if s.estado[j] != a.actual:
            estado = list(s.estado)
            estado[j] = a.actual
            filas.append((s.d.copy(), tuple(estado)))
            nombres.append(a.nombre)
    if not filas:
        return {}
    D, E = problema.matrices([f[0] for f in filas], [f[1] for f in filas])
    modelo = problema.modelo
    completo = _a_medida(modelo, _exacta(problema, s))
    sin = [_a_medida(modelo, float(p)) for p in problema.p(D, E)]
    signo = 1.0 if problema.direccion == SUBIR else -1.0
    return {n: signo * (completo - x) for n, x in zip(nombres, sin)}


def _perfil_referencia(
    problema: ProblemaPrescripcion, fila: pd.DataFrame | None, fijadas: dict[str, float], referencia: ModeloReferencia
) -> pd.DataFrame:
    """Todas las variables tras la intervención: el subgrafo propagado y el resto como en el caso."""
    modelo = problema.modelo
    base = fila.copy() if fila is not None else pd.DataFrame([dict(zip(referencia.columnas, referencia.medianas))])
    valores = {c: (np.array([v]), np.array([True])) for c, v in fijadas.items()}
    propagados = problema.evaluador.valores(valores, 1)
    for v in modelo.variables:
        if v != modelo.objetivo:
            base[v] = float(propagados[v].mean())
    return base


def prescribir_caso(
    modelo: ModeloCausal,
    caso: Caso,
    configuracion: ConfiguracionPrescripcion,
    mu: float,
    referencia: ModeloReferencia | None = None,
    fila: pd.DataFrame | None = None,
    optimizador: Optimizador | None = None,
    problema: ProblemaPrescripcion | None = None,
) -> ResultadoPrescripcion:
    """Prescripción de ``caso`` con ``mu``. ``fila`` (todas las columnas preparadas del caso)
    permite evaluar el modelo de referencia sobre el perfil propagado."""
    optimizador = optimizador or crear_optimizador(configuracion.optimizador, configuracion)
    problema = problema or ProblemaPrescripcion(modelo, caso, configuracion, mu)
    semilla = semilla_de_caso(modelo, caso)
    ceros = Solucion(np.zeros(problema.k), problema.actual, 0.0, 0.0)
    p_antes = _exacta(problema, ceros)
    segundos = 0.0
    if problema.alcanzado(p_antes):
        solucion, ya_cumple = ceros, True
    else:
        ya_cumple = False
        solucion, segundos = optimizar_caso(problema, optimizador, semilla)
        if not problema.alcanzado(_exacta(problema, solucion)):
            # Mejor solución posible: sin penalizar el costo.
            sin_costo = problema.con_mu(0.0)
            alternativa, extra = optimizar_caso(sin_costo, optimizador, semilla, solucion)
            segundos += extra
            if problema.brecha(np.array([_exacta(problema, alternativa)]))[0] < problema.brecha(
                np.array([_exacta(problema, solucion)])
            )[0] - 1e-12:
                solucion = alternativa
    p_despues = _exacta(problema, solucion)
    alcanzado = problema.alcanzado(p_despues)
    fijadas, nombres = _fijadas(problema, solucion)
    contrafactual = contrafactual_preparado(modelo, caso, fijadas, nombres, problema.abduccion)
    restricciones = [] if alcanzado or ya_cumple else _restricciones_activas(problema, solucion)
    por_restriccion = {r.variable: r.restriccion for r in restricciones}
    contribuciones = _contribuciones(problema, solucion)

    valores = {v.variable: v for v in contrafactual.valores}
    acciones, sin_cambio = [], []
    for i, a in enumerate(problema.continuas):
        if solucion.d[i] == 0:
            sin_cambio.append(a.nombre)
            continue
        v = valores[a.columna]
        mantener = abs(solucion.d[i]) < UMBRAL_MANTENER and modelo.info_variables[a.columna]["rol"] == INTERMEDIA
        acciones.append(AccionPrescrita(
            a.nombre, "continua", v.antes, v.despues, v.antes_numerico, v.despues_numerico, v.cambio,
            contribuciones.get(a.nombre, 0.0), por_restriccion.get(a.nombre), v.extrapolacion, mantener,
        ))
    for j, a in enumerate(problema.discretas):
        if solucion.estado[j] == a.actual:
            sin_cambio.append(a.nombre)
            continue
        antes, despues = a.etiquetas[a.actual], a.etiquetas[solucion.estado[j]]
        acciones.append(AccionPrescrita(
            a.nombre, "discreta", antes, despues, None, None, None, contribuciones.get(a.nombre, 0.0),
            por_restriccion.get(a.nombre), False,
        ))
    acciones.sort(key=lambda x: -x.contribucion)
    sin_cambio.extend(sorted(
        n for n in (configuracion.acciones or {}) if not configuracion.acciones[n].permitida and n not in sin_cambio
    ))

    antes_medida, despues_medida = _a_medida(modelo, p_antes), _a_medida(modelo, p_despues)
    deseado = configuracion.objetivo.valor
    falta = 0.0 if alcanzado else abs(deseado - despues_medida)
    requiere_revision, datos_referencia = False, {}
    if referencia is not None:
        perfil = _perfil_referencia(problema, fila, fijadas, referencia)
        p_ref = float(problema.a_clase(referencia.predecir(perfil))[0])
        alcanzado_ref = problema.alcanzado(p_ref)
        requiere_revision = alcanzado_ref != (alcanzado or ya_cumple)
        datos_referencia = {"despues": _a_medida(modelo, p_ref), "alcanzado": alcanzado_ref}
    costo = float(problema.con_mu(1.0).penalizacion(*problema.matrices([solucion.d], [solucion.estado]))[0])
    resultado = ResultadoPrescripcion(
        caso={"origen": caso.origen, "indice": caso.indice},
        objetivo=modelo.objetivo,
        medida="probabilidad" if modelo.binario else "valor",
        direccion=configuracion.objetivo.direccion,
        clase_positiva=problema.clase_positiva,
        deseado=deseado,
        antes=antes_medida,
        despues=despues_medida,
        alcanzado=alcanzado or ya_cumple,
        ya_cumple=ya_cumple,
        falta=falta,
        acciones=acciones,
        sin_cambio=sin_cambio,
        restricciones_activas=restricciones,
        extrapolacion=any(a.extrapolacion for a in acciones) or contrafactual.extrapolacion,
        aproximado=contrafactual.aproximado,
        requiere_revision=requiere_revision,
        referencia=datos_referencia,
        explicacion="",
        costo_total=costo,
        optimizador=optimizador.nombre,
        mu=problema.mu,
        segundos=round(segundos, 4),
        traza=contrafactual.traza,
        valores=contrafactual.valores,
        avisos=contrafactual.avisos,
    )
    return _con_explicacion(resultado)


def _con_explicacion(r: ResultadoPrescripcion) -> ResultadoPrescripcion:
    from dataclasses import replace

    return replace(r, explicacion=explicar(r))

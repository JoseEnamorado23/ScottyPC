"""Explicación de la prescripción: calibración de μ y la prescripción de un caso.

- **Calibración**: parte de la rejilla guardada (éxitos por μ sobre los casos alcanzables de
  train) y reevalúa la regla de elección con otro porcentaje de éxito, sin recalcular nada.
- **Caso**: ejecuta ``prescribir_caso`` exactamente como la pantalla de Prescripción (misma
  semilla, mismo resultado) y descompone la función objetivo en el punto de partida y en la
  solución:

      pérdida = max(0, brecha)² + μ · (Σ costo_i · |d_i| + Σ costo_j · [estado_j ≠ actual_j])

  La solución (los d_i y los estados) se reconstruye desde los valores del contrafactual, y se
  comprueba que reproduce el logro devuelto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pcapp_nucleo.causal.contrafactuales import Caso
from pcapp_nucleo.causal.modelo import ModeloCausal
from pcapp_nucleo.formulas.traza import (
    ORIGEN_CALCULADO,
    ORIGEN_DATASET,
    ORIGEN_UMBRAL,
    PasoFormula,
    Termino,
    Umbral,
    num,
    texto,
)
from pcapp_nucleo.prescripcion.configuracion import (
    SUBIR,
    ConfiguracionPrescripcion,
    _igual,
    variables_prescriptivas,
)
from pcapp_nucleo.prescripcion.prescriptor import ResultadoPrescripcion, prescribir_caso
from pcapp_nucleo.prescripcion.problema import CAMBIO_MAXIMO, DIRECCION, LIMITE, ProblemaPrescripcion
from pcapp_nucleo.prescripcion.referencia import ModeloReferencia

_GE, _LE = r"\ge", r"\le"
_SIN_LIMITE = 10.0  # ``_accion_continua`` usa ±10 cuando no hay restricción en ese lado
_MOTIVOS = {LIMITE: "límite", CAMBIO_MAXIMO: "cambio máximo", DIRECCION: "dirección"}
_TOLERANCIA_LOGRO = 1e-6


# --- Calibración de μ -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PuntoExplicado:
    mu: float
    tasa: float | None
    exitos: int
    evaluados: int
    cumple: bool
    elegido: bool


@dataclass(frozen=True)
class TrazaCalibracion:
    mu: float
    mu_guardado: float
    cambia: bool
    exito_requerido: float
    casos: int
    ya_cumplen: int
    alcanzables: int
    no_alcanzables: int
    puntos: list[PuntoExplicado]
    pasos: list[PasoFormula]
    resumen: str
    advertencia: str | None
    nota: str | None
    umbrales: list[Umbral]


def explicar_calibracion(calibracion: dict[str, Any], exito: float | None = None) -> TrazaCalibracion:
    """Regla de elección de μ sobre la rejilla guardada. ``ValueError`` si ``exito`` no es válido."""
    original = float(calibracion["exito_requerido"])
    exito = original if exito is None else float(exito)
    if not 0 < exito <= 1:
        raise ValueError("El porcentaje de éxito debe estar entre 0 y 1.")
    n = int(calibracion["alcanzables"])
    rejilla = sorted(calibracion["rejilla"], key=lambda p: p["mu"])
    minimo = exito * n - 1e-9
    validos = [p["mu"] for p in rejilla if n and p["exitos"] >= minimo]
    elegido = max(validos) if validos else rejilla[0]["mu"]
    advertencia = None
    if n == 0:
        advertencia = "Ningún caso de entrenamiento que no cumple el objetivo lo puede alcanzar: se usa el μ más pequeño."
    elif not validos:
        advertencia = f"Con ningún μ alcanza el objetivo al menos el {100 * exito:.0f} % de los casos alcanzables: se usa el más pequeño."
    puntos = [
        PuntoExplicado(p["mu"], p["tasa_exito"], p["exitos"], p["evaluados"], p["mu"] in validos, p["mu"] == elegido)
        for p in rejilla
    ]
    elegido_p = next(p for p in puntos if p.elegido)
    pasos = [
        PasoFormula(
            "casos", "1. Casos de entrenamiento que cuentan",
            r"A=\{i\in\text{train}:\ \text{no cumple}\ \land\ \text{alcanza con }\mu=0\}",
            rf"|\text{{train}}|={calibracion['casos'] + calibracion['casos_que_ya_cumplen']},\ "
            rf"\text{{ya cumplen}}={calibracion['casos_que_ya_cumplen']},\ |A|={n},\ \text{{inalcanzables}}={calibracion['no_alcanzables']}",
            "Los casos que ya cumplen no necesitan acción y los inalcanzables (ni sin costo llegan) no dicen nada sobre μ.",
            terminos=[Termino("|A|", "casos alcanzables", str(n), ORIGEN_DATASET)],
        ),
        PasoFormula(
            "tasa", "2. Tasa de éxito con cada μ",
            r"\text{tasa}(\mu)=\frac{\#\{i\in A:\ \text{alcanza el objetivo con }\mu\}}{|A|}",
            rf"\text{{tasa}}({num(elegido_p.mu, 4)})=\frac{{{elegido_p.exitos}}}{{{n}}}={num(elegido_p.tasa)}" if n else None,
            "Un μ mayor penaliza más el costo: las acciones se acortan y algunos casos dejan de llegar.",
        ),
        PasoFormula(
            "regla", "3. Elección",
            r"\mu^*=\max\{\mu\in\text{rejilla}:\ \text{tasa}(\mu)\ge s\}",
            rf"s={num(exito, 2)}\ \Rightarrow\ \mu^*={num(elegido, 4)}",
            f"Se elige el μ más grande (la intervención más pequeña) que mantiene el éxito en al menos el {100 * exito:.0f} %.",
            cumple=bool(validos),
            terminos=[Termino("s", "éxito requerido", texto(exito), ORIGEN_UMBRAL)],
        ),
    ]
    guardado = float(calibracion["mu"])
    cambia = abs(elegido - guardado) > 1e-12
    resumen = f"μ* = {texto(elegido, 4)}" + (f" (el guardado es {texto(guardado, 4)})." if cambia else ".")
    return TrazaCalibracion(
        elegido, guardado, cambia, exito, int(calibracion["casos"]), int(calibracion["casos_que_ya_cumplen"]), n,
        int(calibracion["no_alcanzables"]), puntos, pasos, resumen, advertencia, calibracion.get("nota"),
        [Umbral("exito_calibracion", "s", "Porcentaje de casos alcanzables que deben llegar al objetivo",
                exito, original, 0.5, 1.0, 0.01)],
    )


# --- Prescripción de un caso ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class AccionExplicada:
    variable: str
    tipo: str  # "continua" | "discreta"
    cambia: bool
    antes: str
    despues: str
    d: float | None
    costo: float
    penalizacion: float  # μ · costo · |d|  (o μ · costo si cambia de estado)
    contribucion: float | None
    restriccion_activa: str | None
    pasos: list[PasoFormula] = field(default_factory=list)


@dataclass(frozen=True)
class EntradaPrescripcion:
    nombre: str
    valor: str
    usada: bool
    nota: str


@dataclass(frozen=True)
class TrazaCaso:
    indice: int | None
    medida: str
    direccion: str
    deseado: float
    antes: float
    despues: float
    alcanzado: bool
    ya_cumple: bool
    mu: float
    optimizador: str
    explicacion: str
    fundamentos: list[PasoFormula]
    perdida: list[PasoFormula]
    acciones: list[AccionExplicada]
    entradas: list[EntradaPrescripcion]
    restricciones: list[str]
    avisos: list[str]


def _etiqueta(valor: Any) -> str:
    if isinstance(valor, float):
        return texto(valor, 4) or ""
    return "—" if valor is None else str(valor)


def _solucion(problema: ProblemaPrescripcion, r: ResultadoPrescripcion) -> tuple[np.ndarray, tuple[int, ...]]:
    """d y estados de la solución, reconstruidos desde los valores del contrafactual."""
    u = problema.modelo.unidades
    despues = {v.variable: v for v in r.valores}
    d = np.zeros(problema.k)
    for i, a in enumerate(problema.continuas):
        valor = despues.get(a.columna)
        if valor is not None and valor.intervenida and valor.despues_numerico is not None:
            d[i] = (u.a_preparada(a.columna, valor.despues_numerico) - a.x0) / a.escala
    por_nombre = {a.variable: a for a in r.acciones if a.tipo == "discreta"}
    estados = []
    for a in problema.discretas:
        accion = por_nombre.get(a.nombre)
        if accion is None:
            estados.append(a.actual)
        else:
            estados.append(next((k for k, e in enumerate(a.etiquetas) if _igual(e, accion.despues)), a.actual))
    return d, tuple(estados)


def _perdida(problema: ProblemaPrescripcion, d: np.ndarray, estados: tuple[int, ...], titulo: str, id_: str) -> PasoFormula:
    D, E = problema.matrices([d], [estados])
    p = float(problema.p(D, E)[0])
    brecha = float(problema.brecha(np.array([p]))[0])
    termino = max(0.0, brecha) ** 2
    costo = float(problema.con_mu(1.0).penalizacion(D, E)[0])
    total = termino + problema.mu * costo
    simbolo_p = r"\hat p" if problema.modelo.binario else r"\hat y"
    diferencia = (
        rf"{num(problema.deseado)}-{num(p)}" if problema.direccion == SUBIR else rf"{num(p)}-{num(problema.deseado)}"
    )
    escala = "" if problema.escala_objetivo == 1.0 else rf"/{num(problema.escala_objetivo)}"
    return PasoFormula(
        id_, titulo,
        r"L=\max(0,b)^2+\mu\,C",
        rf"{simbolo_p}={num(p)},\ b=({diferencia}){escala}={num(brecha)},\ "
        rf"L={num(termino)}+{num(problema.mu, 4)}\times{num(costo)}={num(total, 4)}",
        "Alcanza el objetivo (b ≤ 0)." if brecha <= 1e-12 else f"Le falta {texto(brecha)} para el objetivo (en la escala de b).",
        cumple=brecha <= 1e-12,
        terminos=[
            Termino(simbolo_p, "logro: probabilidad o valor esperado propagado por el grafo", texto(p, 4), ORIGEN_CALCULADO),
            Termino("b", "brecha con lo deseado", texto(brecha, 4), ORIGEN_CALCULADO),
            Termino("C", "costo de las acciones (sin μ)", texto(costo, 4), ORIGEN_CALCULADO),
            Termino(r"\mu", "peso de la intervención mínima", texto(problema.mu, 4), ORIGEN_UMBRAL),
        ],
        nota="Evaluada con el modelo exacto; el optimizador usa una versión suavizada de las intermedias binarias.",
    )


_INFINITO, _MENOS_INFINITO = r"\infty", r"-\infty"


def _cota(d: float, infinito: str) -> str:
    return infinito if abs(d) >= _SIN_LIMITE else num(d, 3)


def _limite_original(problema: ProblemaPrescripcion, a, d: float) -> str:
    if abs(d) >= _SIN_LIMITE:
        return r"\text{sin límite}"
    valor = problema.modelo.unidades.a_original_numerico(a.columna, a.x0 + d * a.escala)
    return num(valor, 3)


def explicar_caso(
    modelo: ModeloCausal,
    caso: Caso,
    configuracion: ConfiguracionPrescripcion,
    mu: float,
    referencia: ModeloReferencia | None = None,
    fila: Any = None,
) -> TrazaCaso:
    """Prescribe ``caso`` como la pantalla de Prescripción y descompone la función objetivo."""
    if mu < 0:
        raise ValueError("μ no puede ser negativo.")
    problema = ProblemaPrescripcion(modelo, caso, configuracion, mu)
    r = prescribir_caso(modelo, caso, configuracion, mu, referencia, fila, problema=problema)
    d, estados = _solucion(problema, r)
    avisos = [a.mensaje for a in r.avisos]
    D, E = problema.matrices([d], [estados])
    p_reconstruida = float(problema.p(D, E)[0])
    p_resultado = r.despues if modelo.binario else modelo.unidades.a_preparada(modelo.objetivo, r.despues)
    if modelo.binario and abs(p_reconstruida - p_resultado) > _TOLERANCIA_LOGRO:
        avisos.append("La solución reconstruida no reproduce exactamente el logro devuelto: la descomposición es aproximada.")

    contribuciones = {a.variable: a for a in r.acciones}
    acciones = []
    for i, a in enumerate(problema.continuas):
        prescrita = contribuciones.get(a.nombre)
        x0 = modelo.unidades.a_original_numerico(a.columna, a.x0)
        x1 = modelo.unidades.a_original_numerico(a.columna, a.x0 + d[i] * a.escala)
        pen = problema.mu * a.costo * abs(d[i])
        motivo_lo = _MOTIVOS.get(a.motivo_lo or "", "sin restricción")
        motivo_hi = _MOTIVOS.get(a.motivo_hi or "", "sin restricción")
        pasos = [
            PasoFormula(
                "escala", "Cambio en escala normalizada",
                r"d=\frac{x-x_0}{r},\qquad r=\max_{\text{train}}x-\min_{\text{train}}x",
                rf"d=\frac{{{num(x1)}-{num(x0)}}}{{r}}={num(d[i], 4)}\quad(\text{{unidades preparadas: }}r={num(a.escala, 4)})",
                "Normalizar hace comparables los costos entre variables con escalas distintas.",
                terminos=[
                    Termino("x_0", "valor actual (original)", texto(x0, 4), ORIGEN_DATASET),
                    Termino("x", "valor prescrito (original)", texto(x1, 4), ORIGEN_CALCULADO),
                ],
            ),
            PasoFormula(
                "limites", "Restricciones",
                r"d\in[d_{\min},\,d_{\max}]",
                rf"d\in[{_cota(a.lo, _MENOS_INFINITO)},\ {_cota(a.hi, _INFINITO)}]"
                rf"\ \Leftrightarrow\ x\in[{_limite_original(problema, a, a.lo)},\ {_limite_original(problema, a, a.hi)}]",
                f"Mínimo por {motivo_lo}; máximo por {motivo_hi}. Se combinan límite, cambio máximo y dirección y gana el más estricto.",
                cumple=None,
                nota="Restricción activa: " + prescrita.restriccion_activa if prescrita and prescrita.restriccion_activa else None,
            ),
            PasoFormula(
                "costo", "Costo de la acción",
                r"\mu\cdot c_i\cdot|d_i|",
                rf"{num(problema.mu, 4)}\times{num(a.costo, 2)}\times{num(abs(d[i]), 4)}={num(pen, 5)}",
                "Penalización que esta acción suma a la pérdida.",
                terminos=[Termino("c_i", "costo por unidad normalizada", texto(a.costo), ORIGEN_UMBRAL)],
            ),
        ]
        acciones.append(AccionExplicada(
            a.nombre, "continua", d[i] != 0, _etiqueta(x0), _etiqueta(x1), float(d[i]), a.costo, pen,
            prescrita.contribucion if prescrita else None, prescrita.restriccion_activa if prescrita else None, pasos,
        ))
    for j, a in enumerate(problema.discretas):
        prescrita = contribuciones.get(a.nombre)
        cambia = estados[j] != a.actual
        pen = problema.mu * a.costo if cambia else 0.0
        pasos = [PasoFormula(
            "costo", "Costo del cambio de estado",
            r"\mu\cdot c_j\cdot[\text{estado}\neq\text{actual}]",
            rf"{num(problema.mu, 4)}\times{num(a.costo, 2)}\times{int(cambia)}={num(pen, 5)}",
            f"Estados posibles: {', '.join(_etiqueta(e) for e in a.etiquetas)}.",
        )]
        acciones.append(AccionExplicada(
            a.nombre, "discreta", cambia, _etiqueta(a.etiquetas[a.actual]), _etiqueta(a.etiquetas[estados[j]]),
            None, a.costo, pen, prescrita.contribucion if prescrita else None,
            prescrita.restriccion_activa if prescrita else None, pasos,
        ))

    clasificacion = variables_prescriptivas(modelo, configuracion.modificables)
    en_problema = {a.nombre for a in problema.continuas} | {a.nombre for a in problema.discretas}
    no_permitidas = [v for v in clasificacion.prescriptivas if v not in en_problema]
    no_modificables = sorted(
        {modelo.unidades.grupo_de.get(v, v) for v in modelo.ancestros} - set(clasificacion.prescriptivas)
    )
    entradas = [
        EntradaPrescripcion("Variables prescriptivas (acciones)", ", ".join(sorted(en_problema)) or "ninguna", True,
                            "Modificables y ancestros del objetivo: el optimizador puede moverlas."),
        EntradaPrescripcion("Valores del caso", "abducción", True,
                            "El ruido de cada mecanismo se infiere del caso, así la prescripción es personalizada."),
        EntradaPrescripcion("Ancestros no modificables", ", ".join(no_modificables) or "ninguno", False,
                            "No se intervienen; cambian solo si las acciones los afectan por el grafo."),
        EntradaPrescripcion("Modificables sin camino al objetivo", ", ".join(clasificacion.sin_camino) or "ninguna", False,
                            "Moverlas no cambiaría el objetivo según el modelo causal."),
        EntradaPrescripcion("Acciones no permitidas o sin estados alternativos", ", ".join(no_permitidas) or "ninguna", False,
                            "Excluidas en la configuración o sin otro estado posible."),
        EntradaPrescripcion("Modelo de referencia", "todas las variables", False,
                            "No decide la prescripción: solo marca si conviene revisarla."),
    ]
    simbolo = r"\hat p" if modelo.binario else r"\hat y"
    comparador = _LE if r.direccion != SUBIR else _GE
    fundamentos = [
        PasoFormula(
            "objetivo", "Objetivo deseado",
            rf"{simbolo}\ {comparador}\ \text{{deseado}}",
            rf"{simbolo}_{{\text{{antes}}}}={num(r.antes)},\ \text{{deseado}}={num(r.deseado)}",
            "Ya cumple: no se prescribe ninguna acción." if r.ya_cumple else
            ("Alcanzado con la prescripción." if r.alcanzado else f"No alcanzable con estas restricciones: falta {texto(r.falta)}."),
            cumple=r.alcanzado,
        ),
        PasoFormula(
            "funcion", "Función que se minimiza",
            r"L(d)=\max(0,b(d))^2+\mu\Big(\sum_i c_i|d_i|+\sum_j c_j[e_j\ne e_j^0]\Big)",
            rf"\mu={num(problema.mu, 4)}",
            "El primer término empuja hacia el objetivo; el segundo prefiere la intervención más pequeña.",
            terminos=[Termino(r"\mu", "peso de la intervención mínima", texto(problema.mu, 4), ORIGEN_UMBRAL)],
        ),
        PasoFormula(
            "optimizador", "Optimizador",
            r"\min_{d\in[d_{\min},d_{\max}],\,e\in E}L(d,e)",
            None,
            f"{r.optimizador} con varios arranques; si no se alcanza el objetivo, se busca la mejor solución sin costo (μ = 0).",
        ),
    ]
    perdida = [
        _perdida(problema, np.zeros(problema.k), problema.actual, "Sin actuar (d = 0)", "perdida_antes"),
        _perdida(problema, d, estados, "Con la prescripción", "perdida_despues"),
    ]
    return TrazaCaso(
        caso.indice, r.medida, r.direccion, r.deseado, r.antes, r.despues, r.alcanzado, r.ya_cumple, problema.mu,
        r.optimizador, r.explicacion, fundamentos, perdida, acciones, entradas,
        [x.mensaje for x in r.restricciones_activas], avisos,
    )

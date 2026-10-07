"""Explicación del análisis de PC: cómo las cuentas del bootstrap se vuelven un grafo.

Parte de un ``resultado.json`` con cuentas (una versión del resultado). No repite PC ni usa el
dataset: reutiliza ``reagregacion.reagregar`` (las mismas reglas de ``pc_bootstrap.agregar_cuentas``
y ``caracterizacion.caracterizar``) y le añade, por cada arista y por cada variable, la fórmula
general y los valores reales. Con otro umbral, solo cambia lo que se muestra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


from pcapp_nucleo.caracterizacion import (
    AMBIGUA,
    CAUSA_DIRECTA,
    CAUSA_INDIRECTA,
    CONSECUENCIA,
    SIN_CAMINO,
)
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
from pcapp_nucleo.reagregacion import UMBRAL_ARISTA_DEBIL, ErrorReagregacion, reagregar

MAXIMO_PARES = 200
"""Pares que se detallan (los más frecuentes); el resto solo se cuenta."""
CERCA_DEL_UMBRAL = 0.05
"""Diferencia de frecuencia con el umbral por debajo de la cual una arista «roza» el umbral."""

_GE = r"\ge"
_FLECHA, _GUION = r"\rightarrow", r"-"
_REGLAS_CATEGORIA = {
    CAUSA_DIRECTA: "Hay una arista dirigida de la variable al objetivo.",
    CAUSA_INDIRECTA: "Hay un camino dirigido de dos o más aristas hasta el objetivo.",
    CONSECUENCIA: "Hay un camino dirigido desde el objetivo hasta la variable.",
    AMBIGUA: "Solo se conecta con el objetivo por caminos que, según cómo se orienten sus aristas sin "
             "orientar, podrían ir en uno u otro sentido.",
    SIN_CAMINO: "Ninguna de las anteriores.",
}


@dataclass(frozen=True)
class ParEvaluado:
    a: str
    b: str
    estado: str  # "aceptada" | "debil" | "descartada"
    frecuencia: float
    margen: float  # frecuencia - umbral
    roza_umbral: bool
    tipo: str | None  # "dirigida" | "sin_orientar" | "manual" (solo si se acepta)
    origen: str | None
    destino: str | None
    spearman: float | None
    signo: int | None
    pasos: list[PasoFormula] = field(default_factory=list)


@dataclass(frozen=True)
class VariableCaracterizada:
    nombre: str
    categoria: str
    regla: str
    camino: str | None  # LaTeX
    frecuencia_con_objetivo: float
    modificable: bool
    candidata: bool


@dataclass(frozen=True)
class EntradaAnalisis:
    nombre: str
    valor: str
    usada: bool
    nota: str


@dataclass(frozen=True)
class CambioArista:
    a: str
    b: str
    cambio: str  # "nueva" | "quitada"
    frecuencia: float


@dataclass(frozen=True)
class TrazaAnalisisPC:
    umbral: float
    umbral_guardado: float
    corridas_validas: int
    resumen: str
    fundamentos: list[PasoFormula]
    entradas: list[EntradaAnalisis]
    pares: list[ParEvaluado]
    pares_omitidos: int
    variables: list[VariableCaracterizada]
    cambios: list[CambioArista]
    candidatas: list[str]
    candidatas_guardadas: list[str]
    umbrales: list[Umbral]
    avisos: list[str]


def _flecha(origen: str, destino: str, tipo: str) -> str:
    conector = _GUION if tipo == "sin_orientar" else _FLECHA
    return rf"\text{{{origen}}}\ {conector}\ \text{{{destino}}}"


def _nombre(valor: str) -> str:
    return rf"\text{{{valor}}}"


def _fundamentos(contenido: dict[str, Any], umbral: float) -> list[PasoFormula]:
    configuracion, corridas = contenido["configuracion"], contenido["corridas"]
    validas = corridas["validas"]
    fallidas = len(corridas["fallidas"])
    minimo = umbral * validas
    max_k = configuracion.get("max_k")
    return [
        PasoFormula(
            "corridas", "1. Corridas de bootstrap",
            r"N=B-F,\qquad \text{cada corrida usa una fracción }\varphi\text{ del entrenamiento}",
            rf"N={corridas['completadas']}-{fallidas}={validas},\qquad \varphi={num(configuracion['fraccion_submuestra'], 2)}",
            f"{validas} corridas válidas; PC se ejecutó con {configuracion['prueba']}, α = "
            f"{texto(configuracion['alpha'])} y max_k = {max_k if max_k is not None else 'sin límite'}.",
            terminos=[
                Termino("B", "corridas completadas", str(corridas["completadas"]), ORIGEN_DATASET),
                Termino("F", "corridas fallidas (descartadas)", str(fallidas), ORIGEN_DATASET),
                Termino(r"\varphi", "fracción de submuestra", texto(configuracion["fraccion_submuestra"]), ORIGEN_UMBRAL),
            ],
            nota="Cada corrida usa solo el conjunto de entrenamiento y una semilla derivada de (semilla, corrida).",
        ),
        PasoFormula(
            "frecuencia", "2. Frecuencia de una arista",
            r"f_{ij}=\frac{n_{i\to j}+n_{j\to i}+n_{i-j}}{N}\ \ge\ \tau",
            rf"n_{{\min}}=\tau N={num(umbral, 2)}\times{validas}={num(minimo, 1)}",
            f"Una arista se acepta si aparece, con cualquier orientación, en al menos {texto(minimo, 3)} "
            f"de las {validas} corridas.",
            terminos=[
                Termino(r"\tau", "umbral de frecuencia", texto(umbral), ORIGEN_UMBRAL),
                Termino("N", "corridas válidas", str(validas), ORIGEN_DATASET),
            ],
        ),
        PasoFormula(
            "orientacion", "3. Orientación",
            r"\text{dirección}=\arg\max\{n_{i\to j},\,n_{j\to i},\,n_{i-j}\}",
            None,
            "Gana la orientación más frecuente; si empatan o gana «sin orientar», la arista queda sin orientar.",
            nota="Las aristas bidireccionales (conflictos) se cuentan como sin orientar.",
        ),
        PasoFormula(
            "manual", "4. Orientación manual",
            r"\text{solo si la arista se aceptó y quedó sin orientar}",
            None,
            "Una orientación manual no pisa lo que PC ya orientó.",
        ),
        PasoFormula(
            "signo", "5. Signo de la relación",
            r"s=\operatorname{sgn}(\rho_s)",
            None,
            "El signo viene de la correlación de Spearman en entrenamiento; no influye en aceptar la arista.",
            nota="Asociación monótona, no causalidad.",
        ),
    ]


def _par(
    contenido: dict[str, Any], i: int, j: int, validas: int, umbral: float,
    aristas: dict[frozenset[str], dict[str, Any]],
) -> ParEvaluado | None:
    variables = contenido["variables"]
    dirigidas = contenido["cuentas"]["dirigidas"]
    sin = contenido["cuentas"]["sin_orientar"]
    a, b = variables[i], variables[j]
    n_ab, n_ba, n_u = dirigidas[i][j], dirigidas[j][i], sin[i][j]
    total = n_ab + n_ba + n_u
    if total == 0:
        return None
    frecuencia = total / validas
    arista = aristas.get(frozenset((a, b)))
    estado = "aceptada" if arista else ("debil" if frecuencia >= UMBRAL_ARISTA_DEBIL else "descartada")
    cmp_ = _GE if arista else "<"
    pasos = [PasoFormula(
        "frecuencia", "Frecuencia de la arista",
        r"f=\frac{n_{i\to j}+n_{j\to i}+n_{i-j}}{N}",
        rf"f=\frac{{{n_ab}+{n_ba}+{n_u}}}{{{validas}}}={num(frecuencia)}\ {cmp_}\ \tau={num(umbral, 2)}",
        "Se acepta." if arista else "No llega al umbral.",
        cumple=bool(arista),
        terminos=[
            Termino(r"n_{i\to j}", f"corridas con {a} → {b}", str(n_ab), ORIGEN_DATASET),
            Termino(r"n_{j\to i}", f"corridas con {b} → {a}", str(n_ba), ORIGEN_DATASET),
            Termino(r"n_{i-j}", "corridas sin orientar (incluye bidireccionales)", str(n_u), ORIGEN_DATASET),
            Termino("N", "corridas válidas", str(validas), ORIGEN_DATASET),
            Termino(r"\tau", "umbral de frecuencia", texto(umbral), ORIGEN_UMBRAL),
        ],
    )]
    tipo = origen = destino = signo = None
    rho = None
    if arista:
        tipo, origen, destino = arista["tipo"], arista["origen"], arista["destino"]
        rho, signo = arista["spearman"], arista["signo"]
        directa, inversa, sin_o = arista["frecuencia_origen_destino"], arista["frecuencia_destino_origen"], arista["frecuencia_sin_orientar"]
        pasos.append(PasoFormula(
            "orientacion", "Orientación",
            r"\arg\max\{n_{i\to j},\,n_{j\to i},\,n_{i-j}\}",
            rf"\max\{{{n_ab},\,{n_ba},\,{n_u}\}}\Rightarrow\ {_flecha(origen, destino, tipo if tipo != 'manual' else 'dirigida')}"
            if tipo != "sin_orientar"
            else rf"\max\{{{n_ab},\,{n_ba},\,{n_u}\}}\ \text{{sin ganador claro}}\Rightarrow\ {_flecha(origen, destino, tipo)}",
            {
                "dirigida": f"Orientada {origen} → {destino} por mayoría.",
                "sin_orientar": "Sin orientar: empate o gana «sin orientar».",
                "manual": f"Orientada a mano {origen} → {destino}: {arista.get('justificacion') or 'sin justificación'}",
            }[tipo],
            terminos=[
                Termino("f_{\\to}", f"frecuencia {origen} → {destino}", texto(directa), ORIGEN_CALCULADO),
                Termino("f_{\\leftarrow}", f"frecuencia {destino} → {origen}", texto(inversa), ORIGEN_CALCULADO),
                Termino("f_{-}", "frecuencia sin orientar", texto(sin_o), ORIGEN_CALCULADO),
            ],
        ))
        pasos.append(PasoFormula(
            "signo", "Signo",
            r"s=\operatorname{sgn}(\rho_s)",
            rf"s=\operatorname{{sgn}}({num(rho)})={signo:+d}" if rho is not None else None,
            "Asociación positiva." if signo and signo > 0 else "Asociación negativa." if signo else "Sin signo.",
            terminos=[Termino(r"\rho_s", "Spearman en entrenamiento", texto(rho), ORIGEN_CALCULADO)],
            nota="Asociación monótona, no causalidad.",
        ))
    return ParEvaluado(
        a, b, estado, round(frecuencia, 4), round(frecuencia - umbral, 4),
        abs(frecuencia - umbral) <= CERCA_DEL_UMBRAL, tipo, origen, destino, rho, signo, pasos,
    )


def _camino(nombre: str, objetivo: str, categoria: str, intermedias: list[str]) -> str | None:
    if categoria == CAUSA_DIRECTA:
        nodos = [nombre, objetivo]
    elif categoria == CAUSA_INDIRECTA:
        nodos = [nombre, *intermedias, objetivo]
    elif categoria == CONSECUENCIA:
        nodos = [objetivo, *intermedias, nombre]
    else:
        return None
    return rf"\ {_FLECHA}\ ".join(_nombre(n) for n in nodos)


def explicar_analisis_pc(contenido: dict[str, Any], umbral: float | None = None) -> TrazaAnalisisPC:
    """Traza del grafo agregado de ``contenido`` (un ``resultado.json`` con cuentas).

    ``umbral``: otra frecuencia mínima a probar (por defecto, la de la versión). Las
    orientaciones manuales son las de la versión.

    Raises:
        ValueError: si el umbral no es válido.
    """
    guardado = float(contenido["agregacion"]["umbral_frecuencia"])
    umbral = guardado if umbral is None else float(umbral)
    try:
        nuevo = reagregar(contenido, umbral, contenido["agregacion"]["orientaciones_manuales"])
    except ErrorReagregacion as error:
        raise ValueError(str(error)) from error

    validas = int(contenido["corridas"]["validas"])
    objetivo = contenido["receta"]["objetivo"]
    aristas_nuevas = {frozenset((a["origen"], a["destino"])): a for a in nuevo.contenido["aristas"]}
    aristas_guardadas = {frozenset((a["origen"], a["destino"])): a for a in contenido["aristas"]}
    avisos = list(nuevo.contenido["advertencias"])
    if validas == 0:
        raise ValueError("No hubo corridas válidas: no hay nada que explicar.")

    pares = []
    n = len(contenido["variables"])
    for i in range(n):
        for j in range(i + 1, n):
            par = _par(contenido, i, j, validas, umbral, aristas_nuevas)
            if par is not None:
                pares.append(par)
    pares.sort(key=lambda p: (-p.frecuencia, p.a, p.b))
    omitidos = max(0, len(pares) - MAXIMO_PARES)
    pares = pares[:MAXIMO_PARES]

    cambios = [
        CambioArista(*sorted(clave), "nueva", aristas_nuevas[clave]["frecuencia_total"])
        for clave in aristas_nuevas.keys() - aristas_guardadas.keys()
    ] + [
        CambioArista(*sorted(clave), "quitada", aristas_guardadas[clave]["frecuencia_total"])
        for clave in aristas_guardadas.keys() - aristas_nuevas.keys()
    ]
    cambios.sort(key=lambda c: (c.cambio, c.a, c.b))

    caracterizacion = nuevo.caracterizacion
    candidatas = set(caracterizacion.candidatas_prescriptivas)
    variables = [
        VariableCaracterizada(
            v.variable, v.categoria, _REGLAS_CATEGORIA[v.categoria],
            _camino(v.variable, objetivo, v.categoria, v.a_traves_de),
            v.frecuencia_con_objetivo, v.modificable, v.variable in candidatas,
        )
        for v in caracterizacion.variables
    ]
    aceptadas = len(aristas_nuevas)
    entradas = [
        EntradaAnalisis("Cuentas dirigidas y sin orientar", f"{n} × {n} variables", True,
                        "Fuente de las frecuencias y de la orientación."),
        EntradaAnalisis("Corridas válidas", str(validas), True, "Denominador de toda frecuencia."),
        EntradaAnalisis("Umbral de frecuencia", texto(umbral) or "", True, "Decide qué aristas se aceptan."),
        EntradaAnalisis("Orientaciones manuales", str(len(contenido["agregacion"]["orientaciones_manuales"])), True,
                        "Solo se aplican a aristas aceptadas y sin orientar."),
        EntradaAnalisis("Variables modificables", str(len(contenido["configuracion"]["modificables"])), True,
                        "Solo deciden qué causas son candidatas prescriptivas; no cambian el grafo."),
        EntradaAnalisis("Correlación de Spearman", "entrenamiento", False,
                        "Solo da el signo de cada arista; no influye en aceptarla ni en orientarla."),
        EntradaAnalisis("Corridas fallidas", str(len(contenido["corridas"]["fallidas"])), False,
                        "Se descartan: no cuentan en N."),
        EntradaAnalisis("Pares con f < τ", str(sum(p.estado != "aceptada" for p in pares) + omitidos), False,
                        "No entran al grafo; las que superan "
                        f"{texto(UMBRAL_ARISTA_DEBIL)} se avisan como débiles."),
        EntradaAnalisis("Valor p de cada prueba de independencia", "no se guarda", False,
                        "Cada corrida de PC lo usa internamente (con α); la agregación solo ve el resultado."),
    ]
    resumen = f"Con τ = {texto(umbral)} se aceptan {aceptadas} aristas de {len(pares) + omitidos} pares con alguna frecuencia."
    if cambios:
        resumen += f" Respecto al resultado guardado (τ = {texto(guardado)}): {len(cambios)} cambio(s)."
    editable = Umbral(
        "umbral_frecuencia", r"\tau", "Frecuencia mínima de una arista en las corridas válidas",
        umbral, guardado, 0.05, 1.0, 0.01,
    )
    return TrazaAnalisisPC(
        umbral, guardado, validas, resumen, _fundamentos(contenido, umbral), entradas, pares, omitidos,
        variables, cambios, list(caracterizacion.candidatas_prescriptivas),
        list(contenido["caracterizacion"]["candidatas_prescriptivas"]), [editable], avisos,
    )

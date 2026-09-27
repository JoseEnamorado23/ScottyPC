"""Caracterización de cada variable respecto al objetivo en el grafo agregado.

Categorías, en orden de prioridad:

- ``causa_directa``: arista dirigida (o manual) variable → objetivo.
- ``causa_indirecta``: camino dirigido de dos o más aristas hasta el objetivo.
- ``consecuencia``: camino dirigido desde el objetivo hasta la variable.
- ``ambigua``: solo se conecta con el objetivo mediante caminos que podrían
  ser causales en uno u otro sentido según cómo se orienten sus aristas sin
  orientar (ninguna arista va en contra del sentido del camino y al menos
  una está sin orientar).
- ``sin_camino``: ninguna de las anteriores.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from pcapp_nucleo.pc_bootstrap import GrafoAgregado, ResultadoBootstrap, frecuencia_par

CAUSA_DIRECTA = "causa_directa"
CAUSA_INDIRECTA = "causa_indirecta"
CONSECUENCIA = "consecuencia"
AMBIGUA = "ambigua"
SIN_CAMINO = "sin_camino"


@dataclass(frozen=True)
class CaracterizacionVariable:
    variable: str
    categoria: str
    a_traves_de: list[str] = field(default_factory=list)
    frecuencia_con_objetivo: float = 0.0
    grupo_redundante: list[str] | None = None
    modificable: bool = False


@dataclass(frozen=True)
class Caracterizacion:
    objetivo: str
    variables: list[CaracterizacionVariable]
    candidatas_prescriptivas: list[str]
    mensaje: str


def _adyacencias(grafo: GrafoAgregado) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(sucesores dirigidos, vecinos sin orientar)."""
    sucesores: dict[str, set[str]] = {v: set() for v in grafo.variables}
    sin_orientar: dict[str, set[str]] = {v: set() for v in grafo.variables}
    for arista in grafo.aristas:
        if arista.tipo == "sin_orientar":
            sin_orientar[arista.origen].add(arista.destino)
            sin_orientar[arista.destino].add(arista.origen)
        else:
            sucesores[arista.origen].add(arista.destino)
    return sucesores, sin_orientar


def _caminos_mas_cortos(inicio: str, siguientes: dict[str, set[str]]) -> dict[str, list[str]]:
    """Camino más corto (lista de nodos, sin ``inicio``) a cada nodo alcanzable."""
    caminos: dict[str, list[str]] = {inicio: []}
    cola = deque([inicio])
    while cola:
        actual = cola.popleft()
        for vecino in sorted(siguientes[actual]):
            if vecino not in caminos:
                caminos[vecino] = caminos[actual] + [vecino]
                cola.append(vecino)
    del caminos[inicio]
    return caminos


def _alcanzables_semidirigidos(
    inicio: str, dirigidos: dict[str, set[str]], sin_orientar: dict[str, set[str]]
) -> set[str]:
    """Nodos alcanzables desde ``inicio`` sin ir en contra de ninguna arista
    dirigida y usando al menos una arista sin orientar."""
    visitados = {(inicio, False)}
    cola = deque(visitados)
    alcanzados = set()
    while cola:
        nodo, uso_sin_orientar = cola.popleft()
        pasos = [(v, uso_sin_orientar) for v in dirigidos[nodo]]
        pasos += [(v, True) for v in sin_orientar[nodo]]
        for estado in pasos:
            if estado not in visitados:
                visitados.add(estado)
                cola.append(estado)
                if estado[1]:
                    alcanzados.add(estado[0])
    alcanzados.discard(inicio)
    return alcanzados


def caracterizar(
    grafo: GrafoAgregado,
    resultado: ResultadoBootstrap,
    modificables: list[str],
    grupos_redundantes: list[list[str]] | None = None,
) -> Caracterizacion:
    """Clasifica cada variable respecto al objetivo e identifica las candidatas prescriptivas.

    Args:
        grupos_redundantes: grupos informados por el revisor (``grupo_redundante``).
    """
    objetivo = grafo.objetivo
    sucesores, sin_orientar = _adyacencias(grafo)
    predecesores: dict[str, set[str]] = {v: set() for v in grafo.variables}
    for origen, destinos in sucesores.items():
        for destino in destinos:
            predecesores[destino].add(origen)

    hacia_objetivo = _caminos_mas_cortos(objetivo, predecesores)  # ancestros
    desde_objetivo = _caminos_mas_cortos(objetivo, sucesores)  # descendientes
    ambiguas = _alcanzables_semidirigidos(objetivo, predecesores, sin_orientar) | (
        _alcanzables_semidirigidos(objetivo, sucesores, sin_orientar)
    )
    grupos = {v: grupo for grupo in grupos_redundantes or [] for v in grupo}

    variables = []
    for variable in grafo.variables:
        if variable == objetivo:
            continue
        intermedias: list[str] = []
        if variable in hacia_objetivo and len(hacia_objetivo[variable]) == 1:
            categoria = CAUSA_DIRECTA
        elif variable in hacia_objetivo:
            categoria = CAUSA_INDIRECTA
            intermedias = list(reversed(hacia_objetivo[variable][:-1]))
        elif variable in desde_objetivo:
            categoria = CONSECUENCIA
            intermedias = desde_objetivo[variable][:-1]
        elif variable in ambiguas:
            categoria = AMBIGUA
        else:
            categoria = SIN_CAMINO
        variables.append(
            CaracterizacionVariable(
                variable=variable,
                categoria=categoria,
                a_traves_de=intermedias,
                frecuencia_con_objetivo=frecuencia_par(resultado, variable, objetivo),
                grupo_redundante=grupos.get(variable),
                modificable=variable in modificables,
            )
        )

    causas = [v.variable for v in variables if v.categoria in (CAUSA_DIRECTA, CAUSA_INDIRECTA)]
    candidatas = [v for v in causas if v in modificables]
    if not modificables:
        mensaje = (
            "No se indicaron variables modificables: márquelas en 'modificables' de la "
            "configuración para identificar candidatas prescriptivas."
        )
    elif not candidatas:
        mensaje = (
            "Con estos datos no hay variables prescriptivas: ninguna variable modificable es "
            "causa directa o indirecta del objetivo."
        )
    else:
        mensaje = f"Candidatas prescriptivas: {', '.join(candidatas)}."
    return Caracterizacion(objetivo, variables, candidatas, mensaje)

"""Subgrafo del objetivo y sus ancestros dentro del resultado de PC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

# Ciclos que se buscan como mucho (con uno basta para bloquear).
MAXIMO_CICLOS = 20


@dataclass(frozen=True)
class Subgrafo:
    """Objetivo y ancestros por aristas dirigidas (o manuales).

    ``variables`` está en orden topológico (el objetivo al final) si no hay ciclos.
    ``sin_orientar`` son las aristas sin orientar que tocan el subgrafo: con ellas no se
    sabe qué es ancestro. ``descendientes_objetivo`` usa todo el grafo.
    """

    objetivo: str
    variables: list[str]
    padres: dict[str, list[str]]
    aristas: list[tuple[str, str]]
    sin_orientar: list[tuple[str, str]]
    ciclos: list[list[str]]
    fuera: list[str]
    descendientes_objetivo: list[str]

    @property
    def ancestros(self) -> list[str]:
        return [v for v in self.variables if v != self.objetivo]

    @property
    def raices(self) -> list[str]:
        return [v for v in self.variables if not self.padres[v]]


def _dirigida(arista: dict[str, Any]) -> bool:
    return arista["tipo"] != "sin_orientar"


def subgrafo_objetivo(variables: list[str], aristas: list[dict[str, Any]], objetivo: str) -> Subgrafo:
    """``aristas`` con el formato de ``resultado.json`` (origen, destino, tipo)."""
    completo = nx.DiGraph()
    completo.add_nodes_from(variables)
    completo.add_edges_from((a["origen"], a["destino"]) for a in aristas if _dirigida(a))
    incluidas = set(nx.ancestors(completo, objetivo)) | {objetivo} if objetivo in completo else {objetivo}
    orden_base = [v for v in variables if v in incluidas]
    sub = completo.subgraph(orden_base).copy()
    ciclos = []
    for ciclo in nx.simple_cycles(sub):
        ciclos.append(list(ciclo))
        if len(ciclos) >= MAXIMO_CICLOS:
            break
    if ciclos:
        orden = orden_base
    else:
        posicion = {v: i for i, v in enumerate(variables)}
        orden = list(nx.lexicographical_topological_sort(sub, key=lambda v: posicion[v]))
        orden = [v for v in orden if v != objetivo] + [objetivo]
    padres = {v: [p for p in orden_base if sub.has_edge(p, v)] for v in orden}
    sin_orientar = [
        (a["origen"], a["destino"]) for a in aristas
        if not _dirigida(a) and (a["origen"] in incluidas or a["destino"] in incluidas)
    ]
    descendientes = sorted(nx.descendants(completo, objetivo)) if objetivo in completo else []
    return Subgrafo(
        objetivo=objetivo,
        variables=orden,
        padres=padres,
        aristas=[(o, d) for o, d in sub.edges() if o in incluidas and d in incluidas],
        sin_orientar=sin_orientar,
        ciclos=ciclos,
        fuera=[v for v in variables if v not in incluidas],
        descendientes_objetivo=[v for v in variables if v in descendientes],
    )

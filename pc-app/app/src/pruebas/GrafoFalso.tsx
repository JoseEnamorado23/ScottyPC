// Doble del grafo de Cytoscape para jsdom (no hay canvas): muestra los nodos y las aristas
// como botones que llaman a los mismos avisos que un clic en el grafo real.
import type { ComponentProps } from "react";

import type { GrafoCausal } from "../componentes/resultados/GrafoCausal";

export function GrafoFalso({ resultado, soloRelacionadas, alSeleccionarNodo, alElegirArista }: ComponentProps<typeof GrafoCausal>) {
  const relacionadas = new Set([
    resultado.caracterizacion.objetivo,
    ...resultado.caracterizacion.variables.filter((v) => v.categoria !== "sin_camino").map((v) => v.variable),
  ]);
  const visibles = resultado.variables.filter((v) => !soloRelacionadas || relacionadas.has(v));
  return (
    <div data-testid="grafo">
      {visibles.map((v) => (
        <button key={v} type="button" onClick={() => alSeleccionarNodo(v)}>
          nodo {v}
        </button>
      ))}
      {resultado.aristas
        .filter((a) => visibles.includes(a.origen) && visibles.includes(a.destino))
        .map((a) => (
          <button key={`${a.origen}|${a.destino}`} type="button" onClick={() => alElegirArista(a)}>
            arista {a.origen} {a.tipo === "sin_orientar" ? "—" : "→"} {a.destino}
          </button>
        ))}
    </div>
  );
}

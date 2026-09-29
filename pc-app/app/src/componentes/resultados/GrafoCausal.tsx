// Grafo interactivo con Cytoscape.js.
//
// Una sola instancia por pantalla: se crea al montar y nunca se reemplazan todos sus
// elementos. Cuando llega otro resultado (otra versión o una vista previa del ajuste) se
// aplica un diff dentro de cy.batch(): se quitan y agregan las aristas que cambian, se
// actualizan los datos del resto (y la dirección con edge.move) y la categoría de cada nodo.
// Los nodos nunca se quitan, la disposición y el encuadre (fit) se calculan solo la primera
// vez: se conservan las posiciones que el usuario arrastró, el zoom y el desplazamiento.
import cytoscape from "cytoscape";
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { Paper, Stack, Text } from "@mantine/core";

import type { Esquemas } from "../../api/cliente";
import { formatoPorcentaje, formatoRho } from "../../estado/ajustes";
import { datosAristas, datosNodos, disposicionInicial, relacionadasConObjetivo, type Arista } from "../../estado/grafo";

export interface ControlGrafo {
  /** PNG de la vista actual (con el zoom y el desplazamiento del usuario). */
  png(): Blob;
  ajustar(): void;
  acercar(factor: number): void;
}

interface Props {
  resultado: Esquemas["ResultadoPC"];
  soloRelacionadas: boolean;
  seleccionado: string | null;
  visible: boolean;
  alSeleccionarNodo: (variable: string | null) => void;
  alElegirArista: (arista: Arista) => void;
  ref?: Ref<ControlGrafo>;
}

const ESTILO: cytoscape.StylesheetJson = [
  {
    selector: "node.variable",
    style: {
      shape: "round-rectangle",
      "background-color": "data(color)",
      label: "data(etiqueta)",
      color: "data(colorTexto)",
      "font-size": 12,
      "text-valign": "center",
      "text-halign": "center",
      "text-wrap": "wrap",
      "text-max-width": "124px",
      width: 140,
      height: "data(alto)",
      "border-width": 1,
      "border-color": "#868e96",
    },
  },
  { selector: "node.variable[?modificable]", style: { "border-width": 5, "border-style": "double", "border-color": "#212529" } },
  { selector: "node.variable:selected", style: { "overlay-color": "#228be6", "overlay-opacity": 0.25, "overlay-padding": 6 } },
  {
    selector: "node.titulo",
    style: {
      label: "data(titulo)",
      "background-opacity": 0,
      "border-width": 0,
      width: 1,
      height: 1,
      color: "#495057",
      "font-size": 13,
      "font-weight": "bold",
      "text-wrap": "wrap",
      "text-max-width": "210px",
      events: "no",
    },
  },
  {
    selector: "edge",
    style: {
      width: "data(ancho)",
      "line-color": "data(color)",
      "target-arrow-color": "data(color)",
      "target-arrow-shape": "triangle",
      "arrow-scale": 1.1,
      "curve-style": "bezier",
      opacity: 0.85,
    },
  },
  // Dentro de un nivel la arista se curva hacia un lado para no pasar por detrás de los nodos
  // de la misma columna (como en grafo.png).
  { selector: "edge.mismo-nivel", style: { "curve-style": "unbundled-bezier", "control-point-distances": "data(curva)", "control-point-weights": 0.5 } },
  { selector: "edge[tipo = 'sin_orientar']", style: { "line-style": "dashed", "line-dash-pattern": [8, 5], "target-arrow-shape": "none" } },
  {
    selector: "edge[tipo = 'manual']",
    style: { "line-style": "dotted", "source-arrow-shape": "circle", "source-arrow-color": "data(color)", "arrow-scale": 1.3 },
  },
  { selector: "edge:selected", style: { "overlay-color": "#228be6", "overlay-opacity": 0.25, "overlay-padding": 4 } },
  { selector: ".oculto", style: { display: "none" } },
];

/**
 * Desplazamiento del arco de una arista entre dos variables de la misma columna que no son
 * vecinas (null si la línea recta no pasa por detrás de otro nodo). El signo hace que el
 * arco salga siempre por el mismo lado.
 */
function curvaEnColumna(disposicion: Esquemas["ColumnaDisposicion"][], origen: string, destino: string): number | null {
  const { subcolumna } = disposicionInicial(disposicion);
  const columna = disposicion.find((c) => c.variables.includes(origen));
  if (!columna || subcolumna[origen] !== subcolumna[destino]) return null;
  const salto = columna.variables.indexOf(destino) - columna.variables.indexOf(origen);
  if (Math.abs(salto) < 2) return null;
  return Math.sign(salto) * (70 + 25 * Math.abs(salto));
}

/** Alto del nodo según las líneas que ocupa su nombre (unas 17 letras por línea). */
const altoNodo = (nombre: string) => 22 + 15 * Math.max(1, Math.ceil(nombre.length / 17));

function sincronizar(cy: cytoscape.Core, resultado: Esquemas["ResultadoPC"], soloRelacionadas: boolean) {
  const nodos = datosNodos(resultado);
  const aristas = datosAristas(resultado).map((a) => ({ ...a, curva: curvaEnColumna(resultado.disposicion, a.source, a.target) }));
  const nuevas = new Set(aristas.map((a) => a.id));
  cy.batch(() => {
    for (const nodo of nodos) {
      const existente = cy.getElementById(nodo.id);
      if (existente.nonempty()) existente.data({ ...nodo, alto: altoNodo(nodo.etiqueta) });
      else cy.add({ group: "nodes", classes: "variable", data: { ...nodo, alto: altoNodo(nodo.etiqueta) }, position: { x: 0, y: 0 } });
    }
    cy.edges().forEach((arista) => {
      if (!nuevas.has(arista.id())) arista.remove();
    });
    for (const arista of aristas) {
      const existente = cy.getElementById(arista.id);
      if (existente.empty()) {
        cy.add({ group: "edges", data: arista, classes: arista.curva === null ? "" : "mismo-nivel" });
        continue;
      }
      if (existente.source().id() !== arista.source || existente.target().id() !== arista.target) {
        // move() reemplaza la arista por otra con el mismo id y la nueva dirección.
        existente.move({ source: arista.source, target: arista.target });
      }
      cy.getElementById(arista.id).data(arista).toggleClass("mismo-nivel", arista.curva !== null);
    }
    cy.elements().removeClass("oculto");
    if (soloRelacionadas) {
      const relacionadas = relacionadasConObjetivo(resultado);
      const ocultos = cy.nodes(".variable").filter((n) => !relacionadas.has(n.id()));
      ocultos.addClass("oculto");
      ocultos.connectedEdges().addClass("oculto");
    }
  });
}

interface Emergente {
  x: number;
  y: number;
  arista: Arista;
}

export function GrafoCausal({ resultado, soloRelacionadas, seleccionado, visible, alSeleccionarNodo, alElegirArista, ref }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const encuadrado = useRef(false);
  const avisos = useRef({ alSeleccionarNodo, alElegirArista });
  avisos.current = { alSeleccionarNodo, alElegirArista };
  const [emergente, setEmergente] = useState<Emergente | null>(null);

  const encuadrarUnaVez = () => {
    const cy = cyRef.current;
    if (!cy || encuadrado.current || !contenedor.current?.clientWidth) return;
    cy.resize();
    cy.fit(undefined, 30);
    encuadrado.current = true;
  };

  // Creación (una sola vez): disposición por niveles con los títulos de las columnas.
  useEffect(() => {
    const { posiciones, titulos } = disposicionInicial(resultado.disposicion);
    const cy = cytoscape({
      container: contenedor.current,
      style: ESTILO,
      layout: { name: "preset" },
      minZoom: 0.15,
      maxZoom: 3,
      wheelSensitivity: 0.3,
      boxSelectionEnabled: false,
      elements: [
        ...titulos.map((t) => ({
          group: "nodes" as const,
          classes: "titulo",
          data: { id: t.id, titulo: t.titulo },
          position: { x: t.x, y: t.y },
          locked: true,
          grabbable: false,
          selectable: false,
        })),
        ...datosNodos(resultado).map((nodo) => ({
          group: "nodes" as const,
          classes: "variable",
          data: { ...nodo, alto: altoNodo(nodo.etiqueta) },
          position: posiciones[nodo.id] ?? { x: 0, y: 0 },
        })),
      ],
    });
    cy.on("tap", "node.variable", (evento) => avisos.current.alSeleccionarNodo(evento.target.id()));
    cy.on("tap", (evento) => {
      if (evento.target === cy) avisos.current.alSeleccionarNodo(null);
    });
    cy.on("tap", "edge", (evento) => avisos.current.alElegirArista(evento.target.data() as Arista));
    cy.on("mouseover", "edge", (evento) => {
      const punto = evento.target.renderedMidpoint();
      setEmergente({ x: punto.x, y: punto.y, arista: evento.target.data() as Arista });
    });
    cy.on("mouseout", "edge", () => setEmergente(null));
    cy.on("viewport drag", () => setEmergente(null));
    cyRef.current = cy;
    // El lienzo cambia de tamaño sin que cambie la ventana (p. ej. al abrir el panel lateral):
    // se recalcula el tamaño sin mover el zoom ni el desplazamiento.
    const observador = new ResizeObserver(() => cy.resize());
    if (contenedor.current) observador.observe(contenedor.current);
    return () => {
      observador.disconnect();
      cy.destroy();
      cyRef.current = null;
      encuadrado.current = false;
    };
    // La instancia se crea una sola vez; los cambios del resultado se aplican con el diff.
  }, []);

  // Cada resultado nuevo (versión o vista previa): diff sin mover la vista.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    sincronizar(cy, resultado, soloRelacionadas);
    encuadrarUnaVez();
  }, [resultado, soloRelacionadas]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes(":selected").unselect();
    if (seleccionado) cy.getElementById(seleccionado).select();
  }, [seleccionado]);

  // Al volver a la pestaña del grafo, Cytoscape necesita recalcular el tamaño del lienzo.
  useEffect(() => {
    if (!visible) return;
    cyRef.current?.resize();
    encuadrarUnaVez();
  }, [visible]);

  useImperativeHandle(ref, () => ({
    png: () => cyRef.current!.png({ output: "blob", bg: "#ffffff", full: false, scale: 2 }),
    ajustar: () => cyRef.current?.fit(undefined, 30),
    acercar: (factor: number) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
    },
  }));

  return (
    <div style={{ position: "relative" }}>
      <div
        ref={contenedor}
        data-testid="grafo"
        style={{ height: "clamp(420px, 62vh, 760px)", width: "100%", border: "1px solid var(--mantine-color-gray-3)", borderRadius: 8, background: "#ffffff" }}
      />
      {emergente && <DetalleArista {...emergente} />}
    </div>
  );
}

function DetalleArista({ x, y, arista }: Emergente) {
  const sinOrientar = arista.tipo === "sin_orientar";
  const flecha = sinOrientar ? "—" : "→";
  return (
    <Paper
      shadow="md"
      p="xs"
      withBorder
      style={{ position: "absolute", left: x + 12, top: y + 12, pointerEvents: "none", zIndex: 10, maxWidth: 320 }}
    >
      <Stack gap={2}>
        <Text size="sm" fw={600}>
          {arista.origen} {flecha} {arista.destino}
          {arista.tipo === "manual" && " (manual)"}
        </Text>
        <Text size="xs">Frecuencia total: {formatoPorcentaje(arista.frecuencia_total, 1)}</Text>
        <Text size="xs">
          {arista.origen} → {arista.destino}: {formatoPorcentaje(arista.frecuencia_origen_destino, 1)}
        </Text>
        <Text size="xs">
          {arista.destino} → {arista.origen}: {formatoPorcentaje(arista.frecuencia_destino_origen, 1)}
        </Text>
        <Text size="xs">Sin orientar: {formatoPorcentaje(arista.frecuencia_sin_orientar, 1)}</Text>
        <Text size="xs">ρ de Spearman: {arista.spearman === null ? "no calculable" : formatoRho(arista.spearman)}</Text>
        {arista.justificacion && <Text size="xs" c="dimmed">Justificación: {arista.justificacion}</Text>}
        {(sinOrientar || arista.tipo === "manual") && (
          <Text size="xs" c="blue">
            Clic para {sinOrientar ? "orientarla" : "cambiar o quitar la orientación"}.
          </Text>
        )}
      </Stack>
    </Paper>
  );
}

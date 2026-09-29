// Grafo pequeño del subgrafo del objetivo con la propagación de un escenario: qué variables
// cambiaron, cuánto y por dónde pasó el efecto. Las intervenidas llevan borde grueso y las
// extrapoladas un aviso; el color solo marca «cambió» (la cantidad va siempre en texto).
import { Box } from "@mantine/core";

import type { Esquemas } from "../../api/cliente";
import { cambio, disponerSubgrafo } from "../../estado/modeloCausal";

const ANCHO_NODO = 138;
const ALTO_NODO = 44;
const PASO_X = 178;
const PASO_Y = 62;
const MARGEN = 22;

interface Props {
  variables: string[];
  padres: Record<string, string[]>;
  resultado: Esquemas["ResultadoContrafactual"] | null;
}

const recortar = (texto: string, n = 20) => (texto.length > n ? `${texto.slice(0, n - 1)}…` : texto);

export function GrafoPropagacion({ variables, padres, resultado }: Props) {
  const nodos = disponerSubgrafo(variables, padres);
  const posicion = Object.fromEntries(
    nodos.map((n) => [n.variable, { x: MARGEN + n.columna * PASO_X, y: MARGEN + n.fila * PASO_Y }]),
  );
  const valores = Object.fromEntries((resultado?.valores ?? []).map((v) => [v.variable, v]));
  const cambio_ = (v: string) => valores[v]?.cambio ?? 0;
  const ancho = MARGEN * 2 + (Math.max(...nodos.map((n) => n.columna)) * PASO_X + ANCHO_NODO);
  const alto = MARGEN * 2 + (Math.max(...nodos.map((n) => n.fila)) * PASO_Y + ALTO_NODO) + 12;
  const medida = resultado?.medida ?? "probabilidad";

  return (
    <Box className="viz-causal" style={{ overflowX: "auto" }}>
      <svg
        viewBox={`0 0 ${ancho} ${alto}`}
        width={Math.min(ancho, 900)}
        style={{ display: "block", maxWidth: "100%", fontSize: 11 }}
        role="img"
        aria-label="Propagación del escenario por el grafo"
        data-testid="grafo-propagacion"
      >
        <defs>
          <marker id="flecha-propagacion" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="context-stroke" />
          </marker>
        </defs>
        {variables.flatMap((hijo) =>
          (padres[hijo] ?? []).map((padre) => {
            const a = posicion[padre];
            const b = posicion[hijo];
            const activa = cambio_(padre) !== 0 && cambio_(hijo) !== 0 && !valores[hijo]?.intervenida;
            const x1 = a.x + ANCHO_NODO;
            const y1 = a.y + ALTO_NODO / 2;
            const x2 = b.x - 2;
            const y2 = b.y + ALTO_NODO / 2;
            const salta = b.x - a.x > PASO_X;
            // Una arista que salta columnas se curva por encima de las filas (la cima de la
            // curva queda unos 16 px por encima de los nodos que cruza).
            const arriba = Math.min(a.y, b.y) - 30;
            const d = salta
              ? `M${x1},${y1} C${x1 + 30},${arriba} ${x2 - 30},${arriba} ${x2},${y2}`
              : `M${x1},${y1} L${x2},${y2}`;
            return (
              <path
                key={`${padre}->${hijo}`}
                d={d}
                fill="none"
                stroke={activa ? "var(--serie-1)" : "var(--viz-eje)"}
                strokeWidth={activa ? 2 : 1.2}
                markerEnd="url(#flecha-propagacion)"
              />
            );
          }),
        )}
        {nodos.map(({ variable }) => {
          const { x, y } = posicion[variable];
          const valor = valores[variable];
          const cambiada = (valor?.cambio ?? 0) !== 0;
          const esObjetivo = valor?.rol === "objetivo";
          const texto = !valor
            ? ""
            : valor.intervenida
              ? `intervenida (${cambio(valor.cambio)})`
              : cambiada
                ? `Δ ${cambio(valor.cambio, esObjetivo ? medida : "valor")}`
                : "sin cambio";
          return (
            <g key={variable} data-cambiada={cambiada ? "si" : "no"} data-variable={variable}>
              <title>{`${variable}: ${texto}`}</title>
              <rect
                x={x}
                y={y}
                width={ANCHO_NODO}
                height={ALTO_NODO}
                rx={6}
                fill={cambiada || valor?.intervenida ? "color-mix(in srgb, var(--serie-1) 16%, var(--viz-superficie))" : "var(--viz-superficie)"}
                stroke={cambiada || valor?.intervenida ? "var(--serie-1)" : "var(--viz-eje)"}
                strokeWidth={valor?.intervenida ? 3 : esObjetivo ? 2 : 1}
              />
              <text x={x + 8} y={y + 17} fill="currentColor" fontWeight={esObjetivo ? 700 : 500}>
                {recortar(variable)}
              </text>
              <text x={x + 8} y={y + 33} fill="var(--viz-texto)">
                {texto}
              </text>
              {valor?.extrapolacion && (
                <text x={x + ANCHO_NODO - 6} y={y + 15} textAnchor="end" fill="#e8590c" fontWeight={700}>
                  ⚠
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </Box>
  );
}

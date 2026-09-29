// Gráficos SVG del modelo causal: curva de efecto parcial con el histograma de train y curva
// de calibración. Colores: tonos 1 y 2 de la paleta categórica validada (claro/oscuro), ejes y
// histograma en grises neutros; el texto nunca lleva el color de la serie.
import { Box, Group, Paper, Text } from "@mantine/core";
import { useState, type PointerEvent } from "react";

import type { Esquemas } from "../../api/cliente";
import { numero, porcentaje } from "../../estado/modeloCausal";

export const ESTILO_GRAFICOS = `
.viz-causal {
  --serie-1: #2a78d6; --serie-2: #eb6834;
  --viz-eje: #d6d5cf; --viz-texto: #52514e; --viz-barra: #d9d8d2; --viz-superficie: #ffffff;
}
[data-mantine-color-scheme="dark"] .viz-causal {
  --serie-1: #3987e5; --serie-2: #d95926;
  --viz-eje: #3d3d3a; --viz-texto: #c3c2b7; --viz-barra: #45443f; --viz-superficie: #242424;
}`;

const ANCHO = 340;
const ALTO = 210;
const MARGEN = { izquierda: 44, derecha: 12, arriba: 10, abajo: 30 };
const ALTO_HISTOGRAMA = 36;

function escala(dominio: [number, number], rango: [number, number]) {
  const [d0, d1] = dominio;
  const [r0, r1] = rango;
  const ancho = d1 - d0 || 1;
  return (x: number) => r0 + ((x - d0) / ancho) * (r1 - r0);
}

function marcas(minimo: number, maximo: number, n = 4): number[] {
  if (minimo === maximo) return [minimo];
  return Array.from({ length: n + 1 }, (_, i) => minimo + ((maximo - minimo) * i) / n);
}

interface PropsCurva {
  efecto: Esquemas["EfectoParcial"];
  medida: "probabilidad" | "valor";
}

/** Efecto parcial de un padre sobre el objetivo, con la distribución de train debajo. */
export function CurvaEfecto({ efecto, medida }: PropsCurva) {
  const [activo, setActivo] = useState<number | null>(null);
  const { x, y, histograma } = efecto;
  const xMin = Math.min(...x, ...(histograma?.limites ?? []), ...(histograma?.valores ?? []));
  const xMax = Math.max(...x, ...(histograma?.limites ?? []), ...(histograma?.valores ?? []));
  const yMin = medida === "probabilidad" ? 0 : Math.min(...y);
  const yMax = medida === "probabilidad" ? Math.min(1, Math.max(0.1, Math.ceil(Math.max(...y) * 10) / 10)) : Math.max(...y);
  const abajoCurva = ALTO - MARGEN.abajo - ALTO_HISTOGRAMA - 6;
  const ex = escala([xMin, xMax], [MARGEN.izquierda, ANCHO - MARGEN.derecha]);
  const ey = escala([yMin, yMax], [abajoCurva, MARGEN.arriba]);
  const formatoY = (v: number) => (medida === "probabilidad" ? porcentaje(v, 0) : numero(v, 2));

  const conteos = histograma?.conteos ?? [];
  const maximoConteo = Math.max(1, ...conteos);
  const baseHistograma = ALTO - MARGEN.abajo;
  const barras =
    histograma?.tipo === "histograma" && histograma.limites
      ? conteos.map((c, i) => ({ x0: histograma.limites![i], x1: histograma.limites![i + 1], c }))
      : (histograma?.valores ?? []).map((v, i) => {
          const media = (xMax - xMin) / 40 || 0.5;
          return { x0: v - media, x1: v + media, c: conteos[i] };
        });

  const mover = (evento: PointerEvent<SVGRectElement>) => {
    const caja = evento.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const px = ((evento.clientX - caja.left) / caja.width) * ANCHO;
    let mejor = 0;
    x.forEach((valor, i) => {
      if (Math.abs(ex(valor) - px) < Math.abs(ex(x[mejor]) - px)) mejor = i;
    });
    setActivo(mejor);
  };

  const puntos = x.map((valor, i) => `${ex(valor)},${ey(y[i])}`).join(" ");
  return (
    <Box pos="relative" className="viz-causal">
      <svg
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        width="100%"
        role="img"
        aria-label={`Efecto parcial de ${efecto.padre}`}
        style={{ display: "block", fontSize: 10 }}
      >
        {marcas(yMin, yMax, medida === "probabilidad" ? Math.round(yMax * 10) / (yMax > 0.5 ? 2 : 1) : 3).map((v) => (
          <g key={v}>
            <line x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={ey(v)} y2={ey(v)} stroke="var(--viz-eje)" strokeWidth={1} />
            <text x={MARGEN.izquierda - 4} y={ey(v) + 3} textAnchor="end" fill="var(--viz-texto)">
              {formatoY(v)}
            </text>
          </g>
        ))}
        {barras.map((b, i) => {
          const alto = (ALTO_HISTOGRAMA * b.c) / maximoConteo;
          return (
            <rect
              key={i}
              x={ex(b.x0) + 1}
              width={Math.max(ex(b.x1) - ex(b.x0) - 2, 1)}
              y={baseHistograma - alto}
              height={alto}
              fill="var(--viz-barra)"
              rx={alto > 4 ? 2 : 0}
            />
          );
        })}
        <line x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={baseHistograma} y2={baseHistograma} stroke="var(--viz-eje)" />
        {marcas(xMin, xMax, 3).map((v) => (
          <text key={v} x={ex(v)} y={ALTO - MARGEN.abajo + 13} textAnchor="middle" fill="var(--viz-texto)">
            {numero(v, 2)}
          </text>
        ))}
        <polyline points={puntos} fill="none" stroke="var(--serie-1)" strokeWidth={2} strokeLinejoin="round" />
        {activo !== null && (
          <g>
            <line x1={ex(x[activo])} x2={ex(x[activo])} y1={MARGEN.arriba} y2={baseHistograma} stroke="var(--viz-texto)" strokeWidth={1} opacity={0.4} />
            <circle cx={ex(x[activo])} cy={ey(y[activo])} r={4} fill="var(--serie-1)" stroke="var(--viz-superficie)" strokeWidth={2} />
          </g>
        )}
        <rect
          x={MARGEN.izquierda}
          y={MARGEN.arriba}
          width={ANCHO - MARGEN.izquierda - MARGEN.derecha}
          height={baseHistograma - MARGEN.arriba}
          fill="transparent"
          onPointerMove={mover}
          onPointerLeave={() => setActivo(null)}
        />
      </svg>
      {activo !== null && (
        <Paper
          withBorder
          shadow="xs"
          px={6}
          py={2}
          pos="absolute"
          top={0}
          left={`${(100 * ex(x[activo])) / ANCHO}%`}
          style={{ transform: "translateX(-50%)", pointerEvents: "none" }}
        >
          <Text size="xs">
            {efecto.padre} = {numero(x[activo], 2)} → {formatoY(y[activo])}
          </Text>
        </Paper>
      )}
      <Text size="xs" c="dimmed" ta="center">
        {efecto.padre} (unidades originales) · barras: datos de entrenamiento
      </Text>
    </Box>
  );
}

// --- Calibración ------------------------------------------------------------------------------

type Punto = Esquemas["PuntoCalibracion"];

export function GraficoCalibracion({ cv, test }: { cv: Punto[]; test: Punto[] }) {
  const [activo, setActivo] = useState<{ serie: string; punto: Punto } | null>(null);
  const lado = 220;
  const m = 34;
  const e = escala([0, 1], [m, lado - 8]);
  const ey = escala([0, 1], [lado - m + 8, 8]);
  const series = [
    { nombre: "Validación cruzada", color: "var(--serie-1)", puntos: cv },
    { nombre: "Test", color: "var(--serie-2)", puntos: test },
  ];
  return (
    <Box className="viz-causal" pos="relative" maw={320}>
      <Group gap="md" mb={4}>
        {series.map((s) => (
          <Group key={s.nombre} gap={4}>
            <svg width={18} height={8} aria-hidden>
              <line x1={0} x2={18} y1={4} y2={4} stroke={s.color} strokeWidth={2} />
            </svg>
            <Text size="xs">{s.nombre}</Text>
          </Group>
        ))}
      </Group>
      <svg viewBox={`0 0 ${lado} ${lado}`} width="100%" role="img" aria-label="Curva de calibración" style={{ display: "block", fontSize: 9 }}>
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v}>
            <line x1={e(0)} x2={e(1)} y1={ey(v)} y2={ey(v)} stroke="var(--viz-eje)" />
            <text x={m - 4} y={ey(v) + 3} textAnchor="end" fill="var(--viz-texto)">
              {porcentaje(v, 0)}
            </text>
            <text x={e(v)} y={lado - m + 20} textAnchor="middle" fill="var(--viz-texto)">
              {porcentaje(v, 0)}
            </text>
          </g>
        ))}
        <line x1={e(0)} y1={ey(0)} x2={e(1)} y2={ey(1)} stroke="var(--viz-texto)" strokeWidth={1} opacity={0.5} />
        {series.map((s) => (
          <g key={s.nombre}>
            <polyline
              points={s.puntos.map((p) => `${e(p.probabilidad_media)},${ey(p.frecuencia_observada)}`).join(" ")}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
            />
            {s.puntos.map((p, i) => (
              <g key={i} onPointerEnter={() => setActivo({ serie: s.nombre, punto: p })} onPointerLeave={() => setActivo(null)}>
                <circle cx={e(p.probabilidad_media)} cy={ey(p.frecuencia_observada)} r={10} fill="transparent" />
                <circle cx={e(p.probabilidad_media)} cy={ey(p.frecuencia_observada)} r={3.5} fill={s.color} stroke="var(--viz-superficie)" strokeWidth={1.5} />
              </g>
            ))}
          </g>
        ))}
      </svg>
      <Text size="xs" c="dimmed" ta="center">
        Probabilidad predicha (x) frente a frecuencia observada (y); la diagonal es la calibración perfecta.
      </Text>
      {activo && (
        <Paper withBorder shadow="xs" px={6} py={2} pos="absolute" top={24} right={0} style={{ pointerEvents: "none" }}>
          <Text size="xs">
            {activo.serie}: predicha {porcentaje(activo.punto.probabilidad_media)}, observada{" "}
            {porcentaje(activo.punto.frecuencia_observada)} ({activo.punto.filas} filas)
          </Text>
        </Paper>
      )}
    </Box>
  );
}

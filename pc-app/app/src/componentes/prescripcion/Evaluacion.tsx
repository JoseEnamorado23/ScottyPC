// Evaluación del prescriptor sobre test (interna, según el modelo): métricas, sensibilidad al
// cambio máximo y a μ, y comparación de los dos optimizadores con la prueba de McNemar.
import { Alert, Box, Button, Card, Group, Paper, Select, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import { IconChartLine, IconInfoCircle } from "@tabler/icons-react";
import { useEffect, useState } from "react";

import { useAccionesPrescripcion, useEvaluacion, useEvaluaciones } from "../../api/prescripcion";
import { decimalFijo, numero, porcentaje } from "../../estado/modeloCausal";
import { MensajeError } from "../MensajeError";

const NOMBRE_OPTIMIZADOR: Record<string, string> = { gradiente_proximal: "Gradiente proximal", genetico: "Genético" };

/** Tasa de éxito frente a un parámetro: una sola serie (el título la nombra), con tooltip. */
function GraficoSensibilidad({ titulo, puntos }: { titulo: string; puntos: { etiqueta: string; tasa: number }[] }) {
  const [activo, setActivo] = useState<number | null>(null);
  const ancho = 300;
  const alto = 150;
  const m = { izq: 40, der: 12, arr: 10, aba: 26 };
  const x = (i: number) => m.izq + (i * (ancho - m.izq - m.der)) / Math.max(puntos.length - 1, 1);
  const y = (t: number) => alto - m.aba - t * (alto - m.arr - m.aba);
  return (
    <Box className="viz-causal" pos="relative">
      <Text size="sm" fw={600} mb={4}>{titulo}</Text>
      <svg viewBox={`0 0 ${ancho} ${alto}`} width="100%" role="img" aria-label={titulo} style={{ display: "block", fontSize: 10 }}>
        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <line x1={m.izq} x2={ancho - m.der} y1={y(t)} y2={y(t)} stroke="var(--viz-eje)" />
            <text x={m.izq - 4} y={y(t) + 3} textAnchor="end" fill="var(--viz-texto)">{porcentaje(t, 0)}</text>
          </g>
        ))}
        <polyline points={puntos.map((p, i) => `${x(i)},${y(p.tasa)}`).join(" ")} fill="none" stroke="var(--serie-1)" strokeWidth={2} />
        {puntos.map((p, i) => (
          <g key={p.etiqueta} onPointerEnter={() => setActivo(i)} onPointerLeave={() => setActivo(null)}>
            <circle cx={x(i)} cy={y(p.tasa)} r={12} fill="transparent" />
            <circle cx={x(i)} cy={y(p.tasa)} r={4} fill="var(--serie-1)" stroke="var(--viz-superficie)" strokeWidth={2} />
            <text x={x(i)} y={alto - 8} textAnchor="middle" fill="var(--viz-texto)">{p.etiqueta}</text>
          </g>
        ))}
      </svg>
      {activo !== null && (
        <Paper withBorder shadow="xs" px={6} py={2} pos="absolute" top={20} right={0} style={{ pointerEvents: "none" }}>
          <Text size="xs">{puntos[activo].etiqueta}: éxito {porcentaje(puntos[activo].tasa)}</Text>
        </Paper>
      )}
    </Box>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <Paper withBorder p="sm">
      <Text size="xs" c="dimmed">{etiqueta}</Text>
      <Text fw={700} size="lg">{valor}</Text>
    </Paper>
  );
}

export function EvaluacionPrescriptor({ proyectoId, bloqueado, enCurso }: { proyectoId: string; bloqueado: boolean; enCurso: boolean }) {
  const lista = useEvaluaciones(proyectoId, true);
  const acciones = useAccionesPrescripcion(proyectoId);
  const [numero_, setNumero] = useState<number | null>(null);
  const evaluaciones = lista.data ?? [];
  useEffect(() => {
    if (evaluaciones.length && (numero_ === null || !evaluaciones.some((e) => e.numero === numero_))) {
      setNumero(evaluaciones[evaluaciones.length - 1].numero);
    }
  }, [evaluaciones, numero_]);
  const informe = useEvaluacion(proyectoId, numero_);
  const e = informe.data?.evaluacion;

  return (
    <Stack>
      <Group>
        <Button leftSection={<IconChartLine size={16} />} onClick={() => acciones.evaluar.mutate()} loading={acciones.evaluar.isPending}
          disabled={bloqueado || enCurso}>
          Evaluar sobre test
        </Button>
        {evaluaciones.length > 0 && (
          <Select w={280} allowDeselect={false} aria-label="Evaluación" value={numero_ === null ? null : String(numero_)}
            onChange={(v) => setNumero(Number(v))}
            data={evaluaciones.map((x) => ({ value: String(x.numero), label: `Evaluación ${x.numero} · ${x.casos} casos` }))} />
        )}
      </Group>
      {!e ? (
        <Text size="sm" c="dimmed">Todavía no hay evaluaciones.</Text>
      ) : (
        <Stack data-testid="evaluacion-prescriptor">
          <Alert color="blue" variant="light" icon={<IconInfoCircle size={18} />}>{e.texto}</Alert>
          <SimpleGrid cols={{ base: 2, md: 4 }}>
            <Dato etiqueta="Tasa de éxito" valor={porcentaje(e.tasa_exito)} />
            <Dato etiqueta="No alcanzables" valor={`${e.no_alcanzables} de ${e.casos}`} />
            <Dato etiqueta="Acciones en cero" valor={`${decimalFijo(e.porcentaje_acciones_en_cero, 1)} %`} />
            <Dato etiqueta="Requieren revisión" valor={`${decimalFijo(e.porcentaje_requiere_revision, 1)} %`} />
          </SimpleGrid>
          <Card withBorder>
            <Title order={5} mb="xs">Cambio medio por acción (unidades originales)</Title>
            <Table verticalSpacing={2}>
              <Table.Thead>
                <Table.Tr><Table.Th>Variable</Table.Th><Table.Th ta="right">Cambio medio</Table.Th><Table.Th ta="right">Cambio absoluto medio</Table.Th><Table.Th ta="right">Casos</Table.Th></Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {Object.entries(e.cambio_medio).map(([v, x]) => (
                  <Table.Tr key={v}>
                    <Table.Td>{v}</Table.Td>
                    <Table.Td ta="right">{numero(x.cambio_medio, 3)}</Table.Td>
                    <Table.Td ta="right">{numero(x.cambio_absoluto_medio, 3)}</Table.Td>
                    <Table.Td ta="right">{x.usos}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <GraficoSensibilidad titulo="Éxito según el cambio máximo (% del rango)"
              puntos={e.sensibilidad_cambio_maximo.map((s) => ({ etiqueta: `${Math.round(100 * s.fraccion_rango)} %`, tasa: s.tasa_exito }))} />
            <GraficoSensibilidad titulo="Éxito según μ"
              puntos={e.sensibilidad_mu.map((s) => ({ etiqueta: `μ × ${numero(s.factor, 2)}`, tasa: s.tasa_exito }))} />
          </SimpleGrid>
          <Card withBorder data-testid="comparacion-optimizadores">
            <Title order={5} mb="xs">Comparación de optimizadores (mismos casos)</Title>
            <Table verticalSpacing={2}>
              <Table.Thead>
                <Table.Tr><Table.Th>Optimizador</Table.Th><Table.Th ta="right">Éxito</Table.Th><Table.Th ta="right">Costo medio</Table.Th><Table.Th ta="right">Segundos por caso</Table.Th></Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {e.comparacion_optimizadores.map((c) => (
                  <Table.Tr key={c.optimizador}>
                    <Table.Td>{NOMBRE_OPTIMIZADOR[c.optimizador] ?? c.optimizador}</Table.Td>
                    <Table.Td ta="right">{porcentaje(c.tasa_exito)}</Table.Td>
                    <Table.Td ta="right">{numero(c.costo_medio, 3)}</Table.Td>
                    <Table.Td ta="right">{numero(c.segundos_medios, 3)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Text size="sm" mt="xs">
              {String(e.mcnemar.prueba)}: {String(e.mcnemar.solo_gradiente)} casos solo con gradiente proximal,{" "}
              {String(e.mcnemar.solo_genetico)} solo con el genético; p = {numero(Number(e.mcnemar.p_valor), 4)}.
            </Text>
          </Card>
        </Stack>
      )}
      <MensajeError error={acciones.evaluar.error ?? informe.error} titulo="No se pudo evaluar" />
    </Stack>
  );
}

// Evidencia de vecinos (resultado observado de los casos de train parecidos con las acciones
// prescritas) y comparador de métodos. El gráfico es una sola serie (mejora observada frente a no
// intervenir, positiva = mejor): el prescriptor en el tono 1, los demás métodos en gris neutro; el
// texto nunca lleva el color de la serie. La tabla debajo es también la vista accesible.
import { Alert, Badge, Box, Card, Group, Paper, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import { IconDatabaseSearch, IconInfoCircle } from "@tabler/icons-react";
import { useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { cambio, decimalFijo, numero, porcentaje } from "../../estado/modeloCausal";

type Evidencia = Esquemas["EvidenciaVecinos"];
type Resumen = Esquemas["ResumenEvidencia"];
type Metodo = Esquemas["MetodoComparado"];
type Medida = "probabilidad" | "valor";

const valorMedida = (v: number | null | undefined, medida: Medida) => (medida === "probabilidad" ? porcentaje(v) : numero(v));
const porcentajeDirecto = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${decimalFijo(v, 1)} %`);
const pValor = (p: number | null | undefined) => (p === null || p === undefined ? "—" : p < 0.0001 ? "< 0,0001" : numero(p, 4));

function Dato({ etiqueta, valor, detalle }: { etiqueta: string; valor: string; detalle?: string }) {
  return (
    <Paper withBorder p="sm">
      <Text size="xs" c="dimmed">{etiqueta}</Text>
      <Text fw={700} size="lg">{valor}</Text>
      {detalle && <Text size="xs" c="dimmed">{detalle}</Text>}
    </Paper>
  );
}

/** Evidencia de un caso: los vecinos con la prescripción frente a los vecinos con los valores actuales. */
export function EvidenciaCaso({ e, medida, objetivo, clasePositiva }: { e: Evidencia; medida: Medida; objetivo: string; clasePositiva: number }) {
  const que = medida === "probabilidad" ? `Con ${objetivo} = ${clasePositiva}` : `Media de ${objetivo}`;
  return (
    <Card withBorder data-testid="evidencia-caso">
      <Group justify="space-between" mb="xs">
        <Group gap={6}>
          <IconDatabaseSearch size={18} />
          <Title order={5}>Evidencia en los datos</Title>
        </Group>
        {e.prescrita.con_respaldo
          ? <Badge color="green" variant="light">Con respaldo en los datos</Badge>
          : <Badge color="orange" variant="light">Poco respaldo en los datos</Badge>}
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <Dato etiqueta={`${e.k} vecinos con la prescripción`} valor={valorMedida(e.prescrita.valor, medida)} detalle={que} />
        <Dato etiqueta={`${e.k} vecinos con los valores actuales`} valor={valorMedida(e.actual.valor, medida)} detalle={que} />
        <Dato etiqueta="Mejora observada" valor={cambio(e.mejora, medida)} detalle="Positiva = los vecinos están mejor" />
      </SimpleGrid>
      <Text size="sm" mt="xs">{e.texto}</Text>
    </Card>
  );
}

/** Mejora observada en los vecinos de cada método (barras desde 0 = no intervenir). */
function GraficoComparador({ metodos, medida }: { metodos: Metodo[]; medida: Medida }) {
  const filas = metodos.filter((m) => m.mejora_vecinos_media !== null && m.metodo !== "sin_intervencion");
  const [activo, setActivo] = useState<number | null>(null);
  if (!filas.length) return null;
  const ancho = 560;
  const alto = 22 + filas.length * 34;
  const m = { izq: 200, der: 70, arr: 8, aba: 16 };
  const valores = filas.map((f) => f.mejora_vecinos_media as number);
  const tope = Math.max(...valores.map(Math.abs), 1e-9) * 1.1;
  const minimo = Math.min(0, ...valores) < 0 ? -tope : 0;
  const x = (v: number) => m.izq + ((v - minimo) / (tope - minimo)) * (ancho - m.izq - m.der);
  const banda = (alto - m.arr - m.aba) / filas.length;
  const grosor = 14;
  return (
    <Box className="viz-causal" pos="relative">
      <Text size="sm" fw={600} mb={4}>Mejora observada en los vecinos frente a no intervenir</Text>
      <svg viewBox={`0 0 ${ancho} ${alto}`} width="100%" role="img" aria-label="Mejora observada en los vecinos por método"
        style={{ display: "block", fontSize: 11 }}>
        <line x1={x(0)} x2={x(0)} y1={m.arr} y2={alto - m.aba} stroke="var(--viz-texto)" strokeWidth={1} />
        <text x={x(0)} y={alto - 3} textAnchor="middle" fill="var(--viz-texto)">0 = sin intervención</text>
        {filas.map((f, i) => {
          const v = f.mejora_vecinos_media as number;
          const y = m.arr + i * banda + (banda - grosor) / 2;
          const x0 = Math.min(x(0), x(v));
          const largo = Math.max(Math.abs(x(v) - x(0)), 1);
          return (
            <g key={f.metodo} onPointerEnter={() => setActivo(i)} onPointerLeave={() => setActivo(null)} data-testid={`barra-${f.metodo}`}>
              <rect x={0} y={m.arr + i * banda} width={ancho} height={banda} fill="transparent" />
              <text x={m.izq - 8} y={y + grosor / 2 + 4} textAnchor="end" fill="var(--viz-texto)">{f.nombre}</text>
              <rect x={x0} y={y} width={largo} height={grosor} rx={4}
                fill={f.metodo === "prescriptor" ? "var(--serie-1)" : "var(--viz-barra)"} />
              <text x={v >= 0 ? x(v) + 6 : x(v) - 6} y={y + grosor / 2 + 4} textAnchor={v >= 0 ? "start" : "end"} fill="var(--viz-texto)">
                {cambio(v, medida)}
              </text>
            </g>
          );
        })}
      </svg>
      {activo !== null && (
        <Paper withBorder shadow="xs" px={8} py={4} pos="absolute" top={24} right={0} style={{ pointerEvents: "none" }}>
          <Text size="xs" fw={600}>{filas[activo].nombre}</Text>
          <Text size="xs">Mejora en vecinos: {cambio(filas[activo].mejora_vecinos_media as number, medida)}</Text>
          <Text size="xs">Con respaldo: {porcentajeDirecto(filas[activo].porcentaje_con_respaldo)} · Costo medio: {numero(filas[activo].costo_medio, 3)}</Text>
          {filas[activo].p_valor_frente_prescriptor !== null && (
            <Text size="xs">p frente al prescriptor: {pValor(filas[activo].p_valor_frente_prescriptor)}</Text>
          )}
        </Paper>
      )}
    </Box>
  );
}

/** Resumen de la evidencia de vecinos del prescriptor (casos con respaldo). */
function ResumenVecinos({ e, medida }: { e: Resumen; medida: Medida }) {
  const intervalo = e.intervalo_mejora;
  return (
    <Card withBorder data-testid="evidencia-vecinos">
      <Group gap={6} mb="xs">
        <IconDatabaseSearch size={18} />
        <Title order={5}>Evidencia de vecinos (datos observados)</Title>
      </Group>
      <Alert color="blue" variant="light" icon={<IconInfoCircle size={18} />} mb="sm">{e.texto}</Alert>
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Dato etiqueta="Prescripciones con respaldo" valor={porcentajeDirecto(e.porcentaje_con_respaldo)}
          detalle={`${e.con_respaldo} de ${e.casos} casos · k = ${e.k}`} />
        <Dato etiqueta="Mejora observada media" valor={e.mejora_media === null ? "—" : cambio(e.mejora_media, medida)}
          detalle={intervalo ? `IC 95 %: ${cambio(intervalo[0], medida)} a ${cambio(intervalo[1], medida)}` : undefined} />
        <Dato etiqueta="Vecinos con la prescripción" valor={valorMedida(e.valor_prescrita_medio, medida)}
          detalle={`Con los valores actuales: ${valorMedida(e.valor_actual_medio, medida)}`} />
        <Dato etiqueta="p (Wilcoxon)" valor={pValor(e.p_valor)} detalle="Prescripción frente a valores actuales" />
        <Dato etiqueta="Casos en que los vecinos mejoran" valor={porcentajeDirecto(e.porcentaje_mejora_positiva)} />
        <Dato etiqueta="Vecinos que cumplen el objetivo" valor={porcentajeDirecto(e.porcentaje_cumple)} />
        <Dato etiqueta="Coincidencia modelo / vecinos" valor={porcentajeDirecto(e.coincidencia_modelo)}
          detalle="Ambos dicen lo mismo sobre si se cumple" />
      </SimpleGrid>
      <Text size="xs" c="dimmed" mt="xs">
        Sobre los casos cuya prescripción tiene respaldo: sus vecinos están tan cerca como los de un caso típico de train.
      </Text>
    </Card>
  );
}

export function EvidenciaYComparador({ evidencia, metodos, texto, medida }: {
  evidencia: Resumen | null | undefined; metodos: Metodo[]; texto: string | null | undefined; medida: Medida;
}) {
  if (!evidencia && !metodos.length) {
    return (
      <Text size="sm" c="dimmed" data-testid="sin-evidencia">
        Esta evaluación es anterior a la evidencia de vecinos y al comparador: evalúe de nuevo para verlos.
      </Text>
    );
  }
  return (
    <Stack>
      {evidencia && <ResumenVecinos e={evidencia} medida={medida} />}
      {metodos.length > 0 && (
        <Card withBorder data-testid="comparador-metodos">
          <Title order={5} mb="xs">Comparador de métodos (mismos casos, mismas restricciones)</Title>
          {texto && <Text size="xs" c="dimmed" mb="sm">{texto}</Text>}
          <GraficoComparador metodos={metodos} medida={medida} />
          <Table.ScrollContainer minWidth={820} mt="sm">
            <Table verticalSpacing={2}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Método</Table.Th>
                  <Table.Th ta="right">Éxito (modelo causal)</Table.Th>
                  <Table.Th ta="right">Éxito (referencia)</Table.Th>
                  <Table.Th ta="right">Con respaldo</Table.Th>
                  <Table.Th ta="right">Cumple en vecinos</Table.Th>
                  <Table.Th ta="right">Mejora en vecinos</Table.Th>
                  <Table.Th ta="right">p frente al prescriptor</Table.Th>
                  <Table.Th ta="right">Costo medio</Table.Th>
                  <Table.Th ta="right">Acciones</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {metodos.map((x) => (
                  <Table.Tr key={x.metodo} fw={x.metodo === "prescriptor" ? 600 : undefined}>
                    <Table.Td>{x.nombre}</Table.Td>
                    <Table.Td ta="right">{porcentaje(x.tasa_exito_causal)}</Table.Td>
                    <Table.Td ta="right">{porcentaje(x.tasa_exito_referencia)}</Table.Td>
                    <Table.Td ta="right">{porcentajeDirecto(x.porcentaje_con_respaldo)}</Table.Td>
                    <Table.Td ta="right">{porcentaje(x.tasa_cumple_vecinos)}</Table.Td>
                    <Table.Td ta="right">{x.mejora_vecinos_media === null ? "—" : cambio(x.mejora_vecinos_media, medida)}</Table.Td>
                    <Table.Td ta="right">{x.metodo === "prescriptor" ? "—" : pValor(x.p_valor_frente_prescriptor)}</Table.Td>
                    <Table.Td ta="right">{numero(x.costo_medio, 3)}</Table.Td>
                    <Table.Td ta="right">{numero(x.acciones_medias, 2)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Card>
      )}
    </Stack>
  );
}

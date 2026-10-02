// Prescripción de un caso: selector (fila de test o valores propios), acciones ordenadas por
// contribución, probabilidad antes y después, marcas, restricciones activas, explicación y la
// propagación por el grafo. «Probar una variante» abre el explorador de escenarios con la
// prescripción precargada.
import {
  Alert, Badge, Button, Card, Grid, Group, NumberInput, Paper, SegmentedControl, Select, Stack, Table, Text, Title,
} from "@mantine/core";
import { IconAdjustmentsAlt, IconAlertTriangle, IconArrowRight } from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import type { Esquemas } from "../../api/cliente";
import { useCasosModelo, useModeloCausal } from "../../api/modeloCausal";
import { usePrescripcionCaso } from "../../api/prescripcion";
import { cambio, numero, porcentaje, textoValor } from "../../estado/modeloCausal";
import { intervencionesDe, type VarianteEscenario } from "../../estado/prescripcion";
import { MensajeError } from "../MensajeError";
import { GrafoPropagacion } from "../modelo_causal/GrafoPropagacion";

type Resultado = Esquemas["ResultadoPrescripcion"];
type CasoTest = Esquemas["CasoTest"];

const RESTRICCION: Record<string, string> = {
  limite: "límite", cambio_maximo: "cambio máximo", direccion: "dirección", estados_permitidos: "estados permitidos",
};

export function TarjetaPrescripcion({ r, proyectoId, indiceTest }: { r: Resultado; proyectoId: string; indiceTest: number | null }) {
  const navegar = useNavigate();
  const modelo = useModeloCausal(proyectoId, true);
  const probabilidad = r.medida === "probabilidad";
  const formato = (v: number) => (probabilidad ? porcentaje(v) : numero(v));
  const variante: VarianteEscenario = { indice_test: indiceTest, intervenciones: intervencionesDe(r) };
  return (
    <Stack data-testid="prescripcion-caso">
      <Grid>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper withBorder p="md">
            <Text size="sm" c="dimmed">{probabilidad ? `Probabilidad de ${r.objetivo} = 1` : `Valor esperado de ${r.objetivo}`}</Text>
            <Group gap="xs" mt={4}>
              <Title order={3}>{formato(r.antes)}</Title>
              <IconArrowRight size={20} />
              <Title order={3} data-testid="prescripcion-despues">{formato(r.despues)}</Title>
            </Group>
            <Text size="sm" mt={4}>Objetivo: {r.direccion === "bajar" ? "≤" : "≥"} {formato(r.deseado)}</Text>
            <Group gap={6} mt="xs">
              {r.ya_cumple ? (
                <Badge color="gray" variant="light">Ya cumple el objetivo</Badge>
              ) : r.alcanzado ? (
                <Badge color="green" variant="light">Alcanza el objetivo</Badge>
              ) : (
                <Badge color="red" variant="light">No alcanzable (faltan {formato(r.falta)})</Badge>
              )}
              {r.requiere_revision && <Badge color="orange" variant="light" leftSection={<IconAlertTriangle size={12} />}>Requiere revisión</Badge>}
              {r.extrapolacion && <Badge color="orange" variant="light">Extrapolación</Badge>}
              {r.aproximado && <Badge color="gray" variant="light">Monte Carlo</Badge>}
            </Group>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card withBorder>
            <Text size="sm" data-testid="explicacion">{r.explicacion}</Text>
            {r.requiere_revision && (
              <Text size="xs" c="dimmed" mt="xs">
                El modelo de referencia (todas las variables) no coincide con el modelo causal en si se alcanza el objetivo
                {r.referencia.despues !== undefined && ` (según la referencia: ${formato(Number(r.referencia.despues))})`}.
              </Text>
            )}
          </Card>
        </Grid.Col>
      </Grid>

      {r.acciones.length > 0 && (
        <Table verticalSpacing={4} data-testid="acciones-prescritas">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Acción</Table.Th>
              <Table.Th>Antes → después</Table.Th>
              <Table.Th ta="right">Cambio</Table.Th>
              <Table.Th ta="right">Contribución</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {r.acciones.map((a) => (
              <Table.Tr key={a.variable}>
                <Table.Td>{a.variable}</Table.Td>
                <Table.Td>{textoValor(a.antes)} → {textoValor(a.despues)}</Table.Td>
                <Table.Td ta="right">{a.mantener ? "mantener" : a.cambio === null ? "—" : cambio(a.cambio)}</Table.Td>
                <Table.Td ta="right">{cambio(a.contribucion, r.medida)}</Table.Td>
                <Table.Td>
                  {a.restriccion_activa && <Badge size="xs" variant="light">{RESTRICCION[a.restriccion_activa]}</Badge>}
                  {a.extrapolacion && <Badge size="xs" color="orange" variant="light">extrapolación</Badge>}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {r.sin_cambio.length > 0 && <Text size="xs" c="dimmed">Sin cambio: {r.sin_cambio.join(", ")}.</Text>}
      {r.restricciones_activas.length > 0 && (
        <Alert color="orange" variant="light" title="Restricciones que impiden alcanzar el objetivo" data-testid="restricciones-activas">
          {r.restricciones_activas.map((x) => `${x.variable}: ${x.mensaje}`).join("; ")}. Relájelas en la configuración si procede.
        </Alert>
      )}
      {modelo.data && (
        <GrafoPropagacion variables={modelo.data.modelo.subgrafo.variables} padres={modelo.data.modelo.subgrafo.padres} resultado={r} />
      )}
      <Group>
        <Button
          variant="light" leftSection={<IconAdjustmentsAlt size={16} />} disabled={r.acciones.length === 0}
          onClick={() => navegar(`/proyectos/${proyectoId}/modelo-causal`, { state: { variante } })}
        >
          Probar una variante
        </Button>
        <Text size="xs" c="dimmed">Abre el explorador de escenarios con esta prescripción para ajustarla a mano.</Text>
      </Group>
    </Stack>
  );
}

export function CasoIndividual({ proyectoId, bloqueado }: { proyectoId: string; bloqueado: boolean }) {
  const modelo = useModeloCausal(proyectoId, true);
  const [fuente, setFuente] = useState<"test" | "propio">("test");
  const [pagina, setPagina] = useState(1);
  const casos = useCasosModelo(proyectoId, pagina, true);
  const [fila, setFila] = useState<CasoTest | null>(null);
  const [propios, setPropios] = useState<Record<string, unknown>>({});
  useEffect(() => {
    if (!fila && casos.data?.filas.length) setFila(casos.data.filas[0]);
  }, [casos.data, fila]);
  const solicitud = useMemo(() => {
    if (bloqueado) return null;
    if (fuente === "test") return fila ? { caso: { indice_test: fila.indice } } : null;
    return { caso: { valores: propios } };
  }, [bloqueado, fuente, fila, propios]);
  const resultado = usePrescripcionCaso(proyectoId, solicitud);
  const totalPaginas = casos.data ? Math.max(1, Math.ceil(casos.data.total / casos.data.por_pagina)) : 1;
  const controles = modelo.data?.controles ?? [];

  return (
    <Stack>
      <Card withBorder>
        <Stack gap="xs">
          <SegmentedControl
            value={fuente}
            onChange={(v) => {
              if (v === "propio") setPropios({ ...(fila?.valores ?? {}) });
              setFuente(v as "test" | "propio");
            }}
            data={[{ value: "test", label: "Fila de test" }, { value: "propio", label: "Valores propios" }]}
            w={300}
          />
          {fuente === "test" ? (
            <Group align="flex-end">
              <Select
                label="Caso" w={360} searchable aria-label="Caso a prescribir"
                data={(casos.data?.filas ?? []).map((c) => ({ value: String(c.indice), label: `Fila ${c.indice} · observado: ${textoValor(c.objetivo)}` }))}
                value={fila ? String(fila.indice) : null}
                onChange={(v) => setFila(casos.data?.filas.find((c) => String(c.indice) === v) ?? null)}
              />
              <Button size="xs" variant="default" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anteriores</Button>
              <Text size="xs" c="dimmed">{pagina} / {totalPaginas}</Text>
              <Button size="xs" variant="default" disabled={pagina >= totalPaginas} onClick={() => setPagina(pagina + 1)}>Siguientes</Button>
            </Group>
          ) : (
            <Grid>
              {controles.map((c) => (
                <Grid.Col key={c.nombre} span={{ base: 12, sm: 6, md: 4 }}>
                  {c.control === "numerica" ? (
                    <NumberInput size="xs" label={c.nombre} decimalSeparator=","
                      value={typeof propios[c.nombre] === "number" ? (propios[c.nombre] as number) : ""}
                      onChange={(v) => setPropios({ ...propios, [c.nombre]: typeof v === "number" ? v : null })} />
                  ) : (
                    <Select size="xs" label={c.nombre} data={c.categorias.map((x) => ({ value: String(x), label: String(x) }))}
                      value={propios[c.nombre] === null || propios[c.nombre] === undefined ? null : String(propios[c.nombre])}
                      onChange={(v) => setPropios({ ...propios, [c.nombre]: c.categorias.find((x) => String(x) === v) ?? v })} />
                  )}
                </Grid.Col>
              ))}
            </Grid>
          )}
        </Stack>
      </Card>
      {bloqueado && <Alert color="orange">Resuelva los bloqueantes (y guarde la configuración) para prescribir.</Alert>}
      <MensajeError error={resultado.error} titulo="No se pudo prescribir" />
      {resultado.data && (
        <TarjetaPrescripcion r={resultado.data} proyectoId={proyectoId} indiceTest={fuente === "test" ? (fila?.indice ?? null) : null} />
      )}
    </Stack>
  );
}

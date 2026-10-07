import { Accordion, Alert, Badge, Button, Card, Center, Group, Loader, Slider, Stack, Table, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconInfoCircle } from "@tabler/icons-react";
import { useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { useFormulasModeloCausal } from "../../api/consultas";
import { MensajeError } from "../MensajeError";
import { PanelUmbrales, PasoVista, PasosEnTarjetas, SinEtapa, TablaEntradas } from "./Comunes";

type Traza = Esquemas["TrazaModeloCausal"];
type Mecanismo = Esquemas["MecanismoExplicado"];
type Control = Esquemas["ControlCaso"];

const RETARDO_MS = 300;
const PASOS_DESLIZADOR = 100;

const coma = (v: number | null | undefined, decimales = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(decimales).replace(".", ",");

function Candidatos({ mecanismo }: { mecanismo: Mecanismo }) {
  return (
    <Table fz="xs" withTableBorder mb="xs">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Candidato</Table.Th>
          <Table.Th>Familia</Table.Th>
          <Table.Th>CV ({mecanismo.metrica === "exactitud_balanceada" ? "exactitud balanceada" : "R²"})</Table.Th>
          <Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {mecanismo.candidatos.map((c) => (
          <Table.Tr key={c.tipo}>
            <Table.Td>{c.tipo}</Table.Td>
            <Table.Td>{c.nombre_familia}</Table.Td>
            <Table.Td>{c.puntuacion_cv === null ? c.error ?? "—" : coma(c.puntuacion_cv)}</Table.Td>
            <Table.Td>
              {c.tipo === mecanismo.elegido_guardado && <Badge size="xs" color="green">Elegido</Badge>}
              {mecanismo.cambiaria && c.tipo === mecanismo.elegido && (
                <Badge size="xs" color="yellow" ml={4}>Con estos umbrales</Badge>
              )}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function PanelCaso({
  controles, alCambiar, alRestablecer, modificado,
}: {
  controles: Control[];
  alCambiar: (variable: string, valor: number) => void;
  alRestablecer: () => void;
  modificado: boolean;
}) {
  return (
    <Card withBorder padding="sm">
      <Group justify="space-between" mb="xs">
        <Title order={5}>Caso evaluado</Title>
        <Button size="compact-xs" variant="subtle" disabled={!modificado} onClick={alRestablecer}>
          Medianas
        </Button>
      </Group>
      <Text size="xs" c="dimmed" mb="sm">
        Valores de los padres (unidades preparadas; entre paréntesis, originales). Por defecto, la mediana de
        entrenamiento.
      </Text>
      <Stack gap="md">
        {controles.map((c) => (
          <div key={c.variable}>
            <Group justify="space-between" gap="xs">
              <Text size="xs" fw={500}>{c.variable}</Text>
              <Badge size="sm" variant={c.valor === c.mediana ? "light" : "filled"} color="blue">
                {coma(c.valor)}{c.original !== null ? ` (${c.original})` : ""}
              </Badge>
            </Group>
            <Slider
              min={c.minimo}
              max={c.maximo}
              step={(c.maximo - c.minimo) / PASOS_DESLIZADOR || 1}
              value={c.valor}
              label={null}
              marks={[{ value: c.mediana }]}
              onChange={(v) => alCambiar(c.variable, v)}
              aria-label={`Valor de ${c.variable}`}
            />
          </div>
        ))}
      </Stack>
    </Card>
  );
}

export function ModeloCausal({ id }: { id: string }) {
  const [umbrales, setUmbrales] = useState<Record<string, number>>({});
  const [valores, setValores] = useState<Record<string, number>>({});
  const [umbralesDif] = useDebouncedValue(umbrales, RETARDO_MS);
  const [valoresDif] = useDebouncedValue(valores, RETARDO_MS);
  const consulta = useFormulasModeloCausal(id, umbralesDif, valoresDif);

  if (consulta.isPending) return <Center p="xl"><Loader /></Center>;
  if (consulta.error) return <MensajeError error={consulta.error} />;
  if (!consulta.data) {
    return (
      <SinEtapa
        titulo="Todavía no hay un modelo causal que explorar"
        texto="Esta vista explica qué variables entran al modelo, cómo se elige el mecanismo de cada una y qué calcula con valores reales. Se genera al construir el modelo causal."
        boton="Ir a Modelo causal"
        ruta={`/proyectos/${id}/modelo-causal`}
      />
    );
  }
  const traza: Traza = consulta.data;
  const deslizadores = traza.umbrales.map((u) => ({ ...u, valor: umbrales[u.nombre] ?? u.valor }));
  const controles = traza.controles.map((c) => ({ ...c, valor: valores[c.variable] ?? c.valor }));

  return (
    <Group align="flex-start" wrap="nowrap" gap="md">
      <Stack gap="md" style={{ flex: 1, minWidth: 0 }}>
        <Alert icon={<IconInfoCircle />} color="green" title={`Modelo causal de ${traza.objetivo}`}>{traza.resumen}</Alert>
        {traza.avisos.map((a) => <Alert key={a} color="yellow" variant="light">{a}</Alert>)}

        <Title order={5}>Cómo se construye</Title>
        <PasosEnTarjetas pasos={traza.fundamentos} />

        <Title order={5}>Qué toma y qué ignora</Title>
        <TablaEntradas entradas={traza.entradas} />

        <Title order={5}>Mecanismo de cada variable</Title>
        <Accordion variant="separated" multiple>
          {traza.mecanismos.map((m) => (
            <Accordion.Item key={m.variable} value={m.variable}>
              <Accordion.Control>
                <Group gap="xs">
                  <Text fw={500} size="sm">{m.variable} ← {m.padres.join(", ")}</Text>
                  <Badge size="xs" variant="light" color={m.elegido_guardado === "complejo" ? "grape" : "blue"}>
                    {m.nombre_familia}
                  </Badge>
                  {m.origen === "manual" && <Badge size="xs" variant="outline" color="gray">Manual</Badge>}
                  {m.cambiaria && <Badge size="xs" color="yellow">Cambiaría a {m.elegido}</Badge>}
                  {m.calidad_suficiente === false && <Badge size="xs" color="orange">Se explica mal</Badge>}
                  <Text size="xs" c="dimmed">CV = {coma(m.puntuacion_cv)} · test = {coma(m.puntuacion_test)}</Text>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Candidatos mecanismo={m} />
                {m.pasos.map((p) => <PasoVista key={p.id} paso={p} />)}
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>

        {traza.monotonia.length > 0 && (
          <>
            <Title order={5}>Monotonía de los padres del objetivo</Title>
            <PasosEnTarjetas pasos={traza.monotonia} />
          </>
        )}
        {traza.referencia.length > 0 && (
          <>
            <Title order={5}>Comparación con el modelo de referencia</Title>
            <PasosEnTarjetas pasos={traza.referencia} />
          </>
        )}
      </Stack>
      <Stack gap="md" style={{ width: 340, flexShrink: 0, position: "sticky", top: 68, maxHeight: "calc(100vh - 84px)", overflowY: "auto" }}>
        <PanelUmbrales
          umbrales={deslizadores}
          modificado={Object.keys(umbrales).length > 0}
          alCambiar={(n, v) => setUmbrales((a) => ({ ...a, [n]: v }))}
          alRestablecer={() => setUmbrales({})}
        />
        {controles.length > 0 && (
          <PanelCaso
            controles={controles}
            modificado={Object.keys(valores).length > 0}
            alCambiar={(n, v) => setValores((a) => ({ ...a, [n]: v }))}
            alRestablecer={() => setValores({})}
          />
        )}
      </Stack>
    </Group>
  );
}

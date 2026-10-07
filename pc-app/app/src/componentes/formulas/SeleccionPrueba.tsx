import { Accordion, Alert, Badge, Card, Center, Group, Loader, Slider, Stack, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconCheck, IconCircleDashed, IconInfoCircle, IconX } from "@tabler/icons-react";
import { useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { useFormulasSeleccionPrueba } from "../../api/consultas";
import { Formula } from "../Formula";
import { MensajeError } from "../MensajeError";
import { PanelUmbrales, PasoVista, PasosEnTarjetas, SinEtapa, TablaEntradas } from "./Comunes";

type Traza = Esquemas["TrazaSeleccionPrueba"];
type Regla = Esquemas["ReglaDecision"];

const RETARDO_MS = 300;
const ESTADO_REGLA: Record<Regla["estado"], { texto: string; color: string; icono: typeof IconCheck }> = {
  decide: { texto: "Decide", color: "green", icono: IconCheck },
  sin_efecto: { texto: "Se cumple, pero ya decidió una anterior", color: "yellow", icono: IconCircleDashed },
  no_cumple: { texto: "No se cumple", color: "gray", icono: IconX },
};

function ReglaVista({ regla }: { regla: Regla }) {
  const estado = ESTADO_REGLA[regla.estado];
  const Icono = estado.icono;
  return (
    <Card
      withBorder
      padding="sm"
      style={regla.estado === "decide" ? { borderColor: "var(--mantine-color-green-6)" } : undefined}
    >
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Stack gap={2}>
          <Text fw={600} size="sm">{regla.orden}. {regla.titulo}</Text>
          <Formula latex={regla.condicion} />
          <Formula latex={regla.sustituida} />
          {regla.detalle && <Text size="xs" c="dimmed">{regla.detalle}</Text>}
        </Stack>
        <Stack gap={4} align="flex-end">
          <Badge
            color={estado.color}
            variant="light"
            leftSection={<Icono size={12} />}
            style={{ whiteSpace: "normal", height: "auto" }}
          >
            {estado.texto}
          </Badge>
          {regla.estado !== "no_cumple" && <Badge variant="outline" color="gray">→ {regla.consecuencia}</Badge>}
        </Stack>
      </Group>
    </Card>
  );
}

export function SeleccionPrueba({ id }: { id: string }) {
  const [umbrales, setUmbrales] = useState<Record<string, number>>({});
  const [k, setK] = useState(2);
  const [umbralesDif] = useDebouncedValue(umbrales, RETARDO_MS);
  const [kDif] = useDebouncedValue(k, RETARDO_MS);
  const consulta = useFormulasSeleccionPrueba(id, umbralesDif, kDif);

  if (consulta.isPending) return <Center p="xl"><Loader /></Center>;
  if (consulta.error) return <MensajeError error={consulta.error} />;
  if (!consulta.data) {
    return (
      <SinEtapa
        titulo="Todavía no hay fórmulas que explorar"
        texto="Esta vista explica la elección de la prueba de independencia con los valores reales de su dataset. Se genera al ejecutar la recomendación."
        boton="Ir a Recomendación"
        ruta={`/proyectos/${id}/recomendacion`}
      />
    );
  }
  const traza: Traza = consulta.data;
  // El deslizador muestra el valor que se está moviendo, aunque la consulta aún no haya vuelto.
  const deslizadores = traza.umbrales.map((u) => ({ ...u, valor: umbrales[u.nombre] ?? u.valor }));

  return (
    <Group align="flex-start" wrap="nowrap" gap="md">
      <Stack gap="md" style={{ flex: 1, minWidth: 0 }}>
        <Alert color={traza.cambia ? "yellow" : "green"} icon={<IconInfoCircle />} title={`Prueba: ${traza.prueba}`}>
          {traza.resumen}
        </Alert>
        {traza.avisos.map((a) => <Alert key={a} color="yellow" variant="light">{a}</Alert>)}

        <Title order={5}>Reglas, en orden (la primera que se cumple decide)</Title>
        <Stack gap="xs">{traza.reglas.map((r) => <ReglaVista key={r.orden} regla={r} />)}</Stack>

        <Title order={5}>Qué toma y qué ignora la decisión</Title>
        <TablaEntradas entradas={traza.entradas} />

        <Title order={5}>Diagnóstico por variable</Title>
        <Accordion variant="separated" multiple>
          {traza.variables.map((v) => (
            <Accordion.Item key={v.nombre} value={v.nombre}>
              <Accordion.Control>
                <Group gap="xs">
                  <Text fw={500} size="sm">{v.nombre}</Text>
                  <Badge size="xs" variant="light" color={!v.evaluada ? "gray" : v.no_monotona ? "orange" : "green"}>
                    {!v.evaluada ? "Ignorada" : v.no_monotona ? "No monótona" : "Monótona"}
                  </Badge>
                  <Text size="xs" c="dimmed">{v.resumen}</Text>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                {v.pasos.length === 0
                  ? <Text size="sm">{v.resumen}</Text>
                  : v.pasos.map((p) => <PasoVista key={p.id} paso={p} />)}
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>

        <Group justify="space-between" align="flex-end">
          <Title order={5}>Fórmulas de la prueba elegida ({traza.prueba})</Title>
          <div style={{ width: 240 }}>
            <Text size="xs">Variables de condicionamiento |S| = {k}</Text>
            <Slider min={0} max={10} step={1} value={k} onChange={setK} aria-label="Variables de condicionamiento" />
          </div>
        </Group>
        <PasosEnTarjetas pasos={traza.formulas_prueba} />
      </Stack>
      <div style={{ width: 340, flexShrink: 0, position: "sticky", top: 68 }}>
        <PanelUmbrales
          umbrales={deslizadores}
          modificado={Object.keys(umbrales).length > 0}
          alCambiar={(n, v) => setUmbrales((a) => ({ ...a, [n]: v }))}
          alRestablecer={() => setUmbrales({})}
        />
      </div>
    </Group>
  );
}

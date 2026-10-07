import { Accordion, Alert, Badge, Center, Group, Loader, SegmentedControl, Stack, Table, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconInfoCircle } from "@tabler/icons-react";
import { useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { useFormulasAnalisisPc } from "../../api/consultas";
import { Formula } from "../Formula";
import { MensajeError } from "../MensajeError";
import { PanelUmbrales, PasoVista, PasosEnTarjetas, SinEtapa, TablaEntradas } from "./Comunes";

type Traza = Esquemas["TrazaAnalisisPC"];
type Par = Esquemas["ParEvaluado"];

const RETARDO_MS = 300;
const ESTADO_PAR: Record<Par["estado"], { texto: string; color: string }> = {
  aceptada: { texto: "Aceptada", color: "green" },
  debil: { texto: "Débil", color: "yellow" },
  descartada: { texto: "Descartada", color: "gray" },
};
const CATEGORIA: Record<string, { texto: string; color: string }> = {
  causa_directa: { texto: "Causa directa", color: "green" },
  causa_indirecta: { texto: "Causa indirecta", color: "teal" },
  consecuencia: { texto: "Consecuencia", color: "blue" },
  ambigua: { texto: "Ambigua", color: "yellow" },
  sin_camino: { texto: "Sin camino", color: "gray" },
};
const FILTROS = [
  { value: "todas", label: "Todas" },
  { value: "aceptada", label: "Aceptadas" },
  { value: "cerca", label: "Cerca del umbral" },
  { value: "debil", label: "Débiles" },
  { value: "descartada", label: "Descartadas" },
];

function enlace(par: Par): string {
  if (par.tipo === "dirigida" || par.tipo === "manual") return `${par.origen} → ${par.destino}`;
  return `${par.a} — ${par.b}`;
}

export function AnalisisPc({ id }: { id: string }) {
  const [umbral, setUmbral] = useState<number | null>(null);
  const [umbralDif] = useDebouncedValue(umbral, RETARDO_MS);
  const [filtro, setFiltro] = useState("todas");
  const consulta = useFormulasAnalisisPc(id, umbralDif);

  if (consulta.isPending) return <Center p="xl"><Loader /></Center>;
  if (consulta.error) return <MensajeError error={consulta.error} />;
  if (!consulta.data) {
    return (
      <SinEtapa
        titulo="Todavía no hay un análisis que explorar"
        texto="Esta vista explica cómo las corridas de bootstrap de PC se convierten en aristas y en la caracterización de cada variable. Se genera al ejecutar el análisis."
        boton="Ir a Análisis"
        ruta={`/proyectos/${id}/analisis`}
      />
    );
  }
  const traza: Traza = consulta.data;
  const deslizadores = traza.umbrales.map((u) => ({ ...u, valor: umbral ?? u.valor }));
  const pares = traza.pares.filter((p) =>
    filtro === "todas" ? true : filtro === "cerca" ? p.roza_umbral : p.estado === filtro,
  );

  return (
    <Group align="flex-start" wrap="nowrap" gap="md">
      <Stack gap="md" style={{ flex: 1, minWidth: 0 }}>
        <Alert icon={<IconInfoCircle />} color={traza.cambios.length ? "yellow" : "green"} title={`Resultado, versión ${traza.version}`}>
          {traza.resumen}
        </Alert>
        {traza.cambios.length > 0 && (
          <Group gap="xs">
            {traza.cambios.map((c) => (
              <Badge key={`${c.a}-${c.b}`} color={c.cambio === "nueva" ? "green" : "red"} variant="light">
                {c.cambio === "nueva" ? "+" : "−"} {c.a} — {c.b} (f = {String(c.frecuencia).replace(".", ",")})
              </Badge>
            ))}
          </Group>
        )}
        {traza.candidatas.join() !== traza.candidatas_guardadas.join() && (
          <Alert color="yellow" variant="light">
            Candidatas prescriptivas con este umbral: {traza.candidatas.join(", ") || "ninguna"} (guardado:{" "}
            {traza.candidatas_guardadas.join(", ") || "ninguna"}).
          </Alert>
        )}
        {traza.avisos.map((a) => <Alert key={a} color="yellow" variant="light">{a}</Alert>)}

        <Title order={5}>Cómo se construye el grafo</Title>
        <PasosEnTarjetas pasos={traza.fundamentos} />

        <Title order={5}>Qué toma y qué ignora el análisis</Title>
        <TablaEntradas entradas={traza.entradas} />

        <Group justify="space-between">
          <Title order={5}>Aristas ({traza.pares.length}{traza.pares_omitidos ? ` + ${traza.pares_omitidos} menos frecuentes` : ""})</Title>
          <SegmentedControl size="xs" data={FILTROS} value={filtro} onChange={setFiltro} />
        </Group>
        <Accordion variant="separated" multiple>
          {pares.map((p) => (
            <Accordion.Item key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
              <Accordion.Control>
                <Group gap="xs">
                  <Text fw={500} size="sm">{enlace(p)}</Text>
                  <Badge size="xs" variant="light" color={ESTADO_PAR[p.estado].color}>{ESTADO_PAR[p.estado].texto}</Badge>
                  <Text size="xs" c="dimmed">
                    f = {String(p.frecuencia).replace(".", ",")}
                    {p.roza_umbral ? " · roza el umbral" : ""}
                    {p.tipo === "sin_orientar" ? " · sin orientar" : ""}
                  </Text>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>{p.pasos.map((s) => <PasoVista key={s.id} paso={s} />)}</Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
        {pares.length === 0 && <Text size="sm" c="dimmed">Ninguna arista cumple este filtro.</Text>}

        <Title order={5}>Caracterización respecto al objetivo</Title>
        <Table fz="sm" withTableBorder>
          <Table.Tbody>
            {traza.variables.map((v) => (
              <Table.Tr key={v.nombre}>
                <Table.Td fw={500}>{v.nombre}</Table.Td>
                <Table.Td>
                  <Badge size="xs" variant="light" color={CATEGORIA[v.categoria]?.color ?? "gray"}>
                    {CATEGORIA[v.categoria]?.texto ?? v.categoria}
                  </Badge>
                </Table.Td>
                <Table.Td>{v.camino ? <Formula latex={v.camino} /> : "—"}</Table.Td>
                <Table.Td c="dimmed">{v.regla}</Table.Td>
                <Table.Td>
                  {v.candidata && <Badge size="xs" color="green">Candidata</Badge>}
                  {v.modificable && !v.candidata && <Badge size="xs" variant="outline" color="gray">Modificable</Badge>}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
      <div style={{ width: 340, flexShrink: 0, position: "sticky", top: 68 }}>
        <PanelUmbrales
          umbrales={deslizadores}
          modificado={umbral !== null}
          alCambiar={(_, v) => setUmbral(v)}
          alRestablecer={() => setUmbral(null)}
        />
      </div>
    </Group>
  );
}

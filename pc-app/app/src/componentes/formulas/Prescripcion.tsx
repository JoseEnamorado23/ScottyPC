import {
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  NumberInput,
  Pagination,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconCheck, IconInfoCircle, IconX } from "@tabler/icons-react";
import { useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { useFormulasCalibracion, useFormulasCasoPrescripcion } from "../../api/consultas";
import { useCasosModelo } from "../../api/modeloCausal";
import { MensajeError } from "../MensajeError";
import { PanelUmbrales, PasoVista, PasosEnTarjetas, SinEtapa, TablaEntradas } from "./Comunes";

const RETARDO_MS = 400;

const coma = (v: number | null | undefined, decimales = 3) =>
  v === null || v === undefined ? "—" : v.toFixed(decimales).replace(".", ",");

function Calibracion({ id }: { id: string }) {
  const [exito, setExito] = useState<number | null>(null);
  const [exitoDif] = useDebouncedValue(exito, RETARDO_MS);
  const consulta = useFormulasCalibracion(id, exitoDif);

  if (consulta.isPending) return <Center p="xl"><Loader /></Center>;
  if (consulta.error) return <MensajeError error={consulta.error} />;
  if (!consulta.data) {
    return (
      <SinEtapa
        titulo="Todavía no hay una calibración de μ"
        texto="Esta vista explica cómo se elige μ (el peso de la intervención mínima). Se genera al calibrar μ en Prescripción."
        boton="Ir a Prescripción"
        ruta={`/proyectos/${id}/prescripcion`}
      />
    );
  }
  const traza: Esquemas["TrazaCalibracion"] = consulta.data;
  const deslizadores = traza.umbrales.map((u) => ({ ...u, valor: exito ?? u.valor }));

  return (
    <Group align="flex-start" wrap="nowrap" gap="md">
      <Stack gap="md" style={{ flex: 1, minWidth: 0 }}>
        <Alert icon={<IconInfoCircle />} color={traza.cambia ? "yellow" : "green"} title={traza.resumen}>
          {traza.casos} casos de entrenamiento no cumplen el objetivo: {traza.alcanzables} alcanzables y{" "}
          {traza.no_alcanzables} inalcanzables. {traza.ya_cumplen} ya lo cumplen.
        </Alert>
        {traza.advertencia && <Alert color="yellow" variant="light">{traza.advertencia}</Alert>}
        <PasosEnTarjetas pasos={traza.pasos} />
        <Title order={5}>Rejilla de μ</Title>
        <Table fz="sm" withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>μ</Table.Th>
              <Table.Th>Éxitos</Table.Th>
              <Table.Th>Tasa</Table.Th>
              <Table.Th>¿≥ {Math.round(100 * traza.exito_requerido)} %?</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {traza.puntos.map((p) => (
              <Table.Tr key={p.mu}>
                <Table.Td>{String(p.mu).replace(".", ",")}</Table.Td>
                <Table.Td>{p.exitos} / {p.evaluados}</Table.Td>
                <Table.Td>{p.tasa === null ? "—" : `${coma(100 * p.tasa, 1)} %`}</Table.Td>
                <Table.Td>
                  <Badge size="xs" variant="light" color={p.cumple ? "green" : "gray"}
                    leftSection={p.cumple ? <IconCheck size={10} /> : <IconX size={10} />}>
                    {p.cumple ? "Cumple" : "No cumple"}
                  </Badge>
                </Table.Td>
                <Table.Td>{p.elegido && <Badge size="xs" color="green">Elegido</Badge>}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        {traza.nota && <Text size="xs" c="dimmed">{traza.nota}</Text>}
      </Stack>
      <div style={{ width: 340, flexShrink: 0, position: "sticky", top: 68 }}>
        <PanelUmbrales
          umbrales={deslizadores}
          modificado={exito !== null}
          alCambiar={(_, v) => setExito(v)}
          alRestablecer={() => setExito(null)}
        />
      </div>
    </Group>
  );
}

function SelectorCaso({
  id, indice, alElegir,
}: { id: string; indice: number | null; alElegir: (indice: number | null) => void }) {
  const [pagina, setPagina] = useState(1);
  const casos = useCasosModelo(id, pagina, true);
  if (casos.isPending) return <Loader size="sm" />;
  if (casos.error || !casos.data) return null;
  const { filas, total, por_pagina } = casos.data;
  return (
    <Group align="flex-end" gap="sm">
      <Select
        label="Fila de test"
        placeholder="Elija un caso"
        w={260}
        searchable
        value={indice === null ? null : String(indice)}
        onChange={(v) => alElegir(v === null ? null : Number(v))}
        data={filas.map((f) => ({ value: String(f.indice), label: `Fila ${f.indice} · objetivo observado: ${String(f.objetivo ?? "—")}` }))}
      />
      <Pagination size="sm" total={Math.max(1, Math.ceil(total / por_pagina))} value={pagina} onChange={setPagina} />
    </Group>
  );
}

function Caso({ id }: { id: string }) {
  const [indice, setIndice] = useState<number | null>(null);
  const [mu, setMu] = useState<number | null>(null);
  const [muDif] = useDebouncedValue(mu, RETARDO_MS);
  const consulta = useFormulasCasoPrescripcion(id, indice, muDif);
  const traza = consulta.data;

  return (
    <Stack gap="md">
      <Group align="flex-end" gap="md">
        <SelectorCaso id={id} indice={indice} alElegir={setIndice} />
        <NumberInput
          label="μ"
          w={140}
          min={0}
          step={0.001}
          decimalScale={6}
          placeholder={traza?.mu_guardado != null ? String(traza.mu_guardado) : "guardado"}
          value={mu ?? ""}
          onChange={(v) => setMu(typeof v === "number" ? v : null)}
        />
        <Button variant="subtle" size="xs" disabled={mu === null} onClick={() => setMu(null)}>Usar el guardado</Button>
      </Group>
      <Text size="xs" c="dimmed">
        Se prescribe igual que en la pantalla de Prescripción (mismo resultado) y no se guarda nada. Puede tardar unos segundos.
      </Text>
      {indice === null && <Text size="sm">Elija una fila de test para ver su prescripción descompuesta.</Text>}
      {indice !== null && consulta.isFetching && <Group gap="xs"><Loader size="xs" /><Text size="sm">Prescribiendo…</Text></Group>}
      {consulta.error && <MensajeError error={consulta.error} />}
      {indice !== null && consulta.isSuccess && !traza && (
        <SinEtapa
          titulo="No se puede prescribir todavía"
          texto="La prescripción no está vigente o μ no está calibrado. Configure la prescripción y calibre μ (o fíjelo)."
          boton="Ir a Prescripción"
          ruta={`/proyectos/${id}/prescripcion`}
        />
      )}
      {traza && (
        <>
          <Alert
            icon={traza.alcanzado ? <IconCheck /> : <IconX />}
            color={traza.alcanzado ? "green" : "yellow"}
            title={`Fila ${traza.indice}: ${coma(traza.antes)} → ${coma(traza.despues)} (deseado ${traza.direccion === "bajar" ? "≤" : "≥"} ${coma(traza.deseado)})`}
          >
            {traza.explicacion}
          </Alert>
          {traza.restricciones.map((r) => <Alert key={r} color="yellow" variant="light">Restricción activa: {r}</Alert>)}
          {traza.avisos.map((a) => <Alert key={a} color="yellow" variant="light">{a}</Alert>)}

          <Title order={5}>Qué se minimiza</Title>
          <PasosEnTarjetas pasos={traza.fundamentos} />

          <Title order={5}>Pérdida antes y después</Title>
          <PasosEnTarjetas pasos={traza.perdida} />

          <Title order={5}>Acciones</Title>
          <Accordion variant="separated" multiple>
            {traza.acciones.map((a) => (
              <Accordion.Item key={a.variable} value={a.variable}>
                <Accordion.Control>
                  <Group gap="xs">
                    <Text fw={500} size="sm">{a.variable}</Text>
                    <Badge size="xs" variant="light" color={a.cambia ? "blue" : "gray"}>
                      {a.cambia ? `${a.antes} → ${a.despues}` : "Sin cambio"}
                    </Badge>
                    {a.restriccion_activa && <Badge size="xs" color="yellow">{a.restriccion_activa}</Badge>}
                    <Text size="xs" c="dimmed">
                      penalización = {coma(a.penalizacion, 5)}
                      {a.contribucion !== null ? ` · aporte al logro = ${coma(a.contribucion)}` : ""}
                    </Text>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>{a.pasos.map((p) => <PasoVista key={p.id} paso={p} />)}</Accordion.Panel>
              </Accordion.Item>
            ))}
          </Accordion>

          <Title order={5}>Qué toma y qué ignora</Title>
          <TablaEntradas entradas={traza.entradas} />
        </>
      )}
    </Stack>
  );
}

export function Prescripcion({ id }: { id: string }) {
  const [seccion, setSeccion] = useState("calibracion");
  return (
    <Stack gap="md">
      <SegmentedControl
        w="fit-content"
        value={seccion}
        onChange={setSeccion}
        data={[{ value: "calibracion", label: "Calibración de μ" }, { value: "caso", label: "Un caso" }]}
      />
      <Card withBorder={false} p={0}>
        {seccion === "calibracion" ? <Calibracion id={id} /> : <Caso id={id} />}
      </Card>
    </Stack>
  );
}

import { Alert, Badge, Button, Card, Group, Slider, Stack, Table, Text, Title } from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";
import { useNavigate } from "react-router";

import type { Esquemas } from "../../api/cliente";
import { Formula } from "../Formula";

type Paso = Esquemas["PasoFormula"];
type Umbral = Esquemas["UmbralExplorador"];
type Entrada = Esquemas["EntradaDecision"];

const ORIGEN: Record<string, { texto: string; color: string }> = {
  dataset: { texto: "dataset", color: "blue" },
  umbral: { texto: "umbral", color: "grape" },
  calculado: { texto: "calculado", color: "gray" },
};

/** Un paso: fórmula general, la misma con los valores reales, el resultado y la tabla de términos. */
export function PasoVista({ paso }: { paso: Paso }) {
  return (
    <Stack gap={4} py="xs">
      <Group gap="xs">
        <Text fw={600} size="sm">{paso.titulo}</Text>
        {paso.cumple !== null && (
          <Badge size="xs" variant="light" color={paso.cumple ? "green" : "gray"}>
            {paso.cumple ? "Sí" : "No"}
          </Badge>
        )}
      </Group>
      <Formula latex={paso.formula} bloque />
      {paso.sustituida && <Formula latex={paso.sustituida} bloque />}
      <Text size="sm">{paso.resultado}</Text>
      {paso.terminos.length > 0 && (
        <Table withRowBorders={false} verticalSpacing={2} fz="xs">
          <Table.Tbody>
            {paso.terminos.map((t) => (
              <Table.Tr key={t.simbolo}>
                <Table.Td w={90}><Formula latex={t.simbolo} /></Table.Td>
                <Table.Td>{t.descripcion}</Table.Td>
                <Table.Td>{t.valor ?? "—"}</Table.Td>
                <Table.Td w={90}>
                  <Badge size="xs" variant="outline" color={ORIGEN[t.origen].color}>{ORIGEN[t.origen].texto}</Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {paso.nota && <Text size="xs" c="dimmed">{paso.nota}</Text>}
    </Stack>
  );
}

/** Pasos sueltos, cada uno en su tarjeta. */
export function PasosEnTarjetas({ pasos }: { pasos: Paso[] }) {
  return (
    <>
      {pasos.map((p) => (
        <Card withBorder key={p.id} padding="sm"><PasoVista paso={p} /></Card>
      ))}
    </>
  );
}

/** Qué datos toma la decisión y cuáles ignora (ícono + texto, no solo color). */
export function TablaEntradas({ entradas }: { entradas: Entrada[] }) {
  return (
    <Table fz="sm" withTableBorder>
      <Table.Tbody>
        {entradas.map((e) => (
          <Table.Tr key={e.nombre}>
            <Table.Td>
              <Badge size="xs" color={e.usada ? "green" : "gray"} variant="light">{e.usada ? "Toma" : "Ignora"}</Badge>
            </Table.Td>
            <Table.Td>{e.nombre}</Table.Td>
            <Table.Td>{e.valor}</Table.Td>
            <Table.Td c="dimmed">{e.nota}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

/** Deslizadores de umbrales; solo cambian lo que se muestra. */
export function PanelUmbrales({
  umbrales, modificado, alCambiar, alRestablecer,
}: {
  umbrales: Umbral[];
  modificado: boolean;
  alCambiar: (nombre: string, valor: number) => void;
  alRestablecer: () => void;
}) {
  return (
    <Card withBorder padding="sm">
      <Group justify="space-between" mb="xs">
        <Title order={5}>Probar otros umbrales</Title>
        <Button size="compact-xs" variant="subtle" disabled={!modificado} onClick={alRestablecer}>
          Restablecer
        </Button>
      </Group>
      <Text size="xs" c="dimmed" mb="sm">
        Solo cambia lo que se muestra: el resultado guardado y el resto del flujo no se tocan.
      </Text>
      <Stack gap="md">
        {umbrales.map((u) => (
          <div key={u.nombre}>
            <Group justify="space-between" gap="xs">
              <Group gap={6}><Formula latex={u.simbolo} /><Text size="xs">{u.descripcion}</Text></Group>
              <Badge size="sm" variant={u.valor === u.original ? "light" : "filled"} color="grape">
                {String(u.valor).replace(".", ",")}
              </Badge>
            </Group>
            <Slider
              min={u.minimo}
              max={u.maximo}
              step={u.paso}
              value={u.valor}
              label={null}
              marks={[{ value: u.original }]}
              onChange={(v) => alCambiar(u.nombre, v)}
              aria-label={u.descripcion}
            />
          </div>
        ))}
      </Stack>
    </Card>
  );
}

/** Estado vacío: explica qué paso genera la información y lleva a él. */
export function SinEtapa({ titulo, texto, boton, ruta }: { titulo: string; texto: string; boton: string; ruta: string }) {
  const navegar = useNavigate();
  return (
    <Alert icon={<IconInfoCircle />} title={titulo}>
      <Text size="sm" mb="sm">{texto}</Text>
      <Button onClick={() => navegar(ruta)}>{boton}</Button>
    </Alert>
  );
}

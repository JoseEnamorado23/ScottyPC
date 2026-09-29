// Tabla de mecanismos (con la opción de cambiar el elegido) y, para el objetivo, las curvas de
// efecto parcial por padre con su monotonía editable.
import { Badge, Card, Group, SegmentedControl, Select, SimpleGrid, Stack, Table, Text, Tooltip } from "@mantine/core";

import type { Esquemas } from "../../api/cliente";
import {
  NOMBRES_METRICA, conMecanismo, conMonotonia, metrica, type EleccionMecanismo, type Monotonia, type Solicitud,
} from "../../estado/modeloCausal";
import { CurvaEfecto } from "./Graficos";

type Mecanismo = Esquemas["EvaluacionMecanismo"];
type DecisionMonotonia = Esquemas["DecisionMonotonia"];

const SIGNO: Record<number, string> = { 1: "creciente", [-1]: "decreciente", 0: "sube y baja" };

function textoSigno(efecto: Esquemas["EfectoParcial"]) {
  const signo = SIGNO[efecto.signo] ?? "—";
  return efecto.coeficiente !== null ? `${efecto.padre} (${efecto.coeficiente > 0 ? "+" : "−"})` : `${efecto.padre}: ${signo}`;
}

interface PropsTabla {
  mecanismos: Mecanismo[];
  solicitud: Solicitud;
  alCambiar: (solicitud: Solicitud) => void;
}

export function TablaMecanismos({ mecanismos, solicitud, alCambiar }: PropsTabla) {
  return (
    <Table.ScrollContainer minWidth={720}>
      <Table striped verticalSpacing="xs" data-testid="tabla-mecanismos">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Variable</Table.Th>
            <Table.Th>Padres (signo)</Table.Th>
            <Table.Th>Mecanismo</Table.Th>
            <Table.Th>Métrica</Table.Th>
            <Table.Th ta="right">Validación cruzada</Table.Th>
            <Table.Th ta="right">Test</Table.Th>
            <Table.Th>Elegir</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {mecanismos.map((m) => {
            const simple = m.candidatos.find((c) => c.tipo === "simple");
            const complejo = m.candidatos.find((c) => c.tipo === "complejo");
            const override = solicitud.mecanismos?.[m.variable] ?? "auto";
            return (
              <Table.Tr key={m.variable}>
                <Table.Td>
                  <Group gap={4}>
                    <Text size="sm" fw={m.rol === "objetivo" ? 700 : 400}>
                      {m.variable}
                    </Text>
                    {m.rol === "objetivo" && <Badge size="xs">objetivo</Badge>}
                    {m.tipo === "binaria" && m.rol !== "objetivo" && <Badge size="xs" variant="light">binaria</Badge>}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="xs">{m.efectos.map(textoSigno).join(", ")}</Text>
                </Table.Td>
                <Table.Td>
                  <Tooltip label={m.motivo} multiline w={320}>
                    <Group gap={4}>
                      <Text size="sm">{m.nombre_familia}</Text>
                      {m.origen === "manual" && <Badge size="xs" color="grape" variant="light">manual</Badge>}
                    </Group>
                  </Tooltip>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{NOMBRES_METRICA[m.metrica]}</Text>
                </Table.Td>
                <Table.Td ta="right">
                  <Tooltip
                    label={`Simple: ${metrica(simple?.puntuacion_cv)} · Complejo: ${complejo?.error ?? metrica(complejo?.puntuacion_cv)}`}
                    multiline
                    w={300}
                  >
                    <Text size="sm">{metrica(m.puntuacion_cv)}</Text>
                  </Tooltip>
                </Table.Td>
                <Table.Td ta="right">
                  <Text size="sm">{metrica(m.puntuacion_test)}</Text>
                </Table.Td>
                <Table.Td>
                  <Select
                    size="xs"
                    w={130}
                    aria-label={`Mecanismo de ${m.variable}`}
                    value={override}
                    allowDeselect={false}
                    onChange={(valor) => alCambiar(conMecanismo(solicitud, m.variable, (valor ?? "auto") as EleccionMecanismo | "auto"))}
                    data={[
                      { value: "auto", label: "Automático" },
                      { value: "simple", label: simple?.nombre_familia ?? "Simple" },
                      { value: "complejo", label: complejo?.nombre_familia ?? "Complejo", disabled: !!complejo?.error },
                    ]}
                  />
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

const TEXTO_RESTRICCION: Record<string, string> = { creciente: "Creciente", decreciente: "Decreciente", ninguna: "Libre" };

interface PropsObjetivo {
  mecanismo: Mecanismo;
  monotonia: DecisionMonotonia[];
  medida: "probabilidad" | "valor";
  solicitud: Solicitud;
  alCambiar: (solicitud: Solicitud) => void;
}

/** Curvas de efecto parcial por padre del objetivo, con la monotonía de cada uno. */
export function EfectosObjetivo({ mecanismo, monotonia, medida, solicitud, alCambiar }: PropsObjetivo) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} data-testid="efectos-objetivo">
      {mecanismo.efectos.map((efecto) => {
        const decision = monotonia.find((d) => d.padre === efecto.padre);
        const override = solicitud.monotonia?.[efecto.padre];
        const aplica = decision?.origen !== "no_aplica";
        return (
          <Card key={efecto.padre} withBorder padding="sm">
            <Stack gap={6}>
              <Group justify="space-between" gap={4}>
                <Text fw={600} size="sm">
                  {efecto.padre}
                </Text>
                {decision && (
                  <Tooltip label={decision.motivo} multiline w={280}>
                    <Badge variant="light" color={decision.origen === "manual" ? "grape" : "gray"} size="sm">
                      {aplica ? `${TEXTO_RESTRICCION[decision.restriccion ?? "ninguna"]} · ${decision.origen === "manual" ? "manual" : "automática"}` : "lineal"}
                    </Badge>
                  </Tooltip>
                )}
              </Group>
              <CurvaEfecto efecto={efecto} medida={medida} />
              {aplica && (
                <Stack gap={2}>
                  <Text size="xs" c="dimmed">
                    Monotonía en el GAM{mecanismo.familia.startsWith("gam") ? "" : " (se aplica si se elige el GAM)"}
                  </Text>
                  <SegmentedControl
                    size="xs"
                    aria-label={`Monotonía de ${efecto.padre}`}
                    value={override ?? "auto"}
                    onChange={(valor) => alCambiar(conMonotonia(solicitud, efecto.padre, valor as Monotonia | "auto"))}
                    data={[
                      { value: "auto", label: "Auto" },
                      { value: "creciente", label: "Creciente" },
                      { value: "decreciente", label: "Decreciente" },
                      { value: "ninguna", label: "Libre" },
                    ]}
                  />
                </Stack>
              )}
            </Stack>
          </Card>
        );
      })}
    </SimpleGrid>
  );
}

import {
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Radio,
  ScrollArea,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconArrowRight } from "@tabler/icons-react";
import { useNavigate, useParams } from "react-router";

import type { Esquemas } from "../api/cliente";
import { useProyecto } from "../api/consultas";

import { MensajeError } from "../componentes/MensajeError";
import { ProblemasValidacion } from "../componentes/ProblemasValidacion";
import { formatoValor, nombreAccion, nombreTipo } from "../estado/textos";
import { useElecciones } from "../estado/useElecciones";

type Hallazgo = Esquemas["Hallazgo"];
type Accion = Esquemas["AccionHallazgo"];

const SEVERIDADES = [
  { clave: "alta", nombre: "Severidad alta", color: "red" },
  { clave: "media", nombre: "Severidad media", color: "orange" },
  { clave: "baja", nombre: "Severidad baja", color: "blue" },
] as const;

export function Revision() {
  const { id = "" } = useParams();
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const { revision, borrador, elegir, acciones, pendientes, previsualizacion } = useElecciones(id);

  if (proyecto.isPending || revision.isPending) return <Center><Loader /></Center>;
  if (proyecto.error || revision.error) return <MensajeError error={proyecto.error ?? revision.error} />;
  const informe = revision.data;

  return (
    <Stack>

      <Group justify="space-between" align="flex-start">
        <Stack gap={0}>
          <Title order={2}>Revisión del dataset</Title>
          <Text size="sm" c="dimmed">
            Objetivo: <b>{informe.objetivo}</b> · {informe.hallazgos.length} hallazgos
          </Text>
        </Stack>
        <Group>
          <Button variant="default" onClick={() => navegar(`/proyectos/${id}/datos`)}>
            Cambiar hoja u objetivo
          </Button>
          <Button
            rightSection={<IconArrowRight size={16} />}
            disabled={!informe.valido || pendientes.length > 0 || !previsualizacion.data}
            onClick={() => navegar(`/proyectos/${id}/decisiones`)}
          >
            {pendientes.length > 0 ? `Continuar (faltan ${pendientes.length} por confirmar)` : "Continuar a decisiones"}
          </Button>
        </Group>
      </Group>

      <ProblemasValidacion problemas={informe.validacion.errores} bloqueantes />
      <ProblemasValidacion problemas={informe.validacion.advertencias} bloqueantes={false} />
      <MensajeError error={previsualizacion.error} />

      {SEVERIDADES.map(({ clave, nombre, color }) => {
        const grupo = informe.hallazgos.filter((h) => h.severidad === clave);
        if (grupo.length === 0) return null;
        return (
          <Stack key={clave} gap="sm">
            <Group gap="xs">
              <Title order={4}>{nombre}</Title>
              <Badge color={color} variant="light">
                {grupo.length}
              </Badge>
            </Group>
            {grupo.map((h) => (
              <TarjetaHallazgo
                key={h.identificador}
                hallazgo={h}
                accion={acciones[h.identificador]}
                elegida={borrador?.elecciones[h.identificador]}
                pendiente={pendientes.includes(h.identificador)}
                alElegir={(a) => elegir(h.identificador, a)}
              />
            ))}
          </Stack>
        );
      })}

      <Title order={4}>Perfil de las columnas</Title>
      <ScrollArea>
        <Table striped withTableBorder fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Columna</Table.Th>
              <Table.Th>Tipo detectado</Table.Th>
              <Table.Th ta="right">Faltantes</Table.Th>
              <Table.Th ta="right">Valores únicos</Table.Th>
              <Table.Th ta="right">Mínimo</Table.Th>
              <Table.Th ta="right">Máximo</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {informe.perfiles_columnas.map((p) => (
              <Table.Tr key={p.nombre}>
                <Table.Td>{p.nombre}</Table.Td>
                <Table.Td>{p.tipo_detectado}</Table.Td>
                <Table.Td ta="right">
                  {formatoValor(p.faltantes)} ({formatoValor(p.porcentaje_faltantes)} %)
                </Table.Td>
                <Table.Td ta="right">{formatoValor(p.valores_unicos)}</Table.Td>
                <Table.Td ta="right">{formatoValor(p.minimo)}</Table.Td>
                <Table.Td ta="right">{formatoValor(p.maximo)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </Stack>
  );
}

interface PropsTarjeta {
  hallazgo: Hallazgo;
  accion: Accion | undefined;
  elegida: string | undefined;
  pendiente: boolean;
  alElegir: (accion: string) => void;
}

function TarjetaHallazgo({ hallazgo, accion, elegida, pendiente, alElegir }: PropsTarjeta) {
  const opciones = accion?.opciones ?? hallazgo.acciones_posibles;
  const actual = elegida ?? accion?.accion ?? hallazgo.accion_sugerida ?? null;
  const evidencia = Object.entries(hallazgo.evidencia ?? {});
  return (
    <Card
      withBorder
      data-testid={`hallazgo-${hallazgo.identificador}`}
      style={pendiente ? { borderColor: "var(--mantine-color-orange-5)", borderWidth: 2 } : undefined}
    >
      <Group justify="space-between" mb="xs">
        <Group gap="xs">
          <Text fw={600}>{nombreTipo(hallazgo.tipo)}</Text>
          {hallazgo.columnas_involucradas.map((c) => (
            <Badge key={c} variant="outline" color="gray">
              {c}
            </Badge>
          ))}
        </Group>
        {pendiente && (
          <Badge color="orange" variant="filled">
            Pendiente de confirmar
          </Badge>
        )}
      </Group>
      <Text size="sm">{hallazgo.detalle}</Text>

      {evidencia.length > 0 && (
        <Table fz="xs" mt="xs" withRowBorders={false} verticalSpacing={2}>
          <Table.Tbody>
            {evidencia.map(([clave, valor]) => (
              <Table.Tr key={clave}>
                <Table.Td c="dimmed" w={220}>
                  {clave.replace(/_/g, " ")}
                </Table.Td>
                <Table.Td>{formatoValor(valor)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {opciones.length > 0 && (
        <Radio.Group
          mt="sm"
          label="Acción"
          value={actual}
          onChange={alElegir}
          name={hallazgo.identificador}
        >
          <Stack gap={6} mt={4}>
            {opciones.map((o) => (
              <Radio
                key={o}
                value={o}
                label={o === hallazgo.accion_sugerida ? `${nombreAccion(o)} (sugerida)` : nombreAccion(o)}
              />
            ))}
          </Stack>
        </Radio.Group>
      )}
      {pendiente && actual && (
        <Group mt="xs">
          <Button size="xs" variant="light" color="orange" onClick={() => alElegir(actual)}>
            Confirmar: {nombreAccion(actual)}
          </Button>
        </Group>
      )}
      {accion?.descripcion && !pendiente && (
        <Text size="xs" c="dimmed" mt="xs">
          {accion.descripcion}
        </Text>
      )}
    </Card>
  );
}

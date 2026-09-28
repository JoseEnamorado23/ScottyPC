import { Alert, Badge, Button, Card, Center, Group, List, Loader, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IconDeviceFloppy } from "@tabler/icons-react";
import { useNavigate, useParams } from "react-router";

import { datos, ErrorApi, type Esquemas } from "../api/cliente";
import { claves, useDatosHoja, useProyecto } from "../api/consultas";
import { useApi } from "../api/contexto";
import { useConfirmarInvalidacion } from "../componentes/ConfirmarInvalidacion";
import { EditorAgrupacion, EditorConversion, EditorOrden } from "../componentes/EditoresDecisiones";
import { Etapas } from "../componentes/Etapas";
import { MensajeError } from "../componentes/MensajeError";
import { etapasQueSeDesactualizan } from "../estado/etapas";
import { formatoValor, nombreAccion } from "../estado/textos";
import { useElecciones } from "../estado/useElecciones";

type Decisiones = Esquemas["DecisionesUsuario"];

const IMPUTACION: Record<string, string> = {
  mediana: "Mediana",
  multivariada: "Multivariada",
  eliminar_filas: "Eliminar filas",
};

export function PantallaDecisiones() {
  const { id = "" } = useParams();
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const { revision, borrador, editar, pendientes, previsualizacion, decisiones } = useElecciones(id);
  const muestras = useDatosHoja(id, proyecto.data?.hoja ?? null);
  const { confirmar, modal } = useConfirmarInvalidacion();

  const guardar = useMutation({
    mutationFn: async (valor: Decisiones) => {
      if (!(await confirmar(etapasQueSeDesactualizan(proyecto.data!, "decisiones")))) return false;
      await datos(
        cliente.PUT("/proyectos/{proyecto_id}/decisiones", { params: { path: { proyecto_id: id } }, body: valor }),
      );
      return true;
    },
    onSuccess: async (hecho) => {
      if (!hecho) return;
      notifications.show({ color: "green", message: "Decisiones guardadas." });
      await consultas.invalidateQueries({ queryKey: claves.proyecto(id) });
      await consultas.invalidateQueries({ queryKey: claves.decisionesGuardadas(id) });
      await consultas.invalidateQueries({ queryKey: claves.proyectos });
    },
  });
  const errores = guardar.error instanceof ErrorApi ? guardar.error.porCampo : {};
  const erroresSinEditor = Object.entries(errores).filter(
    ([campo]) => !/^conversiones\.\d+\./.test(campo) && !/^codificaciones\.[^.]+\.(orden|grupos)/.test(campo),
  );

  if (proyecto.isPending || revision.isPending || !borrador) return <Center><Loader /></Center>;
  if (proyecto.error || revision.error) return <MensajeError error={proyecto.error ?? revision.error} />;

  const codificaciones = Object.entries(decisiones?.codificaciones ?? {});
  const columnaDe = (columna: string) =>
    (muestras.data?.vista_previa ?? []).map((fila) => fila[columna]).filter((v) => v !== null && v !== undefined);

  return (
    <Stack>
      {modal}
      <Etapas proyecto={proyecto.data} actual="decisiones" />
      <Group justify="space-between">
        <Title order={2}>Decisiones</Title>
        <Group>
          <Button variant="default" onClick={() => navegar(`/proyectos/${id}/revision`)}>
            Volver a la revisión
          </Button>
          <Button
            leftSection={<IconDeviceFloppy size={16} />}
            disabled={!decisiones || pendientes.length > 0}
            loading={guardar.isPending}
            onClick={() => decisiones && guardar.mutate(decisiones)}
          >
            Guardar decisiones
          </Button>
        </Group>
      </Group>

      {pendientes.length > 0 && (
        <Alert color="orange" title="Faltan confirmaciones">
          Hay {pendientes.length} hallazgos pendientes de confirmar en la revisión.
        </Alert>
      )}
      {guardar.error && <MensajeError error={guardar.error} titulo="No se pudieron guardar las decisiones" />}
      {erroresSinEditor.length > 0 && (
        <Alert color="red" variant="outline" title="Campos con errores">
          <List size="sm">
            {erroresSinEditor.map(([campo, mensaje]) => (
              <List.Item key={campo}>
                <b>{campo}</b>: {mensaje}
              </List.Item>
            ))}
          </List>
        </Alert>
      )}
      <MensajeError error={previsualizacion.error} titulo="No se pudieron calcular las decisiones" />
      {!decisiones ? (
        <Center>
          <Loader />
        </Center>
      ) : (
        <>
          {(decisiones.conversiones.length > 0 ||
            codificaciones.some(([, c]) => c.tipo === "ordinal" || c.tipo === "agrupacion")) && (
            <>
              <Title order={4}>Ajustes</Title>
              <SimpleGrid cols={{ base: 1, lg: 2 }}>
                {decisiones.conversiones.map((c, i) => (
                  <EditorConversion
                    key={c.columna}
                    indice={i}
                    conversion={c}
                    editada={borrador.ediciones.conversiones[c.columna]}
                    muestras={columnaDe(c.columna)}
                    editar={editar}
                    errores={errores}
                  />
                ))}
                {codificaciones.map(([columna, c]) =>
                  c.tipo === "ordinal" ? (
                    <EditorOrden key={columna} columna={columna} codificacion={c} editar={editar} errores={errores} />
                  ) : c.tipo === "agrupacion" ? (
                    <EditorAgrupacion key={columna} columna={columna} codificacion={c} editar={editar} errores={errores} />
                  ) : null,
                )}
              </SimpleGrid>
            </>
          )}
          <Resumen decisiones={decisiones} />
        </>
      )}
    </Stack>
  );
}

function Resumen({ decisiones }: { decisiones: Decisiones }) {
  const faltantes = Object.entries(decisiones.faltantes);
  const codificaciones = Object.entries(decisiones.codificaciones);
  return (
    <Stack>
      <Title order={4}>Resumen</Title>
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <Card withBorder>
          <Text fw={600} mb="xs">
            Filas y columnas
          </Text>
          <Text size="sm">Duplicados: {decisiones.eliminar_duplicados ? "se eliminan" : "se conservan"}</Text>
          <Text size="sm" mt="xs">
            Columnas excluidas:
          </Text>
          <Group gap={4}>
            {decisiones.columnas_excluidas.length === 0 && <Text size="sm" c="dimmed">ninguna</Text>}
            {decisiones.columnas_excluidas.map((c) => (
              <Badge key={c} variant="light" color="gray">
                {c}
              </Badge>
            ))}
          </Group>
          <Text size="sm" mt="xs">
            Logaritmo: {decisiones.logaritmos.length ? decisiones.logaritmos.join(", ") : "ninguna"}
          </Text>
          <Text size="sm" mt="xs">
            Separación: {decisiones.separacion.tipo === "temporal" ? `temporal por «${decisiones.separacion.columna_fecha}»` : "estratificada"}{" "}
            ({formatoValor(decisiones.separacion.proporcion_test * 100)} % de prueba)
          </Text>
        </Card>
        <Card withBorder>
          <Text fw={600} mb="xs">
            Faltantes
          </Text>
          {faltantes.length === 0 ? (
            <Text size="sm" c="dimmed">Sin tratamiento de faltantes.</Text>
          ) : (
            <Table fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Columna</Table.Th>
                  <Table.Th>Ceros como faltantes</Table.Th>
                  <Table.Th>Indicador</Table.Th>
                  <Table.Th>Imputación</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {faltantes.map(([columna, t]) => (
                  <Table.Tr key={columna}>
                    <Table.Td>{columna}</Table.Td>
                    <Table.Td>{t.ceros_como_faltantes ? "Sí" : "No"}</Table.Td>
                    <Table.Td>{t.indicador_medido ? "Sí" : "No"}</Table.Td>
                    <Table.Td>{t.imputacion ? IMPUTACION[t.imputacion] : "Ninguna"}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Card>
        <Card withBorder>
          <Text fw={600} mb="xs">
            Codificaciones
          </Text>
          {codificaciones.length === 0 ? (
            <Text size="sm" c="dimmed">Ninguna.</Text>
          ) : (
            <List size="sm">
              {codificaciones.map(([columna, c]) => (
                <List.Item key={columna}>
                  <b>{columna}</b>: {c.tipo}
                  {c.orden && ` (${c.orden.map(formatoValor).join(" < ")})`}
                </List.Item>
              ))}
            </List>
          )}
        </Card>
        <Card withBorder>
          <Text fw={600} mb="xs">
            Acciones por hallazgo
          </Text>
          <List size="sm">
            {Object.entries(decisiones.acciones_hallazgos).map(([hallazgo, a]) => (
              <List.Item key={hallazgo}>
                <b>{nombreAccion(a.accion)}</b> — {a.descripcion}
              </List.Item>
            ))}
          </List>
        </Card>
      </SimpleGrid>
      {decisiones.notas.length > 0 && (
        <Alert color="blue" variant="light" title="Notas">
          <List size="sm">
            {decisiones.notas.map((n, i) => (
              <List.Item key={i}>{n}</List.Item>
            ))}
          </List>
        </Alert>
      )}
    </Stack>
  );
}

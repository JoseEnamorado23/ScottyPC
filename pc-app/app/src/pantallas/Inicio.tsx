import { Button, Center, Group, Loader, Modal, Stack, Table, Text, Title } from "@mantine/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IconFolderOpen, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { datos, type Esquemas } from "../api/cliente";
import { claves, useProyectos } from "../api/consultas";
import { useApi } from "../api/contexto";
import { MensajeError } from "../componentes/MensajeError";
import { ETAPAS, rutaDeProyecto } from "../estado/etapas";

type Proyecto = Esquemas["Proyecto"];

const fecha = (iso: string) => new Date(iso).toLocaleString("es");
const nombreEtapa = (clave: string | null) => ETAPAS.find((e) => e.clave === clave)?.nombre ?? "Sin empezar";

export function Inicio() {
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const proyectos = useProyectos();
  const [aEliminar, setAEliminar] = useState<Proyecto | null>(null);

  const eliminar = useMutation({
    mutationFn: (id: string) =>
      datos(cliente.DELETE("/proyectos/{proyecto_id}", { params: { path: { proyecto_id: id } } })),
    onSuccess: async () => {
      setAEliminar(null);
      await consultas.invalidateQueries({ queryKey: claves.proyectos });
    },
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Proyectos</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => navegar("/nuevo")}>
          Nuevo proyecto
        </Button>
      </Group>

      <MensajeError error={proyectos.error} titulo="No se pudieron cargar los proyectos" />
      {proyectos.isPending && (
        <Center>
          <Loader />
        </Center>
      )}
      {proyectos.data?.length === 0 && <Text c="dimmed">Todavía no hay proyectos. Cree uno a partir de un CSV o Excel.</Text>}
      {!!proyectos.data?.length && (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Nombre</Table.Th>
              <Table.Th>Objetivo</Table.Th>
              <Table.Th>Etapa</Table.Th>
              <Table.Th>Actualizado</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {proyectos.data.map((p) => (
              <Table.Tr key={p.id}>
                <Table.Td>
                  <Text fw={500}>{p.nombre}</Text>
                  <Text size="xs" c="dimmed">
                    {p.archivo_original}
                  </Text>
                </Table.Td>
                <Table.Td>{p.objetivo ?? "—"}</Table.Td>
                <Table.Td>{nombreEtapa(p.etapa_actual)}</Table.Td>
                <Table.Td>{fecha(p.actualizado_en)}</Table.Td>
                <Table.Td>
                  <Group gap="xs" justify="flex-end">
                    <Button size="xs" variant="light" leftSection={<IconFolderOpen size={14} />} onClick={() => navegar(rutaDeProyecto(p))}>
                      Abrir
                    </Button>
                    <Button size="xs" variant="subtle" color="red" leftSection={<IconTrash size={14} />} onClick={() => setAEliminar(p)}>
                      Eliminar
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={aEliminar !== null} onClose={() => setAEliminar(null)} title="Eliminar proyecto">
        <Stack>
          <Text size="sm">
            Se eliminará el proyecto <b>{aEliminar?.nombre}</b> con su copia de los datos y sus resultados.
          </Text>
          <Text size="sm">
            Su archivo original (<b>{aEliminar?.archivo_original}</b>) no se elimina ni se modifica.
          </Text>
          <MensajeError error={eliminar.error} />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setAEliminar(null)}>
              Cancelar
            </Button>
            <Button color="red" loading={eliminar.isPending} onClick={() => aEliminar && eliminar.mutate(aEliminar.id)}>
              Eliminar
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

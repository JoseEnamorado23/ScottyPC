import { Button, Center, Grid, Group, Loader, Paper, ScrollArea, Select, Stack, Table, Text, Title } from "@mantine/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";

import { datos, ErrorApi } from "../api/cliente";
import { claves, useDatosHoja, useDistribucion, useProyecto } from "../api/consultas";
import { useApi } from "../api/contexto";
import { useConfirmarInvalidacion } from "../componentes/ConfirmarInvalidacion";
import { Etapas } from "../componentes/Etapas";
import { MensajeError } from "../componentes/MensajeError";
import { esListaDeProblemas, ProblemasValidacion } from "../componentes/ProblemasValidacion";
import { VistaDistribucion } from "../componentes/VistaDistribucion";
import { BORRADOR_VACIO, useBorrador } from "../estado/borrador";
import { etapasQueSeDesactualizan } from "../estado/etapas";

const celda = (valor: unknown) => (valor === null || valor === undefined ? "" : String(valor));

export function DatosProyecto() {
  const { id = "" } = useParams();
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const [hoja, setHoja] = useState<string | null>(null);
  const [objetivo, setObjetivo] = useState<string | null>(null);
  const hojaElegida = hoja ?? proyecto.data?.hoja ?? null;
  const tabla = useDatosHoja(id, hojaElegida);
  const hojaActual = tabla.data?.hoja ?? null;
  const objetivoElegido = objetivo ?? (tabla.data?.columnas.includes(proyecto.data?.objetivo ?? "") ? proyecto.data!.objetivo : null);
  const distribucion = useDistribucion(id, objetivoElegido, hojaActual);
  const { confirmar, modal } = useConfirmarInvalidacion();
  const { inicializar } = useBorrador(id);

  const revisar = useMutation({
    mutationFn: async () => {
      if (!(await confirmar(etapasQueSeDesactualizan(proyecto.data!, "revision")))) return false;
      await datos(
        cliente.POST("/proyectos/{proyecto_id}/revision", {
          params: { path: { proyecto_id: id } },
          body: { objetivo: objetivoElegido!, hoja: hojaActual },
        }),
      );
      return true;
    },
    onSuccess: async (hecho) => {
      if (!hecho) return;
      inicializar(BORRADOR_VACIO);
      await consultas.invalidateQueries({ queryKey: claves.proyecto(id) });
      await consultas.invalidateQueries({ queryKey: claves.proyectos });
      navegar(`/proyectos/${id}/revision`);
    },
  });

  const noValido =
    revisar.error instanceof ErrorApi && revisar.error.codigo === "DATASET_NO_VALIDO" && esListaDeProblemas(revisar.error.detalles)
      ? revisar.error.detalles
      : null;

  if (proyecto.isPending) return <Center><Loader /></Center>;
  if (proyecto.error) return <MensajeError error={proyecto.error} />;

  return (
    <Stack>
      {modal}
      <Etapas proyecto={proyecto.data} actual="revision" />
      <Title order={2}>{proyecto.data.nombre}</Title>
      <Text size="sm" c="dimmed">
        {proyecto.data.archivo_original}
      </Text>

      <Group align="flex-end">
        {tabla.data?.hojas && (
          <Select
            label="Hoja"
            data={tabla.data.hojas}
            value={hojaActual}
            allowDeselect={false}
            onChange={(h) => {
              setHoja(h);
              setObjetivo(null);
            }}
          />
        )}
        <Select
          label="Variable objetivo"
          placeholder="Elija la columna a explicar"
          searchable
          data={tabla.data?.columnas ?? []}
          value={objetivoElegido}
          onChange={setObjetivo}
          w={280}
        />
        <Button disabled={!objetivoElegido || !tabla.data} loading={revisar.isPending} onClick={() => revisar.mutate()}>
          Revisar dataset
        </Button>
      </Group>

      {noValido ? <ProblemasValidacion problemas={noValido} bloqueantes /> : <MensajeError error={revisar.error} />}
      <MensajeError error={tabla.error} titulo="No se pudo leer la hoja" />

      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Paper withBorder p="sm">
            <Text fw={500} mb="xs">
              Vista previa {tabla.data && `(20 de ${tabla.data.filas.toLocaleString("es")} filas)`}
            </Text>
            {tabla.isPending ? (
              <Loader size="sm" />
            ) : (
              tabla.data && (
                <ScrollArea h={420}>
                  <Table striped withTableBorder fz="xs" stickyHeader>
                    <Table.Thead>
                      <Table.Tr>
                        {tabla.data.columnas.map((c) => (
                          <Table.Th key={c} bg={c === objetivoElegido ? "blue.1" : undefined}>
                            {c}
                          </Table.Th>
                        ))}
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {tabla.data.vista_previa.map((fila, i) => (
                        <Table.Tr key={i}>
                          {tabla.data.columnas.map((c) => (
                            <Table.Td key={c}>{celda(fila[c])}</Table.Td>
                          ))}
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </ScrollArea>
              )
            )}
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Paper withBorder p="sm">
            <Text fw={500} mb="xs">
              Distribución del objetivo
            </Text>
            {!objetivoElegido && <Text size="sm" c="dimmed">Elija la variable objetivo.</Text>}
            {distribucion.isFetching && <Loader size="sm" />}
            <MensajeError error={distribucion.error} />
            {distribucion.data && <VistaDistribucion distribucion={distribucion.data} />}
          </Paper>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

// Pantalla provisional de resultados (la fase 7 la reemplaza por la vista completa).
import { Alert, Badge, Card, Center, Group, Image, Loader, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useParams } from "react-router";

import { claves, useProyecto, useResultado } from "../api/consultas";
import { useApi } from "../api/contexto";
import { ErrorApi } from "../api/cliente";
import { Etapas } from "../componentes/Etapas";
import { MensajeError } from "../componentes/MensajeError";

/** grafo.png descargado con fetch (lleva el encabezado X-Token) y mostrado con una URL de objeto. */
function useGrafo(id: string, habilitado: boolean) {
  const { cliente } = useApi();
  const consulta = useQuery({
    queryKey: claves.grafo(id),
    enabled: habilitado,
    queryFn: async () => {
      const { data, response } = await cliente.GET("/proyectos/{proyecto_id}/archivos/{nombre}", {
        params: { path: { proyecto_id: id, nombre: "grafo.png" } },
        parseAs: "blob",
      });
      if (!response.ok || !(data instanceof Blob)) {
        throw new ErrorApi(response.status, "GRAFO_NO_DISPONIBLE", "No se pudo descargar el grafo.");
      }
      return data;
    },
  });
  const url = useMemo(() => (consulta.data ? URL.createObjectURL(consulta.data) : null), [consulta.data]);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);
  return { url, error: consulta.error, cargando: consulta.isPending && habilitado };
}

export function Resultados() {
  const { id = "" } = useParams();
  const proyecto = useProyecto(id);
  const resultado = useResultado(id);
  const grafo = useGrafo(id, !!resultado.data);

  if (proyecto.isPending || resultado.isPending) return <Center><Loader /></Center>;
  if (proyecto.error || resultado.error) return <MensajeError error={proyecto.error ?? resultado.error} />;
  if (!resultado.data) return <Alert color="orange">No hay un análisis vigente.</Alert>;

  const { caracterizacion, corridas } = resultado.data;
  const directas = caracterizacion.variables.filter((v) => v.categoria === "causa_directa").map((v) => v.variable);

  return (
    <Stack>
      <Etapas proyecto={proyecto.data} actual="analisis" />
      <Title order={2}>Resultados</Title>
      <Text size="sm" c="dimmed">
        Vista provisional. Objetivo: {caracterizacion.objetivo} · {corridas.validas} corridas válidas de {corridas.totales}.
      </Text>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder>
          <Text fw={600} mb="xs">
            Causas directas
          </Text>
          <Group gap="xs" data-testid="causas-directas">
            {directas.length === 0 && <Text size="sm" c="dimmed">Ninguna.</Text>}
            {directas.map((v) => (
              <Badge key={v} size="lg" variant="light">
                {v}
              </Badge>
            ))}
          </Group>
        </Card>
        <Card withBorder>
          <Text fw={600} mb="xs">
            Candidatas prescriptivas
          </Text>
          <Group gap="xs" data-testid="candidatas-prescriptivas">
            {caracterizacion.candidatas_prescriptivas.length === 0 && <Text size="sm" c="dimmed">Ninguna.</Text>}
            {caracterizacion.candidatas_prescriptivas.map((v) => (
              <Badge key={v} size="lg" color="green" variant="light">
                {v}
              </Badge>
            ))}
          </Group>
        </Card>
      </SimpleGrid>
      <Text size="sm">{caracterizacion.mensaje}</Text>
      <Card withBorder>
        <Text fw={600} mb="xs">
          Grafo
        </Text>
        {grafo.cargando && <Loader size="sm" />}
        {grafo.url && <Image src={grafo.url} alt="Grafo causal" fit="contain" mah={600} />}
        <MensajeError error={grafo.error} titulo="No se pudo mostrar el grafo" />
      </Card>
    </Stack>
  );
}

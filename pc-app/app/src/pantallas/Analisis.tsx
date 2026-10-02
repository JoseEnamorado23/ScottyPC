import { Alert, Button, Card, Center, Group, Loader, Stack, Text, Title } from "@mantine/core";
import { IconPlayerPlay } from "@tabler/icons-react";
import { useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router";

import { esFinal, useProyecto, useTrabajo } from "../api/consultas";
import { useAccionesTrabajo } from "../api/trabajos";

import { MensajeError } from "../componentes/MensajeError";
import { ProgresoTrabajo } from "../componentes/ProgresoTrabajo";
import { estadoEtapa, trabajoDelProyecto } from "../estado/etapas";
import { useVigilancia } from "../estado/trabajos";

export function Analisis() {
  const { id = "" } = useParams();
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const trabajoId = proyecto.data ? trabajoDelProyecto(proyecto.data, "pc") : null;
  const trabajo = useTrabajo(trabajoId);
  const { lanzarPc, cancelar, reanudar } = useAccionesTrabajo(id);
  const { vigilar } = useVigilancia();

  // Si el análisis termina mientras se mira esta pantalla, se pasa a los resultados.
  const visto = useRef<string | null>(null);
  useEffect(() => {
    const estado = trabajo.data?.estado;
    if (trabajo.data && !esFinal(estado)) vigilar(trabajo.data);
    if (visto.current && !esFinal(visto.current) && estado === "completado") {
      navegar(`/proyectos/${id}/resultados`);
    }
    visto.current = estado ?? null;
  }, [trabajo.data, vigilar, navegar, id]);

  if (proyecto.isPending) return <Center><Loader /></Center>;
  if (proyecto.error) return <MensajeError error={proyecto.error} />;

  const configuracionVigente = estadoEtapa(proyecto.data, "configuracion_pc") === "vigente";
  const analisisVigente = estadoEtapa(proyecto.data, "analisis") === "vigente";
  const datosTrabajo = trabajo.data;
  const enCurso = datosTrabajo && !esFinal(datosTrabajo.estado);
  const reanudable = proyecto.data.ultimo_trabajo?.reanudable ?? false;

  return (
    <Stack>

      <Group justify="space-between">
        <Title order={2}>Análisis</Title>
        <Group>
          <Button variant="default" onClick={() => navegar(`/proyectos/${id}/configuracion`)}>
            Volver a la configuración
          </Button>
          {analisisVigente && (
            <Button onClick={() => navegar(`/proyectos/${id}/resultados`)}>Ver resultados</Button>
          )}
        </Group>
      </Group>

      {!configuracionVigente && (
        <Alert color="orange">Guarde la configuración de PC antes de ejecutar el análisis.</Alert>
      )}

      {datosTrabajo && (datosTrabajo.estado !== "completado" || !analisisVigente) && (
        <ProgresoTrabajo
          trabajo={datosTrabajo}
          reanudable={reanudable}
          alCancelar={() => cancelar.mutate(datosTrabajo.id)}
          alReanudar={() => reanudar.mutate(datosTrabajo.id)}
          cancelando={cancelar.isPending}
          reanudando={reanudar.isPending}
        />
      )}
      <MensajeError error={cancelar.error ?? reanudar.error ?? trabajo.error} />

      {!enCurso && (
        <Card withBorder>
          <Group justify="space-between">
            <Text size="sm">
              {analisisVigente
                ? "El análisis está al día. Puede ejecutarlo de nuevo (el resultado anterior se archiva)."
                : datosTrabajo && reanudable
                  ? "También puede empezar de nuevo; se descarta el avance guardado."
                  : "Ejecuta PC con bootstrap según la configuración guardada."}
            </Text>
            <Button
              leftSection={<IconPlayerPlay size={16} />}
              onClick={() => lanzarPc.mutate()}
              loading={lanzarPc.isPending}
              disabled={!configuracionVigente}
              variant={datosTrabajo && reanudable ? "light" : "filled"}
            >
              {datosTrabajo && reanudable ? "Empezar de nuevo" : "Ejecutar análisis"}
            </Button>
          </Group>
          <MensajeError error={lanzarPc.error} titulo="No se pudo iniciar el análisis" />
        </Card>
      )}
    </Stack>
  );
}

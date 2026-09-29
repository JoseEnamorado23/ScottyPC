// Modelo causal: verificación de aplicabilidad, construcción (trabajo) con overrides de
// mecanismo y de monotonía, tabla de mecanismos con las curvas del objetivo, evaluación y
// explorador de escenarios. El núcleo decide; esta pantalla solo muestra y envía elecciones.
import { Alert, Badge, Button, Card, Center, Group, Loader, Stack, Switch, Tabs, Text, Title } from "@mantine/core";
import { IconAlertTriangle, IconHammer } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { esFinal, useProyecto, useTrabajo } from "../api/consultas";
import { useAplicabilidad, useConstruirModelo, useModeloCausal } from "../api/modeloCausal";
import { useAccionesTrabajo } from "../api/trabajos";
import { Etapas } from "../componentes/Etapas";
import { MensajeError } from "../componentes/MensajeError";
import { ProgresoTrabajo } from "../componentes/ProgresoTrabajo";
import { ListaAplicabilidad } from "../componentes/modelo_causal/Aplicabilidad";
import { ExploradorEscenarios } from "../componentes/modelo_causal/Escenarios";
import { PanelEvaluacion } from "../componentes/modelo_causal/Evaluacion";
import { ESTILO_GRAFICOS } from "../componentes/modelo_causal/Graficos";
import { EfectosObjetivo, TablaMecanismos } from "../componentes/modelo_causal/Mecanismos";
import { estadoEtapa, trabajoDelProyecto } from "../estado/etapas";
import {
  SOLICITUD_VACIA, mecanismoObjetivo, mismaSolicitud, solicitudDelModelo, type Solicitud,
} from "../estado/modeloCausal";
import { useVigilancia } from "../estado/trabajos";

export function ModeloCausal() {
  const { id = "" } = useParams();
  return <PantallaModeloCausal key={id} id={id} />;
}

function PantallaModeloCausal({ id }: { id: string }) {
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const estadoModelo = proyecto.data ? estadoEtapa(proyecto.data, "modelo_causal") : "pendiente";
  const analisisVigente = proyecto.data ? estadoEtapa(proyecto.data, "analisis") === "vigente" : false;
  const modelo = useModeloCausal(id, estadoModelo === "vigente");
  const trabajoId = proyecto.data ? trabajoDelProyecto(proyecto.data, "modelo_causal") : null;
  const trabajo = useTrabajo(trabajoId);
  const construir = useConstruirModelo(id);
  const { cancelar, reanudar } = useAccionesTrabajo(id);
  const { vigilar } = useVigilancia();

  const guardada = modelo.data ? solicitudDelModelo(modelo.data.modelo.configuracion) : SOLICITUD_VACIA;
  const [solicitud, setSolicitud] = useState<Solicitud | null>(null);
  const actual = solicitud ?? guardada;
  const cambiada = !mismaSolicitud(actual, guardada);
  const aplicabilidad = useAplicabilidad(id, actual, !!proyecto.data);
  const [pestana, setPestana] = useState<string | null>("mecanismos");

  useEffect(() => {
    if (trabajo.data && !esFinal(trabajo.data.estado)) vigilar(trabajo.data);
  }, [trabajo.data, vigilar]);
  // Al llegar un modelo nuevo, las elecciones parten de su configuración.
  const huella = modelo.data?.modelo.huella;
  useEffect(() => setSolicitud(null), [huella]);

  if (proyecto.isPending) return <Center><Loader /></Center>;
  if (proyecto.error) return <MensajeError error={proyecto.error} />;

  const enCurso = !!trabajo.data && !esFinal(trabajo.data.estado);
  const bloqueado = aplicabilidad.data?.bloqueado ?? true;
  const vista = modelo.data ?? null;
  const binario = vista?.modelo.tipo_objetivo === "binario";
  const objetivo = vista ? mecanismoObjetivo(vista.evaluacion) : null;
  // Advertencias que solo se conocen al ajustar (intermedia mal explicada, costo de la parsimonia...).
  const previas = new Set((aplicabilidad.data?.problemas ?? []).map((p) => p.codigo));
  const advertenciasAjuste = (vista?.modelo.advertencias ?? []).filter((p) => !previas.has(p.codigo));

  return (
    <Stack>
      <style>{ESTILO_GRAFICOS}</style>
      <Etapas proyecto={proyecto.data} actual="modelo_causal" />
      <Group justify="space-between">
        <Title order={2}>Modelo causal</Title>
        <Button variant="default" onClick={() => navegar(`/proyectos/${id}/resultados`)} disabled={!analisisVigente}>
          Volver a los resultados
        </Button>
      </Group>

      <Card withBorder>
        <Stack gap="sm">
          <Text fw={600}>Verificación de aplicabilidad</Text>
          {aplicabilidad.isPending ? (
            <Loader size="sm" />
          ) : (
            aplicabilidad.data && <ListaAplicabilidad proyectoId={id} problemas={aplicabilidad.data.problemas} />
          )}
          <MensajeError error={aplicabilidad.error} />
        </Stack>
      </Card>

      {estadoModelo === "desactualizada" && !enCurso && (
        <Alert color="orange" icon={<IconAlertTriangle size={18} />} data-testid="modelo-desactualizado">
          El modelo causal está desactualizado: cambió el resultado de PC (su versión actual) o una etapa anterior.
          Vuelva a construirlo.
        </Alert>
      )}
      {vista && !vista.vigente && <Alert color="orange">{vista.motivo_desactualizado}</Alert>}

      {trabajo.data && (enCurso || trabajo.data.estado !== "completado") && (
        <ProgresoTrabajo
          trabajo={trabajo.data}
          reanudable={proyecto.data.ultimo_trabajo?.reanudable ?? false}
          alCancelar={() => cancelar.mutate(trabajo.data!.id)}
          alReanudar={() => reanudar.mutate(trabajo.data!.id)}
          cancelando={cancelar.isPending}
          reanudando={reanudar.isPending}
        />
      )}

      {!enCurso && (
        <Card withBorder>
          <Group justify="space-between" align="flex-start">
            <Stack gap={4} maw={620}>
              <Text size="sm">
                {vista
                  ? cambiada
                    ? "Hay cambios en los mecanismos o la monotonía: reconstruya el modelo para aplicarlos."
                    : `Modelo construido sobre la versión ${vista.modelo.resultado_pc.version} del resultado de PC.`
                  : "Ajusta un mecanismo por cada variable con padres del subgrafo del objetivo (solo con train)."}
              </Text>
              <Switch
                size="sm"
                label="Pesos de clase en el objetivo"
                description="Solo si lo necesita: las probabilidades dejan de estar calibradas (por defecto el desbalance se compensa con el umbral)."
                checked={Boolean(actual.pesos_clase)}
                onChange={(e) => setSolicitud({ ...actual, pesos_clase: e.currentTarget.checked })}
              />
            </Stack>
            <Group gap="xs">
              {cambiada && (
                <Button variant="default" onClick={() => setSolicitud(null)}>
                  Descartar cambios
                </Button>
              )}
              <Button
                leftSection={<IconHammer size={16} />}
                onClick={() => construir.mutate(actual)}
                loading={construir.isPending}
                disabled={bloqueado || !analisisVigente}
                variant={vista && !cambiada ? "light" : "filled"}
              >
                {vista ? (cambiada ? "Reconstruir con los cambios" : "Reconstruir") : "Construir modelo"}
              </Button>
            </Group>
          </Group>
          {cambiada && (
            <Badge color="orange" variant="light" mt="xs" data-testid="cambios-sin-aplicar">
              Cambios sin aplicar
            </Badge>
          )}
          <MensajeError error={construir.error} titulo="No se pudo construir el modelo" />
        </Card>
      )}

      {estadoModelo === "vigente" && modelo.isPending && <Center><Loader /></Center>}
      <MensajeError error={modelo.error} />
      {vista && objetivo && (
        <Tabs value={pestana} onChange={setPestana} keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="mecanismos">Mecanismos</Tabs.Tab>
            <Tabs.Tab value="evaluacion">Evaluación</Tabs.Tab>
            <Tabs.Tab value="escenarios">Escenarios</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="mecanismos" pt="md">
            <Stack>
              {advertenciasAjuste.length > 0 && <ListaAplicabilidad proyectoId={id} problemas={advertenciasAjuste} delAjuste />}
              <TablaMecanismos mecanismos={vista.evaluacion.mecanismos} solicitud={actual} alCambiar={setSolicitud} />
              <Text fw={600}>Efecto parcial de cada causa directa de {vista.modelo.objetivo}</Text>
              <EfectosObjetivo
                mecanismo={objetivo}
                monotonia={vista.modelo.monotonia}
                medida={binario ? "probabilidad" : "valor"}
                solicitud={actual}
                alCambiar={setSolicitud}
              />
              {vista.modelo.subgrafo.fuera.length > 0 && (
                <Text size="xs" c="dimmed">
                  Fuera del modelo (no son ancestros del objetivo): {vista.modelo.subgrafo.fuera.join(", ")}.
                </Text>
              )}
            </Stack>
          </Tabs.Panel>
          <Tabs.Panel value="evaluacion" pt="md">
            <PanelEvaluacion evaluacion={vista.evaluacion} binario={binario} />
          </Tabs.Panel>
          <Tabs.Panel value="escenarios" pt="md">
            <ExploradorEscenarios proyectoId={id} vista={vista} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Stack>
  );
}

// Prescripción: condiciones, configuración (con la declaración de supuestos), caso individual,
// lotes y evaluación. El aviso sobre datos observacionales está siempre visible.
import { Alert, Center, Loader, Stack, Tabs, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { esFinal, useProyecto, useTrabajo } from "../api/consultas";
import {
  useAccionesPrescripcion, useCondicionesPrescripcion, useConfiguracionPrescripcion, useValidacionPrescripcion,
  type ConfiguracionPrescripcion as Configuracion,
} from "../api/prescripcion";
import { useAccionesTrabajo } from "../api/trabajos";
import { MensajeError } from "../componentes/MensajeError";
import { ProgresoTrabajo } from "../componentes/ProgresoTrabajo";
import { ListaAplicabilidad } from "../componentes/modelo_causal/Aplicabilidad";
import { ESTILO_GRAFICOS } from "../componentes/modelo_causal/Graficos";
import { CasoIndividual } from "../componentes/prescripcion/Caso";
import { ConfiguracionPrescripcion } from "../componentes/prescripcion/Configuracion";
import { EvaluacionPrescriptor } from "../componentes/prescripcion/Evaluacion";
import { Lotes } from "../componentes/prescripcion/Lote";
import { estadoEtapa } from "../estado/etapas";
import { AVISO_PRESCRIPCION, completarCon, erroresPorCampo, mismaConfiguracion } from "../estado/prescripcion";
import { useVigilancia } from "../estado/trabajos";

export const RETARDO_VALIDACION_PRESCRIPCION_MS = 300;
const TIPOS_TRABAJO = ["calibracion_mu", "lote_prescripcion", "evaluacion_prescripcion"];
/** Sección de la configuración donde se resuelve cada problema. */
const SECCION_DEL_PROBLEMA: Record<string, string> = {
  SUPUESTOS_SIN_CONFIRMAR: "seccion-supuestos",
  SIN_PRESCRIPTIVAS: "seccion-modificables",
  NINGUNA_PERMITIDA: "seccion-modificables",
  MODIFICABLES_SIN_CAMINO: "seccion-modificables",
  MODIFICABLES_DESCONOCIDAS: "seccion-modificables",
};

export function Prescripcion() {
  const { id = "" } = useParams();
  return <PantallaPrescripcion key={id} id={id} />;
}

function PantallaPrescripcion({ id }: { id: string }) {
  const proyecto = useProyecto(id);
  const modeloVigente = proyecto.data ? estadoEtapa(proyecto.data, "modelo_causal") === "vigente" : false;
  const etapa = proyecto.data ? estadoEtapa(proyecto.data, "prescripcion") : "pendiente";
  const vista = useConfiguracionPrescripcion(id, modeloVigente);
  const [borrador, setBorrador] = useState<Configuracion | null>(null);
  const actual = borrador ?? vista.data?.configuracion ?? null;
  const sinGuardar = !!borrador && !!vista.data && !mismaConfiguracion(borrador, vista.data.configuracion);
  const [diferido] = useDebouncedValue(sinGuardar ? borrador : null, RETARDO_VALIDACION_PRESCRIPCION_MS);
  const validacion = useValidacionPrescripcion(id, diferido);
  const condiciones = useCondicionesPrescripcion(id, diferido, !!proyecto.data);
  const acciones = useAccionesPrescripcion(id);
  const { cancelar, reanudar } = useAccionesTrabajo(id);
  const { vigilar } = useVigilancia();
  const [pestana, setPestana] = useState<string | null>("configuracion");

  const ultimo = proyecto.data?.ultimo_trabajo;
  const trabajoId = ultimo && TIPOS_TRABAJO.includes(ultimo.tipo) ? ultimo.id : null;
  const trabajo = useTrabajo(trabajoId);
  const enCurso = !!trabajo.data && !esFinal(trabajo.data.estado);
  useEffect(() => {
    if (trabajo.data && !esFinal(trabajo.data.estado)) vigilar(trabajo.data);
  }, [trabajo.data, vigilar]);

  // El núcleo completa las acciones de las nuevas prescriptivas al cambiar las modificables.
  const completada = validacion.data?.configuracion;
  useEffect(() => {
    if (!borrador || !completada) return;
    const nuevo = completarCon(borrador, completada);
    if (!mismaConfiguracion(nuevo, borrador)) setBorrador(nuevo);
  }, [completada, borrador]);

  // Abre la pestaña de configuración y lleva a la sección donde se resuelve el problema.
  const irALaConfiguracion = (problema: { codigo: string }) => {
    setPestana("configuracion");
    const seccion = SECCION_DEL_PROBLEMA[problema.codigo] ?? "seccion-modificables";
    const desplazar = (intentos: number) => {
      const elemento = document.getElementById(seccion);
      if (elemento) elemento.scrollIntoView({ behavior: "smooth", block: "start" });
      else if (intentos > 0) setTimeout(() => desplazar(intentos - 1), 50);
    };
    desplazar(20);
  };

  if (proyecto.isPending) return <Center><Loader /></Center>;
  if (proyecto.error) return <MensajeError error={proyecto.error} />;

  const aviso = (
    <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={18} />} data-testid="aviso-prescripcion">
      <Text size="sm" fw={600}>{AVISO_PRESCRIPCION}</Text>
    </Alert>
  );
  const problemas = condiciones.data?.problemas ?? [];
  const bloqueado = condiciones.data?.bloqueado ?? true;
  const errores = erroresPorCampo(sinGuardar ? validacion.data?.errores : []);
  const guardar = () =>
    actual &&
    acciones.guardar.mutate(actual, {
      onSuccess: () => {
        setBorrador(null);
        notifications.show({ color: "green", message: "Configuración de la prescripción guardada." });
      },
    });

  return (
    <Stack>
      <style>{ESTILO_GRAFICOS}</style>
      <Title order={2}>Prescripción</Title>
      {aviso}
      <Stack gap="xs">
        <Text fw={600}>Condiciones para prescribir</Text>
        {condiciones.isPending ? <Loader size="sm" /> : (
          <ListaAplicabilidad
            proyectoId={id} problemas={problemas} sinBloqueantes="Sin bloqueantes: se puede prescribir."
            destinosLocales={{ prescripcion: { texto: "Ir a la configuración", accion: irALaConfiguracion } }}
          />
        )}
        <MensajeError error={condiciones.error} />
      </Stack>

      {etapa === "desactualizada" && (
        <Alert color="orange">La prescripción está desactualizada (cambió el modelo causal): revise y vuelva a guardar la configuración.</Alert>
      )}
      {trabajo.data && (enCurso || trabajo.data.estado !== "completado") && (
        <ProgresoTrabajo
          trabajo={trabajo.data} reanudable={ultimo?.reanudable ?? false}
          alCancelar={() => cancelar.mutate(trabajo.data!.id)} alReanudar={() => reanudar.mutate(trabajo.data!.id)}
          cancelando={cancelar.isPending} reanudando={reanudar.isPending}
        />
      )}

      {!modeloVigente ? (
        <Alert color="orange">Construya un modelo causal vigente para configurar la prescripción.</Alert>
      ) : vista.isPending || !actual ? (
        <Center><Loader /></Center>
      ) : vista.data ? (
        <Tabs value={pestana} onChange={setPestana} keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="configuracion">Configuración</Tabs.Tab>
            <Tabs.Tab value="caso">Caso individual</Tabs.Tab>
            <Tabs.Tab value="lote">Lote</Tabs.Tab>
            <Tabs.Tab value="evaluacion">Evaluación</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="configuracion" pt="md">
            <ConfiguracionPrescripcion
              vista={vista.data} borrador={actual} errores={errores} sinGuardar={sinGuardar || !vista.data.guardada}
              guardando={acciones.guardar.isPending} calibrando={acciones.calibrar.isPending || enCurso}
              alCambiar={setBorrador} alGuardar={guardar} alDescartar={() => setBorrador(null)}
              alCalibrar={() => acciones.calibrar.mutate()}
            />
            <MensajeError error={acciones.guardar.error ?? acciones.calibrar.error} titulo="No se pudo completar la acción" />
          </Tabs.Panel>
          <Tabs.Panel value="caso" pt="md">
            <CasoIndividual proyectoId={id} bloqueado={bloqueado || sinGuardar || etapa !== "vigente"} />
          </Tabs.Panel>
          <Tabs.Panel value="lote" pt="md">
            <Lotes proyectoId={id} bloqueado={bloqueado || sinGuardar || etapa !== "vigente"} enCurso={enCurso} />
          </Tabs.Panel>
          <Tabs.Panel value="evaluacion" pt="md">
            <EvaluacionPrescriptor proyectoId={id} bloqueado={bloqueado || sinGuardar || etapa !== "vigente"} enCurso={enCurso} />
          </Tabs.Panel>
        </Tabs>
      ) : (
        <MensajeError error={vista.error} />
      )}
    </Stack>
  );
}

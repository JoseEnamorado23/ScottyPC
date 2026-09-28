import {
  Accordion,
  Alert,
  Button,
  Card,
  Center,
  Checkbox,
  Group,
  List,
  Loader,
  NumberInput,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IconArrowRight, IconRestore } from "@tabler/icons-react";
import { useEffect, useMemo, useReducer, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { datos, ErrorApi, type Esquemas } from "../api/cliente";
import { claves, useConfiguracionPc, useProyecto, useValidacionConfiguracion } from "../api/consultas";
import { useApi } from "../api/contexto";
import { useConfirmarInvalidacion } from "../componentes/ConfirmarInvalidacion";
import { EditorNiveles } from "../componentes/EditorNiveles";
import { Etapas } from "../componentes/Etapas";
import { MensajeError } from "../componentes/MensajeError";
import { useBorradorAnalisis } from "../estado/borradorAnalisis";
import { estadoEtapa, etapasQueSeDesactualizan } from "../estado/etapas";
import { aConfiguracion, crearEstado, reducirNiveles } from "../estado/niveles";

type Configuracion = Esquemas["ConfiguracionPC"];

/** Retardo antes de validar la configuración tras un cambio. */
export const RETARDO_VALIDACION_MS = 300;

export function PantallaConfiguracionPc() {
  const { id = "" } = useParams();
  const proyecto = useProyecto(id);
  const servidor = useConfiguracionPc(id);
  const { configuracion, eleccion, editarConfiguracion } = useBorradorAnalisis(id);

  // Borrador inicial: la del servidor (guardada o plantilla) con la prueba elegida en la recomendación.
  useEffect(() => {
    if (configuracion || !servidor.data) return;
    editarConfiguracion({ ...servidor.data.configuracion, ...(eleccion ?? {}) });
  }, [configuracion, servidor.data, eleccion, editarConfiguracion]);

  if (proyecto.isPending || servidor.isPending) return <Center><Loader /></Center>;
  if (proyecto.error || servidor.error) return <MensajeError error={proyecto.error ?? servidor.error} />;
  if (servidor.data === null) {
    return <Alert color="orange">Para configurar PC primero se necesita una preparación vigente.</Alert>;
  }
  if (!configuracion) return <Center><Loader /></Center>;
  return (
    <EditorConfiguracion
      key={id}
      proyecto={proyecto.data}
      inicial={configuracion}
      guardada={servidor.data.guardada ? servidor.data.configuracion : null}
      alCambiar={editarConfiguracion}
    />
  );
}

function EditorConfiguracion({ proyecto, inicial, guardada, alCambiar }: {
  proyecto: Esquemas["Proyecto"];
  inicial: Configuracion;
  guardada: Configuracion | null;
  alCambiar: (c: Configuracion) => void;
}) {
  const id = proyecto.id;
  const objetivo = proyecto.objetivo ?? "";
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const { confirmar, modal } = useConfirmarInvalidacion();
  const [niveles, despachar] = useReducer(reducirNiveles, inicial, (c) => crearEstado(c.niveles, c.nombres_niveles));
  const [resto, setResto] = useState<Configuracion>(inicial);

  const configuracion = useMemo<Configuracion>(() => ({ ...resto, ...aConfiguracion(niveles) }), [resto, niveles]);
  useEffect(() => alCambiar(configuracion), [configuracion, alCambiar]);

  const [aValidar] = useDebouncedValue(configuracion, RETARDO_VALIDACION_MS);
  const validacion = useValidacionConfiguracion(id, aValidar);

  const restablecer = useMutation({
    mutationFn: () =>
      datos(cliente.GET("/proyectos/{proyecto_id}/configuracion-pc/plantilla", { params: { path: { proyecto_id: id } } })),
    onSuccess: (plantilla) => despachar({ tipo: "restablecer", niveles: plantilla.niveles }),
  });

  const guardar = useMutation({
    mutationFn: async (valor: Configuracion) => {
      if (!(await confirmar(etapasQueSeDesactualizan(proyecto, "configuracion_pc")))) return false;
      await datos(
        cliente.PUT("/proyectos/{proyecto_id}/configuracion-pc", { params: { path: { proyecto_id: id } }, body: valor }),
      );
      return true;
    },
    onSuccess: async (hecho) => {
      if (!hecho) return;
      notifications.show({ color: "green", message: "Configuración guardada." });
      await consultas.invalidateQueries({ queryKey: claves.proyecto(id) });
      await consultas.invalidateQueries({ queryKey: claves.proyectos, exact: true });
    },
  });

  // Errores por campo: los del último guardado o, si no, los de la validación en vivo.
  const errores: Record<string, string> = useMemo(() => {
    if (guardar.error instanceof ErrorApi) return guardar.error.porCampo;
    if (validacion.error instanceof ErrorApi) return validacion.error.porCampo;
    const resultado: Record<string, string> = {};
    for (const e of validacion.data?.errores ?? []) resultado[e.campo] ??= e.mensaje;
    return resultado;
  }, [guardar.error, validacion.error, validacion.data]);
  const erroresValidacion = validacion.data?.errores ?? [];
  const advertencias = validacion.data?.advertencias ?? [];
  const sinGuardar = !guardada || JSON.stringify(guardada) !== JSON.stringify(configuracion);
  const vigente = estadoEtapa(proyecto, "configuracion_pc") === "vigente";
  const variables = niveles.niveles.flatMap((n) => n.variables).filter((v) => v !== objetivo);
  const cambiar = (cambio: Partial<Configuracion>) => {
    guardar.reset();
    setResto((r) => ({ ...r, ...cambio }));
  };

  return (
    <Stack>
      {modal}
      <Etapas proyecto={proyecto} actual="configuracion_pc" />
      <Group justify="space-between">
        <Title order={2}>Configuración de PC</Title>
        <Group>
          <Button variant="default" onClick={() => navegar(`/proyectos/${id}/recomendacion`)}>
            Volver a la recomendación
          </Button>
          <Button
            onClick={() => guardar.mutate(configuracion)}
            loading={guardar.isPending}
            disabled={erroresValidacion.length > 0 || !sinGuardar}
          >
            Guardar configuración
          </Button>
          <Button
            rightSection={<IconArrowRight size={16} />}
            disabled={sinGuardar || !vigente}
            onClick={() => navegar(`/proyectos/${id}/analisis`)}
          >
            Continuar al análisis
          </Button>
        </Group>
      </Group>
      {sinGuardar && guardada && <Text size="sm" c="orange">Hay cambios sin guardar.</Text>}
      {guardar.error && <MensajeError error={guardar.error} titulo="No se pudo guardar la configuración" />}

      <Card withBorder>
        <Group justify="space-between" mb="xs">
          <Text fw={600}>Niveles</Text>
          <Button
            size="xs"
            variant="subtle"
            leftSection={<IconRestore size={14} />}
            loading={restablecer.isPending}
            onClick={() => {
              guardar.reset();
              restablecer.mutate();
            }}
          >
            Restablecer
          </Button>
        </Group>
        <Text size="sm" c="dimmed" mb="sm">
          Ordene las variables en niveles de izquierda a derecha: nada de un nivel posterior puede causar algo de uno
          anterior. Por ejemplo: demografía → síntomas → diagnóstico (el diagnóstico no cambia la edad). Las variables
          de un mismo nivel pueden relacionarse en cualquier sentido.
        </Text>
        <EditorNiveles
          estado={niveles}
          despachar={(accion) => {
            guardar.reset();
            despachar(accion);
          }}
          objetivo={objetivo}
          errores={errores}
        />
        {(errores["niveles"] || errores["nombres_niveles"]) && (
          <Alert color="red" mt="sm" role="alert">
            {[errores["niveles"], errores["nombres_niveles"]].filter(Boolean).join(" ")}
          </Alert>
        )}
        {erroresValidacion.length > 1 && (
          <List size="sm" c="red" mt="xs" data-testid="errores-configuracion">
            {erroresValidacion.map((e, i) => (
              <List.Item key={i}>{e.mensaje}</List.Item>
            ))}
          </List>
        )}
        {advertencias.map((a, i) => (
          <Alert key={i} color="yellow" mt="sm" title="Atención">
            {a.mensaje}
          </Alert>
        ))}
      </Card>

      <Card withBorder>
        <Text fw={600}>Variables modificables</Text>
        <Text size="sm" c="dimmed" mb="xs">
          Marque las variables sobre las que se puede actuar (p. ej. un tratamiento o un hábito). Se usan para proponer
          las variables prescriptivas: causas del objetivo que además se pueden modificar.
        </Text>
        <SimpleGrid cols={{ base: 2, sm: 3, lg: 4 }}>
          {variables.map((v) => (
            <Checkbox
              key={v}
              label={v}
              checked={resto.modificables.includes(v)}
              onChange={(e) => {
                const marcado = e.currentTarget.checked;
                cambiar({ modificables: marcado ? [...resto.modificables, v] : resto.modificables.filter((m) => m !== v) });
              }}
            />
          ))}
          <Checkbox label={`${objetivo} (objetivo)`} checked={false} disabled />
        </SimpleGrid>
        {errores["modificables"] && (
          <Text size="xs" c="red" mt="xs" role="alert">
            {errores["modificables"]}
          </Text>
        )}
      </Card>

      <Accordion variant="contained">
        <Accordion.Item value="avanzados">
          <Accordion.Control>Parámetros avanzados</Accordion.Control>
          <Accordion.Panel>
            <Text size="sm" mb="sm">
              Prueba: <b>{resto.prueba}</b> (se elige en la recomendación).
            </Text>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <NumberInput
                label="alpha"
                description="Nivel de significación de cada prueba de independencia."
                value={resto.alpha}
                min={0.001}
                max={0.5}
                step={0.01}
                decimalScale={3}
                onChange={(v) => cambiar({ alpha: Number(v) })}
                error={errores["alpha"]}
              />
              <NumberInput
                label="Corridas de bootstrap"
                description="Cuántas veces se repite PC sobre submuestras; más corridas, resultado más estable."
                value={resto.corridas_bootstrap}
                min={1}
                allowDecimal={false}
                onChange={(v) => cambiar({ corridas_bootstrap: Number(v) })}
                error={errores["corridas_bootstrap"]}
              />
              <NumberInput
                label="Fracción de submuestra"
                description="Proporción de filas de entrenamiento que usa cada corrida."
                value={resto.fraccion_submuestra}
                min={0.1}
                max={1}
                step={0.05}
                decimalScale={2}
                onChange={(v) => cambiar({ fraccion_submuestra: Number(v) })}
                error={errores["fraccion_submuestra"]}
              />
              <NumberInput
                label="Umbral de frecuencia"
                description="Fracción mínima de corridas en que debe aparecer una arista para aceptarla."
                value={resto.umbral_frecuencia}
                min={0.05}
                max={1}
                step={0.05}
                decimalScale={2}
                onChange={(v) => cambiar({ umbral_frecuencia: Number(v) })}
                error={errores["umbral_frecuencia"]}
              />
              <NumberInput
                label="max_k"
                description="Máximo de variables de condicionamiento; vacío = sin límite (más lento)."
                placeholder="Sin límite"
                value={resto.max_k ?? ""}
                min={0}
                allowDecimal={false}
                onChange={(v) => cambiar({ max_k: v === "" ? null : Number(v) })}
                error={errores["max_k"]}
              />
              <NumberInput
                label="Semilla"
                description="Misma semilla y datos, mismas submuestras y mismo resultado."
                value={resto.semilla}
                allowDecimal={false}
                onChange={(v) => cambiar({ semilla: Number(v) })}
                error={errores["semilla"]}
              />
              <Stack gap={4}>
                <Text size="sm" fw={500}>
                  Modo de ejecución
                </Text>
                <Text size="xs" c="dimmed">
                  Automático mide la primera corrida y usa varios procesos solo si compensa; no cambia el resultado.
                </Text>
                <SegmentedControl
                  value={resto.modo_ejecucion}
                  onChange={(v) => cambiar({ modo_ejecucion: v as Configuracion["modo_ejecucion"] })}
                  data={[
                    { value: "adaptativo", label: "Automático" },
                    { value: "secuencial", label: "Secuencial" },
                    { value: "paralelo", label: "Paralelo" },
                  ]}
                />
              </Stack>
              <NumberInput
                label="Procesos"
                description="Procesos en paralelo cuando se usa el modo paralelo."
                value={resto.procesos}
                min={1}
                allowDecimal={false}
                onChange={(v) => cambiar({ procesos: Number(v) })}
                error={errores["procesos"]}
              />
            </SimpleGrid>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
      {validacion.error && !(validacion.error instanceof ErrorApi) && <MensajeError error={validacion.error} />}
    </Stack>
  );
}

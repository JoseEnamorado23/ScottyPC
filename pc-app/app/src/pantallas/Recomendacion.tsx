import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Group,
  List,
  Loader,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconArrowRight } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import type { Esquemas } from "../api/cliente";
import { esFinal, useEvaluacionPrueba, useProyecto, useRecomendacion, useTrabajo } from "../api/consultas";
import { useAccionesTrabajo } from "../api/trabajos";

import { MensajeError } from "../componentes/MensajeError";
import { formatoDuracion, ProgresoTrabajo } from "../componentes/ProgresoTrabajo";
import { useBorradorAnalisis, type EleccionPrueba, type Prueba } from "../estado/borradorAnalisis";
import { trabajoDelProyecto } from "../estado/etapas";
import { formatoValor } from "../estado/textos";
import { useVigilancia } from "../estado/trabajos";

export const PRUEBAS: { value: Prueba; label: string }[] = [
  { value: "fisherz", label: "Fisher-z (fisherz)" },
  { value: "chisq", label: "Chi-cuadrado (chisq)" },
  { value: "mv_fisherz", label: "Fisher-z con faltantes (mv_fisherz)" },
  { value: "kci", label: "KCI (kci)" },
];

/** Retardo antes de evaluar la prueba elegida tras un cambio. */
export const RETARDO_EVALUACION_MS = 300;

export function Recomendacion() {
  const { id = "" } = useParams();
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const recomendacion = useRecomendacion(id);
  const trabajoId = proyecto.data ? trabajoDelProyecto(proyecto.data, "recomendacion") : null;
  const trabajo = useTrabajo(trabajoId);
  const { lanzarRecomendacion, cancelar, reanudar } = useAccionesTrabajo(id);
  const { vigilar } = useVigilancia();
  const [estimar, setEstimar] = useState(true);
  const { eleccion, elegirPrueba } = useBorradorAnalisis(id);

  useEffect(() => {
    if (trabajo.data && !esFinal(trabajo.data.estado)) vigilar(trabajo.data);
  }, [trabajo.data, vigilar]);

  const sugerida: EleccionPrueba | null = recomendacion.data
    ? { prueba: recomendacion.data.prueba as Prueba, max_k: recomendacion.data.max_k_sugerido }
    : null;
  const actual = eleccion ?? sugerida;
  const [aEvaluar] = useDebouncedValue(actual, RETARDO_EVALUACION_MS);
  const evaluacion = useEvaluacionPrueba(id, recomendacion.data ? aEvaluar : null);

  if (proyecto.isPending || recomendacion.isPending) return <Center><Loader /></Center>;
  if (proyecto.error || recomendacion.error) return <MensajeError error={proyecto.error ?? recomendacion.error} />;

  const enCurso = trabajo.data && !esFinal(trabajo.data.estado);
  const mostrarProgreso = trabajo.data && trabajo.data.estado !== "completado";
  const rec = recomendacion.data;
  const noMonotonas = rec?.diagnosticos.filter((d) => d.monotona === false) ?? [];

  return (
    <Stack>

      <Group justify="space-between">
        <Title order={2}>Recomendación de prueba</Title>
        <Group>
          <Button variant="default" onClick={() => navegar(`/proyectos/${id}/preparacion`)}>
            Volver a Preparación
          </Button>
          <Button rightSection={<IconArrowRight size={16} />} onClick={() => navegar(`/proyectos/${id}/configuracion`)}>
            Continuar a la configuración
          </Button>
        </Group>
      </Group>

      <Card withBorder>
        <Group justify="space-between" align="flex-end">
          <Switch
            label="Estimar el tiempo"
            description="Ejecuta PC un par de veces para estimar cuánto tardará el análisis (puede tardar unos minutos)."
            checked={estimar}
            onChange={(e) => setEstimar(e.currentTarget.checked)}
            disabled={!!enCurso}
          />
          <Button
            onClick={() => lanzarRecomendacion.mutate(estimar)}
            loading={lanzarRecomendacion.isPending}
            disabled={!!enCurso}
          >
            {rec ? "Volver a analizar" : "Analizar los datos y sugerir la prueba"}
          </Button>
        </Group>
        <MensajeError error={lanzarRecomendacion.error} titulo="No se pudo iniciar el análisis" />
      </Card>

      {mostrarProgreso && (
        <ProgresoTrabajo
          trabajo={trabajo.data!}
          reanudable={proyecto.data.ultimo_trabajo?.reanudable ?? false}
          alCancelar={() => cancelar.mutate(trabajo.data!.id)}
          alReanudar={() => reanudar.mutate(trabajo.data!.id)}
          cancelando={cancelar.isPending}
          reanudando={reanudar.isPending}
        />
      )}
      <MensajeError error={cancelar.error ?? reanudar.error} />

      {!rec && !enCurso && <Text c="dimmed">Todavía no hay una recomendación vigente.</Text>}
      {rec && (
        <>
          <Card withBorder>
            <Group gap="xs" mb="xs">
              <Text fw={600}>Prueba sugerida:</Text>
              <Badge size="lg">{rec.prueba}</Badge>
              {rec.discretizacion && <Text size="sm" c="dimmed">(variables continuas en {rec.discretizacion})</Text>}
            </Group>
            <Text size="sm">{rec.motivo}</Text>
          </Card>

          {noMonotonas.length > 0 && (
            <Stack gap="xs">
              <Title order={4}>Relaciones no monótonas</Title>
              <Text size="sm" c="dimmed">
                {noMonotonas[0].medida ? `${noMonotonas[0].medida[0].toUpperCase()}${noMonotonas[0].medida.slice(1)}` : "Objetivo"}{" "}
                en cada sextil de la variable: una forma de U o de ∩ es una relación que una prueba lineal puede no ver.
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
                {noMonotonas.map((d) => (
                  <GraficoSextiles key={d.nombre} diagnostico={d} />
                ))}
              </SimpleGrid>
            </Stack>
          )}

          <Card withBorder>
            <Text fw={600} mb="xs">
              Tiempo estimado
            </Text>
            {rec.tiempo_estimado_bootstrap_s === null && !rec.nota_tiempo ? (
              <Text size="sm" c="dimmed">No se estimó el tiempo.</Text>
            ) : (
              <Stack gap={4}>
                {rec.tiempo_estimado_bootstrap_s !== null && (
                  <Text size="sm">Sin max_k: {formatoDuracion(rec.tiempo_estimado_bootstrap_s)}</Text>
                )}
                {rec.max_k_sugerido !== null && (
                  <Text size="sm">
                    Con max_k = {rec.max_k_sugerido}: {formatoDuracion(rec.tiempo_estimado_bootstrap_max_k_s)}
                  </Text>
                )}
                {rec.nota_tiempo && <Text size="sm" c="dimmed">{rec.nota_tiempo}</Text>}
              </Stack>
            )}
          </Card>

          <Card withBorder>
            <Text fw={600} mb="xs">
              Alternativas
            </Text>
            <Table fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Prueba</Table.Th>
                  <Table.Th>Ventajas</Table.Th>
                  <Table.Th>Desventajas</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rec.alternativas.map((a) => (
                  <Table.Tr key={a.prueba}>
                    <Table.Td>{a.prueba}</Table.Td>
                    <Table.Td>{a.ventajas}</Table.Td>
                    <Table.Td>{a.desventajas}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>

          {actual && (
            <ElegirPrueba
              eleccion={actual}
              sugerida={sugerida!}
              evaluacion={evaluacion.data}
              errorEvaluacion={evaluacion.error}
              alElegir={elegirPrueba}
            />
          )}
        </>
      )}
    </Stack>
  );
}

function ElegirPrueba({ eleccion, sugerida, evaluacion, errorEvaluacion, alElegir }: {
  eleccion: EleccionPrueba;
  sugerida: EleccionPrueba;
  evaluacion: Esquemas["EvaluacionEleccion"] | undefined;
  errorEvaluacion: unknown;
  alElegir: (e: EleccionPrueba) => void;
}) {
  const esSugerida = eleccion.prueba === sugerida.prueba && eleccion.max_k === sugerida.max_k;
  const notas = evaluacion?.advertencias.filter((a) => a.nivel !== "advertencia") ?? [];
  const campo = (nombre: string) =>
    evaluacion?.advertencias.filter((a) => a.campo === nombre && a.nivel === "advertencia").map((a) => a.mensaje).join(" ") || undefined;
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <Text fw={600}>Prueba para el análisis</Text>
        {!esSugerida && (
          <Button size="xs" variant="subtle" onClick={() => alElegir(sugerida)}>
            Usar la sugerida
          </Button>
        )}
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Select
          label="Prueba"
          data={PRUEBAS}
          value={eleccion.prueba}
          allowDeselect={false}
          onChange={(prueba) => prueba && alElegir({ ...eleccion, prueba: prueba as Prueba })}
          error={campo("prueba")}
        />
        <NumberInput
          label="max_k"
          description="Máximo de variables de condicionamiento; vacío = sin límite."
          placeholder="Sin límite"
          min={0}
          allowDecimal={false}
          value={eleccion.max_k ?? ""}
          onChange={(valor) => alElegir({ ...eleccion, max_k: valor === "" ? null : Number(valor) })}
          error={campo("max_k")}
        />
      </SimpleGrid>
      {evaluacion?.tiempo_estimado_s != null && (
        <Text size="sm" mt="xs">
          Tiempo estimado con esta elección: {formatoDuracion(evaluacion.tiempo_estimado_s)}
        </Text>
      )}
      {/* Las advertencias van junto a su campo; aquí, las notas informativas. */}
      {notas.length > 0 && (
        <List size="sm" mt="xs" data-testid="advertencias-eleccion">
          {notas.map((a) => (
            <List.Item key={a.codigo}>
              <Text span size="sm" c="dimmed">
                {a.mensaje}
              </Text>
            </List.Item>
          ))}
        </List>
      )}
      {errorEvaluacion != null && <MensajeError error={errorEvaluacion} />}
      <Text size="xs" c="dimmed" mt="xs">
        La elección se aplica a la configuración de PC en el siguiente paso.
      </Text>
    </Card>
  );
}

/** Tasa (o media) del objetivo por sextil de una variable no monótona. */
export function GraficoSextiles({ diagnostico }: { diagnostico: Esquemas["DiagnosticoVariable"] }) {
  const valores = diagnostico.valores_por_intervalo;
  const limites = diagnostico.limites_intervalos;
  const minimo = Math.min(...valores);
  const maximo = Math.max(...valores);
  const rango = maximo - minimo || 1;
  const conLimites = limites.length === valores.length + 1;
  return (
    <Card withBorder padding="sm" data-testid={`sextiles-${diagnostico.nombre}`}>
      <Text fw={500} size="sm" truncate>
        {diagnostico.nombre}
      </Text>
      <Group gap={3} align="flex-end" h={90} wrap="nowrap" mt="xs">
        {valores.map((v, i) => (
          <Tooltip
            key={i}
            label={`${conLimites ? `${formatoValor(limites[i])} – ${formatoValor(limites[i + 1])}` : `Sextil ${i + 1}`}: ${formatoValor(v)} (${formatoValor(diagnostico.filas_por_intervalo[i])} filas)`}
          >
            <Box style={{ flex: 1 }} h={`${15 + (85 * (v - minimo)) / rango}%`} bg="grape.6" aria-label={`Sextil ${i + 1}: ${formatoValor(v)}`} />
          </Tooltip>
        ))}
      </Group>
      <Group justify="space-between" mt={4}>
        <Text size="xs" c="dimmed">
          bajo
        </Text>
        <Text size="xs" c="dimmed">
          alto
        </Text>
      </Group>
      {diagnostico.motivo && (
        <Text size="xs" c="dimmed" mt={4}>
          {diagnostico.motivo}
        </Text>
      )}
      {!conLimites && valores.length === 0 && <Alert color="gray">Sin datos por intervalo.</Alert>}
    </Card>
  );
}

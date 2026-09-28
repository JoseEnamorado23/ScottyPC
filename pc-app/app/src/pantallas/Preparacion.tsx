import {
  Alert,
  Button,
  Card,
  Center,
  Group,
  List,
  Loader,
  NumberInput,
  Radio,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IconArrowRight } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { datos, ErrorApi, type Esquemas } from "../api/cliente";
import { claves, useEstadoPreparacion, useProyecto } from "../api/consultas";
import { useApi } from "../api/contexto";
import { useConfirmarInvalidacion } from "../componentes/ConfirmarInvalidacion";
import { Etapas } from "../componentes/Etapas";
import { MensajeError } from "../componentes/MensajeError";
import { etapasQueSeDesactualizan } from "../estado/etapas";
import { formatoValor } from "../estado/textos";

type Separacion = Esquemas["ConfiguracionSeparacion"];
type Resumen = Esquemas["ResumenPreparacion"];

const TIPOS_COLUMNA: Record<string, string> = {
  continua: "Continua",
  binaria: "Binaria",
  ordinal: "Ordinal",
  one_hot: "One-hot",
  indicador: "Indicador de medición",
  objetivo: "Objetivo",
};

const legible = (texto: string) => texto.replace(/_/g, " ");

export function Preparacion() {
  const { id = "" } = useParams();
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const navegar = useNavigate();
  const proyecto = useProyecto(id);
  const estado = useEstadoPreparacion(id);
  const [separacion, setSeparacion] = useState<Separacion | null>(null);
  const { confirmar, modal } = useConfirmarInvalidacion();

  useEffect(() => {
    if (estado.data && separacion === null) setSeparacion(estado.data.separacion);
  }, [estado.data, separacion]);

  const preparar = useMutation({
    mutationFn: async (valor: Separacion) => {
      if (!(await confirmar(etapasQueSeDesactualizan(proyecto.data!, "preparacion")))) return null;
      return datos(
        cliente.POST("/proyectos/{proyecto_id}/preparar", {
          params: { path: { proyecto_id: id } },
          body: { separacion: valor },
        }),
      );
    },
    onSuccess: async (resumen) => {
      if (!resumen) return;
      notifications.show({ color: "green", message: "Datos preparados." });
      await consultas.invalidateQueries({ queryKey: claves.proyecto(id) });
      await consultas.invalidateQueries({ queryKey: claves.proyectos, exact: true });
    },
  });
  const errores = preparar.error instanceof ErrorApi ? preparar.error.porCampo : {};
  const errorDe = (campo: string) => errores[`separacion.${campo}`];

  if (proyecto.isPending || estado.isPending || !separacion) return <Center><Loader /></Center>;
  if (proyecto.error || estado.error) return <MensajeError error={proyecto.error ?? estado.error} />;

  const fechas = estado.data.columnas_fecha_disponibles;
  const resumen = estado.data.vigente ? estado.data.resumen : null;
  const cambiar = (cambio: Partial<Separacion>) => setSeparacion({ ...separacion, ...cambio });
  const temporal = separacion.tipo === "temporal";
  const porCorte = temporal && separacion.corte != null;

  return (
    <Stack>
      {modal}
      <Etapas proyecto={proyecto.data} actual="preparacion" />
      <Group justify="space-between">
        <Title order={2}>Preparación</Title>
        <Group>
          <Button variant="default" onClick={() => navegar(`/proyectos/${id}/decisiones`)}>
            Volver a Decisiones
          </Button>
          <Button
            rightSection={<IconArrowRight size={16} />}
            disabled={!resumen || resumen.limite_columnas.estado === "bloqueado"}
            onClick={() => navegar(`/proyectos/${id}/recomendacion`)}
          >
            Continuar a la recomendación
          </Button>
        </Group>
      </Group>

      <Card withBorder>
        <Text fw={600} mb="xs">
          Separación en entrenamiento y test
        </Text>
        <Stack>
          <SegmentedControl
            value={separacion.tipo}
            onChange={(tipo) =>
              cambiar(
                tipo === "temporal"
                  ? { tipo, columna_fecha: separacion.columna_fecha ?? fechas[0] ?? null }
                  : { tipo, columna_fecha: null, corte: null },
              )
            }
            data={[
              { value: "estratificada", label: "Estratificada" },
              { value: "temporal", label: "Temporal", disabled: fechas.length === 0 },
            ]}
            aria-label="Tipo de separación"
          />
          {fechas.length === 0 && (
            <Text size="xs" c="dimmed">
              La separación temporal necesita una columna de fecha detectada en la revisión.
            </Text>
          )}
          {!temporal && (
            <Text size="sm" c="dimmed">
              Reparte las filas al azar manteniendo la proporción de cada clase del objetivo en ambos conjuntos.
            </Text>
          )}
          {temporal && (
            <>
              <Select
                label="Columna de fecha"
                data={fechas}
                value={separacion.columna_fecha ?? null}
                onChange={(columna_fecha) => cambiar({ columna_fecha })}
                error={errorDe("columna_fecha")}
                allowDeselect={false}
              />
              <Radio.Group
                label="Dónde cortar"
                value={porCorte ? "corte" : "proporcion"}
                onChange={(modo) => cambiar({ corte: modo === "corte" ? separacion.corte ?? "" : null })}
              >
                <Group mt={4}>
                  <Radio value="corte" label="En una fecha de corte" />
                  <Radio value="proporcion" label="Por proporción cronológica" />
                </Group>
              </Radio.Group>
              {porCorte && (
                <DatePickerInput
                  label="Fecha de corte"
                  description="Entrenamiento: fechas anteriores al corte; test: el corte y posteriores."
                  placeholder="Elija una fecha"
                  valueFormat="DD/MM/YYYY"
                  value={separacion.corte || null}
                  onChange={(corte) => cambiar({ corte: corte ?? "" })}
                  error={errorDe("corte")}
                  maw={280}
                />
              )}
            </>
          )}
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            {(!temporal || !porCorte) && (
              <NumberInput
                label={temporal ? "Proporción de test (las fechas más recientes)" : "Proporción de test"}
                suffix=" %"
                min={5}
                max={95}
                step={5}
                value={Math.round(separacion.proporcion_test * 100)}
                onChange={(valor) => cambiar({ proporcion_test: Number(valor) / 100 })}
                error={errorDe("proporcion_test")}
              />
            )}
            {!temporal && (
              <NumberInput
                label="Semilla"
                description="Misma semilla, misma separación."
                value={separacion.semilla}
                onChange={(valor) => cambiar({ semilla: Number(valor) })}
                error={errorDe("semilla")}
                allowDecimal={false}
              />
            )}
          </SimpleGrid>
          <Group>
            <Button loading={preparar.isPending} onClick={() => preparar.mutate(separacion)}>
              Preparar datos
            </Button>
          </Group>
          {preparar.error && !Object.keys(errores).length && (
            <MensajeError error={preparar.error} titulo="No se pudieron preparar los datos" />
          )}
          {preparar.error && Object.keys(errores).length > 0 && (
            <Text size="sm" c="red">
              {preparar.error.message}
            </Text>
          )}
        </Stack>
      </Card>

      {!resumen && estado.data.resumen === null && (
        <Text c="dimmed">Todavía no hay una preparación vigente: elija la separación y pulse «Preparar datos».</Text>
      )}
      {resumen && <ResumenPreparacion resumen={resumen} alVolver={() => navegar(`/proyectos/${id}/decisiones`)} />}
    </Stack>
  );
}

function ResumenPreparacion({ resumen, alVolver }: { resumen: Resumen; alVolver: () => void }) {
  const limite = resumen.limite_columnas;
  const faltantes = Object.entries(resumen.faltantes_restantes);
  const aplicada = resumen.separacion as { tipo: string; columna_fecha?: string; corte?: string };
  return (
    <Stack>
      {limite.estado !== "ok" && (
        <Alert
          color={limite.estado === "bloqueado" ? "red" : "yellow"}
          title={limite.estado === "bloqueado" ? "Demasiadas columnas para PC" : "PC será lento"}
          role={limite.estado === "bloqueado" ? "alert" : undefined}
        >
          <Text size="sm">{limite.mensaje}</Text>
          <Button size="xs" mt="xs" variant="light" color={limite.estado === "bloqueado" ? "red" : "yellow"} onClick={alVolver}>
            Volver a Decisiones
          </Button>
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <ConjuntoCard titulo="Entrenamiento" filas={resumen.filas_train} distribucion={resumen.distribucion_objetivo.train} />
        <ConjuntoCard titulo="Test" filas={resumen.filas_test} distribucion={resumen.distribucion_objetivo.test} />
      </SimpleGrid>
      <Text size="sm" c="dimmed">
        Separación aplicada: {aplicada.tipo}
        {aplicada.tipo === "temporal" && ` por «${aplicada.columna_fecha}», corte ${aplicada.corte}`}.
      </Text>

      {faltantes.length > 0 && (
        <Alert color="blue" title="Faltantes sin imputar">
          <Text size="sm">
            Quedan faltantes en el entrenamiento; obligan a usar la prueba mv_fisherz (las demás no los admiten). Si
            prefiere otra prueba, vuelva a Decisiones para imputarlos.
          </Text>
          <List size="sm" mt="xs">
            {faltantes.map(([columna, n]) => (
              <List.Item key={columna}>
                {columna}: {formatoValor(n)}
              </List.Item>
            ))}
          </List>
        </Alert>
      )}
      {resumen.advertencias.length > 0 && (
        <Alert color="yellow" title="Advertencias">
          <List size="sm">
            {resumen.advertencias.map((a, i) => (
              <List.Item key={i}>{a}</List.Item>
            ))}
          </List>
        </Alert>
      )}

      <Card withBorder>
        <Text fw={600} mb="xs">
          Columnas finales ({limite.columnas})
        </Text>
        <Table fz="sm" striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Columna</Table.Th>
              <Table.Th>Tipo</Table.Th>
              <Table.Th>Transformaciones</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {resumen.columnas.map((c) => (
              <Table.Tr key={c.nombre}>
                <Table.Td>{c.nombre}</Table.Td>
                <Table.Td>{TIPOS_COLUMNA[c.tipo_final] ?? c.tipo_final}</Table.Td>
                <Table.Td>{c.transformaciones.length ? c.transformaciones.map(legible).join(", ") : "—"}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  );
}

function ConjuntoCard({ titulo, filas, distribucion }: {
  titulo: string;
  filas: number;
  distribucion: Esquemas["DistribucionObjetivo"];
}) {
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <Text fw={600}>{titulo}</Text>
        <Text>{formatoValor(filas)} filas</Text>
      </Group>
      {distribucion.tipo === "clases" ? (
        <Stack gap={4}>
          {distribucion.clases.map((c) => (
            <Group key={String(c.valor)} gap="xs" wrap="nowrap">
              <Text size="sm" w={80}>
                {String(c.valor)}
              </Text>
              <div style={{ flex: 1, background: "var(--mantine-color-gray-1)" }}>
                <div style={{ height: 12, width: `${c.porcentaje}%`, background: "var(--mantine-color-blue-6)" }} />
              </div>
              <Text size="sm" w={120} ta="right">
                {formatoValor(c.conteo)} ({formatoValor(c.porcentaje)} %)
              </Text>
            </Group>
          ))}
        </Stack>
      ) : (
        <Text size="sm">
          Media {formatoValor(distribucion.media)} · mediana {formatoValor(distribucion.mediana)} · rango{" "}
          {formatoValor(distribucion.minimo)} – {formatoValor(distribucion.maximo)}
        </Text>
      )}
    </Card>
  );
}

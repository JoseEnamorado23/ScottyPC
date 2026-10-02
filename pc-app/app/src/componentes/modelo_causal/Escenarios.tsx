// Explorador de escenarios («¿qué pasa si…?»): se elige un caso (fila de test o valores
// propios), se desplaza o fija cada ancestro del objetivo en unidades originales y se ve la
// probabilidad (o el valor) antes y después, con la propagación por el grafo.
import {
  Alert, Badge, Button, Card, Grid, Group, NumberInput, Paper, SegmentedControl, Select, Stack, Table, Text, Title,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconAlertTriangle, IconArrowRight, IconRefresh } from "@tabler/icons-react";
import { useEffect, useMemo, useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { useCasosModelo, useEscenario } from "../../api/modeloCausal";
import {
  aIntervenciones, cambio, fueraDeRango, modosDe, numero, porcentaje, textoValor,
  type Intervencion, type Intervenciones, type ModoIntervencion,
} from "../../estado/modeloCausal";
import type { VarianteEscenario } from "../../estado/prescripcion";
import { MensajeError } from "../MensajeError";
import { GrafoPropagacion } from "./GrafoPropagacion";

type Vista = Esquemas["ModeloCausal"];
type Control = Esquemas["ControlVariable"];
type CasoTest = Esquemas["CasoTest"];

export const RETARDO_ESCENARIO_MS = 300;
const SIN_INTERVENCION: Intervencion = { modo: "ninguna", valor: null };
const NOMBRE_MODO: Record<ModoIntervencion, string> = { ninguna: "Sin cambio", desplazar: "Desplazar", fijar: "Fijar" };

const opcionesCategorias = (control: Control) => control.categorias.map((c) => ({ value: String(c), label: String(c) }));

/** Valor de una categoría con su tipo original (el Select trabaja con textos). */
const categoriaOriginal = (control: Control, texto: string | null) =>
  texto === null ? null : (control.categorias.find((c) => String(c) === texto) ?? texto);

interface PropsControl {
  control: Control;
  valorCaso: unknown;
  intervencion: Intervencion;
  extrapolado: boolean;
  alCambiar: (i: Intervencion) => void;
}

function FilaControl({ control, valorCaso, intervencion, extrapolado, alCambiar }: PropsControl) {
  const numerico = control.control === "numerica";
  const conCategorias = !numerico && (control.control !== "ordinal" || intervencion.modo === "fijar");
  const fuera = extrapolado || fueraDeRango(control, valorCaso, intervencion);
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={500}>
          {control.nombre}
        </Text>
        <Text size="xs" c="dimmed">
          {control.rol === "raiz" ? "raíz" : "intermedia"}
          {numerico && control.minimo !== null && ` · train: ${numero(control.minimo, 2)} – ${numero(control.maximo, 2)}`}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{textoValor(valorCaso)}</Text>
      </Table.Td>
      <Table.Td>
        <SegmentedControl
          size="xs"
          aria-label={`Intervención en ${control.nombre}`}
          value={intervencion.modo}
          onChange={(modo) => alCambiar({ modo: modo as ModoIntervencion, valor: null })}
          data={modosDe(control).map((m) => ({ value: m, label: NOMBRE_MODO[m] }))}
        />
      </Table.Td>
      <Table.Td>
        {intervencion.modo === "ninguna" ? null : conCategorias ? (
          <Select
            size="xs"
            w={150}
            aria-label={`Valor de ${control.nombre}`}
            placeholder="Elija"
            data={opcionesCategorias(control)}
            value={intervencion.valor === null ? null : String(intervencion.valor)}
            onChange={(v) => alCambiar({ ...intervencion, valor: categoriaOriginal(control, v) as string | number | null })}
          />
        ) : (
          <NumberInput
            size="xs"
            w={150}
            aria-label={`Valor de ${control.nombre}`}
            placeholder={intervencion.modo === "desplazar" ? "+ / − cantidad" : "valor"}
            decimalSeparator=","
            value={typeof intervencion.valor === "number" ? intervencion.valor : ""}
            onChange={(v) => alCambiar({ ...intervencion, valor: typeof v === "number" ? v : null })}
          />
        )}
      </Table.Td>
      <Table.Td>
        {fuera && (
          <Badge color="orange" variant="light" leftSection={<IconAlertTriangle size={12} />}>
            extrapolación
          </Badge>
        )}
      </Table.Td>
    </Table.Tr>
  );
}

interface Props {
  proyectoId: string;
  vista: Vista;
  /** Escenario precargado (p. ej. una prescripción que se quiere ajustar a mano). */
  inicial?: VarianteEscenario | null;
}

export function ExploradorEscenarios({ proyectoId, vista, inicial = null }: Props) {
  const { modelo, controles } = vista;
  const [fuente, setFuente] = useState<"test" | "propio">("test");
  const [pagina, setPagina] = useState(1);
  const casos = useCasosModelo(proyectoId, pagina, true);
  const [fila, setFila] = useState<CasoTest | null>(
    inicial?.indice_test != null ? { indice: inicial.indice_test, valores: {}, objetivo: null } : null,
  );
  const [propios, setPropios] = useState<Record<string, unknown>>({});
  const [intervenciones, setIntervenciones] = useState<Intervenciones>(inicial?.intervenciones ?? {});
  const [diferidas] = useDebouncedValue(intervenciones, RETARDO_ESCENARIO_MS);

  // Primer caso por defecto: la primera fila de test.
  useEffect(() => {
    if (!casos.data?.filas.length) return;
    if (!fila) setFila(casos.data.filas[0]);
    // Un caso precargado solo trae el índice: si está en la página, se completan sus valores.
    else if (!Object.keys(fila.valores).length) {
      const completa = casos.data.filas.find((c) => c.indice === fila.indice);
      if (completa) setFila(completa);
    }
  }, [casos.data, fila]);

  const valoresCaso: Record<string, unknown> = fuente === "test" ? (fila?.valores ?? {}) : propios;
  const solicitud = useMemo(() => {
    if (fuente === "test" && !fila) return null;
    const caso = fuente === "test" ? { indice_test: fila!.indice } : { valores: propios };
    return { caso, intervenciones: aIntervenciones(diferidas) };
  }, [fuente, fila, propios, diferidas]);
  const escenario = useEscenario(proyectoId, solicitud);
  const r = escenario.data ?? null;
  const medida = r?.medida ?? (modelo.tipo_objetivo === "binario" ? "probabilidad" : "valor");
  const formato = (v: number) => (medida === "probabilidad" ? porcentaje(v) : numero(v));
  const extrapoladas = new Set((r?.valores ?? []).filter((v) => v.extrapolacion).flatMap((v) => [v.variable, v.grupo ?? ""]));
  const clasePositiva = modelo.clase_positiva?.length ? modelo.clase_positiva.join(", ") : "1";

  const pasarAPropios = () => {
    setPropios({ ...(fila?.valores ?? {}) });
    setFuente("propio");
  };

  const totalPaginas = casos.data ? Math.max(1, Math.ceil(casos.data.total / casos.data.por_pagina)) : 1;
  return (
    <Stack data-testid="explorador">
      <Card withBorder>
        <Stack gap="xs">
          <Group justify="space-between">
            <SegmentedControl
              value={fuente}
              onChange={(v) => (v === "propio" ? pasarAPropios() : setFuente("test"))}
              data={[
                { value: "test", label: "Fila de test" },
                { value: "propio", label: "Valores propios" },
              ]}
            />
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconRefresh size={14} />}
              onClick={() => setIntervenciones({})}
              disabled={aIntervenciones(intervenciones).length === 0}
            >
              Quitar intervenciones
            </Button>
          </Group>
          {fuente === "test" ? (
            <Group align="flex-end">
              <Select
                label="Caso"
                w={360}
                searchable
                aria-label="Fila de test"
                data={(casos.data?.filas ?? []).map((c) => ({
                  value: String(c.indice),
                  label: `Fila ${c.indice} · ${modelo.objetivo} observado: ${textoValor(c.objetivo)}`,
                }))}
                value={fila ? String(fila.indice) : null}
                onChange={(v) => setFila(casos.data?.filas.find((c) => String(c.indice) === v) ?? null)}
              />
              <Group gap={4}>
                <Button size="xs" variant="default" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>
                  Anteriores
                </Button>
                <Text size="xs" c="dimmed">
                  {pagina} / {totalPaginas} ({casos.data?.total ?? 0} filas de test)
                </Text>
                <Button size="xs" variant="default" disabled={pagina >= totalPaginas} onClick={() => setPagina(pagina + 1)}>
                  Siguientes
                </Button>
              </Group>
            </Group>
          ) : (
            <Grid>
              {controles.map((c) => (
                <Grid.Col key={c.nombre} span={{ base: 12, sm: 6, md: 4 }}>
                  {c.control === "numerica" ? (
                    <NumberInput
                      size="xs"
                      label={c.nombre}
                      decimalSeparator=","
                      value={typeof propios[c.nombre] === "number" ? (propios[c.nombre] as number) : ""}
                      onChange={(v) => setPropios({ ...propios, [c.nombre]: typeof v === "number" ? v : null })}
                    />
                  ) : (
                    <Select
                      size="xs"
                      label={c.nombre}
                      data={opcionesCategorias(c)}
                      value={propios[c.nombre] === null || propios[c.nombre] === undefined ? null : String(propios[c.nombre])}
                      onChange={(v) => setPropios({ ...propios, [c.nombre]: categoriaOriginal(c, v) })}
                    />
                  )}
                </Grid.Col>
              ))}
            </Grid>
          )}
          <MensajeError error={casos.error} />
        </Stack>
      </Card>

      <Table.ScrollContainer minWidth={640}>
        <Table verticalSpacing={6} data-testid="controles-escenario">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Ancestro del objetivo</Table.Th>
              <Table.Th>Valor del caso</Table.Th>
              <Table.Th>Intervención</Table.Th>
              <Table.Th>Valor (unidades originales)</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {controles.map((c) => (
              <FilaControl
                key={c.nombre}
                control={c}
                valorCaso={valoresCaso[c.nombre]}
                intervencion={intervenciones[c.nombre] ?? SIN_INTERVENCION}
                extrapolado={extrapoladas.has(c.nombre)}
                alCambiar={(i) => setIntervenciones({ ...intervenciones, [c.nombre]: i })}
              />
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      <MensajeError error={escenario.error} titulo="No se pudo calcular el escenario" />
      {r && (
        <Grid>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Paper withBorder p="md" data-testid="resultado-escenario">
              <Text size="sm" c="dimmed">
                {medida === "probabilidad" ? `Probabilidad de ${modelo.objetivo} = ${clasePositiva}` : `Valor esperado de ${modelo.objetivo}`}
              </Text>
              <Group gap="xs" align="center" mt={4}>
                <Title order={3}>{formato(r.antes)}</Title>
                <IconArrowRight size={20} />
                <Title order={3} data-testid="despues">
                  {formato(r.despues)}
                </Title>
              </Group>
              <Text size="sm" fw={600} mt={4}>
                Cambio: {cambio(r.cambio, medida)}
              </Text>
              {r.umbral_decision !== null && (
                <Text size="xs" c="dimmed" mt={4}>
                  Con el umbral {porcentaje(r.umbral_decision)}: clase {r.clase_antes} → {r.clase_despues}
                </Text>
              )}
              {r.caso.observado_objetivo !== null && r.caso.observado_objetivo !== undefined && (
                <Text size="xs" c="dimmed">
                  Observado en el caso: {textoValor(r.caso.observado_objetivo)}
                </Text>
              )}
              {r.aproximado && (
                <Badge mt="xs" variant="light" color="gray">
                  Aproximado ({r.muestras} muestras)
                </Badge>
              )}
            </Paper>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 8 }}>
            <GrafoPropagacion variables={modelo.subgrafo.variables} padres={modelo.subgrafo.padres} resultado={r} />
          </Grid.Col>
        </Grid>
      )}
      {r && r.avisos.length > 0 && (
        <Stack gap={4}>
          {r.avisos.map((a) => (
            <Alert key={a.codigo} color={a.codigo === "APROXIMADO" ? "gray" : "orange"} variant="light" py={6} icon={<IconAlertTriangle size={16} />}>
              <Text size="sm">{a.mensaje}</Text>
            </Alert>
          ))}
        </Stack>
      )}
      {r && r.traza.length > 0 && (
        <Table verticalSpacing={4} data-testid="traza">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Variable</Table.Th>
              <Table.Th ta="right">Antes</Table.Th>
              <Table.Th ta="right">Después</Table.Th>
              <Table.Th ta="right">Cambio</Table.Th>
              <Table.Th>Por culpa de</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {r.traza.map((paso) => {
              const esObjetivo = paso.variable === modelo.objetivo;
              const m = esObjetivo ? medida : "valor";
              const f = (v: number | null) => (v === null ? "—" : esObjetivo && medida === "probabilidad" ? porcentaje(v) : numero(v));
              return (
                <Table.Tr key={paso.variable}>
                  <Table.Td>{paso.variable}</Table.Td>
                  <Table.Td ta="right">{f(paso.antes)}</Table.Td>
                  <Table.Td ta="right">{f(paso.despues)}</Table.Td>
                  <Table.Td ta="right">{cambio(paso.cambio, m)}</Table.Td>
                  <Table.Td>
                    {paso.causa === "intervencion"
                      ? "intervención"
                      : paso.por_padre.map((c) => `${c.padre} (${cambio(c.contribucion, m)})`).join(", ")}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

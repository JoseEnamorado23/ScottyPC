// Paneles de la pantalla de resultados: ajuste del umbral, historial de versiones, detalle de
// una variable, advertencias, configuración y leyenda del grafo.
import {
  ActionIcon, Alert, Badge, Button, Card, Code, CloseButton, Group, List, Paper, SimpleGrid, Slider, Stack, Table, Text, Title, Tooltip,
} from "@mantine/core";
import { IconAlertTriangle, IconInfoCircle, IconTrash } from "@tabler/icons-react";

import type { Esquemas } from "../../api/cliente";
import {
  formatoPorcentaje, UMBRAL_BAJO, UMBRAL_MAXIMO, UMBRAL_MINIMO, type Ajuste,
} from "../../estado/ajustes";
import { CATEGORIAS, SIGNOS, caminoAlObjetivo } from "../../estado/grafo";
import { InsigniaCategoria } from "./Tablas";

type Resultado = Esquemas["ResultadoPC"];
type Version = Esquemas["VersionResultado"];

const numero = (valor: number) => valor.toLocaleString("es", { maximumFractionDigits: 6 });

const fecha = (iso: string) =>
  new Date(iso).toLocaleString("es", { dateStyle: "short", timeStyle: "short" });

// --- Ajuste -----------------------------------------------------------------------------------------

interface PropsAjuste {
  ajuste: Ajuste;
  umbralOriginal: number;
  sinGuardar: boolean;
  calculando: boolean;
  guardando: boolean;
  alCambiarUmbral: (umbral: number) => void;
  alQuitarOrientacion: (origen: string, destino: string) => void;
  alGuardar: () => void;
  alDescartar: () => void;
}

export function PanelAjuste(p: PropsAjuste) {
  return (
    <Card withBorder>
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <div>
            <Text fw={600}>Ajustar sin volver a ejecutar PC</Text>
            <Text size="sm" c="dimmed">
              Umbral de frecuencia: {formatoPorcentaje(p.ajuste.umbral)} (original: {formatoPorcentaje(p.umbralOriginal)}). Haga
              clic en una arista discontinua (sin orientar) para orientarla.
            </Text>
          </div>
          {p.sinGuardar && (
            <Group gap="xs">
              <Badge color="orange" variant="light" size="lg" data-testid="sin-guardar">
                Cambios sin guardar
              </Badge>
              <Button variant="default" onClick={p.alDescartar} disabled={p.guardando}>
                Descartar
              </Button>
              <Button onClick={p.alGuardar} loading={p.guardando} disabled={p.calculando}>
                Guardar como versión nueva
              </Button>
            </Group>
          )}
        </Group>
        <Slider
          label={(valor) => formatoPorcentaje(valor)}
          min={UMBRAL_MINIMO}
          max={UMBRAL_MAXIMO}
          step={0.01}
          value={p.ajuste.umbral}
          onChange={p.alCambiarUmbral}
          marks={[0.2, 0.4, 0.6, 0.8, 1].map((valor) => ({ value: valor, label: formatoPorcentaje(valor) }))}
          thumbLabel="Umbral de frecuencia"
          mb="lg"
        />
        {p.ajuste.umbral < UMBRAL_BAJO && (
          <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />} py="xs" data-testid="umbral-bajo">
            Umbrales bajos incluyen más aristas espurias.
          </Alert>
        )}
        {p.ajuste.orientaciones.length > 0 && (
          <div>
            <Text size="sm" fw={600}>
              Orientaciones manuales
            </Text>
            <List size="sm" spacing={4}>
              {p.ajuste.orientaciones.map((o) => (
                <List.Item key={`${o.origen}|${o.destino}`}>
                  <Group gap={6} wrap="nowrap">
                    <Text size="sm">
                      {o.origen} → {o.destino}: <Text span c="dimmed">{o.justificacion || "sin justificación"}</Text>
                    </Text>
                    <Tooltip label="Quitar la orientación manual">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="red"
                        aria-label={`Quitar la orientación ${o.origen} → ${o.destino}`}
                        onClick={() => p.alQuitarOrientacion(o.origen, o.destino)}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                </List.Item>
              ))}
            </List>
          </div>
        )}
      </Stack>
    </Card>
  );
}

// --- Versiones ---------------------------------------------------------------------------------------

export function HistorialVersiones({
  versiones, vista, alVer, cambiando,
}: { versiones: Version[]; vista: number; alVer: (version: number) => void; cambiando: boolean }) {
  return (
    <Table.ScrollContainer minWidth={640}>
      <Table data-testid="historial-versiones">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Versión</Table.Th>
            <Table.Th>Descripción</Table.Th>
            <Table.Th>Base</Table.Th>
            <Table.Th>Orientaciones manuales</Table.Th>
            <Table.Th>Fecha</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {versiones.map((v) => (
            <Table.Tr key={v.version} bg={v.version === vista ? "var(--mantine-color-blue-light)" : undefined}>
              <Table.Td>
                {v.version}
                {v.migrada && (
                  <Tooltip label="Resultado anterior a las versiones: sus cuentas se reconstruyeron al abrirlo.">
                    <Badge ml={6} size="xs" variant="outline">
                      migrada
                    </Badge>
                  </Tooltip>
                )}
              </Table.Td>
              <Table.Td>
                <Badge color={v.etiqueta === "Original" ? "blue" : "orange"} variant="light">
                  {v.etiqueta}
                </Badge>
              </Table.Td>
              <Table.Td>{v.base ?? "—"}</Table.Td>
              <Table.Td>
                {v.orientaciones_manuales.length === 0
                  ? "—"
                  : v.orientaciones_manuales.map((o) => `${o.origen} → ${o.destino}`).join("; ")}
              </Table.Td>
              <Table.Td>{fecha(v.creada_en)}</Table.Td>
              <Table.Td>
                {v.version === vista ? (
                  <Text size="sm" c="dimmed">
                    Viendo
                  </Text>
                ) : (
                  <Button size="compact-sm" variant="light" onClick={() => alVer(v.version)} disabled={cambiando}>
                    Ver versión {v.version}
                  </Button>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

// --- Variable seleccionada ------------------------------------------------------------------------------

export function PanelVariable({ resultado, variable, alCerrar }: { resultado: Resultado; variable: string; alCerrar: () => void }) {
  const objetivo = resultado.caracterizacion.objetivo;
  const datos = resultado.caracterizacion.variables.find((v) => v.variable === variable);
  return (
    <Paper withBorder p="md" data-testid="panel-variable">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Title order={4} style={{ wordBreak: "break-word" }}>
          {variable}
        </Title>
        <CloseButton aria-label="Cerrar el detalle" onClick={alCerrar} />
      </Group>
      {!datos ? (
        <Text size="sm" mt="xs">
          Es el objetivo del análisis.
        </Text>
      ) : (
        <Stack gap="xs" mt="xs">
          <InsigniaCategoria categoria={datos.categoria} />
          <div>
            <Text size="xs" c="dimmed">
              Camino
            </Text>
            <Text size="sm">{caminoAlObjetivo(datos, objetivo)}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed">
              Frecuencia con el objetivo
            </Text>
            <Text size="sm">
              {formatoPorcentaje(datos.frecuencia_con_objetivo, 1)} de las corridas
              {datos.frecuencia_con_objetivo < resultado.agregacion.umbral_frecuencia && datos.frecuencia_con_objetivo > 0
                ? " (por debajo del umbral: no hay arista directa con el objetivo)"
                : ""}
            </Text>
          </div>
          <div>
            <Text size="xs" c="dimmed">
              Grupo redundante
            </Text>
            <Text size="sm">{datos.grupo_redundante?.join(", ") ?? "Ninguno"}</Text>
          </div>
          <Text size="sm">{datos.modificable ? "Modificable (se puede intervenir)." : "No marcada como modificable."}</Text>
        </Stack>
      )}
    </Paper>
  );
}

// --- Advertencias -------------------------------------------------------------------------------------

export function ListaAvisos({ avisos }: { avisos: Esquemas["AvisoResultado"][] }) {
  if (avisos.length === 0) return <Text c="dimmed">Sin advertencias para este resultado.</Text>;
  return (
    <Stack>
      {avisos.map((aviso, i) => (
        <Alert
          key={`${aviso.codigo}-${i}`}
          color={aviso.nivel === "advertencia" ? "orange" : "blue"}
          variant="light"
          title={aviso.titulo}
          icon={aviso.nivel === "advertencia" ? <IconAlertTriangle /> : <IconInfoCircle />}
          data-codigo={aviso.codigo}
        >
          <Text size="sm">{aviso.mensaje}</Text>
          {aviso.pares.length > 0 && (
            <Table mt="xs" withTableBorder maw={520}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Par</Table.Th>
                  <Table.Th ta="right">Frecuencia</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {aviso.pares.map((par) => (
                  <Table.Tr key={`${par.variable_a}|${par.variable_b}`}>
                    <Table.Td>
                      {par.variable_a} — {par.variable_b}
                      {par.con_objetivo && (
                        <Badge ml={6} size="xs" color="orange">
                          objetivo
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td ta="right">{formatoPorcentaje(par.frecuencia, 1)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Alert>
      ))}
    </Stack>
  );
}

// --- Configuración ---------------------------------------------------------------------------------------

function TablaLineas({ lineas }: { lineas: Esquemas["LineaResumen"][] }) {
  return (
    <Table>
      <Table.Tbody>
        {lineas.map((l, i) => (
          <Table.Tr key={`${l.concepto}-${i}`}>
            <Table.Td w="40%" c="dimmed">
              {l.concepto}
            </Table.Td>
            <Table.Td>{l.detalle}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function Orientaciones({ lista }: { lista: Esquemas["OrientacionManual"][] }) {
  if (lista.length === 0) return <Text size="sm">Ninguna.</Text>;
  return (
    <List size="sm">
      {lista.map((o) => (
        <List.Item key={`${o.origen}|${o.destino}`}>
          {o.origen} → {o.destino}: <Text span c="dimmed">{o.justificacion || "sin justificación"}</Text>
        </List.Item>
      ))}
    </List>
  );
}

export function ResumenConfiguracion({
  procedencia, resultado,
}: { procedencia: Esquemas["Procedencia"]; resultado: Resultado }) {
  const c = procedencia.configuracion;
  const nombres = c.nombres_niveles ?? c.niveles.map((_, i) => `Nivel ${i + 1}`);
  const distinta = procedencia.prueba_recomendada && procedencia.prueba_recomendada !== c.prueba;
  return (
    <SimpleGrid cols={{ base: 1, lg: 2 }}>
      <Card withBorder>
        <Title order={5} mb="xs">
          Datos
        </Title>
        <TablaLineas
          lineas={[
            { concepto: "Archivo", detalle: `${procedencia.archivo ?? "—"}${procedencia.hoja ? ` (hoja ${procedencia.hoja})` : ""}` },
            { concepto: "Objetivo", detalle: `${procedencia.objetivo} (${procedencia.tipo_objetivo ?? "tipo no determinado"})` },
            { concepto: "Filas", detalle: `${procedencia.filas_train ?? "—"} de entrenamiento y ${procedencia.filas_test ?? "—"} de test` },
          ]}
        />
        <Text size="xs" c="dimmed" mt="xs">
          SHA-256: <Code style={{ wordBreak: "break-all" }}>{procedencia.sha256 ?? "—"}</Code>
        </Text>
      </Card>
      <Card withBorder>
        <Title order={5} mb="xs">
          Ajustes de la versión vista
        </Title>
        <TablaLineas
          lineas={[
            { concepto: "Versión", detalle: resultado.version === null ? "Vista previa sin guardar" : String(resultado.version) },
            { concepto: "Umbral usado", detalle: formatoPorcentaje(resultado.agregacion.umbral_frecuencia) },
            { concepto: "Umbral original", detalle: formatoPorcentaje(c.umbral_frecuencia) },
          ]}
        />
        <Text size="sm" fw={600} mt="xs">
          Orientaciones manuales aplicadas
        </Text>
        <Orientaciones lista={resultado.agregacion.orientaciones_manuales} />
      </Card>
      <Card withBorder>
        <Title order={5} mb="xs">
          Decisiones de preparación
        </Title>
        <TablaLineas lineas={procedencia.decisiones} />
        <Title order={6} mt="sm" mb={4}>
          Separación
        </Title>
        <TablaLineas lineas={procedencia.separacion} />
      </Card>
      <Card withBorder>
        <Title order={5} mb="xs">
          Configuración de PC (original)
        </Title>
        <TablaLineas
          lineas={[
            { concepto: "Prueba", detalle: c.prueba + (procedencia.prueba_recomendada ? ` (recomendada: ${procedencia.prueba_recomendada})` : "") },
            { concepto: "alpha", detalle: numero(c.alpha) },
            { concepto: "max_k", detalle: c.max_k === null || c.max_k === undefined ? "sin límite" : String(c.max_k) },
            { concepto: "Corridas de bootstrap", detalle: String(c.corridas_bootstrap) },
            { concepto: "Fracción de la submuestra", detalle: numero(c.fraccion_submuestra) },
            { concepto: "Umbral de frecuencia", detalle: formatoPorcentaje(c.umbral_frecuencia) },
            { concepto: "Semilla", detalle: String(c.semilla) },
            { concepto: "Modificables", detalle: c.modificables?.join(", ") || "ninguna" },
          ]}
        />
        {distinta && (
          <Alert color="orange" variant="light" mt="xs" py="xs">
            La prueba usada no es la recomendada.
          </Alert>
        )}
        <Title order={6} mt="sm" mb={4}>
          Niveles
        </Title>
        <TablaLineas lineas={c.niveles.map((nivel, i) => ({ concepto: nombres[i] ?? `Nivel ${i + 1}`, detalle: nivel.join(", ") }))} />
        <Title order={6} mt="sm" mb={4}>
          Orientaciones manuales de la configuración
        </Title>
        <Orientaciones lista={c.orientaciones_manuales ?? []} />
      </Card>
    </SimpleGrid>
  );
}

// --- Leyenda -------------------------------------------------------------------------------------------

function Linea({ color, estilo, flecha }: { color: string; estilo: "solid" | "dashed" | "dotted"; flecha: boolean }) {
  return (
    <svg width="34" height="10" aria-hidden>
      <line
        x1="1" y1="5" x2={flecha ? 26 : 33} y2="5" stroke={color} strokeWidth="2.5"
        strokeDasharray={estilo === "dashed" ? "6 4" : estilo === "dotted" ? "1.5 3" : undefined}
      />
      {flecha && <polygon points="26,1 33,5 26,9" fill={color} />}
    </svg>
  );
}

export function LeyendaGrafo() {
  return (
    <Group gap="md" data-testid="leyenda">
      {Object.entries(CATEGORIAS).map(([clave, c]) => (
        <Group key={clave} gap={4} wrap="nowrap">
          <span style={{ width: 14, height: 14, borderRadius: 3, background: c.color, border: "1px solid #868e96", display: "inline-block" }} />
          <Text size="xs">{c.etiqueta}</Text>
        </Group>
      ))}
      <Group gap={4} wrap="nowrap">
        <span style={{ width: 14, height: 14, borderRadius: 3, border: "3px double #212529", display: "inline-block" }} />
        <Text size="xs">Modificable (borde doble)</Text>
      </Group>
      <Group gap={4} wrap="nowrap">
        <Linea color={SIGNOS["1"].color} estilo="solid" flecha />
        <Text size="xs">Positiva</Text>
      </Group>
      <Group gap={4} wrap="nowrap">
        <Linea color={SIGNOS["-1"].color} estilo="solid" flecha />
        <Text size="xs">Negativa</Text>
      </Group>
      <Group gap={4} wrap="nowrap">
        <Linea color="#495057" estilo="dashed" flecha={false} />
        <Text size="xs">Sin orientar</Text>
      </Group>
      <Group gap={4} wrap="nowrap">
        <Linea color="#495057" estilo="dotted" flecha />
        <Text size="xs">Orientación manual</Text>
      </Group>
      <Text size="xs" c="dimmed">
        Grosor = frecuencia
      </Text>
    </Group>
  );
}

// Pestañas «Caracterización» y «Aristas» de los resultados.
import { Alert, Badge, Button, Card, Chip, Group, Select, Stack, Table, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconArrowDown, IconArrowUp, IconArrowsSort, IconSearch } from "@tabler/icons-react";
import { useMemo, useState } from "react";

import type { Esquemas } from "../../api/cliente";
import { formatoPorcentaje, formatoRho } from "../../estado/ajustes";
import { CATEGORIAS, caminoAlObjetivo, type Arista, type Categoria } from "../../estado/grafo";

type Resultado = Esquemas["ResultadoPC"];

export function InsigniaCategoria({ categoria }: { categoria: Categoria }) {
  const { etiqueta, color, texto } = CATEGORIAS[categoria];
  return (
    <Badge style={{ backgroundColor: color, color: texto }} variant="filled" radius="sm">
      {etiqueta}
    </Badge>
  );
}

// --- Caracterización ---------------------------------------------------------------------------

export function CandidatasPrescriptivas({
  caracterizacion, nota,
}: { caracterizacion: Resultado["caracterizacion"]; nota?: string }) {
  const candidatas = caracterizacion.candidatas_prescriptivas;
  const origen = nota ? (
    <Text size="xs" c="dimmed" mt={4} data-testid="origen-candidatas">
      {nota}
    </Text>
  ) : null;
  if (candidatas.length === 0) {
    return (
      <Alert color="orange" variant="light" title="Sin candidatas prescriptivas" data-testid="candidatas-prescriptivas">
        {caracterizacion.mensaje}
        {origen}
      </Alert>
    );
  }
  return (
    <Card withBorder style={{ borderLeft: "4px solid var(--mantine-color-green-7)" }} data-testid="candidatas-prescriptivas">
      <Text fw={600}>Candidatas prescriptivas</Text>
      <Text size="sm" c="dimmed" mb="xs">
        Variables modificables que son causa directa o indirecta del objetivo.
      </Text>
      <Group gap="xs">
        {candidatas.map((v) => (
          <Badge key={v} size="lg" color="green" variant="light">
            {v}
          </Badge>
        ))}
      </Group>
      {origen}
    </Card>
  );
}

const ORDEN_CATEGORIAS: Esquemas["CaracterizacionVariable"]["categoria"][] = [
  "causa_directa", "causa_indirecta", "consecuencia", "ambigua", "sin_camino",
];

export function TablaCaracterizacion({ resultado, alElegir }: { resultado: Resultado; alElegir: (variable: string) => void }) {
  const { caracterizacion } = resultado;
  const [filtro, setFiltro] = useState<string[]>(ORDEN_CATEGORIAS);
  const cuentas = useMemo(() => {
    const c: Record<string, number> = {};
    for (const v of caracterizacion.variables) c[v.categoria] = (c[v.categoria] ?? 0) + 1;
    return c;
  }, [caracterizacion]);
  const filas = caracterizacion.variables.filter((v) => filtro.includes(v.categoria));

  return (
    <Stack>
      <CandidatasPrescriptivas caracterizacion={caracterizacion} nota={resultado.nota_candidatas} />
      <Chip.Group multiple value={filtro} onChange={setFiltro}>
        <Group gap="xs" aria-label="Filtrar por categoría" role="group">
          {ORDEN_CATEGORIAS.map((categoria) => (
            <Chip key={categoria} value={categoria} size="sm">
              {CATEGORIAS[categoria].etiqueta} ({cuentas[categoria] ?? 0})
            </Chip>
          ))}
        </Group>
      </Chip.Group>
      <Table.ScrollContainer minWidth={720}>
        <Table striped highlightOnHover data-testid="tabla-caracterizacion">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Variable</Table.Th>
              <Table.Th>Categoría</Table.Th>
              <Table.Th>Camino</Table.Th>
              <Table.Th ta="right">Frecuencia con el objetivo</Table.Th>
              <Table.Th>Grupo redundante</Table.Th>
              <Table.Th>Modificable</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filas.map((v) => (
              <Table.Tr key={v.variable} onClick={() => alElegir(v.variable)} style={{ cursor: "pointer" }}>
                <Table.Td fw={500}>{v.variable}</Table.Td>
                <Table.Td>
                  <InsigniaCategoria categoria={v.categoria} />
                </Table.Td>
                <Table.Td>{caminoAlObjetivo(v, caracterizacion.objetivo)}</Table.Td>
                <Table.Td ta="right">{formatoPorcentaje(v.frecuencia_con_objetivo, 1)}</Table.Td>
                <Table.Td>{v.grupo_redundante?.join(", ") ?? "—"}</Table.Td>
                <Table.Td>{v.modificable ? "Sí" : "No"}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {filas.length === 0 && (
        <Text size="sm" c="dimmed">
          Ninguna variable con las categorías elegidas.
        </Text>
      )}
    </Stack>
  );
}

// --- Aristas ----------------------------------------------------------------------------------------

const TIPOS: Record<Arista["tipo"], string> = { dirigida: "Dirigida", sin_orientar: "Sin orientar", manual: "Manual" };

type Columna =
  | "origen" | "destino" | "tipo" | "frecuencia_total" | "frecuencia_origen_destino"
  | "frecuencia_destino_origen" | "frecuencia_sin_orientar" | "spearman";

const COLUMNAS: { clave: Columna; titulo: string; numerica?: boolean }[] = [
  { clave: "origen", titulo: "Origen" },
  { clave: "destino", titulo: "Destino" },
  { clave: "tipo", titulo: "Tipo" },
  { clave: "frecuencia_total", titulo: "Frecuencia total", numerica: true },
  { clave: "frecuencia_origen_destino", titulo: "Origen → destino", numerica: true },
  { clave: "frecuencia_destino_origen", titulo: "Destino → origen", numerica: true },
  { clave: "frecuencia_sin_orientar", titulo: "Sin orientar", numerica: true },
  { clave: "spearman", titulo: "ρ de Spearman", numerica: true },
];

export function TablaAristas({ aristas, alOrientar }: { aristas: Arista[]; alOrientar: (arista: Arista) => void }) {
  const [busqueda, setBusqueda] = useState("");
  const [tipo, setTipo] = useState<string | null>(null);
  const [orden, setOrden] = useState<{ columna: Columna; ascendente: boolean }>({ columna: "frecuencia_total", ascendente: false });

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    const filtradas = aristas.filter(
      (a) =>
        (!tipo || a.tipo === tipo) &&
        (!texto || a.origen.toLowerCase().includes(texto) || a.destino.toLowerCase().includes(texto)),
    );
    const signo = orden.ascendente ? 1 : -1;
    return [...filtradas].sort((x, y) => {
      const a = x[orden.columna];
      const b = y[orden.columna];
      if (a === b) return 0;
      if (a === null) return 1;
      if (b === null) return -1;
      return (a < b ? -1 : 1) * signo;
    });
  }, [aristas, busqueda, tipo, orden]);

  const ordenarPor = (columna: Columna) =>
    setOrden((o) => ({ columna, ascendente: o.columna === columna ? !o.ascendente : !COLUMNAS.find((c) => c.clave === columna)?.numerica }));

  return (
    <Stack>
      <Group>
        <TextInput
          placeholder="Buscar variable"
          aria-label="Buscar variable"
          leftSection={<IconSearch size={16} />}
          value={busqueda}
          onChange={(e) => setBusqueda(e.currentTarget.value)}
        />
        <Select
          aria-label="Tipo de arista"
          placeholder="Todos los tipos"
          clearable
          data={Object.entries(TIPOS).map(([value, label]) => ({ value, label }))}
          value={tipo}
          onChange={setTipo}
        />
        <Text size="sm" c="dimmed">
          {filas.length} de {aristas.length} aristas
        </Text>
      </Group>
      <Table.ScrollContainer minWidth={960}>
        <Table striped highlightOnHover data-testid="tabla-aristas">
          <Table.Thead>
            <Table.Tr>
              {COLUMNAS.map((c) => (
                <Table.Th key={c.clave} ta={c.numerica ? "right" : undefined}>
                  <UnstyledButton onClick={() => ordenarPor(c.clave)} aria-label={`Ordenar por ${c.titulo}`}>
                    <Group gap={4} wrap="nowrap" justify={c.numerica ? "flex-end" : undefined}>
                      <Text size="sm" fw={600}>
                        {c.titulo}
                      </Text>
                      {orden.columna !== c.clave ? (
                        <IconArrowsSort size={14} />
                      ) : orden.ascendente ? (
                        <IconArrowUp size={14} />
                      ) : (
                        <IconArrowDown size={14} />
                      )}
                    </Group>
                  </UnstyledButton>
                </Table.Th>
              ))}
              <Table.Th>Justificación</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filas.map((a) => (
              <Table.Tr key={`${a.origen}|${a.destino}`}>
                <Table.Td>{a.origen}</Table.Td>
                <Table.Td>{a.destino}</Table.Td>
                <Table.Td>{TIPOS[a.tipo]}</Table.Td>
                <Table.Td ta="right">{formatoPorcentaje(a.frecuencia_total, 1)}</Table.Td>
                <Table.Td ta="right">{formatoPorcentaje(a.frecuencia_origen_destino, 1)}</Table.Td>
                <Table.Td ta="right">{formatoPorcentaje(a.frecuencia_destino_origen, 1)}</Table.Td>
                <Table.Td ta="right">{formatoPorcentaje(a.frecuencia_sin_orientar, 1)}</Table.Td>
                <Table.Td ta="right">{a.spearman === null ? "—" : formatoRho(a.spearman)}</Table.Td>
                <Table.Td>{a.justificacion ?? "—"}</Table.Td>
                <Table.Td>
                  {a.tipo !== "dirigida" && (
                    <Button size="compact-xs" variant="light" onClick={() => alOrientar(a)} aria-label={`Orientar ${a.origen} — ${a.destino}`}>
                      {a.tipo === "manual" ? "Cambiar" : "Orientar"}
                    </Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {aristas.length === 0 && (
        <Text size="sm" c="dimmed">
          No se aceptó ninguna arista con este umbral.
        </Text>
      )}
    </Stack>
  );
}

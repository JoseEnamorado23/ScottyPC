// Editores de los valores concretos de las decisiones: orden ordinal, grupos de
// clases del objetivo y conversiones de unidades. Cada campo muestra el error 422
// del servidor cuya ruta le corresponde.
import { ActionIcon, Card, Group, Select, SimpleGrid, Stack, Table, Text, TextInput } from "@mantine/core";
import { IconArrowDown, IconArrowUp } from "@tabler/icons-react";

import type { Esquemas } from "../api/cliente";
import { comoNumero, type ConversionEditada, type Ediciones } from "../estado/borrador";
import { formatoValor } from "../estado/textos";

type Codificacion = Esquemas["Codificacion"];
type Conversion = Esquemas["ConversionUnidades"];
type Errores = Record<string, string>;
type Editar = (cambiar: (e: Ediciones) => Ediciones) => void;

/** Error del campo exacto o de alguno de sus subcampos (p. ej. `codificaciones.nivel.orden.2`). */
export function errorDe(errores: Errores, ruta: string): string | undefined {
  if (errores[ruta]) return errores[ruta];
  const clave = Object.keys(errores).find((c) => c.startsWith(`${ruta}.`));
  return clave ? errores[clave] : undefined;
}

export function EditorOrden({ columna, codificacion, editar, errores }: {
  columna: string;
  codificacion: Codificacion;
  editar: Editar;
  errores: Errores;
}) {
  const orden = codificacion.orden ?? [];
  const mover = (desde: number, hasta: number) => {
    const nuevo = [...orden];
    [nuevo[desde], nuevo[hasta]] = [nuevo[hasta], nuevo[desde]];
    editar((e) => ({ ...e, ordenes: { ...e.ordenes, [columna]: nuevo } }));
  };
  const error = errorDe(errores, `codificaciones.${columna}.orden`) ?? errorDe(errores, `codificaciones.${columna}`);
  return (
    <Card withBorder>
      <Text fw={600}>Orden de «{columna}»</Text>
      <Text size="xs" c="dimmed" mb="xs">
        De menor a mayor; se codifica como 0, 1, 2…
      </Text>
      <Stack gap={4}>
        {orden.map((valor, i) => (
          <Group key={String(valor)} gap="xs">
            <Text size="sm" w={24} c="dimmed">
              {i}
            </Text>
            <Text size="sm" style={{ flex: 1 }}>
              {formatoValor(valor)}
            </Text>
            <ActionIcon variant="subtle" disabled={i === 0} onClick={() => mover(i, i - 1)} aria-label={`Subir ${String(valor)}`}>
              <IconArrowUp size={14} />
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              disabled={i === orden.length - 1}
              onClick={() => mover(i, i + 1)}
              aria-label={`Bajar ${String(valor)}`}
            >
              <IconArrowDown size={14} />
            </ActionIcon>
          </Group>
        ))}
      </Stack>
      {error && (
        <Text size="xs" c="red" mt="xs" role="alert">
          {error}
        </Text>
      )}
    </Card>
  );
}

export function EditorAgrupacion({ columna, codificacion, editar, errores }: {
  columna: string;
  codificacion: Codificacion;
  editar: Editar;
  errores: Errores;
}) {
  const grupos = (codificacion.grupos ?? {}) as Record<string, number>;
  const fijar = (clase: string, grupo: number) =>
    editar((e) => ({ ...e, grupos: { ...e.grupos, [columna]: { ...grupos, [clase]: grupo } } }));
  const error = errorDe(errores, `codificaciones.${columna}.grupos`) ?? errorDe(errores, `codificaciones.${columna}`);
  return (
    <Card withBorder>
      <Text fw={600}>Agrupación de las clases de «{columna}»</Text>
      <Text size="xs" c="dimmed" mb="xs">
        El objetivo pasa a ser binario: cada clase va al grupo 0 o al 1.
      </Text>
      <Stack gap={4}>
        {Object.entries(grupos).map(([clase, grupo]) => (
          <Group key={clase} gap="xs">
            <Text size="sm" style={{ flex: 1 }}>
              {clase}
            </Text>
            <Select
              size="xs"
              w={110}
              aria-label={`Grupo de ${clase}`}
              data={[
                { value: "0", label: "Grupo 0" },
                { value: "1", label: "Grupo 1" },
              ]}
              value={String(grupo)}
              allowDeselect={false}
              onChange={(v) => v !== null && fijar(clase, Number(v))}
            />
          </Group>
        ))}
      </Stack>
      {error && (
        <Text size="xs" c="red" mt="xs" role="alert">
          {error}
        </Text>
      )}
    </Card>
  );
}

const CONDICIONES = [">", ">=", "<", "<="] as const;

function cumple(valor: number, condicion: Conversion["condicion"], umbral: number): boolean {
  switch (condicion) {
    case ">":
      return valor > umbral;
    case ">=":
      return valor >= umbral;
    case "<":
      return valor < umbral;
    case "<=":
      return valor <= umbral;
  }
}

export function EditorConversion({ indice, conversion, editada, muestras, editar, errores }: {
  indice: number;
  /** Conversión efectiva (la del núcleo con las ediciones aplicadas). */
  conversion: Conversion;
  /** Valores tal como los escribió el usuario, si los editó. */
  editada: ConversionEditada | undefined;
  /** Valores de ejemplo de la columna (vista previa del dataset). */
  muestras: unknown[];
  editar: Editar;
  errores: Errores;
}) {
  const columna = conversion.columna;
  const actual: ConversionEditada = {
    condicion: conversion.condicion,
    umbral: conversion.umbral,
    restar: conversion.restar,
    multiplicar: conversion.multiplicar,
  };
  const fijar = (cambio: Partial<ConversionEditada>) =>
    editar((e) => ({
      ...e,
      conversiones: { ...e.conversiones, [columna]: { ...(e.conversiones[columna] ?? actual), ...cambio } },
    }));
  // Se muestra lo que el usuario escribió (p. ej. «5/9»), no el número ya convertido.
  const texto = (campo: "umbral" | "restar" | "multiplicar") => String(editada?.[campo] ?? conversion[campo]);
  const error = (campo: string) => errores[`conversiones.${indice}.${campo}`];

  const umbral = comoNumero(conversion.umbral);
  const restar = comoNumero(conversion.restar);
  const multiplicar = comoNumero(conversion.multiplicar);
  const numericos = typeof umbral === "number" && typeof restar === "number" && typeof multiplicar === "number";
  const ejemplos = muestras
    .map((v) => (typeof v === "number" ? v : Number(v)))
    .filter((v) => Number.isFinite(v))
    .slice(0, 12);

  return (
    <Card withBorder>
      <Text fw={600}>Conversión de unidades de «{columna}»</Text>
      <Text size="xs" c="dimmed" mb="xs">
        Si el valor cumple la condición: nuevo = (valor − restar) × multiplicar. Admite fracciones como 5/9.
      </Text>
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Select
          label="Condición"
          data={[...CONDICIONES]}
          value={conversion.condicion}
          allowDeselect={false}
          onChange={(v) => v && fijar({ condicion: v as Conversion["condicion"] })}
          error={error("condicion")}
        />
        <TextInput label="Umbral" value={texto("umbral")} onChange={(e) => fijar({ umbral: e.currentTarget.value })} error={error("umbral")} />
        <TextInput label="Restar" value={texto("restar")} onChange={(e) => fijar({ restar: e.currentTarget.value })} error={error("restar")} />
        <TextInput
          label="Multiplicar"
          value={texto("multiplicar")}
          onChange={(e) => fijar({ multiplicar: e.currentTarget.value })}
          error={error("multiplicar")}
        />
      </SimpleGrid>
      {error("columna") && <Text size="xs" c="red" role="alert">{error("columna")}</Text>}

      <Text size="sm" fw={500} mt="sm">
        Vista previa sobre valores de ejemplo
      </Text>
      {!numericos ? (
        <Text size="xs" c="dimmed">
          Complete umbral, restar y multiplicar con números para ver la vista previa.
        </Text>
      ) : (
        <Table fz="xs" withTableBorder data-testid={`vista-conversion-${columna}`}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Valor</Table.Th>
              <Table.Th>Resultado</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {ejemplos.map((v, i) => {
              const convierte = cumple(v, conversion.condicion, umbral);
              return (
                <Table.Tr key={i}>
                  <Table.Td>{formatoValor(v)}</Table.Td>
                  <Table.Td fw={convierte ? 600 : undefined} c={convierte ? undefined : "dimmed"}>
                    {convierte ? formatoValor((v - restar) * multiplicar) : "sin cambio"}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

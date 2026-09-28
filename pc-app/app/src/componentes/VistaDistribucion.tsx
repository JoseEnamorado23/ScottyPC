import { Box, Group, Stack, Text, Tooltip } from "@mantine/core";

import type { Esquemas } from "../api/cliente";

const numero = (x: number) => x.toLocaleString("es", { maximumFractionDigits: 2 });

/** Barras horizontales por categoría o histograma de columnas numéricas. */
export function VistaDistribucion({ distribucion }: { distribucion: Esquemas["Distribucion"] }) {
  const { total, faltantes, valores_distintos: distintos } = distribucion;
  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">
        {numero(total)} filas · {numero(distintos)} valores distintos · {numero(faltantes)} faltantes
      </Text>
      {distribucion.tipo === "categorias" ? (
        <Stack gap={4}>
          {distribucion.categorias.map((c) => (
            <Group key={String(c.valor)} gap="xs" wrap="nowrap">
              <Text size="sm" w={120} truncate title={String(c.valor)}>
                {String(c.valor)}
              </Text>
              <Box style={{ flex: 1 }} bg="gray.1">
                <Box h={14} w={`${c.porcentaje}%`} bg="blue.6" />
              </Box>
              <Text size="sm" w={120} ta="right">
                {numero(c.conteo)} ({numero(c.porcentaje)} %)
              </Text>
            </Group>
          ))}
        </Stack>
      ) : (
        distribucion.histograma && <Histograma {...distribucion.histograma} />
      )}
    </Stack>
  );
}

function Histograma({ limites, conteos }: Esquemas["Histograma"]) {
  const maximo = Math.max(...conteos, 1);
  return (
    <Stack gap={2}>
      <Group gap={2} align="flex-end" h={120} wrap="nowrap">
        {conteos.map((conteo, i) => (
          <Tooltip key={i} label={`${numero(limites[i])} – ${numero(limites[i + 1])}: ${numero(conteo)}`}>
            <Box style={{ flex: 1 }} h={`${(100 * conteo) / maximo}%`} mih={conteo ? 2 : 0} bg="blue.6" />
          </Tooltip>
        ))}
      </Group>
      <Group justify="space-between">
        <Text size="xs" c="dimmed">
          {numero(limites[0])}
        </Text>
        <Text size="xs" c="dimmed">
          {numero(limites[limites.length - 1])}
        </Text>
      </Group>
    </Stack>
  );
}

// Panel de evaluación del objetivo: métricas en validación cruzada y en test (con el umbral y el
// Brier), curva de calibración y comparación con el modelo de referencia (todas las variables).
import { Alert, Badge, Grid, Group, Stack, Table, Text } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";

import type { Esquemas } from "../../api/cliente";
import { NOMBRES_METRICA, metrica, porcentaje } from "../../estado/modeloCausal";
import { GraficoCalibracion } from "./Graficos";

interface Props {
  evaluacion: Esquemas["EvaluacionModeloCausal"];
  binario: boolean;
}

export function PanelEvaluacion({ evaluacion, binario }: Props) {
  const objetivo = evaluacion.evaluacion_objetivo;
  const referencia = evaluacion.referencia;
  const metricas = binario ? ["exactitud_balanceada", "auc", "brier"] : ["r2", "rmse"];
  return (
    <Stack data-testid="panel-evaluacion">
      <Grid>
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="xs">
            {binario && (
              <Group gap="xs">
                <Badge variant="light" size="lg">
                  Umbral de decisión: {porcentaje(objetivo.umbral_decision)}
                </Badge>
                <Text size="xs" c="dimmed">
                  Elegido en validación cruzada para maximizar la exactitud balanceada (prevalencia en
                  entrenamiento: {porcentaje(objetivo.prevalencia_train)}).
                </Text>
              </Group>
            )}
            {binario && objetivo.pesos_clase && (
              <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />} py="xs">
                El objetivo se ajustó con pesos de clase: las probabilidades no están calibradas.
              </Alert>
            )}
            <Table withTableBorder verticalSpacing={4}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Métrica</Table.Th>
                  <Table.Th ta="right">Validación cruzada</Table.Th>
                  <Table.Th ta="right">Test</Table.Th>
                  <Table.Th ta="right">Referencia (CV)</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {metricas.map((m) => (
                  <Table.Tr key={m}>
                    <Table.Td>
                      {NOMBRES_METRICA[m]}
                      {m === "brier" && (
                        <Text span size="xs" c="dimmed">
                          {" "}
                          (menor es mejor)
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td ta="right">{metrica(objetivo.cv[m])}</Table.Td>
                    <Table.Td ta="right">{metrica(objetivo.test[m])}</Table.Td>
                    <Table.Td ta="right">{metrica(referencia.cv[m])}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Text size="xs" c="dimmed">
              Test se calculó una sola vez, al construir el modelo. Referencia: {referencia.familia.toLowerCase()} con las{" "}
              {referencia.variables.length} variables preparadas.
            </Text>
            {referencia.advertencia ? (
              <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />} title="Costo de la parsimonia" data-testid="costo-parsimonia">
                {referencia.advertencia}
              </Alert>
            ) : (
              <Text size="sm">
                El mecanismo del objetivo predice tan bien como el modelo de referencia: las causas directas capturan la
                información predictiva disponible.
              </Text>
            )}
          </Stack>
        </Grid.Col>
        {objetivo.calibracion && (
          <Grid.Col span={{ base: 12, md: 5 }}>
            <GraficoCalibracion cv={objetivo.calibracion.cv} test={objetivo.calibracion.test} />
          </Grid.Col>
        )}
      </Grid>
    </Stack>
  );
}

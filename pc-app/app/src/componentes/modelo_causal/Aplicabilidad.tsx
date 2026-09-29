// Lista de verificación de aplicabilidad: bloqueantes y advertencias, cada una con su
// explicación y un botón que lleva a la pantalla donde se resuelve.
import { Alert, Button, Group, Stack, Text, ThemeIcon } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck, IconCircleX } from "@tabler/icons-react";
import { useNavigate } from "react-router";

import type { Esquemas } from "../../api/cliente";

type Problema = Esquemas["ProblemaAplicabilidad"];

const DESTINOS: Record<string, { ruta: string; texto: string }> = {
  resultados: { ruta: "resultados", texto: "Ir a Resultados" },
  decisiones: { ruta: "decisiones", texto: "Ir a Decisiones" },
  preparacion: { ruta: "preparacion", texto: "Ir a Preparación" },
  analisis: { ruta: "analisis", texto: "Ir al Análisis" },
};

interface Props {
  proyectoId: string;
  problemas: Problema[];
  /** Advertencias del ajuste (sin la línea de resumen de la aplicabilidad). */
  delAjuste?: boolean;
}

export function ListaAplicabilidad({ proyectoId, problemas, delAjuste = false }: Props) {
  const navegar = useNavigate();
  const bloqueantes = problemas.filter((p) => p.severidad === "bloqueante");
  const advertencias = problemas.filter((p) => p.severidad === "advertencia");
  return (
    <Stack gap="xs" data-testid={delAjuste ? "advertencias-ajuste" : "aplicabilidad"}>
      {delAjuste ? null : bloqueantes.length === 0 ? (
        <Group gap="xs">
          <ThemeIcon color="green" variant="light" size="sm">
            <IconCircleCheck size={14} />
          </ThemeIcon>
          <Text size="sm">Sin bloqueantes: se puede construir el modelo causal.</Text>
        </Group>
      ) : (
        <Text size="sm" fw={600}>
          {bloqueantes.length === 1 ? "Un problema impide" : `${bloqueantes.length} problemas impiden`} construir el modelo:
        </Text>
      )}
      {[...bloqueantes, ...advertencias].map((p, i) => {
        const bloquea = p.severidad === "bloqueante";
        const destino = p.destino ? DESTINOS[p.destino] : undefined;
        return (
          <Alert
            key={`${p.codigo}-${i}`}
            color={bloquea ? "red" : "orange"}
            variant="light"
            icon={bloquea ? <IconCircleX size={18} /> : <IconAlertTriangle size={18} />}
            title={bloquea ? "Bloqueante" : "Advertencia"}
            py="xs"
          >
            <Stack gap={4}>
              <Text size="sm">{p.mensaje}</Text>
              <Group justify="space-between" gap="xs">
                <Text size="sm" c="dimmed">
                  {p.accion}
                </Text>
                {destino && (
                  <Button size="xs" variant="default" onClick={() => navegar(`/proyectos/${proyectoId}/${destino.ruta}`)}>
                    {destino.texto}
                  </Button>
                )}
              </Group>
            </Stack>
          </Alert>
        );
      })}
    </Stack>
  );
}

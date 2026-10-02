// Progreso de un trabajo (recomendación o análisis PC) y sus acciones: cancelar (con
// confirmación) y reanudar.
import { Alert, Badge, Button, Card, Group, Modal, Progress, SimpleGrid, Stack, Text } from "@mantine/core";
import { useState } from "react";

import type { Esquemas } from "../api/cliente";

type Trabajo = Esquemas["Trabajo"];

export function formatoDuracion(segundos: number | null | undefined): string {
  if (segundos === null || segundos === undefined) return "—";
  const s = Math.round(segundos);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${String(s % 60).padStart(2, "0")} s`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

function textoModo(detalles: Trabajo["detalles"]): string | null {
  if (!detalles) return null;
  if (detalles.modo === "midiendo") return "Midiendo cuánto tarda una corrida para elegir el modo…";
  if (detalles.modo === "paralelo") return `En paralelo con ${detalles.procesos} procesos`;
  return "Secuencial (un proceso)";
}

const EXPLICACION_CANCELAR = {
  pc: "El avance se guarda: podrá reanudar el análisis desde la última corrida guardada y el resultado será el mismo que sin interrumpir.",
  recomendacion: "La recomendación no guarda avance parcial: al reanudarla se repite desde el principio.",
  modelo_causal: "La construcción del modelo no guarda avance parcial: al reanudarla se repite con la misma configuración.",
  calibracion_mu: "La calibración de μ no guarda avance parcial: al reanudarla se repite desde el principio.",
  lote_prescripcion: "El lote no guarda avance parcial: al reanudarlo se repite desde el principio.",
  evaluacion_prescripcion: "La evaluación no guarda avance parcial: al reanudarla se repite desde el principio.",
} as const;

interface Props {
  trabajo: Trabajo;
  reanudable: boolean;
  alCancelar: () => void;
  alReanudar: () => void;
  cancelando?: boolean;
  reanudando?: boolean;
}

export function ProgresoTrabajo({ trabajo, reanudable, alCancelar, alReanudar, cancelando, reanudando }: Props) {
  const [confirmar, setConfirmar] = useState(false);
  const esPc = trabajo.tipo === "pc";
  const total = trabajo.total ?? 0;
  const porcentaje = total ? (100 * trabajo.completadas) / total : 0;
  const enCurso = trabajo.estado === "en_curso" || trabajo.estado === "pendiente";
  const modo = textoModo(trabajo.detalles);

  return (
    <Card withBorder data-testid="progreso-trabajo">
      <Stack gap="sm">
        <Group justify="space-between">
          <Text fw={600}>{esPc ? "Análisis PC con bootstrap" : "Análisis de los datos para sugerir la prueba"}</Text>
          <EstadoTrabajo estado={trabajo.estado} />
        </Group>

        {esPc && total > 0 && (
          <>
            <Progress value={porcentaje} animated={enCurso} striped={enCurso} size="lg" aria-label="Progreso" />
            <SimpleGrid cols={{ base: 2, md: 4 }}>
              <Dato etiqueta="Corridas" valor={`${trabajo.completadas} de ${total}`} />
              <Dato etiqueta="Fallidas" valor={String(trabajo.fallidas)} />
              <Dato etiqueta="Tiempo transcurrido" valor={formatoDuracion(trabajo.segundos_transcurridos)} />
              <Dato
                etiqueta="Tiempo restante estimado"
                valor={enCurso ? formatoDuracion(trabajo.segundos_restantes_estimados) : "—"}
              />
            </SimpleGrid>
          </>
        )}
        {!esPc && enCurso && (
          <>
            <Progress value={100} animated striped size="lg" aria-label="Progreso" />
            <Text size="sm" c="dimmed">
              Diagnosticando las variables{trabajo.parametros?.estimar_tiempo ? " y estimando el tiempo de PC" : ""}… (
              {formatoDuracion(trabajo.segundos_transcurridos)})
            </Text>
          </>
        )}
        {enCurso && modo && <Text size="sm">Modo: {modo}</Text>}

        {trabajo.estado === "cancelado" && (
          <Alert color="gray">
            Cancelado{esPc && total ? ` con ${trabajo.completadas} de ${total} corridas hechas` : ""}. {EXPLICACION_CANCELAR[trabajo.tipo]}
          </Alert>
        )}
        {trabajo.estado === "interrumpido" && (
          <Alert color="orange" title="Trabajo interrumpido">
            Se interrumpió porque la aplicación o el motor de análisis se cerraron.{" "}
            {esPc ? "El avance guardado se conserva: puede reanudarlo." : "Puede repetirlo."}
          </Alert>
        )}
        {trabajo.estado === "fallido" && (
          <Alert color="red" title="El trabajo falló">
            {trabajo.error}
          </Alert>
        )}
        {trabajo.estado === "completado" && trabajo.mensaje && (
          <Alert color="green">{trabajo.mensaje}</Alert>
        )}

        <Group justify="flex-end">
          {enCurso && (
            <Button color="red" variant="light" onClick={() => setConfirmar(true)} loading={cancelando}>
              Cancelar
            </Button>
          )}
          {!enCurso && reanudable && trabajo.estado !== "completado" && (
            <Button onClick={alReanudar} loading={reanudando}>
              {trabajo.estado === "fallido" ? "Reintentar" : "Reanudar"}
            </Button>
          )}
        </Group>
      </Stack>

      <Modal opened={confirmar} onClose={() => setConfirmar(false)} title="¿Cancelar el trabajo?">
        <Text size="sm">{EXPLICACION_CANCELAR[trabajo.tipo]}</Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setConfirmar(false)}>
            Seguir
          </Button>
          <Button
            color="red"
            onClick={() => {
              setConfirmar(false);
              alCancelar();
            }}
          >
            Cancelar el trabajo
          </Button>
        </Group>
      </Modal>
    </Card>
  );
}

const ESTADOS: Record<Trabajo["estado"], { texto: string; color: string }> = {
  pendiente: { texto: "Pendiente", color: "gray" },
  en_curso: { texto: "En curso", color: "blue" },
  completado: { texto: "Completado", color: "green" },
  cancelado: { texto: "Cancelado", color: "gray" },
  interrumpido: { texto: "Interrumpido", color: "orange" },
  fallido: { texto: "Fallido", color: "red" },
};

export function EstadoTrabajo({ estado }: { estado: Trabajo["estado"] }) {
  return (
    <Badge color={ESTADOS[estado].color} variant="light">
      {ESTADOS[estado].texto}
    </Badge>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">
        {etiqueta}
      </Text>
      <Text fw={500}>{valor}</Text>
    </Stack>
  );
}

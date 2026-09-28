// Elecciones del proyecto (borrador) y decisiones resultantes calculadas por el núcleo.
import { useDebouncedValue } from "@mantine/hooks";
import { useEffect, useMemo } from "react";

import { useDecisionesGuardadas, usePrevisualizacion, useRevision } from "../api/consultas";
import { aplicarEdiciones, BORRADOR_VACIO, borradorDesdeGuardadas, useBorrador } from "./borrador";

/** Retardo antes de pedir la previsualización tras un cambio de elección. */
export const RETARDO_PREVISUALIZACION_MS = 300;

export function useElecciones(id: string) {
  const revision = useRevision(id);
  const guardadas = useDecisionesGuardadas(id);
  const { borrador, inicializar, elegir, editar } = useBorrador(id);

  // Se inicializa una vez: desde las decisiones guardadas vigentes o vacío (todo sugerido).
  useEffect(() => {
    if (borrador || guardadas.isPending || guardadas.isError) return;
    inicializar(guardadas.data ? borradorDesdeGuardadas(guardadas.data) : BORRADOR_VACIO);
  }, [borrador, guardadas.isPending, guardadas.isError, guardadas.data, inicializar]);

  const [elecciones] = useDebouncedValue(borrador?.elecciones ?? null, RETARDO_PREVISUALIZACION_MS);
  const previsualizacion = usePrevisualizacion(id, revision.isSuccess ? elecciones : null);

  const acciones = previsualizacion.data?.acciones_hallazgos ?? {};
  const pendientes = useMemo(
    () =>
      Object.entries(previsualizacion.data?.acciones_hallazgos ?? {})
        .filter(([hallazgo, accion]) => accion.requiere_confirmacion && !borrador?.confirmadas[hallazgo])
        .map(([hallazgo]) => hallazgo),
    [previsualizacion.data, borrador?.confirmadas],
  );
  const decisiones = useMemo(
    () => (previsualizacion.data && borrador ? aplicarEdiciones(previsualizacion.data, borrador.ediciones) : null),
    [previsualizacion.data, borrador],
  );

  return {
    revision,
    guardadas,
    borrador,
    elegir,
    editar,
    previsualizacion,
    /** Acción vigente, opciones y descripción de cada hallazgo (del núcleo). */
    acciones,
    /** Hallazgos que requieren confirmación y aún no se eligieron explícitamente. */
    pendientes,
    /** Decisiones del núcleo con las ediciones del usuario superpuestas. */
    decisiones,
  };
}

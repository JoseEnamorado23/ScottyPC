// Modelo causal: aplicabilidad, modelo guardado, casos de test, escenarios y construcción (trabajo).
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useVigilancia } from "../estado/trabajos";
import { datos, type Esquemas } from "./cliente";
import { claves, opcional } from "./consultas";
import { useApi } from "./contexto";

export type SolicitudModelo = Esquemas["SolicitudModeloCausal"];
export type SolicitudEscenario = Esquemas["SolicitudContrafactual"];

const ruta = (id: string) => ({ params: { path: { proyecto_id: id } } });

/** Bloqueantes y advertencias con la configuración propuesta (no construye nada). */
export function useAplicabilidad(id: string, configuracion: SolicitudModelo, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.aplicabilidad(id, configuracion),
    enabled: habilitada,
    placeholderData: keepPreviousData,
    queryFn: () =>
      datos(cliente.POST("/proyectos/{proyecto_id}/modelo-causal/aplicabilidad", { ...ruta(id), body: configuracion })),
  });
}

/** Modelo guardado con su evaluación; `null` si no hay un modelo vigente. */
export function useModeloCausal(id: string, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.modelo(id),
    enabled: habilitada,
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/modelo-causal", ruta(id)))),
  });
}

export function useCasosModelo(id: string, pagina: number, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.casos(id, pagina),
    enabled: habilitada,
    placeholderData: keepPreviousData,
    queryFn: () =>
      datos(
        cliente.GET("/proyectos/{proyecto_id}/modelo-causal/casos", {
          params: { path: { proyecto_id: id }, query: { pagina } },
        }),
      ),
  });
}

/** Resultado de un escenario (`null` = todavía no hay caso). El mismo escenario da siempre lo mismo. */
export function useEscenario(id: string, solicitud: SolicitudEscenario | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.escenario(id, solicitud),
    enabled: solicitud !== null,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    retry: false,
    queryFn: () =>
      datos(cliente.POST("/proyectos/{proyecto_id}/modelo-causal/contrafactual", { ...ruta(id), body: solicitud! })),
  });
}

export function useConstruirModelo(id: string) {
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const { vigilar } = useVigilancia();
  return useMutation({
    mutationFn: (configuracion: SolicitudModelo) =>
      datos(cliente.POST("/proyectos/{proyecto_id}/modelo-causal", { ...ruta(id), body: configuracion })),
    onSuccess: async (trabajo) => {
      consultas.setQueryData(claves.trabajo(trabajo.id), trabajo);
      vigilar(trabajo);
      await consultas.invalidateQueries({ queryKey: claves.proyecto(id), exact: true });
    },
  });
}

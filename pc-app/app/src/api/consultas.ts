// Consultas de TanStack Query sobre el cliente tipado.
import { useQuery } from "@tanstack/react-query";

import { datos, ErrorApi } from "./cliente";
import { useApi } from "./contexto";

export const claves = {
  proyectos: ["proyectos"] as const,
  proyecto: (id: string) => ["proyectos", id] as const,
  datos: (id: string, hoja: string | null) => ["proyectos", id, "datos", hoja] as const,
  distribucion: (id: string, columna: string, hoja: string | null) =>
    ["proyectos", id, "distribucion", columna, hoja] as const,
  revision: (id: string) => ["proyectos", id, "revision"] as const,
  decisionesGuardadas: (id: string) => ["proyectos", id, "decisiones"] as const,
  previsualizacion: (id: string, elecciones: Record<string, string>) =>
    ["proyectos", id, "previsualizacion", elecciones] as const,
};

const ruta = (id: string) => ({ params: { path: { proyecto_id: id } } });

export function useProyectos() {
  const { cliente } = useApi();
  return useQuery({ queryKey: claves.proyectos, queryFn: () => datos(cliente.GET("/proyectos")) });
}

export function useProyecto(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.proyecto(id),
    queryFn: () => datos(cliente.GET("/proyectos/{proyecto_id}", ruta(id))),
  });
}

export function useDatosHoja(id: string, hoja: string | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.datos(id, hoja),
    queryFn: () =>
      datos(
        cliente.GET("/proyectos/{proyecto_id}/datos", {
          params: { path: { proyecto_id: id }, query: hoja ? { hoja } : {} },
        }),
      ),
  });
}

export function useDistribucion(id: string, columna: string | null, hoja: string | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.distribucion(id, columna ?? "", hoja),
    enabled: columna !== null,
    queryFn: () =>
      datos(
        cliente.GET("/proyectos/{proyecto_id}/distribucion", {
          params: { path: { proyecto_id: id }, query: { columna: columna!, ...(hoja ? { hoja } : {}) } },
        }),
      ),
  });
}

export function useRevision(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.revision(id),
    queryFn: () => datos(cliente.GET("/proyectos/{proyecto_id}/revision", ruta(id))),
  });
}

/** Decisiones guardadas; `null` si todavía no hay (o están desactualizadas). */
export function useDecisionesGuardadas(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.decisionesGuardadas(id),
    queryFn: async () => {
      try {
        return await datos(cliente.GET("/proyectos/{proyecto_id}/decisiones", ruta(id)));
      } catch (error) {
        if (error instanceof ErrorApi && error.estado === 409) return null;
        throw error;
      }
    },
  });
}

/** Decisiones que resultan de las elecciones, calculadas por el núcleo. */
export function usePrevisualizacion(id: string, elecciones: Record<string, string> | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.previsualizacion(id, elecciones ?? {}),
    enabled: elecciones !== null,
    placeholderData: (anterior) => anterior,
    queryFn: () =>
      datos(
        cliente.POST("/proyectos/{proyecto_id}/decisiones/previsualizar", {
          ...ruta(id),
          body: { elecciones: elecciones ?? {} },
        }),
      ),
  });
}

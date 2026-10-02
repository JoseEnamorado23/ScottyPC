// Prescripción: configuración, condiciones, caso, lotes, evaluaciones, trabajos y exportación.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useVigilancia } from "../estado/trabajos";
import { datos, type Esquemas } from "./cliente";
import { claves, opcional } from "./consultas";
import { useApi } from "./contexto";

export type ConfiguracionPrescripcion = Esquemas["ConfiguracionPrescripcion"];
type Trabajo = Esquemas["Trabajo"];

const ruta = (id: string) => ({ params: { path: { proyecto_id: id } } });
export const clavesPrescripcion = {
  todo: (id: string) => ["proyectos", id, "prescripcion"] as const,
  configuracion: (id: string) => ["proyectos", id, "prescripcion", "configuracion"] as const,
  condiciones: (id: string, configuracion: unknown) => ["proyectos", id, "prescripcion", "condiciones", configuracion] as const,
  validacion: (id: string, configuracion: unknown) => ["proyectos", id, "prescripcion", "validacion", configuracion] as const,
  caso: (id: string, solicitud: unknown) => ["proyectos", id, "prescripcion", "caso", solicitud] as const,
  lotes: (id: string) => ["proyectos", id, "prescripcion", "lotes"] as const,
  lote: (id: string, numero: number, pagina: number, filtro: string | null) =>
    ["proyectos", id, "prescripcion", "lotes", numero, pagina, filtro] as const,
  evaluaciones: (id: string) => ["proyectos", id, "prescripcion", "evaluaciones"] as const,
  evaluacion: (id: string, numero: number) => ["proyectos", id, "prescripcion", "evaluaciones", numero] as const,
};

/** Configuración guardada o sugerida; `null` si no hay un modelo causal vigente (409). */
export function useConfiguracionPrescripcion(id: string, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.configuracion(id),
    enabled: habilitada,
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/prescripcion/configuracion", ruta(id)))),
  });
}

/** Condiciones con la configuración en edición (o la guardada si es `null`). */
export function useCondicionesPrescripcion(id: string, configuracion: ConfiguracionPrescripcion | null, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.condiciones(id, configuracion),
    enabled: habilitada,
    placeholderData: keepPreviousData,
    queryFn: () =>
      datos(
        cliente.POST("/proyectos/{proyecto_id}/prescripcion/condiciones", {
          ...ruta(id),
          ...(configuracion ? { body: configuracion } : {}),
        }),
      ),
  });
}

export function useValidacionPrescripcion(id: string, configuracion: ConfiguracionPrescripcion | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.validacion(id, configuracion),
    enabled: configuracion !== null,
    placeholderData: keepPreviousData,
    retry: false,
    queryFn: () =>
      datos(cliente.POST("/proyectos/{proyecto_id}/prescripcion/configuracion/validar", { ...ruta(id), body: configuracion! })),
  });
}

export function usePrescripcionCaso(id: string, solicitud: Esquemas["SolicitudCasoPrescripcion"] | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.caso(id, solicitud),
    enabled: solicitud !== null,
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: Infinity,
    queryFn: () => datos(cliente.POST("/proyectos/{proyecto_id}/prescripcion/caso", { ...ruta(id), body: solicitud! })),
  });
}

export function useLotes(id: string, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.lotes(id),
    enabled: habilitada,
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/prescripcion/lotes", ruta(id)))),
  });
}

export function usePaginaLote(id: string, numero: number | null, pagina: number, filtro: string | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.lote(id, numero ?? 0, pagina, filtro),
    enabled: numero !== null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      datos(
        cliente.GET("/proyectos/{proyecto_id}/prescripcion/lotes/{numero}", {
          params: { path: { proyecto_id: id, numero: numero! }, query: { pagina, ...(filtro ? { filtro } : {}) } },
        }),
      ),
  });
}

export function useEvaluaciones(id: string, habilitada: boolean) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.evaluaciones(id),
    enabled: habilitada,
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/prescripcion/evaluaciones", ruta(id)))),
  });
}

export function useEvaluacion(id: string, numero: number | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: clavesPrescripcion.evaluacion(id, numero ?? 0),
    enabled: numero !== null,
    queryFn: () =>
      datos(
        cliente.GET("/proyectos/{proyecto_id}/prescripcion/evaluaciones/{numero}", {
          params: { path: { proyecto_id: id, numero: numero! } },
        }),
      ),
  });
}

export function useAccionesPrescripcion(id: string) {
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const { vigilar } = useVigilancia();

  const alIniciar = async (trabajo: Trabajo) => {
    consultas.setQueryData(claves.trabajo(trabajo.id), trabajo);
    vigilar(trabajo);
    await consultas.invalidateQueries({ queryKey: claves.proyecto(id), exact: true });
  };

  const guardar = useMutation({
    mutationFn: (configuracion: ConfiguracionPrescripcion) =>
      datos(cliente.PUT("/proyectos/{proyecto_id}/prescripcion/configuracion", { ...ruta(id), body: configuracion })),
    onSuccess: async (vista) => {
      consultas.setQueryData(clavesPrescripcion.configuracion(id), vista);
      // Guardar archiva los lotes, las evaluaciones y la calibración anteriores.
      await consultas.invalidateQueries({ queryKey: clavesPrescripcion.todo(id) });
      await consultas.invalidateQueries({ queryKey: claves.proyecto(id), exact: true });
      await consultas.invalidateQueries({ queryKey: claves.resultados(id) });
    },
  });

  const calibrar = useMutation({
    mutationFn: () => datos(cliente.POST("/proyectos/{proyecto_id}/prescripcion/calibrar-mu", ruta(id))),
    onSuccess: alIniciar,
  });

  const lote = useMutation({
    mutationFn: (solicitud: Esquemas["SolicitudLote"]) =>
      datos(cliente.POST("/proyectos/{proyecto_id}/prescripcion/lote", { ...ruta(id), body: solicitud })),
    onSuccess: alIniciar,
  });

  const evaluar = useMutation({
    mutationFn: () => datos(cliente.POST("/proyectos/{proyecto_id}/prescripcion/evaluacion", ruta(id))),
    onSuccess: alIniciar,
  });

  const exportar = useMutation({
    mutationFn: (solicitud: Esquemas["SolicitudExportarPrescripcion"]) =>
      datos(cliente.POST("/proyectos/{proyecto_id}/prescripcion/exportar", { ...ruta(id), body: solicitud })),
  });

  return { guardar, calibrar, lote, evaluar, exportar };
}

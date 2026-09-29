// Consultas de TanStack Query sobre el cliente tipado.
import { useQuery } from "@tanstack/react-query";

import { datos, ErrorApi, type Esquemas } from "./cliente";
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
  preparacion: (id: string) => ["proyectos", id, "preparacion"] as const,
  recomendacion: (id: string) => ["proyectos", id, "recomendacion"] as const,
  evaluacion: (id: string, prueba: string, maxK: number | null) =>
    ["proyectos", id, "evaluacion", prueba, maxK] as const,
  configuracionPc: (id: string) => ["proyectos", id, "configuracion-pc"] as const,
  plantillaPc: (id: string) => ["proyectos", id, "configuracion-pc", "plantilla"] as const,
  validacionPc: (id: string, configuracion: unknown) => ["proyectos", id, "configuracion-pc", "validacion", configuracion] as const,
  /** Prefijo de todo lo que depende del resultado (versiones, vista previa, procedencia). */
  resultados: (id: string) => ["proyectos", id, "resultado"] as const,
  resultado: (id: string, version: number | null) => ["proyectos", id, "resultado", "version", version] as const,
  versiones: (id: string) => ["proyectos", id, "resultado", "versiones"] as const,
  vistaPrevia: (id: string, ajuste: unknown) => ["proyectos", id, "resultado", "vista-previa", ajuste] as const,
  procedencia: (id: string) => ["proyectos", id, "resultado", "procedencia"] as const,
  trabajo: (id: string) => ["trabajos", id] as const,
  /** Prefijo de todo lo del modelo causal (aplicabilidad, modelo, casos, escenarios). */
  modeloCausal: (id: string) => ["proyectos", id, "modelo-causal"] as const,
  aplicabilidad: (id: string, configuracion: unknown) => ["proyectos", id, "modelo-causal", "aplicabilidad", configuracion] as const,
  modelo: (id: string) => ["proyectos", id, "modelo-causal", "modelo"] as const,
  casos: (id: string, pagina: number) => ["proyectos", id, "modelo-causal", "casos", pagina] as const,
  escenario: (id: string, solicitud: unknown) => ["proyectos", id, "modelo-causal", "escenario", solicitud] as const,
};

/** Intervalo de sondeo del progreso de un trabajo en curso. */
export const INTERVALO_SONDEO_MS = 1000;
export const ESTADOS_FINALES = ["completado", "cancelado", "fallido", "interrumpido"] as const;
export const esFinal = (estado: string | undefined) => (ESTADOS_FINALES as readonly string[]).includes(estado ?? "");

/** `null` si la etapa no está vigente (409), en vez de un error. */
export async function opcional<T>(peticion: Promise<T>): Promise<T | null> {
  try {
    return await peticion;
  } catch (error) {
    if (error instanceof ErrorApi && error.estado === 409) return null;
    throw error;
  }
}

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

export function useEstadoPreparacion(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.preparacion(id),
    queryFn: () => datos(cliente.GET("/proyectos/{proyecto_id}/preparacion", ruta(id))),
  });
}

/** Recomendación guardada; `null` si no hay una vigente. */
export function useRecomendacion(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.recomendacion(id),
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/recomendacion", ruta(id)))),
  });
}

/** Advertencias del núcleo sobre la prueba y el max_k elegidos (null = sin elección todavía). */
export function useEvaluacionPrueba(id: string, eleccion: { prueba: string; max_k: number | null } | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.evaluacion(id, eleccion?.prueba ?? "", eleccion?.max_k ?? null),
    enabled: eleccion !== null,
    placeholderData: (anterior) => anterior,
    queryFn: () =>
      datos(
        cliente.POST("/proyectos/{proyecto_id}/recomendacion/evaluar", {
          ...ruta(id),
          body: { prueba: eleccion!.prueba as Esquemas["SolicitudEvaluarPrueba"]["prueba"], max_k: eleccion!.max_k },
        }),
      ),
  });
}

export function useConfiguracionPc(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.configuracionPc(id),
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/configuracion-pc", ruta(id)))),
  });
}

/** Errores y advertencias de una configuración sin guardarla (validada por el núcleo). */
export function useValidacionConfiguracion(id: string, configuracion: Esquemas["ConfiguracionPC"] | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.validacionPc(id, configuracion),
    enabled: configuracion !== null,
    placeholderData: (anterior) => anterior,
    queryFn: () =>
      datos(cliente.POST("/proyectos/{proyecto_id}/configuracion-pc/validar", { ...ruta(id), body: configuracion! })),
  });
}

/** Resultado de una versión (`null` = la actual); `null` si no hay un análisis vigente. */
export function useResultado(id: string, version: number | null = null, habilitado = true) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.resultado(id, version),
    enabled: habilitado,
    // Al cambiar de versión se conserva la anterior mientras llega la nueva: el grafo no se desmonta.
    placeholderData: (anterior) => anterior,
    queryFn: () =>
      opcional(
        datos(
          cliente.GET("/proyectos/{proyecto_id}/resultado", {
            params: { path: { proyecto_id: id }, query: version === null ? {} : { version } },
          }),
        ),
      ),
  });
}

export function useVersiones(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.versiones(id),
    queryFn: () => opcional(datos(cliente.GET("/proyectos/{proyecto_id}/resultado/versiones", ruta(id)))),
  });
}

export function useProcedencia(id: string) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.procedencia(id),
    queryFn: () => datos(cliente.GET("/proyectos/{proyecto_id}/resultado/procedencia", ruta(id))),
  });
}

/**
 * Resultado reagregado con otro umbral u otras orientaciones, sin guardar (`null` = no hay
 * cambios que previsualizar). Mientras llega la nueva vista se conserva la anterior.
 */
export function useVistaPrevia(id: string, ajuste: Esquemas["SolicitudReagregar"] | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.vistaPrevia(id, ajuste),
    enabled: ajuste !== null,
    placeholderData: (anterior) => anterior,
    // El mismo ajuste da siempre el mismo resultado (hasta que cambia el análisis, que invalida todo).
    staleTime: Infinity,
    queryFn: () => datos(cliente.POST("/proyectos/{proyecto_id}/resultado/reagregar", { ...ruta(id), body: ajuste! })),
  });
}

/**
 * Estado de un trabajo. Se sondea cada segundo mientras está pendiente o en curso; el
 * sondeo se detiene al llegar a un estado final, si la consulta falla (p. ej. el motor
 * no responde) o mientras la ventana no está visible.
 */
export function useTrabajo(trabajoId: string | null) {
  const { cliente } = useApi();
  return useQuery({
    queryKey: claves.trabajo(trabajoId ?? ""),
    enabled: trabajoId !== null,
    refetchIntervalInBackground: false,
    refetchInterval: (consulta) => {
      if (consulta.state.status === "error") return false;
      return esFinal(consulta.state.data?.estado) ? false : INTERVALO_SONDEO_MS;
    },
    queryFn: () =>
      datos(cliente.GET("/trabajos/{trabajo_id}", { params: { path: { trabajo_id: trabajoId! } } })),
  });
}

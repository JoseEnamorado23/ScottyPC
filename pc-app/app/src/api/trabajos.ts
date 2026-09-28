// Acciones sobre trabajos: lanzar la recomendación o el análisis, cancelar y reanudar.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useVigilancia } from "../estado/trabajos";
import { datos, type Esquemas } from "./cliente";
import { claves } from "./consultas";
import { useApi } from "./contexto";

type Trabajo = Esquemas["Trabajo"];

export function useAccionesTrabajo(proyectoId: string) {
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const { vigilar } = useVigilancia();

  const alIniciar = async (trabajo: Trabajo) => {
    consultas.setQueryData(claves.trabajo(trabajo.id), trabajo);
    vigilar(trabajo);
    await consultas.invalidateQueries({ queryKey: claves.proyecto(proyectoId), exact: true });
    await consultas.invalidateQueries({ queryKey: claves.proyectos, exact: true });
  };

  const lanzarRecomendacion = useMutation({
    mutationFn: (estimar: boolean) =>
      datos(
        cliente.POST("/proyectos/{proyecto_id}/recomendacion", {
          params: { path: { proyecto_id: proyectoId }, query: { estimar_tiempo: estimar } },
        }),
      ),
    onSuccess: alIniciar,
  });

  const lanzarPc = useMutation({
    mutationFn: () => datos(cliente.POST("/proyectos/{proyecto_id}/pc", { params: { path: { proyecto_id: proyectoId } } })),
    onSuccess: alIniciar,
  });

  const cancelar = useMutation({
    mutationFn: (trabajoId: string) =>
      datos(cliente.POST("/trabajos/{trabajo_id}/cancelar", { params: { path: { trabajo_id: trabajoId } } })),
    onSuccess: (trabajo) => consultas.invalidateQueries({ queryKey: claves.trabajo(trabajo.id) }),
  });

  const reanudar = useMutation({
    mutationFn: (trabajoId: string) =>
      datos(cliente.POST("/trabajos/{trabajo_id}/reanudar", { params: { path: { trabajo_id: trabajoId } } })),
    onSuccess: alIniciar,
  });

  return { lanzarRecomendacion, lanzarPc, cancelar, reanudar };
}

// Acciones sobre el resultado: guardar un ajuste como versión, cambiar la versión actual,
// validar una orientación manual y exportar.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { aSolicitud, type Ajuste } from "../estado/ajustes";
import { datos, type Esquemas } from "./cliente";
import { claves } from "./consultas";
import { useApi } from "./contexto";

export function useAccionesResultado(proyectoId: string) {
  const { cliente } = useApi();
  const consultas = useQueryClient();
  const ruta = { params: { path: { proyecto_id: proyectoId } } };

  const alCambiarVersiones = async (versiones: Esquemas["VersionesResultado"]) => {
    consultas.setQueryData(claves.versiones(proyectoId), versiones);
    await consultas.invalidateQueries({ queryKey: claves.resultado(proyectoId, null) });
  };

  const guardarVersion = useMutation({
    mutationFn: ({ ajuste, base }: { ajuste: Ajuste; base: number }) =>
      datos(
        cliente.POST("/proyectos/{proyecto_id}/resultado/versiones", {
          ...ruta,
          body: { ...aSolicitud(ajuste), version_base: base },
        }),
      ),
    onSuccess: alCambiarVersiones,
  });

  const cambiarVersion = useMutation({
    mutationFn: (version: number) =>
      datos(cliente.PUT("/proyectos/{proyecto_id}/resultado/version-actual", { ...ruta, body: { version } })),
    onSuccess: alCambiarVersiones,
  });

  /** Reagrega con el ajuste propuesto (valida en el núcleo) y deja la vista en la caché. */
  const previsualizar = async (ajuste: Ajuste) => {
    const solicitud = aSolicitud(ajuste);
    const vista = await datos(cliente.POST("/proyectos/{proyecto_id}/resultado/reagregar", { ...ruta, body: solicitud }));
    consultas.setQueryData(claves.vistaPrevia(proyectoId, solicitud), vista);
    return vista;
  };

  const exportar = useMutation({
    mutationFn: ({ carpeta, version }: { carpeta: string; version: number }) =>
      datos(cliente.POST("/proyectos/{proyecto_id}/exportar", { ...ruta, body: { carpeta_destino: carpeta, version } })),
  });

  return { guardarVersion, cambiarVersion, previsualizar, exportar };
}

import type { Esquemas } from "../api/cliente";

export type ClaveEtapa = "revision" | "decisiones" | "preparacion" | "recomendacion" | "configuracion_pc" | "analisis";
export type EstadoEtapa = "vigente" | "desactualizada" | "pendiente";

/** Las seis etapas en el orden del sidecar (`etapas.ETAPAS`). */
export const ETAPAS: { clave: ClaveEtapa; nombre: string; ruta: string | null }[] = [
  { clave: "revision", nombre: "Revisión", ruta: "revision" },
  { clave: "decisiones", nombre: "Decisiones", ruta: "decisiones" },
  { clave: "preparacion", nombre: "Preparación", ruta: null },
  { clave: "recomendacion", nombre: "Recomendación", ruta: null },
  { clave: "configuracion_pc", nombre: "Configuración PC", ruta: null },
  { clave: "analisis", nombre: "Análisis", ruta: null },
];

export function estadoEtapa(proyecto: Esquemas["Proyecto"], clave: ClaveEtapa): EstadoEtapa {
  return proyecto.etapas[clave] ?? "pendiente";
}

/** Nombres de las etapas vigentes que quedarán desactualizadas al volver a guardar `etapa`. */
export function etapasQueSeDesactualizan(proyecto: Esquemas["Proyecto"], etapa: ClaveEtapa): string[] {
  const indice = ETAPAS.findIndex((e) => e.clave === etapa);
  return ETAPAS.slice(indice + 1)
    .filter((e) => estadoEtapa(proyecto, e.clave) === "vigente")
    .map((e) => e.nombre);
}

/** Ruta a la que lleva «Abrir» un proyecto: la última etapa con pantalla disponible. */
export function rutaDeProyecto(proyecto: Esquemas["Proyecto"]): string {
  const base = `/proyectos/${proyecto.id}`;
  if (proyecto.etapas.decisiones) return `${base}/decisiones`;
  if (proyecto.etapas.revision === "vigente") return `${base}/revision`;
  return `${base}/datos`;
}

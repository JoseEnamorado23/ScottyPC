import type { Esquemas } from "../api/cliente";

export type ClaveEtapa =
  | "revision" | "decisiones" | "preparacion" | "recomendacion" | "configuracion_pc" | "analisis" | "modelo_causal"
  | "prescripcion";
export type EstadoEtapa = "vigente" | "desactualizada" | "pendiente";
type Proyecto = Esquemas["Proyecto"];

/** Las ocho etapas en el orden del sidecar (`etapas.ETAPAS`), con su pantalla y su requisito. */
export const ETAPAS: { clave: ClaveEtapa; nombre: string; ruta: string; requisito: ClaveEtapa | null }[] = [
  { clave: "revision", nombre: "Revisión", ruta: "revision", requisito: null },
  { clave: "decisiones", nombre: "Decisiones", ruta: "decisiones", requisito: "revision" },
  { clave: "preparacion", nombre: "Preparación", ruta: "preparacion", requisito: "decisiones" },
  { clave: "recomendacion", nombre: "Recomendación", ruta: "recomendacion", requisito: "preparacion" },
  { clave: "configuracion_pc", nombre: "Configuración PC", ruta: "configuracion", requisito: "preparacion" },
  { clave: "analisis", nombre: "Análisis", ruta: "analisis", requisito: "configuracion_pc" },
  { clave: "modelo_causal", nombre: "Modelo causal", ruta: "modelo-causal", requisito: "analisis" },
  { clave: "prescripcion", nombre: "Prescripción", ruta: "prescripcion", requisito: "modelo_causal" },
];

export function estadoEtapa(proyecto: Proyecto, clave: ClaveEtapa): EstadoEtapa {
  return proyecto.etapas[clave] ?? "pendiente";
}

/** Si se puede abrir la pantalla de una etapa: ya se hizo o su requisito está vigente. */
export function etapaDisponible(proyecto: Proyecto, clave: ClaveEtapa): boolean {
  const etapa = ETAPAS.find((e) => e.clave === clave)!;
  return (
    estadoEtapa(proyecto, clave) !== "pendiente" ||
    etapa.requisito === null ||
    estadoEtapa(proyecto, etapa.requisito) === "vigente"
  );
}

/** Nombres de las etapas vigentes que quedarán desactualizadas al volver a guardar `etapa`. */
export function etapasQueSeDesactualizan(proyecto: Proyecto, etapa: ClaveEtapa): string[] {
  const indice = ETAPAS.findIndex((e) => e.clave === etapa);
  return ETAPAS.slice(indice + 1)
    .filter((e) => estadoEtapa(proyecto, e.clave) === "vigente")
    .map((e) => e.nombre);
}

/** Id del trabajo de un tipo a mostrar: el activo o, si no, el último (p. ej. interrumpido). */
export function trabajoDelProyecto(proyecto: Proyecto, tipo: Esquemas["Trabajo"]["tipo"]): string | null {
  const ultimo = proyecto.ultimo_trabajo;
  if (ultimo && ultimo.tipo === tipo) return ultimo.id;
  return null;
}

/** Ruta a la que lleva «Abrir» un proyecto. */
export function rutaDeProyecto(proyecto: Proyecto): string {
  const base = `/proyectos/${proyecto.id}`;
  const ultimo = proyecto.ultimo_trabajo;
  if (proyecto.trabajo_activo || ultimo?.reanudable) {
    const rutas = {
      recomendacion: "recomendacion", pc: "analisis", modelo_causal: "modelo-causal",
      calibracion_mu: "prescripcion", lote_prescripcion: "prescripcion", evaluacion_prescripcion: "prescripcion",
    } as const;
    return `${base}/${rutas[ultimo?.tipo ?? "pc"]}`;
  }
  if (estadoEtapa(proyecto, "prescripcion") === "vigente") return `${base}/prescripcion`;
  if (estadoEtapa(proyecto, "modelo_causal") === "vigente") return `${base}/modelo-causal`;
  if (estadoEtapa(proyecto, "analisis") === "vigente") return `${base}/resultados`;
  const ultimaHecha = [...ETAPAS].reverse().find((e) => estadoEtapa(proyecto, e.clave) !== "pendiente");
  if (!ultimaHecha) return `${base}/datos`;
  if (ultimaHecha.clave === "revision" && estadoEtapa(proyecto, "revision") !== "vigente") return `${base}/datos`;
  return `${base}/${ultimaHecha.ruta}`;
}

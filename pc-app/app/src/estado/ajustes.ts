// Borrador del ajuste de un resultado: umbral y orientaciones manuales. Solo guarda lo que
// el usuario cambia; qué aristas quedan, su orientación y su caracterización las calcula el
// núcleo (POST .../resultado/reagregar).
import type { Esquemas } from "../api/cliente";

export type Orientacion = Esquemas["OrientacionManual"];

export interface Ajuste {
  umbral: number;
  orientaciones: Orientacion[];
}

export const UMBRAL_MINIMO = 0.2;
export const UMBRAL_MAXIMO = 1;
/** Por debajo se avisa de que se incluyen más aristas espurias. */
export const UMBRAL_BAJO = 0.5;

export const ajusteDe = (agregacion: Esquemas["Agregacion"]): Ajuste => ({
  umbral: agregacion.umbral_frecuencia,
  orientaciones: agregacion.orientaciones_manuales,
});

export const aSolicitud = (ajuste: Ajuste): Esquemas["SolicitudReagregar"] => ({
  umbral_frecuencia: ajuste.umbral,
  orientaciones_manuales: ajuste.orientaciones,
});

/** Clave del par sin orientación (la misma para A→B y B→A). */
export const clavePar = (a: string, b: string) => [a, b].sort().join("|");

const claveOrientacion = (o: Orientacion) => `${o.origen}→${o.destino}→${o.justificacion ?? ""}`;

export function mismoAjuste(a: Ajuste, b: Ajuste): boolean {
  if (Math.abs(a.umbral - b.umbral) > 1e-9 || a.orientaciones.length !== b.orientaciones.length) return false;
  const claves = new Set(a.orientaciones.map(claveOrientacion));
  return b.orientaciones.every((o) => claves.has(claveOrientacion(o)));
}

/** Umbral redondeado a centésimas (el paso del deslizante). */
export const conUmbral = (ajuste: Ajuste, umbral: number): Ajuste => ({
  ...ajuste,
  umbral: Math.round(Math.min(UMBRAL_MAXIMO, Math.max(UMBRAL_MINIMO, umbral)) * 100) / 100,
});

/** Orienta una arista; reemplaza la orientación manual que ya tuviera ese par. La nueva queda al final. */
export const conOrientacion = (ajuste: Ajuste, orientacion: Orientacion): Ajuste => ({
  ...ajuste,
  orientaciones: [
    ...ajuste.orientaciones.filter((o) => clavePar(o.origen, o.destino) !== clavePar(orientacion.origen, orientacion.destino)),
    orientacion,
  ],
});

export const sinOrientacion = (ajuste: Ajuste, a: string, b: string): Ajuste => ({
  ...ajuste,
  orientaciones: ajuste.orientaciones.filter((o) => clavePar(o.origen, o.destino) !== clavePar(a, b)),
});

export function orientacionDe(ajuste: Ajuste, a: string, b: string): Orientacion | undefined {
  return ajuste.orientaciones.find((o) => clavePar(o.origen, o.destino) === clavePar(a, b));
}

export const formatoPorcentaje = (valor: number, decimales = 0) =>
  `${(100 * valor).toLocaleString("es", { maximumFractionDigits: decimales, minimumFractionDigits: decimales })} %`;

export const formatoRho = (rho: number) =>
  rho.toLocaleString("es", { minimumFractionDigits: 3, maximumFractionDigits: 3, signDisplay: "exceptZero" });

// Lógica de la pantalla del modelo causal que no depende de React: formatos, overrides de la
// construcción, intervenciones del explorador de escenarios y disposición del grafo pequeño.
import type { Esquemas } from "../api/cliente";

type Control = Esquemas["ControlVariable"];
type Evaluacion = Esquemas["EvaluacionModeloCausal"];
export type Solicitud = Esquemas["SolicitudModeloCausal"];
export type Monotonia = "creciente" | "decreciente" | "ninguna";
export type EleccionMecanismo = "simple" | "complejo";

export const SOLICITUD_VACIA: Solicitud = { monotonia: {}, mecanismos: {}, pesos_clase: false };

export const NOMBRES_METRICA: Record<string, string> = {
  r2: "R²",
  exactitud_balanceada: "Exactitud balanceada",
  auc: "AUC",
  brier: "Brier",
  rmse: "RMSE",
};

export const numero = (valor: number | null | undefined, decimales = 3) =>
  valor === null || valor === undefined ? "—" : valor.toLocaleString("es", { maximumFractionDigits: decimales });

/** Métrica con decimales fijos (para comparar columnas). */
export const metrica = (valor: number | null | undefined) =>
  valor === null || valor === undefined
    ? "—"
    : valor.toLocaleString("es", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

export const porcentaje = (valor: number | null | undefined, decimales = 1) =>
  valor === null || valor === undefined
    ? "—"
    : `${(100 * valor).toLocaleString("es", { minimumFractionDigits: decimales, maximumFractionDigits: decimales })} %`;

/** Cambio con signo: «+3,2 pp» para probabilidades, «+1,5» para valores. */
export function cambio(valor: number, medida: "probabilidad" | "valor" = "valor", decimales = 1): string {
  if (valor === 0) return medida === "probabilidad" ? "0 pp" : "0";
  const signo = valor > 0 ? "+" : "−";
  const absoluto = Math.abs(medida === "probabilidad" ? 100 * valor : valor);
  const texto = absoluto.toLocaleString("es", { maximumFractionDigits: medida === "probabilidad" ? decimales : 2 });
  return `${signo}${texto}${medida === "probabilidad" ? " pp" : ""}`;
}

/** Valor de una variable para mostrar (etiqueta, número o probabilidad de 1 si es binaria aproximada). */
export function textoValor(valor: unknown): string {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "number") return numero(valor, 3);
  return String(valor);
}

// --- Overrides ------------------------------------------------------------------------------------

export function conMonotonia(s: Solicitud, padre: string, valor: Monotonia | "auto"): Solicitud {
  const monotonia = { ...(s.monotonia ?? {}) };
  if (valor === "auto") delete monotonia[padre];
  else monotonia[padre] = valor;
  return { ...s, monotonia };
}

export function conMecanismo(s: Solicitud, variable: string, valor: EleccionMecanismo | "auto"): Solicitud {
  const mecanismos = { ...(s.mecanismos ?? {}) };
  if (valor === "auto") delete mecanismos[variable];
  else mecanismos[variable] = valor;
  return { ...s, mecanismos };
}

/** Configuración con la que se construyó el modelo guardado (para partir de ella al editar). */
export function solicitudDelModelo(configuracion: Record<string, unknown>): Solicitud {
  return {
    monotonia: (configuracion.monotonia as Solicitud["monotonia"]) ?? {},
    mecanismos: (configuracion.mecanismos as Solicitud["mecanismos"]) ?? {},
    pesos_clase: Boolean(configuracion.pesos_clase),
  };
}

export function mismaSolicitud(a: Solicitud, b: Solicitud): boolean {
  const ordenar = (s: Solicitud) =>
    JSON.stringify({
      monotonia: Object.entries(s.monotonia ?? {}).sort(),
      mecanismos: Object.entries(s.mecanismos ?? {}).sort(),
      pesos: Boolean(s.pesos_clase),
    });
  return ordenar(a) === ordenar(b);
}

// --- Escenarios -----------------------------------------------------------------------------------

export type ModoIntervencion = "ninguna" | "desplazar" | "fijar";
export interface Intervencion {
  modo: ModoIntervencion;
  valor: number | string | null;
}
export type Intervenciones = Record<string, Intervencion>;

/** Modos que admite un control: las categorías solo se fijan. */
export function modosDe(control: Control): ModoIntervencion[] {
  return control.control === "numerica" || control.control === "ordinal"
    ? ["ninguna", "desplazar", "fijar"]
    : ["ninguna", "fijar"];
}

/** Intervenciones completas para la API (se omiten las que no tienen valor). */
export function aIntervenciones(intervenciones: Intervenciones): Esquemas["IntervencionEntrada"][] {
  return Object.entries(intervenciones)
    .filter(([, i]) => i.modo !== "ninguna" && i.valor !== null && i.valor !== "")
    .map(([variable, i]) => ({ variable, tipo: i.modo as "desplazar" | "fijar", valor: i.valor }))
    .sort((a, b) => a.variable.localeCompare(b.variable));
}

/** Si el valor elegido para un control numérico sale del rango de entrenamiento. */
export function fueraDeRango(control: Control, valorActual: unknown, intervencion: Intervencion): boolean {
  if (control.control !== "numerica" || control.minimo === null || control.maximo === null) return false;
  if (intervencion.modo === "ninguna" || typeof intervencion.valor !== "number") return false;
  const base = typeof valorActual === "number" ? valorActual : null;
  const nuevo = intervencion.modo === "fijar" ? intervencion.valor : base === null ? null : base + intervencion.valor;
  return nuevo !== null && (nuevo < control.minimo || nuevo > control.maximo);
}

// --- Grafo pequeño ------------------------------------------------------------------------------

export interface NodoDispuesto {
  variable: string;
  columna: number;
  fila: number;
}

/** Columnas por profundidad (camino más largo desde una raíz); el objetivo queda en la última. */
export function disponerSubgrafo(variables: string[], padres: Record<string, string[]>): NodoDispuesto[] {
  const profundidad: Record<string, number> = {};
  for (const v of variables) {
    const ps = padres[v] ?? [];
    profundidad[v] = ps.length ? Math.max(...ps.map((p) => (profundidad[p] ?? 0) + 1)) : 0;
  }
  const filas: Record<number, number> = {};
  return variables.map((variable) => {
    const columna = profundidad[variable];
    const fila = filas[columna] ?? 0;
    filas[columna] = fila + 1;
    return { variable, columna, fila };
  });
}

/** Mecanismo del objetivo en la evaluación. */
export const mecanismoObjetivo = (evaluacion: Evaluacion) =>
  evaluacion.mecanismos.find((m) => m.rol === "objetivo") ?? null;

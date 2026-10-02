// Lógica de la pantalla de prescripción que no depende de React: edición del borrador de la
// configuración, declaración de supuestos y paso de una prescripción al explorador de escenarios.
import type { Esquemas } from "../api/cliente";
import type { Intervenciones } from "./modeloCausal";

type Configuracion = Esquemas["ConfiguracionPrescripcion"];
type Accion = Esquemas["ConfiguracionAccion"];
type Supuestos = Esquemas["Supuestos"];
type Resultado = Esquemas["ResultadoPrescripcion"];

export const AVISO_PRESCRIPCION =
  "Recomendaciones basadas en datos observacionales. No reemplazan el criterio de un experto ni una validación experimental.";

export const SUPUESTOS: { campo: keyof Omit<Supuestos, "confirmado_en">; texto: string }[] = [
  { campo: "modificable_por_decision", texto: "Se puede modificar mediante una decisión real" },
  { campo: "medida_antes_del_resultado", texto: "Se mide antes del resultado" },
  { campo: "no_define_el_objetivo", texto: "No es parte de la definición del objetivo" },
];

export const FILTROS_LOTE = [
  { valor: "todos", etiqueta: "Todos" },
  { valor: "alcanzado", etiqueta: "Alcanzado" },
  { valor: "no_alcanzable", etiqueta: "No alcanzable" },
  { valor: "requiere_revision", etiqueta: "Requiere revisión" },
  { valor: "ya_cumple", etiqueta: "Ya cumple" },
] as const;

const SIN_SUPUESTOS: Supuestos = {
  modificable_por_decision: false,
  medida_antes_del_resultado: false,
  no_define_el_objetivo: false,
  confirmado_en: null,
};

export function supuestosDe(c: Configuracion, variable: string): Supuestos {
  return c.supuestos?.[variable] ?? SIN_SUPUESTOS;
}

export const confirmados = (s: Supuestos) =>
  s.modificable_por_decision && s.medida_antes_del_resultado && s.no_define_el_objetivo && !!s.confirmado_en;

/** Marca o desmarca un supuesto; al quedar los tres marcados se guarda la fecha de confirmación. */
export function conSupuesto(
  c: Configuracion, variable: string, campo: keyof Omit<Supuestos, "confirmado_en">, valor: boolean,
  fecha: () => string = () => new Date().toISOString().slice(0, 19),
): Configuracion {
  const actuales = { ...supuestosDe(c, variable), [campo]: valor };
  const todos = actuales.modificable_por_decision && actuales.medida_antes_del_resultado && actuales.no_define_el_objetivo;
  actuales.confirmado_en = todos ? (actuales.confirmado_en ?? fecha()) : null;
  return { ...c, supuestos: { ...(c.supuestos ?? {}), [variable]: actuales } };
}

export function conAccion(c: Configuracion, variable: string, cambios: Partial<Accion>): Configuracion {
  return { ...c, acciones: { ...c.acciones, [variable]: { ...c.acciones[variable], ...cambios } } };
}

/** Incorpora las acciones y supuestos que el núcleo completa (p. ej. al cambiar las modificables). */
export function completarCon(borrador: Configuracion, completada: Configuracion): Configuracion {
  const acciones: Configuracion["acciones"] = {};
  for (const [v, a] of Object.entries(completada.acciones)) acciones[v] = borrador.acciones[v] ?? a;
  const supuestos: NonNullable<Configuracion["supuestos"]> = {};
  for (const v of Object.keys(completada.acciones)) supuestos[v] = borrador.supuestos?.[v] ?? completada.supuestos?.[v] ?? SIN_SUPUESTOS;
  return { ...borrador, acciones, supuestos };
}

export const mismaConfiguracion = (a: Configuracion, b: Configuracion) => JSON.stringify(a) === JSON.stringify(b);

/** Errores de la validación por campo (`acciones.BMI.costo` → mensaje). */
export function erroresPorCampo(errores: { campo: string; mensaje: string }[] | undefined): Record<string, string> {
  return Object.fromEntries((errores ?? []).map((e) => [e.campo, e.mensaje]));
}

/** Intervenciones del explorador de escenarios que reproducen una prescripción (para ajustarla). */
export function intervencionesDe(resultado: Resultado): Intervenciones {
  const intervenciones: Intervenciones = {};
  for (const a of resultado.acciones) {
    intervenciones[a.variable] = {
      modo: "fijar",
      valor: a.tipo === "continua" && a.despues_numerico !== null ? a.despues_numerico : (a.despues as string | number),
    };
  }
  return intervenciones;
}

export interface VarianteEscenario {
  indice_test: number | null;
  intervenciones: Intervenciones;
}

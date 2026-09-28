// Borrador por proyecto de lo que el usuario elige antes de guardar: la acción
// de cada hallazgo (y si la confirmó) y las ediciones de valores concretos.
// Las decisiones las calcula siempre el núcleo (POST .../decisiones/previsualizar);
// aquí solo se superponen los valores editados (orden, grupos, conversiones).
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import type { Esquemas } from "../api/cliente";

type Decisiones = Esquemas["DecisionesUsuario"];
type Conversion = Esquemas["ConversionUnidades"];

/** Los campos numéricos admiten texto mientras se editan: el servidor los valida (422 por campo). */
export type ConversionEditada = Pick<Conversion, "condicion"> & {
  umbral: number | string;
  restar: number | string;
  multiplicar: number | string;
};

export interface Ediciones {
  ordenes: Record<string, unknown[]>;
  grupos: Record<string, Record<string, number>>;
  conversiones: Record<string, ConversionEditada>;
}

export interface Borrador {
  /** Identificador del hallazgo → acción elegida. Sin entrada = sugerida. */
  elecciones: Record<string, string>;
  /** Hallazgos cuya acción el usuario eligió explícitamente. */
  confirmadas: Record<string, boolean>;
  ediciones: Ediciones;
}

export const BORRADOR_VACIO: Borrador = {
  elecciones: {},
  confirmadas: {},
  ediciones: { ordenes: {}, grupos: {}, conversiones: {} },
};

/** Borrador a partir de decisiones ya guardadas: todo queda confirmado y editado como estaba. */
export function borradorDesdeGuardadas(decisiones: Decisiones): Borrador {
  const elecciones: Record<string, string> = {};
  const confirmadas: Record<string, boolean> = {};
  for (const [id, accion] of Object.entries(decisiones.acciones_hallazgos)) {
    elecciones[id] = accion.accion;
    confirmadas[id] = true;
  }
  const ediciones: Ediciones = { ordenes: {}, grupos: {}, conversiones: {} };
  for (const [columna, codificacion] of Object.entries(decisiones.codificaciones)) {
    if (codificacion.tipo === "ordinal" && codificacion.orden) ediciones.ordenes[columna] = codificacion.orden;
    if (codificacion.tipo === "agrupacion" && codificacion.grupos) ediciones.grupos[columna] = codificacion.grupos as Record<string, number>;
  }
  for (const c of decisiones.conversiones) {
    ediciones.conversiones[c.columna] = { condicion: c.condicion, umbral: c.umbral, restar: c.restar, multiplicar: c.multiplicar };
  }
  return { elecciones, confirmadas, ediciones };
}

/**
 * Texto numérico a número: admite coma decimal y fracciones («5/9»). Si no es un
 * número se devuelve el texto tal cual para que el servidor lo rechace en su campo.
 */
export function comoNumero(valor: number | string): number | string {
  if (typeof valor === "number") return valor;
  const texto = valor.trim().replace(",", ".");
  const fraccion = /^(-?\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/.exec(texto);
  if (fraccion && Number(fraccion[2]) !== 0) return Number(fraccion[1]) / Number(fraccion[2]);
  return texto !== "" && Number.isFinite(Number(texto)) ? Number(texto) : valor;
}

/** Superpone las ediciones a las decisiones calculadas por el núcleo (solo donde siguen aplicando). */
export function aplicarEdiciones(base: Decisiones, ediciones: Ediciones): Decisiones {
  const codificaciones = { ...base.codificaciones };
  for (const [columna, codificacion] of Object.entries(codificaciones)) {
    if (codificacion.tipo === "ordinal" && ediciones.ordenes[columna]) {
      codificaciones[columna] = { ...codificacion, orden: ediciones.ordenes[columna] };
    }
    if (codificacion.tipo === "agrupacion" && ediciones.grupos[columna]) {
      codificaciones[columna] = { ...codificacion, grupos: ediciones.grupos[columna] };
    }
  }
  const conversiones = base.conversiones.map((c) => {
    const editada = ediciones.conversiones[c.columna];
    if (!editada) return c;
    return {
      ...c,
      condicion: editada.condicion,
      umbral: comoNumero(editada.umbral),
      restar: comoNumero(editada.restar),
      multiplicar: comoNumero(editada.multiplicar),
    } as Conversion;
  });
  return { ...base, codificaciones, conversiones };
}

interface ValorBorradores {
  obtener: (proyecto: string) => Borrador | undefined;
  fijar: (proyecto: string, cambiar: (anterior: Borrador) => Borrador) => void;
}

const ContextoBorradores = createContext<ValorBorradores | null>(null);

export function ProveedorBorradores({ children }: { children: ReactNode }) {
  const [borradores, setBorradores] = useState<Record<string, Borrador>>({});
  const obtener = useCallback((proyecto: string) => borradores[proyecto], [borradores]);
  const fijar = useCallback((proyecto: string, cambiar: (anterior: Borrador) => Borrador) => {
    setBorradores((todos) => ({ ...todos, [proyecto]: cambiar(todos[proyecto] ?? BORRADOR_VACIO) }));
  }, []);
  const valor = useMemo(() => ({ obtener, fijar }), [obtener, fijar]);
  return <ContextoBorradores.Provider value={valor}>{children}</ContextoBorradores.Provider>;
}

export function useBorrador(proyecto: string) {
  const contexto = useContext(ContextoBorradores);
  if (!contexto) throw new Error("useBorrador debe usarse dentro de ProveedorBorradores");
  const { obtener, fijar } = contexto;
  const borrador = obtener(proyecto);
  return useMemo(
    () => ({
      /** `undefined` hasta que se inicializa (desde decisiones guardadas o vacío). */
      borrador,
      inicializar: (inicial: Borrador) => fijar(proyecto, () => inicial),
      elegir: (hallazgo: string, accion: string) =>
        fijar(proyecto, (b) => ({
          ...b,
          elecciones: { ...b.elecciones, [hallazgo]: accion },
          confirmadas: { ...b.confirmadas, [hallazgo]: true },
        })),
      editar: (cambiar: (ediciones: Ediciones) => Ediciones) =>
        fijar(proyecto, (b) => ({ ...b, ediciones: cambiar(b.ediciones) })),
    }),
    [borrador, fijar, proyecto],
  );
}

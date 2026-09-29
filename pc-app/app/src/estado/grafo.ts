// Datos del grafo para Cytoscape a partir del resultado (solo presentación: las aristas, su
// orientación, las categorías y el orden de cada columna vienen del núcleo).
import type { Esquemas } from "../api/cliente";
import { clavePar } from "./ajustes";

type Resultado = Esquemas["ResultadoPC"];
export type Arista = Esquemas["AristaAgregada"];
export type Categoria = "objetivo" | Esquemas["CaracterizacionVariable"]["categoria"];

export const CATEGORIAS: Record<Categoria, { etiqueta: string; color: string; texto: string }> = {
  objetivo: { etiqueta: "Objetivo", color: "#d9480f", texto: "#ffffff" },
  causa_directa: { etiqueta: "Causa directa", color: "#2b8a3e", texto: "#ffffff" },
  causa_indirecta: { etiqueta: "Causa indirecta", color: "#8ce99a", texto: "#1b1f24" },
  consecuencia: { etiqueta: "Consecuencia", color: "#b197fc", texto: "#1b1f24" },
  ambigua: { etiqueta: "Ambigua", color: "#ffd43b", texto: "#1b1f24" },
  sin_camino: { etiqueta: "Sin camino", color: "#e9ecef", texto: "#495057" },
};

export const SIGNOS: Record<string, { etiqueta: string; color: string }> = {
  "1": { etiqueta: "Relación positiva", color: "#1971c2" },
  "-1": { etiqueta: "Relación negativa", color: "#e03131" },
  "0": { etiqueta: "Sin signo", color: "#868e96" },
};

export interface DatosNodo {
  id: string;
  etiqueta: string;
  categoria: Categoria;
  color: string;
  colorTexto: string;
  modificable: boolean;
}

export interface DatosArista extends Arista {
  /** Par sin orientación: la arista conserva su id aunque cambie de dirección. */
  id: string;
  source: string;
  target: string;
  color: string;
  ancho: number;
}

export function datosNodos(resultado: Resultado): DatosNodo[] {
  const objetivo = resultado.caracterizacion.objetivo;
  const porVariable = new Map(resultado.caracterizacion.variables.map((v) => [v.variable, v]));
  return resultado.variables.map((variable) => {
    const categoria: Categoria = variable === objetivo ? "objetivo" : (porVariable.get(variable)?.categoria ?? "sin_camino");
    return {
      id: variable,
      etiqueta: variable,
      categoria,
      color: CATEGORIAS[categoria].color,
      colorTexto: CATEGORIAS[categoria].texto,
      modificable: porVariable.get(variable)?.modificable ?? false,
    };
  });
}

export function datosAristas(resultado: Resultado): DatosArista[] {
  return resultado.aristas.map((a) => ({
    ...a,
    id: clavePar(a.origen, a.destino),
    source: a.origen,
    target: a.destino,
    color: SIGNOS[String(a.signo)]?.color ?? SIGNOS["0"].color,
    ancho: 1.5 + 5 * a.frecuencia_total,
  }));
}

/** Variables relacionadas con el objetivo (cualquier categoría salvo «sin camino»). */
export function relacionadasConObjetivo(resultado: Resultado): Set<string> {
  const relacionadas = new Set([resultado.caracterizacion.objetivo]);
  for (const v of resultado.caracterizacion.variables) if (v.categoria !== "sin_camino") relacionadas.add(v.variable);
  return relacionadas;
}

export const SEPARACION_X = 240;
export const SEPARACION_SUBCOLUMNA = 175;
export const SEPARACION_Y = 90;
/** Un nivel con más variables se reparte en varias subcolumnas bajo el mismo título. */
export const MAXIMO_POR_SUBCOLUMNA = 8;

/**
 * Posición inicial de cada variable (una columna por nivel, partida en subcolumnas si el
 * nivel es largo) y de los títulos de los niveles. `subcolumna` identifica la columna
 * visual de cada variable (para curvar las aristas entre variables de la misma).
 */
export function disposicionInicial(disposicion: Esquemas["ColumnaDisposicion"][]) {
  const filas = Math.min(MAXIMO_POR_SUBCOLUMNA, Math.max(1, ...disposicion.map((c) => c.variables.length)));
  const posiciones: Record<string, { x: number; y: number }> = {};
  const subcolumna: Record<string, string> = {};
  let x = 0;
  const titulos = disposicion.map((columna, i) => {
    const partes = Math.max(1, Math.ceil(columna.variables.length / MAXIMO_POR_SUBCOLUMNA));
    columna.variables.forEach((variable, indice) => {
      const parte = Math.floor(indice / MAXIMO_POR_SUBCOLUMNA);
      const enParte = columna.variables.slice(parte * MAXIMO_POR_SUBCOLUMNA, (parte + 1) * MAXIMO_POR_SUBCOLUMNA).length;
      const fila = indice % MAXIMO_POR_SUBCOLUMNA;
      posiciones[variable] = { x: x + parte * SEPARACION_SUBCOLUMNA, y: (fila - (enParte - 1) / 2) * SEPARACION_Y };
      subcolumna[variable] = `${i}.${parte}`;
    });
    const ancho = (partes - 1) * SEPARACION_SUBCOLUMNA;
    const titulo = { id: `titulo:${i}`, titulo: columna.titulo, x: x + ancho / 2, y: -((filas - 1) / 2) * SEPARACION_Y - 70 };
    x += ancho + SEPARACION_X;
    return titulo;
  });
  return { posiciones, titulos, subcolumna };
}

/** Camino de la variable al objetivo (o del objetivo a la variable) según su categoría. */
export function caminoAlObjetivo(v: Esquemas["CaracterizacionVariable"], objetivo: string): string {
  switch (v.categoria) {
    case "causa_directa":
    case "causa_indirecta":
      return [v.variable, ...v.a_traves_de, objetivo].join(" → ");
    case "consecuencia":
      return [objetivo, ...v.a_traves_de, v.variable].join(" → ");
    case "ambigua":
      return "Conectada con el objetivo solo por aristas sin orientar";
    default:
      return "Sin camino hasta el objetivo";
  }
}

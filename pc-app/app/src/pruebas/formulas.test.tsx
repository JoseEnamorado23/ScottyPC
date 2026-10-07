import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Esquemas } from "../api/cliente";
import { proyecto, renderizar, respuesta } from "./utilidades";

type Traza = Esquemas["TrazaSeleccionPrueba"];

const TRAZA: Traza = {
  prueba: "chisq", prueba_original: "chisq", cambia: false, resumen: "Se elige chisq.",
  entradas: [
    { nombre: "Columnas con faltantes", valor: "0", usada: true, nota: "Regla 1." },
    { nombre: "Tiempo estimado de PC", valor: "4000", usada: false, nota: "No influye en qué prueba se elige." },
  ],
  reglas: [
    { orden: 1, titulo: "Faltantes", condicion: "F>0", sustituida: "F=0", cumple: false, estado: "no_cumple", consecuencia: "mv_fisherz", detalle: null },
    { orden: 2, titulo: "Relaciones no monótonas", condicion: "\exists x", sustituida: "n=1", cumple: true, estado: "decide", consecuencia: "chisq", detalle: "Variables: variabilidad." },
  ],
  variables: [{
    nombre: "variabilidad", tipo_final: "continua", evaluada: true, no_monotona: true, criterio: "forma_u",
    resumen: "No monótona (la curva sube y baja).",
    pasos: [{
      id: "dependencia", titulo: "3. ¿Hay dependencia por intervalos?", formula: "p<\alpha", sustituida: "p=0{,}0001",
      resultado: "Hay dependencia.", cumple: true, nota: null,
      terminos: [{ simbolo: "p", descripcion: "valor p", valor: "0,0001", origen: "calculado" }],
    }],
  }],
  formulas_prueba: [],
  umbrales: [{
    nombre: "spearman_debil", simbolo: "\rho_0", descripcion: "Spearman débil", valor: 0.1, original: 0.1,
    minimo: 0, maximo: 1, paso: 0.01, entero: false,
  }],
  k: 2, avisos: [],
};

const RUTA = "/proyectos/p1/formulas";
const ETAPAS = { revision: "vigente", decisiones: "vigente", preparacion: "vigente", recomendacion: "vigente" } as const;

describe("Explorador de fórmulas", () => {
  it("muestra la regla que decide, lo que toma y lo que ignora, y las variables", async () => {
    renderizar(RUTA, {
      "GET /proyectos/p1": proyecto(ETAPAS),
      "POST /proyectos/p1/formulas/seleccion-prueba": TRAZA,
    });
    expect(await screen.findByText("Prueba: chisq")).toBeInTheDocument();
    expect(screen.getByText("2. Relaciones no monótonas")).toBeInTheDocument();
    expect(screen.getByText("Decide")).toBeInTheDocument();
    expect(screen.getByText("Tiempo estimado de PC").closest("tr")).toHaveTextContent("Ignora");
    expect(screen.getByText("variabilidad")).toBeInTheDocument();
    expect(screen.getByLabelText("Spearman débil")).toBeInTheDocument();
  });

  it("sin recomendación vigente (409) explica qué paso la genera", async () => {
    renderizar(RUTA, {
      "GET /proyectos/p1": proyecto({ revision: "vigente" }),
      "POST /proyectos/p1/formulas/seleccion-prueba": respuesta(409, {
        error: { codigo: "ETAPA_NO_VIGENTE", mensaje: "La etapa no está vigente.", detalles: null },
      }),
    });
    await waitFor(() => expect(screen.getByText("Todavía no hay fórmulas que explorar")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Ir a Recomendación" })).toBeInTheDocument();
  });
});

const ANALISIS: Esquemas["TrazaAnalisisPC"] = {
  version: 1, umbral: 0.6, umbral_guardado: 0.6, corridas_validas: 100,
  resumen: "Con τ = 0,6 se aceptan 1 aristas de 2 pares con alguna frecuencia.",
  fundamentos: [{
    id: "frecuencia", titulo: "2. Frecuencia de una arista", formula: "f\ge\tau", sustituida: "n=60",
    resultado: "Se acepta si aparece en 60 corridas.", cumple: null, terminos: [], nota: null,
  }],
  entradas: [{ nombre: "Correlación de Spearman", valor: "entrenamiento", usada: false, nota: "Solo da el signo." }],
  pares: [
    {
      a: "A", b: "B", estado: "aceptada", frecuencia: 0.9, margen: 0.3, roza_umbral: false, tipo: "dirigida",
      origen: "A", destino: "B", spearman: 0.5, signo: 1,
      pasos: [{ id: "frecuencia", titulo: "Frecuencia de la arista", formula: "f", sustituida: "f=0{,}9", resultado: "Se acepta.", cumple: true, terminos: [], nota: null }],
    },
    {
      a: "A", b: "C", estado: "debil", frecuencia: 0.45, margen: -0.15, roza_umbral: false, tipo: null,
      origen: null, destino: null, spearman: null, signo: null, pasos: [],
    },
  ],
  pares_omitidos: 0,
  variables: [{
    nombre: "A", categoria: "causa_directa", regla: "Hay una arista dirigida de la variable al objetivo.",
    camino: "\text{A}\ \rightarrow\ \text{Y}", frecuencia_con_objetivo: 0.9, modificable: true, candidata: true,
  }],
  cambios: [], candidatas: ["A"], candidatas_guardadas: ["A"],
  umbrales: [{
    nombre: "umbral_frecuencia", simbolo: "\tau", descripcion: "Frecuencia mínima de una arista", valor: 0.6,
    original: 0.6, minimo: 0.05, maximo: 1, paso: 0.01, entero: false,
  }],
  avisos: [],
};

describe("Explorador de fórmulas: análisis de PC", () => {
  it("muestra aristas con su estado, la caracterización y filtra por estado", async () => {
    renderizar(`${RUTA}?etapa=analisis-pc`, {
      "GET /proyectos/p1": proyecto({ ...ETAPAS, configuracion_pc: "vigente", analisis: "vigente" }),
      "POST /proyectos/p1/formulas/analisis-pc": ANALISIS,
    });
    expect(await screen.findByText("Resultado, versión 1")).toBeInTheDocument();
    expect(screen.getByText("A → B")).toBeInTheDocument();
    expect(screen.getByText("A — C")).toBeInTheDocument();
    expect(screen.getByText("Candidata")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Débiles"));
    expect(screen.queryByText("A → B")).not.toBeInTheDocument();
    expect(screen.getByText("A — C")).toBeInTheDocument();
  });

  it("sin análisis vigente lleva a la etapa que lo genera", async () => {
    renderizar(`${RUTA}?etapa=analisis-pc`, {
      "GET /proyectos/p1": proyecto(ETAPAS),
      "POST /proyectos/p1/formulas/analisis-pc": respuesta(409, {
        error: { codigo: "ETAPA_NO_VIGENTE", mensaje: "La etapa no está vigente.", detalles: null },
      }),
    });
    expect(await screen.findByRole("button", { name: "Ir a Análisis" })).toBeInTheDocument();
  });
});

const PASO = (id: string, titulo: string): Esquemas["PasoFormula"] => ({
  id, titulo, formula: "\eta", sustituida: "\eta=1", resultado: `${titulo}: resultado.`, cumple: null, terminos: [], nota: null,
});

const MODELO: Esquemas["TrazaModeloCausal"] = {
  objetivo: "Y",
  resumen: "2 mecanismos (1 complejos, 1 simples) para Y y sus ancestros.",
  fundamentos: [PASO("subgrafo", "1. Variables del modelo")],
  entradas: [{ nombre: "Variables fuera del subgrafo", valor: "D", usada: false, nota: "No son ancestros." }],
  mecanismos: [{
    variable: "B", rol: "intermedia", tipo: "continua", padres: ["A"], metrica: "r2", familia: "splines_ridge",
    nombre_familia: "Splines + Ridge",
    candidatos: [
      { tipo: "simple", familia: "lineal", nombre_familia: "Regresión lineal", puntuacion_cv: 0.6, error: null },
      { tipo: "complejo", familia: "splines_ridge", nombre_familia: "Splines + Ridge", puntuacion_cv: 0.7, error: null },
    ],
    mejora: 0.1, elegido: "simple", elegido_guardado: "complejo", origen: "automatico", cambiaria: true,
    puntuacion_cv: 0.6, puntuacion_test: 0.68, calidad_suficiente: true, resumen: "Splines + Ridge (complejo).",
    pasos: [PASO("parsimonia", "Regla de parsimonia"), PASO("caso", "Evaluado en el caso")],
  }],
  monotonia: [], referencia: [],
  controles: [{ variable: "A", valor: 0.5, minimo: 0, maximo: 1, mediana: 0.5, original: "10" }],
  umbrales: [{
    nombre: "umbral_parsimonia", simbolo: "\delta", descripcion: "Mejora mínima en CV", valor: 0.2, original: 0.02,
    minimo: 0, maximo: 0.5, paso: 0.005, entero: false,
  }],
  avisos: ["Con estos umbrales cambiaría el mecanismo de: B."],
};

describe("Explorador de fórmulas: modelo causal", () => {
  it("muestra cada mecanismo, sus candidatos, lo que cambiaría y el caso evaluado", async () => {
    renderizar(`${RUTA}?etapa=modelo-causal`, {
      "GET /proyectos/p1": proyecto({ ...ETAPAS, configuracion_pc: "vigente", analisis: "vigente", modelo_causal: "vigente" }),
      "POST /proyectos/p1/formulas/modelo-causal": MODELO,
    });
    expect(await screen.findByText("Modelo causal de Y")).toBeInTheDocument();
    expect(screen.getByText("B ← A")).toBeInTheDocument();
    expect(screen.getByText("Cambiaría a simple")).toBeInTheDocument();
    expect(screen.getByText("Con estos umbrales cambiaría el mecanismo de: B.")).toBeInTheDocument();
    expect(screen.getByLabelText("Valor de A")).toBeInTheDocument();
    expect(screen.getByText("Variables fuera del subgrafo").closest("tr")).toHaveTextContent("Ignora");
  });

  it("sin modelo vigente lleva a construirlo", async () => {
    renderizar(`${RUTA}?etapa=modelo-causal`, {
      "GET /proyectos/p1": proyecto(ETAPAS),
      "POST /proyectos/p1/formulas/modelo-causal": respuesta(409, {
        error: { codigo: "ETAPA_NO_VIGENTE", mensaje: "La etapa no está vigente.", detalles: null },
      }),
    });
    expect(await screen.findByRole("button", { name: "Ir a Modelo causal" })).toBeInTheDocument();
  });
});

const CALIBRACION: Esquemas["TrazaCalibracion"] = {
  mu: 0.01, mu_guardado: 0.01, cambia: false, exito_requerido: 0.95, casos: 100, ya_cumplen: 50, alcanzables: 80,
  no_alcanzables: 20,
  puntos: [
    { mu: 0.001, tasa: 1, exitos: 80, evaluados: 80, cumple: true, elegido: false },
    { mu: 0.01, tasa: 0.975, exitos: 78, evaluados: 80, cumple: true, elegido: true },
    { mu: 0.1, tasa: 0.5, exitos: 40, evaluados: 80, cumple: false, elegido: false },
  ],
  pasos: [PASO("regla", "3. Elección")], resumen: "μ* = 0,01.", advertencia: null, nota: "Nota de calibración.",
  umbrales: [{
    nombre: "exito_calibracion", simbolo: "s", descripcion: "Porcentaje de éxito", valor: 0.95, original: 0.95,
    minimo: 0.5, maximo: 1, paso: 0.01, entero: false,
  }],
};

const CASO: Esquemas["TrazaCaso"] = {
  indice: 7, medida: "probabilidad", direccion: "bajar", deseado: 0.3, antes: 0.7, despues: 0.29, alcanzado: true,
  ya_cumple: false, mu: 0.01, mu_guardado: 0.01, optimizador: "gradiente_proximal",
  explicacion: "Reducir X1 de 9,5 a 6.", fundamentos: [PASO("funcion", "Función que se minimiza")],
  perdida: [PASO("perdida_antes", "Sin actuar (d = 0)"), PASO("perdida_despues", "Con la prescripción")],
  acciones: [{
    variable: "X1", tipo: "continua", cambia: true, antes: "9,5", despues: "6", d: -0.35, costo: 1, penalizacion: 0.0035,
    contribucion: 0.3, restriccion_activa: null, pasos: [PASO("escala", "Cambio en escala normalizada")],
  }],
  entradas: [{ nombre: "Modelo de referencia", valor: "todas las variables", usada: false, nota: "No decide." }],
  restricciones: [], avisos: [],
};

describe("Explorador de fórmulas: prescripción", () => {
  const ETAPAS_TODAS = {
    ...ETAPAS, configuracion_pc: "vigente", analisis: "vigente", modelo_causal: "vigente", prescripcion: "vigente",
  } as const;

  it("muestra la rejilla de μ con el elegido y, al elegir un caso, su pérdida descompuesta", async () => {
    const usuario = userEvent.setup();
    renderizar(`${RUTA}?etapa=prescripcion`, {
      "GET /proyectos/p1": proyecto(ETAPAS_TODAS),
      "POST /proyectos/p1/formulas/prescripcion/calibracion": CALIBRACION,
      "GET /proyectos/p1/modelo-causal/casos": {
        total: 1, pagina: 1, por_pagina: 50, filas: [{ indice: 7, valores: {}, objetivo: 1 }],
      },
      "POST /proyectos/p1/formulas/prescripcion/caso": CASO,
    });
    expect(await screen.findByText("μ* = 0,01.")).toBeInTheDocument();
    expect(screen.getByText("Elegido")).toBeInTheDocument();
    expect(screen.getByLabelText("Porcentaje de éxito")).toBeInTheDocument();

    await usuario.click(screen.getByText("Un caso"));
    await usuario.click(await screen.findByRole("combobox", { name: "Fila de test" }));
    await usuario.click(await screen.findByRole("option", { name: "Fila 7 · objetivo observado: 1", hidden: true }));
    expect(await screen.findByText("Reducir X1 de 9,5 a 6.")).toBeInTheDocument();
    expect(screen.getByText("Con la prescripción")).toBeInTheDocument();
    expect(screen.getByText("9,5 → 6")).toBeInTheDocument();
  });

  it("sin calibración lleva a Prescripción", async () => {
    renderizar(`${RUTA}?etapa=prescripcion`, {
      "GET /proyectos/p1": proyecto(ETAPAS_TODAS),
      "POST /proyectos/p1/formulas/prescripcion/calibracion": respuesta(409, {
        error: { codigo: "MU_SIN_CALIBRAR", mensaje: "Todavía no se calibró μ.", detalles: null },
      }),
    });
    expect(await screen.findByText("Todavía no hay una calibración de μ")).toBeInTheDocument();
  });
});

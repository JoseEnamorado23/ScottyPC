// Datos de ejemplo del modelo causal: Age → Glucose → Outcome, BMI → Outcome, y la categoría
// «zona» (dummies zona=b y zona=c) → Outcome.
import type { Esquemas } from "../api/cliente";
import { proyecto } from "./utilidades";

type Problema = Esquemas["ProblemaAplicabilidad"];

export const ETAPAS_ANALIZADO = {
  revision: "vigente", decisiones: "vigente", preparacion: "vigente", recomendacion: "vigente",
  configuracion_pc: "vigente", analisis: "vigente",
} as const;

export const bloqueante: Problema = {
  codigo: "ARISTA_SIN_ORIENTAR",
  severidad: "bloqueante",
  mensaje: "La arista Pregnancies — Age está sin orientar y toca al objetivo o a sus ancestros.",
  accion: "Oriente la arista Pregnancies — Age en Resultados.",
  destino: "resultados",
  variables: ["Pregnancies", "Age"],
};

export const advertencia: Problema = {
  codigo: "FUERA_DEL_SUBGRAFO",
  severidad: "advertencia",
  mensaje: "Estas variables no son ancestros del objetivo y el modelo las ignora: BloodPressure.",
  accion: "No requiere acción.",
  destino: null,
  variables: ["BloodPressure"],
};

export function aplicabilidad(problemas: Problema[]): Esquemas["Aplicabilidad"] {
  return {
    problemas,
    bloqueado: problemas.some((p) => p.severidad === "bloqueante"),
    version_resultado: 2,
    subgrafo: {
      objetivo: "Outcome",
      variables: ["Age", "BMI", "zona=b", "Glucose", "Outcome"],
      padres: { Age: [], BMI: [], "zona=b": [], Glucose: ["Age"], Outcome: ["Glucose", "BMI", "zona=b"] },
      aristas: [["Age", "Glucose"], ["Glucose", "Outcome"], ["BMI", "Outcome"], ["zona=b", "Outcome"]],
      sin_orientar: [],
      fuera: ["BloodPressure"],
    },
  };
}

const candidato = (tipo: "simple" | "complejo", familia: string, nombre: string, cv: number | null, error: string | null = null) => ({
  tipo, familia, nombre_familia: nombre, puntuacion_cv: cv, umbral_cv: null, error, rescate: [],
});

const efecto = (padre: string, coeficiente: number | null, x: number[], y: number[], histograma = true): Esquemas["EfectoParcial"] => ({
  padre,
  coeficiente,
  signo: 1,
  x,
  y,
  histograma: histograma ? { tipo: "histograma", limites: [x[0], (x[0] + x[x.length - 1]) / 2, x[x.length - 1]], valores: null, conteos: [30, 12] } : null,
});

export const MODELO: Esquemas["ModeloCausal"] = {
  vigente: true,
  motivo_desactualizado: null,
  filas_test: 3,
  modelo: {
    version_formato: 1,
    objetivo: "Outcome",
    tipo_objetivo: "binario",
    clase_positiva: null,
    resultado_pc: { version: 2, sha256: "a".repeat(64) },
    train_sha256: "b".repeat(64),
    semilla: 42,
    configuracion: { monotonia: {}, mecanismos: {}, pesos_clase: false },
    subgrafo: {
      variables: ["Age", "BMI", "zona=b", "Glucose", "Outcome"],
      padres: { Age: [], BMI: [], "zona=b": [], Glucose: ["Age"], Outcome: ["Glucose", "BMI", "zona=b"] },
      aristas: [["Age", "Glucose"], ["Glucose", "Outcome"], ["BMI", "Outcome"], ["zona=b", "Outcome"]],
      fuera: ["BloodPressure"],
      descendientes_objetivo: [],
    },
    variables: {},
    monotonia: [
      { padre: "Glucose", restriccion: "creciente", origen: "automatico", motivo: "Relación monótona (ρ = +0,48)." },
      { padre: "BMI", restriccion: null, origen: "automatico", motivo: "Relación no monótona: sube y baja." },
      { padre: "zona=b", restriccion: null, origen: "no_aplica", motivo: "Padre discreto." },
    ],
    umbral_decision: 0.35,
    pesos_clase: false,
    imputadas_en_modelo: [],
    advertencias: [],
    versiones: { pygam: "0.12.0" },
    huella: "c".repeat(64),
    mecanismos: {},
  },
  evaluacion: {
    objetivo: "Outcome",
    mecanismos: [
      {
        variable: "Glucose", rol: "intermedia", tipo: "continua", padres: ["Age"], familia: "lineal",
        nombre_familia: "Regresión lineal", elegido: "simple", origen: "automatico",
        motivo: "El modelo complejo solo cambia la validación cruzada en +0,001.", metrica: "r2",
        candidatos: [candidato("simple", "lineal", "Regresión lineal", 0.08), candidato("complejo", "splines_ridge", "Splines + Ridge", 0.081)],
        puntuacion_cv: 0.08, puntuacion_test: 0.05, filas_train: 530, filas_test: 230, rescate: [],
        efectos: [efecto("Age", 0.3, [21, 81], [100, 140], false)],
      },
      {
        variable: "Outcome", rol: "objetivo", tipo: "binaria", padres: ["Glucose", "BMI", "zona=b"], familia: "logistica",
        nombre_familia: "Regresión logística", elegido: "simple", origen: "automatico",
        motivo: "Se prefiere el simple.", metrica: "exactitud_balanceada",
        candidatos: [candidato("simple", "logistica", "Regresión logística", 0.75), candidato("complejo", "gam_logistico", "GAM logístico", 0.76)],
        puntuacion_cv: 0.75, puntuacion_test: 0.73, filas_train: 537, filas_test: 231, rescate: [],
        efectos: [
          efecto("Glucose", 3.2, [57, 127.5, 198], [0.05, 0.3, 0.8]),
          efecto("BMI", 2.1, [18, 42, 67], [0.1, 0.35, 0.6]),
          efecto("zona=b", 0.4, [0, 1], [0.3, 0.38]),
        ],
      },
    ],
    evaluacion_objetivo: {
      umbral_decision: 0.35,
      pesos_clase: false,
      cv: { exactitud_balanceada: 0.754, auc: 0.836, brier: 0.153 },
      test: { exactitud_balanceada: 0.732, auc: 0.828, brier: 0.168 },
      calibracion: {
        cv: [{ probabilidad_media: 0.1, frecuencia_observada: 0.12, filas: 50 }, { probabilidad_media: 0.7, frecuencia_observada: 0.68, filas: 50 }],
        test: [{ probabilidad_media: 0.12, frecuencia_observada: 0.1, filas: 20 }, { probabilidad_media: 0.72, frecuencia_observada: 0.75, filas: 20 }],
      },
      prevalencia_train: 0.35,
    },
    referencia: {
      familia: "Regresión logística",
      variables: ["Age", "BMI", "Glucose", "BloodPressure", "zona=b", "zona=c"],
      umbral: 0.4,
      cv: { exactitud_balanceada: 0.8, auc: 0.9, brier: 0.12 },
      test: { exactitud_balanceada: 0.78, auc: 0.88, brier: 0.13 },
      comparacion: [{ metrica: "auc", modelo_causal: 0.836, referencia: 0.9, diferencia: -0.064 }],
      principal: "auc",
      advertencia: "El mecanismo del objetivo predice claramente peor que un modelo con todas las variables (costo de la parsimonia).",
    },
  },
  controles: [
    { nombre: "Age", control: "numerica", columnas: ["Age"], categorias: [], minimo: 21, maximo: 81, rol: "raiz", columnas_en_modelo: ["Age"] },
    { nombre: "BMI", control: "numerica", columnas: ["BMI"], categorias: [], minimo: 18.2, maximo: 67.1, rol: "raiz", columnas_en_modelo: ["BMI"] },
    { nombre: "zona", control: "grupo_one_hot", columnas: ["zona=b", "zona=c"], categorias: ["a", "b", "c"], minimo: null, maximo: null, rol: "raiz", columnas_en_modelo: ["zona=b"] },
    { nombre: "Glucose", control: "numerica", columnas: ["Glucose"], categorias: [], minimo: 57, maximo: 198, rol: "intermedia", columnas_en_modelo: ["Glucose"] },
  ],
};

export const CASOS: Esquemas["CasosModelo"] = {
  total: 2,
  pagina: 1,
  por_pagina: 50,
  filas: [
    { indice: 7, valores: { Age: 50, BMI: 30, zona: "a", Glucose: 120 }, objetivo: 1 },
    { indice: 12, valores: { Age: 25, BMI: 22, zona: "b", Glucose: 90 }, objetivo: 0 },
  ],
};

const valor = (
  variable: string, rol: "raiz" | "intermedia" | "objetivo", antes: number, despues: number,
  extra: Partial<Esquemas["ValorContrafactual"]> = {},
): Esquemas["ValorContrafactual"] => ({
  variable, rol, tipo: rol === "objetivo" ? "binaria" : "continua", grupo: null, antes, despues,
  antes_numerico: antes, despues_numerico: despues, cambio: despues - antes, intervenida: false,
  extrapolacion: false, observado: rol !== "objetivo", ...extra,
});

/** Escenario: sin intervenciones no cambia nada; con Age, pasa por Glucose. */
export function escenario(solicitud: Esquemas["SolicitudContrafactual"]): Esquemas["ResultadoContrafactual"] {
  const conAge = solicitud.intervenciones?.find((i) => i.variable === "Age");
  const delta = conAge ? Number(conAge.valor) : 0;
  const despues = 0.4 + delta * 0.002;
  return {
    objetivo: "Outcome",
    medida: "probabilidad",
    antes: 0.4,
    despues,
    cambio: despues - 0.4,
    umbral_decision: 0.35,
    clase_antes: 1,
    clase_despues: despues >= 0.35 ? 1 : 0,
    valores: [
      valor("Age", "raiz", 50, 50 + delta, { intervenida: !!conAge, extrapolacion: 50 + delta > 81 }),
      valor("BMI", "raiz", 30, 30),
      valor("zona=b", "raiz", 0, 0, { grupo: "zona" }),
      valor("Glucose", "intermedia", 120, 120 + delta * 0.3),
      valor("Outcome", "objetivo", 0.4, despues),
    ],
    traza: conAge
      ? [
          { variable: "Age", causa: "intervencion", antes: 50, despues: 50 + delta, cambio: delta, por_padre: [] },
          { variable: "Glucose", causa: "propagacion", antes: 120, despues: 120 + delta * 0.3, cambio: delta * 0.3, por_padre: [{ padre: "Age", contribucion: delta * 0.3 }] },
          { variable: "Outcome", causa: "propagacion", antes: 0.4, despues, cambio: despues - 0.4, por_padre: [{ padre: "Glucose", contribucion: despues - 0.4 }] },
        ]
      : [],
    avisos: 50 + delta > 81
      ? [{ codigo: "EXTRAPOLACION", mensaje: "La intervención en Age sale del rango observado en entrenamiento.", variables: ["Age"] }]
      : [],
    aproximado: false,
    muestras: 1,
    extrapolacion: 50 + delta > 81,
    caso: { origen: "test", indice: 7, observado_objetivo: 1 },
  };
}

export function simulacionModelo({ conModelo = true, problemas = [advertencia] as Problema[] } = {}) {
  const etapas = conModelo ? { ...ETAPAS_ANALIZADO, modelo_causal: "vigente" as const } : ETAPAS_ANALIZADO;
  return {
    "GET /proyectos/p1": proyecto(etapas),
    "POST /proyectos/p1/modelo-causal/aplicabilidad": aplicabilidad(problemas),
    "GET /proyectos/p1/modelo-causal": MODELO,
    "GET /proyectos/p1/modelo-causal/casos": CASOS,
    "POST /proyectos/p1/modelo-causal/contrafactual": (p: { cuerpo: unknown }) =>
      escenario(p.cuerpo as Esquemas["SolicitudContrafactual"]),
  };
}

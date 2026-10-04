// Datos de ejemplo de la prescripción, sobre el modelo causal de datosModeloCausal.
import type { Esquemas } from "../api/cliente";
import { MODELO, simulacionModelo } from "./datosModeloCausal";
import { proyecto } from "./utilidades";

type Configuracion = Esquemas["ConfiguracionPrescripcion"];
type Problema = Esquemas["ProblemaAplicabilidad"];

export const ETAPAS_CON_MODELO = {
  revision: "vigente", decisiones: "vigente", preparacion: "vigente", recomendacion: "vigente",
  configuracion_pc: "vigente", analisis: "vigente", modelo_causal: "vigente",
} as const;

const SIN_SUPUESTOS = { modificable_por_decision: false, medida_antes_del_resultado: false, no_define_el_objetivo: false, confirmado_en: null };

export function configuracion(confirmada = false): Configuracion {
  const supuestos = confirmada
    ? { modificable_por_decision: true, medida_antes_del_resultado: true, no_define_el_objetivo: true, confirmado_en: "2026-09-29T10:00:00" }
    : SIN_SUPUESTOS;
  return {
    modificables: ["BMI", "Glucose", "BloodPressure"],
    objetivo: { direccion: "bajar", valor: 0.25, clase_positiva: 1 },
    acciones: {
      BMI: { variable: "BMI", permitida: true, direccion: "ambas", minimo: 18.2, maximo: 67.1, cambio_maximo: 12.2, costo: 1, estados_permitidos: null },
      Glucose: { variable: "Glucose", permitida: true, direccion: "ambas", minimo: 57, maximo: 198, cambio_maximo: 35.25, costo: 1, estados_permitidos: null },
    },
    supuestos: { BMI: { ...supuestos }, Glucose: { ...supuestos } },
    mu: 0.01,
    optimizador: "gradiente_proximal",
    rejilla_mu: [0.001, 0.01, 0.1],
    exito_calibracion: 0.95,
    arranques_aleatorios: 4,
    iteraciones_maximas: 300,
    tolerancia: 1e-8,
    tau_suavizado: 0.25,
    poblacion: 40,
    generaciones: 60,
    alfa_blx: 0.5,
    probabilidad_mutacion: 0.2,
    elite: 2,
  };
}

export function vista(c: Configuracion, guardada: boolean): Esquemas["VistaConfiguracionPrescripcion"] {
  return {
    configuracion: c,
    guardada,
    prescriptivas: ["BMI", "Glucose"],
    sin_camino: ["BloodPressure"],
    desconocidas: [],
    controles: MODELO.controles.filter((x) => x.nombre === "BMI" || x.nombre === "Glucose"),
    variables_grafo: ["Age", "BMI", "Glucose", "BloodPressure", "zona=b", "zona=c"],
    modificables_pc: ["BMI", "Glucose", "BloodPressure"],
    objetivo: "Outcome",
    medida: "probabilidad",
    umbral_decision: 0.35,
    calibracion: null,
    mu_efectivo: 0.01,
    aviso: "Recomendaciones basadas en datos observacionales. No reemplazan el criterio de un experto ni una validación experimental.",
  };
}

export const supuestosSinConfirmar: Problema = {
  codigo: "SUPUESTOS_SIN_CONFIRMAR", severidad: "bloqueante",
  mensaje: "Falta confirmar la declaración de supuestos de: BMI, Glucose.", accion: "Confirme la declaración de supuestos.",
  destino: "prescripcion", variables: ["BMI", "Glucose"],
};

export const sinPrescriptivas: Problema = {
  codigo: "SIN_PRESCRIPTIVAS", severidad: "bloqueante",
  mensaje: "Con estos datos no hay variables prescriptivas: una variable prescriptiva debe ser a la vez ancestro del objetivo y modificable, y no hay ninguna variable marcada como modificable.",
  accion: "Marque como modificables variables que sean causas del objetivo.", destino: "prescripcion", variables: [],
};

export const RESULTADO: Esquemas["ResultadoPrescripcion"] = {
  caso: { origen: "test", indice: 7 },
  objetivo: "Outcome", medida: "probabilidad", direccion: "bajar", clase_positiva: 1, deseado: 0.25, antes: 0.62, despues: 0.25,
  alcanzado: true, ya_cumple: false, falta: 0,
  acciones: [
    { variable: "Glucose", tipo: "continua", antes: 148, despues: 131, antes_numerico: 148, despues_numerico: 131, cambio: -17, contribucion: 0.22, restriccion_activa: null, extrapolacion: false, mantener: false },
    { variable: "BMI", tipo: "continua", antes: 34.2, despues: 30.1, antes_numerico: 34.2, despues_numerico: 30.1, cambio: -4.1, contribucion: 0.08, restriccion_activa: null, extrapolacion: false, mantener: false },
  ],
  sin_cambio: [],
  restricciones_activas: [],
  extrapolacion: false, aproximado: false, requiere_revision: true,
  referencia: { despues: 0.31, alcanzado: false },
  explicacion: "Reducir Glucose de 148 a 131 (−17) y reducir BMI de 34,2 a 30,1 (−4,1). Con esto, la probabilidad baja de 0,62 a 0,25.",
  costo_total: 0.2, optimizador: "gradiente_proximal", mu: 0.01, segundos: 0.1,
  traza: [], valores: [], avisos: [],
};

const meta = {
  numero: 1, origen: "test" as const, ruta_csv: null, casos: 2, mu: 0.01, optimizador: "gradiente_proximal",
  filas_con_problemas: [], columnas_ignoradas: [], huella_modelo: "h", creado_en: "2026-09-29",
  resumen: { alcanzado: 1, no_alcanzable: 1, requiere_revision: 1, ya_cumple: 0 },
};

const NO_ALCANZABLE: Esquemas["ResultadoPrescripcion"] = {
  ...RESULTADO, caso: { origen: "test", indice: 12 }, alcanzado: false, despues: 0.4, falta: 0.15, requiere_revision: false,
  restricciones_activas: [{ variable: "Glucose", restriccion: "cambio_maximo", mensaje: "está en su cambio máximo" }],
  explicacion: "No alcanza el objetivo.",
};

export const EVALUACION: Esquemas["InformeEvaluacion"] = {
  meta: { numero: 1, casos: 113, mu: 0.01, optimizador: "gradiente_proximal", tasa_exito: 0.796, huella_modelo: "h", creado_en: "2026-09-29" },
  evaluacion: {
    casos: 113, tasa_exito: 0.796, no_alcanzables: 23,
    cambio_medio: { Glucose: { cambio_medio: -22, cambio_absoluto_medio: 22, usos: 113, rango_train: 141 } },
    porcentaje_acciones_en_cero: 6.6, porcentaje_requiere_revision: 21.2, porcentaje_extrapolacion: 0,
    sensibilidad_cambio_maximo: [{ fraccion_rango: 0.1, tasa_exito: 0.38, costo_medio: 0.16 }, { fraccion_rango: 0.25, tasa_exito: 0.8, costo_medio: 0.27 }, { fraccion_rango: 0.4, tasa_exito: 0.98, costo_medio: 0.3 }],
    sensibilidad_mu: [{ mu: 0.005, factor: 0.5, tasa_exito: 0.8, costo_medio: 0.28 }, { mu: 0.01, factor: 1, tasa_exito: 0.8, costo_medio: 0.27 }, { mu: 0.02, factor: 2, tasa_exito: 0.8, costo_medio: 0.28 }],
    comparacion_optimizadores: [
      { optimizador: "gradiente_proximal", tasa_exito: 0.796, costo_medio: 0.275, segundos_medios: 0.1 },
      { optimizador: "genetico", tasa_exito: 0.796, costo_medio: 0.283, segundos_medios: 0.64 },
    ],
    mcnemar: { solo_gradiente: 0, solo_genetico: 0, p_valor: 1, prueba: "McNemar exacta (binomial sobre los pares discordantes)" },
    mu: 0.01,
    texto: "Esta es una evaluación INTERNA: indica qué lograría el prescriptor según el modelo causal.",
  },
};

export function simulacionPrescripcion({ guardada = true, confirmada = true, problemas = [] as Problema[] } = {}) {
  const etapas = guardada ? { ...ETAPAS_CON_MODELO, prescripcion: "vigente" as const } : ETAPAS_CON_MODELO;
  return {
    ...simulacionModelo(),
    "GET /proyectos/p1": proyecto(etapas),
    "GET /proyectos/p1/prescripcion/configuracion": vista(configuracion(confirmada), guardada),
    "POST /proyectos/p1/prescripcion/condiciones": { problemas, bloqueado: problemas.some((p) => p.severidad === "bloqueante"), aviso: "" },
    "POST /proyectos/p1/prescripcion/configuracion/validar": (p: { cuerpo: unknown }) => ({
      valida: true, errores: [], condiciones: [], configuracion: p.cuerpo,
    }),
    "PUT /proyectos/p1/prescripcion/configuracion": (p: { cuerpo: unknown }) => vista(p.cuerpo as Configuracion, true),
    "POST /proyectos/p1/prescripcion/caso": RESULTADO,
    "GET /proyectos/p1/prescripcion/lotes": [meta],
    "GET /proyectos/p1/prescripcion/lotes/1": (p: { consulta: Record<string, string> }) => {
      const filas = p.consulta.filtro === "no_alcanzable" ? [NO_ALCANZABLE] : [RESULTADO, NO_ALCANZABLE];
      return { meta, total: filas.length, pagina: 1, por_pagina: 50, filas };
    },
    "GET /proyectos/p1/prescripcion/evaluaciones": [EVALUACION.meta],
    "GET /proyectos/p1/prescripcion/evaluaciones/1": EVALUACION,
  };
}

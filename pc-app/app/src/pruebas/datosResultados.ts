// Resultado de PC de ejemplo y sidecar simulado con versiones (pantalla Resultados).
import type { Esquemas } from "../api/cliente";
import { clavePar } from "../estado/ajustes";
import { proyecto as proyectoBase, respuesta, type Peticion } from "./utilidades";

type Resultado = Esquemas["ResultadoPC"];
type Arista = Esquemas["AristaAgregada"];
type Orientacion = Esquemas["OrientacionManual"];

export const ETAPAS = {
  revision: "vigente", decisiones: "vigente", preparacion: "vigente", recomendacion: "vigente",
  configuracion_pc: "vigente", analisis: "vigente",
} as const;

export const arista = (origen: string, destino: string, tipo: Arista["tipo"], total: number, signo = 1): Arista => ({
  origen, destino, tipo, frecuencia_total: total, frecuencia_origen_destino: tipo === "sin_orientar" ? 0.1 : total - 0.05,
  frecuencia_destino_origen: 0.05, frecuencia_sin_orientar: tipo === "sin_orientar" ? total - 0.15 : 0,
  spearman: 0.3 * signo, signo, justificacion: null,
});

export const variable = (
  nombre: string, categoria: Esquemas["CaracterizacionVariable"]["categoria"], frecuencia: number, modificable = false, a_traves_de: string[] = [],
): Esquemas["CaracterizacionVariable"] => ({ variable: nombre, categoria, a_traves_de, frecuencia_con_objetivo: frecuencia, grupo_redundante: null, modificable });

export const CONFIGURACION: Esquemas["ConfiguracionPC"] = {
  prueba: "fisherz", alpha: 0.05, corridas_bootstrap: 100, fraccion_submuestra: 0.8, umbral_frecuencia: 0.6,
  max_k: null, semilla: 42, procesos: 1, niveles: [["Age", "Insulin", "BloodPressure"], ["BMI"], ["Glucose"], ["Outcome"]],
  modificables: ["Glucose", "BMI", "BloodPressure"], orientaciones_manuales: [], punto_control_cada: 10,
  modo_ejecucion: "adaptativo", umbral_paralelo_s: 30, nombres_niveles: ["Demografía", "Medidas", "Laboratorio", "Diagnóstico"],
};

/** Doble del resultado: solo lo que muestran las pantallas (las reglas están en el núcleo). */
export function resultado({ umbral = 0.6, orientaciones = [] as Orientacion[], version = 1 as number | null, candidatas = true } = {}): Resultado {
  const manual = (a: Arista) => {
    const o = orientaciones.find((x) => clavePar(x.origen, x.destino) === clavePar(a.origen, a.destino));
    return o ? { ...a, origen: o.origen, destino: o.destino, tipo: "manual" as const, justificacion: o.justificacion ?? "" } : a;
  };
  const aristas = [
    arista("Glucose", "Outcome", "dirigida", 0.95),
    arista("BMI", "Outcome", "dirigida", 0.8),
    arista("Age", "Glucose", "dirigida", 0.7),
    arista("BloodPressure", "BMI", "sin_orientar", 0.65),
    ...(umbral <= 0.45 ? [arista("Insulin", "Outcome", "dirigida", 0.45, -1)] : []),
  ].map(manual);
  const ajustada = umbral !== 0.6 || orientaciones.length > 0;
  return {
    configuracion: CONFIGURACION,
    receta: { archivo: "diabetes.csv", hoja: null, sha256: "abc", objetivo: "Outcome", tipo_objetivo: "binario" },
    corridas: { totales: 100, completadas: 100, validas: 100, fallidas: [], completo: true },
    tiempo_s: 12, ejecucion: null, limites_discretizacion: {},
    variables: ["Age", "Insulin", "BMI", "BloodPressure", "Glucose", "Outcome"],
    aristas,
    ciclos: [],
    caracterizacion: {
      objetivo: "Outcome",
      variables: [
        variable("Age", "causa_indirecta", 0.2, false, ["Glucose"]),
        variable("Insulin", umbral <= 0.45 ? "causa_directa" : "sin_camino", 0.45),
        variable("BMI", "causa_directa", 0.8, true),
        variable("BloodPressure", "ambigua", 0.1, true),
        variable("Glucose", "causa_directa", 0.95, true),
      ],
      candidatas_prescriptivas: candidatas ? ["BMI", "Glucose"] : [],
      mensaje: candidatas ? "Candidatas prescriptivas: BMI, Glucose." : "No se indicaron variables modificables: márquelas en 'modificables' de la configuración para identificar candidatas prescriptivas.",
    },
    matrices: { frecuencia_dirigida: [], frecuencia_sin_orientar: [] },
    advertencias: [],
    agregacion: { umbral_frecuencia: umbral, orientaciones_manuales: orientaciones },
    version,
    etiqueta: ajustada ? `Ajustada: umbral ${String(umbral).replace(".", ",")}, original 0,6` : "Original",
    avisos: umbral > 0.45
      ? [{
          codigo: "ARISTAS_DEBILES_OBJETIVO", nivel: "advertencia", titulo: "Aristas débiles con el objetivo",
          mensaje: "Aparecen en al menos el 40 % de las corridas, pero no alcanzan el umbral.",
          variables: ["Insulin"], pares: [{ variable_a: "Outcome", variable_b: "Insulin", frecuencia: 0.45, con_objetivo: true }],
        }]
      : [{
          codigo: "ARISTAS_POR_UMBRAL_BAJO", nivel: "advertencia", titulo: "Aristas añadidas al bajar el umbral",
          mensaje: "Estas aristas solo aparecen porque el umbral se bajó de 60 % a 45 %.",
          variables: [], pares: [{ variable_a: "Outcome", variable_b: "Insulin", frecuencia: 0.45, con_objetivo: true }],
        }],
    origen_candidatas: "configuracion_pc",
    nota_candidatas: "Candidatas calculadas con las variables modificables de la configuración de PC.",
    disposicion: [
      { titulo: "Demografía", variables: ["Age", "Insulin", "BloodPressure"] },
      { titulo: "Medidas", variables: ["BMI"] },
      { titulo: "Laboratorio", variables: ["Glucose"] },
      { titulo: "Diagnóstico", variables: ["Outcome"] },
    ],
  };
}

export const version = (numero: number, umbral: number, orientaciones: Orientacion[] = []): Esquemas["VersionResultado"] => ({
  version: numero, base: numero === 1 ? null : 1, umbral_frecuencia: umbral, orientaciones_manuales: orientaciones,
  creada_en: "2026-09-28T10:00:00+00:00", migrada: false,
  etiqueta: numero === 1 ? "Original" : `Ajustada: umbral ${String(umbral).replace(".", ",")}, original 0,6`,
});

const NIVEL: Record<string, number> = { Age: 0, Insulin: 0, BloodPressure: 0, BMI: 1, Glucose: 2, Outcome: 3 };

/** Sidecar con versiones: guardar crea la 2; reagregar rechaza lo que contradice los niveles. */
export function simulacion({ candidatas = true } = {}) {
  const estado = { actual: 1, versiones: [version(1, 0.6)] };
  const guardadas: Record<number, Resultado> = { 1: resultado({ candidatas }) };
  const vista = () => ({ version_actual: estado.actual, umbral_original: 0.6, versiones: estado.versiones });
  return {
    "GET /proyectos/p1": { ...proyectoBase(ETAPAS), nombre: "Diabetes", etapa_actual: "analisis" },
    "GET /proyectos/p1/resultado/versiones": vista,
    "GET /proyectos/p1/resultado": (p: Peticion) => guardadas[Number(p.consulta.version ?? estado.actual)],
    "POST /proyectos/p1/resultado/reagregar": (p: Peticion) => {
      const { umbral_frecuencia, orientaciones_manuales = [] } = p.cuerpo as Esquemas["SolicitudReagregar"];
      const errores = orientaciones_manuales.flatMap((o, i) =>
        NIVEL[o.origen] > NIVEL[o.destino]
          ? [{ campo: `orientaciones_manuales.${i}`, mensaje: `La orientación manual ${o.origen} → ${o.destino} contradice los niveles.` }]
          : [],
      );
      if (errores.length) return respuesta(422, { error: { codigo: "AJUSTE_NO_VALIDO", mensaje: errores[0].mensaje, detalles: errores } });
      return resultado({ umbral: umbral_frecuencia, orientaciones: orientaciones_manuales, version: null, candidatas });
    },
    "POST /proyectos/p1/resultado/versiones": (p: Peticion) => {
      const { umbral_frecuencia, orientaciones_manuales = [] } = p.cuerpo as Esquemas["SolicitudVersion"];
      const numero = estado.versiones.length + 1;
      estado.versiones = [...estado.versiones, version(numero, umbral_frecuencia, orientaciones_manuales)];
      guardadas[numero] = resultado({ umbral: umbral_frecuencia, orientaciones: orientaciones_manuales, version: numero, candidatas });
      estado.actual = numero;
      return respuesta(201, vista());
    },
    "PUT /proyectos/p1/resultado/version-actual": (p: Peticion) => {
      estado.actual = (p.cuerpo as { version: number }).version;
      return vista();
    },
    "GET /proyectos/p1/resultado/procedencia": {
      archivo: "diabetes.csv", hoja: null, sha256: "abc123", objetivo: "Outcome", tipo_objetivo: "binario",
      filas_train: 537, filas_test: 231,
      decisiones: [{ concepto: "Faltantes de Glucose", detalle: "ceros como faltantes; imputar con la mediana" }],
      separacion: [{ concepto: "Tipo", detalle: "estratificada" }],
      configuracion: CONFIGURACION, prueba_recomendada: "mv_fisherz",
    },
  };
}

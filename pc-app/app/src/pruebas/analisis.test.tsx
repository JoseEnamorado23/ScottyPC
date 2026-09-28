import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Esquemas } from "../api/cliente";
import { proyecto as proyectoBase, renderizar, respuesta, type Peticion } from "./utilidades";

type Trabajo = Esquemas["Trabajo"];

const ETAPAS_HASTA_CONFIGURACION = {
  revision: "vigente", decisiones: "vigente", preparacion: "vigente", recomendacion: "vigente", configuracion_pc: "vigente",
} as const;

function proyecto(ultimo: Trabajo | null, etapas: Record<string, "vigente" | "desactualizada"> = ETAPAS_HASTA_CONFIGURACION) {
  return {
    ...proyectoBase(etapas),
    trabajo_activo: ultimo && ["en_curso", "pendiente"].includes(ultimo.estado) ? ultimo.id : null,
    ultimo_trabajo: ultimo && {
      id: ultimo.id, tipo: ultimo.tipo, estado: ultimo.estado, completadas: ultimo.completadas,
      total: ultimo.total, mensaje: ultimo.mensaje, reanudable: ["cancelado", "interrumpido", "fallido"].includes(ultimo.estado),
    },
  };
}

function trabajo(estado: Trabajo["estado"], cambios: Partial<Trabajo> = {}): Trabajo {
  return {
    id: "t1", proyecto_id: "p1", tipo: "pc", estado, completadas: 12, total: 100, fallidas: 1,
    segundos_transcurridos: 65, segundos_restantes_estimados: estado === "en_curso" ? 480 : null,
    mensaje: null, error: null, parametros: {}, inicio: "2026-09-27T10:00:00", fin: null, detalles: null,
    ...cambios,
  };
}

// --- Recomendación: advertencias de la elección ----------------------------------------------------------

const RECOMENDACION: Esquemas["RecomendacionPrueba"] = {
  prueba: "chisq",
  motivo: "Estas variables tienen una relación no monótona con el objetivo: variabilidad.",
  discretizacion: "quintiles",
  variables_no_monotonas: ["variabilidad"],
  faltantes_restantes: {},
  proporcion_categoricas: 0.1,
  filas_train: 1488,
  variables: 21,
  diagnosticos: [
    {
      nombre: "variabilidad", tipo_final: "continua", spearman: -0.05, p_intervalos: 0.0001,
      limites_intervalos: [0, 1, 2, 3, 4, 5, 6], valores_por_intervalo: [0.4, 0.2, 0.1, 0.1, 0.25, 0.5],
      filas_por_intervalo: [248, 248, 248, 248, 248, 248], medida: "tasa de la clase positiva",
      amplitud_en_desviaciones: 0.9, monotona: false, motivo: "La curva baja y vuelve a subir.",
    },
  ],
  alternativas: [{ prueba: "fisherz", ventajas: "Muy rápida.", desventajas: "Supone relaciones lineales." }],
  limites_discretizacion: {},
  tiempo_por_ejecucion_s: 40,
  tiempo_estimado_bootstrap_s: 4000,
  estimacion_completa: true,
  max_k_sugerido: 3,
  tiempo_estimado_bootstrap_max_k_s: 600,
  nota_tiempo: "Se sugiere limitar el condicionamiento a max_k = 3.",
};

/** Doble de POST .../evaluar: las reglas reales están en el núcleo (evaluar_eleccion). */
function evaluar(p: Peticion) {
  const { prueba, max_k } = p.cuerpo as { prueba: string; max_k: number | null };
  const advertencias = [];
  if (prueba === "fisherz") {
    advertencias.push({ codigo: "RELACIONES_NO_MONOTONAS", campo: "prueba", nivel: "advertencia", mensaje: "fisherz puede no detectar la relación en U de: variabilidad." });
  }
  if (prueba === "chisq" && max_k === null) {
    advertencias.push({ codigo: "CHISQ_SIN_MAX_K", campo: "max_k", nivel: "advertencia", mensaje: "Sin max_k, el análisis con chisq tardaría unas horas." });
  }
  return { prueba, max_k, advertencias, tiempo_estimado_s: prueba === "chisq" && max_k === 3 ? 600 : null };
}

describe("Recomendación de prueba", () => {
  it("muestra la forma en U y las advertencias del núcleo si la elección contradice los datos", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/recomendacion", {
      "GET /proyectos/p1": proyecto(null),
      "GET /proyectos/p1/recomendacion": RECOMENDACION,
      "POST /proyectos/p1/recomendacion/evaluar": evaluar,
    });

    expect(await screen.findByTestId("sextiles-variabilidad")).toBeInTheDocument();
    expect(screen.getByText("Tasa de la clase positiva", { exact: false })).toBeInTheDocument();
    expect(await screen.findByText("Tiempo estimado con esta elección: 10 min 00 s")).toBeInTheDocument();
    expect(screen.queryByTestId("advertencias-eleccion")).toBeNull();

    await usuario.click(screen.getByRole("combobox", { name: "Prueba" }));
    await usuario.click(await screen.findByRole("option", { name: "Fisher-z (fisherz)", hidden: true }));
    expect(await screen.findByText("fisherz puede no detectar la relación en U de: variabilidad.", { selector: "p, span" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Prueba" })).toHaveAttribute("aria-invalid", "true");

    await usuario.click(screen.getByRole("combobox", { name: "Prueba" }));
    await usuario.click(await screen.findByRole("option", { name: "Chi-cuadrado (chisq)", hidden: true }));
    await usuario.clear(screen.getByRole("textbox", { name: "max_k" }));
    expect(await screen.findByText("Sin max_k, el análisis con chisq tardaría unas horas.", { selector: "p, span" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "max_k" })).toHaveAttribute("aria-invalid", "true");

    const cuerpos = sidecar.peticiones.filter((p) => p.ruta.endsWith("/evaluar")).map((p) => p.cuerpo);
    expect(cuerpos).toContainEqual({ prueba: "fisherz", max_k: 3 });
    expect(cuerpos).toContainEqual({ prueba: "chisq", max_k: null });
  });
});

// --- Pantalla de progreso -------------------------------------------------------------------------------------

describe("Progreso del análisis", () => {
  it("en curso: corridas, fallidas, tiempos y modo; cancelar pide confirmación", async () => {
    const usuario = userEvent.setup();
    const enCurso = trabajo("en_curso", { detalles: { modo: "paralelo", procesos: 4 } });
    const sidecar = renderizar("/proyectos/p1/analisis", {
      "GET /proyectos/p1": proyecto(enCurso),
      "GET /trabajos/t1": enCurso,
      "POST /trabajos/t1/cancelar": { ...enCurso, mensaje: "Cancelación solicitada." },
    });

    const progreso = await screen.findByTestId("progreso-trabajo");
    expect(within(progreso).getByText("12 de 100")).toBeInTheDocument();
    expect(within(progreso).getByText("1")).toBeInTheDocument();
    expect(within(progreso).getByText("1 min 05 s")).toBeInTheDocument();
    expect(within(progreso).getByText("8 min 00 s")).toBeInTheDocument();
    expect(within(progreso).getByText("Modo: En paralelo con 4 procesos")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ejecutar análisis" })).toBeNull();

    await usuario.click(within(progreso).getByRole("button", { name: "Cancelar" }));
    const dialogo = await screen.findByRole("dialog");
    expect(within(dialogo).getByText(/El avance se guarda: podrá reanudar el análisis/)).toBeInTheDocument();
    expect(sidecar.peticiones.some((p) => p.ruta.endsWith("/cancelar"))).toBe(false);
    await usuario.click(within(dialogo).getByRole("button", { name: "Cancelar el trabajo" }));
    await waitFor(() => expect(sidecar.peticiones.some((p) => p.ruta === "/trabajos/t1/cancelar")).toBe(true));
  });

  it.each([
    ["cancelado", /Cancelado con 12 de 100 corridas hechas/],
    ["interrumpido", /Se interrumpió porque la aplicación o el motor de análisis se cerraron/],
  ] as const)("%s: explica el estado y permite reanudar", async (estado, texto) => {
    const usuario = userEvent.setup();
    const detenido = trabajo(estado);
    const sidecar = renderizar("/proyectos/p1/analisis", {
      "GET /proyectos/p1": proyecto(detenido),
      "GET /trabajos/t1": detenido,
      "POST /trabajos/t1/reanudar": respuesta(202, trabajo("en_curso")),
    });

    expect(await screen.findByText(texto)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Empezar de nuevo" })).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Reanudar" }));
    await waitFor(() => expect(sidecar.peticiones.some((p) => p.ruta === "/trabajos/t1/reanudar")).toBe(true));
  });

  it("completado: al terminar mientras se mira, pasa a los resultados provisionales", async () => {
    let consultas = 0;
    const final = trabajo("completado", { completadas: 100, mensaje: "Glucose y BMI son candidatas prescriptivas." });
    renderizar("/proyectos/p1/analisis", {
      "GET /proyectos/p1": () => proyecto(consultas > 1 ? final : trabajo("en_curso"), consultas > 1
        ? { ...ETAPAS_HASTA_CONFIGURACION, analisis: "vigente" } : ETAPAS_HASTA_CONFIGURACION),
      "GET /trabajos/t1": () => (++consultas > 1 ? final : trabajo("en_curso")),
      "GET /proyectos/p1/resultado": {
        corridas: { totales: 100, completadas: 100, validas: 100, fallidas: [], completo: true },
        caracterizacion: {
          objetivo: "Outcome",
          variables: [
            { variable: "Glucose", categoria: "causa_directa", a_traves_de: [], frecuencia_con_objetivo: 1, grupo_redundante: null, modificable: true },
            { variable: "Age", categoria: "causa_indirecta", a_traves_de: ["Glucose"], frecuencia_con_objetivo: 0.9, grupo_redundante: null, modificable: false },
          ],
          candidatas_prescriptivas: ["Glucose"],
          mensaje: "Glucose es candidata prescriptiva.",
        },
      },
    });

    expect(await screen.findByText("12 de 100")).toBeInTheDocument();
    const causas = await screen.findByTestId("causas-directas", {}, { timeout: 4000 });
    expect(within(causas).getByText("Glucose")).toBeInTheDocument();
    expect(within(causas).queryByText("Age")).toBeNull();
    expect(within(screen.getByTestId("candidatas-prescriptivas")).getByText("Glucose")).toBeInTheDocument();
  });
});

// --- Configuración de PC: validación en vivo -------------------------------------------------------------------

const PLANTILLA: Esquemas["ConfiguracionPC"] = {
  prueba: "fisherz", alpha: 0.05, corridas_bootstrap: 100, fraccion_submuestra: 0.8, umbral_frecuencia: 0.6,
  max_k: null, semilla: 42, procesos: 3, niveles: [["Age", "BMI", "Glucose"], ["Outcome"]], modificables: [],
  orientaciones_manuales: [], punto_control_cada: 10, modo_ejecucion: "adaptativo", umbral_paralelo_s: 30,
  nombres_niveles: null,
};

/** Doble de POST .../validar: solo para las situaciones de la prueba (las reglas están en el núcleo). */
function validar(p: Peticion) {
  const { niveles } = p.cuerpo as Esquemas["ConfiguracionPC"];
  const errores = niveles.flatMap((nivel, i) =>
    nivel.length ? [] : [{ campo: `niveles.${i}`, mensaje: `El nivel ${i + 1} está vacío: agregue variables o elimínelo.` }],
  );
  const posicion = niveles.findIndex((n) => n.includes("Outcome"));
  const advertencias = niveles.slice(posicion + 1).some((n) => n.length)
    ? [{ campo: "niveles", mensaje: "El objetivo 'Outcome' no está en el último nivel." }]
    : [];
  return { valida: errores.length === 0, errores, advertencias };
}

describe("Configuración de PC", () => {
  it("valida en vivo con el núcleo: errores por nivel, advertencia del objetivo y guardado bloqueado", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/configuracion", {
      "GET /proyectos/p1": { ...proyecto(null), objetivo: "Outcome" },
      "GET /proyectos/p1/configuracion-pc": { configuracion: PLANTILLA, guardada: false },
      "POST /proyectos/p1/configuracion-pc/validar": validar,
    });

    const guardar = await screen.findByRole("button", { name: "Guardar configuración" });
    await waitFor(() => expect(guardar).toBeEnabled());
    expect(screen.getByRole("checkbox", { name: "Outcome (objetivo)" })).toBeDisabled();

    // Mover el objetivo al primer nivel deja vacío el segundo.
    await usuario.click(screen.getByRole("button", { name: "Mover Outcome" }));
    await usuario.click(await screen.findByRole("menuitem", { name: "Nivel 1", hidden: true }));

    const segundo = screen.getByTestId("nivel-1");
    expect(await within(segundo).findByText("El nivel 2 está vacío: agregue variables o elimínelo.")).toBeInTheDocument();
    await waitFor(() => expect(guardar).toBeDisabled());

    // Con otra variable al final, el nivel ya no está vacío pero el objetivo queda antes: advertencia.
    await usuario.click(screen.getByRole("button", { name: "Mover BMI" }));
    await usuario.click(await screen.findByRole("menuitem", { name: "Nivel 2", hidden: true }));
    expect(await screen.findByText("El objetivo 'Outcome' no está en el último nivel.")).toBeInTheDocument();
    await waitFor(() => expect(guardar).toBeEnabled());

    const ultima = sidecar.peticiones.filter((p) => p.ruta.endsWith("/validar")).at(-1)!;
    expect((ultima.cuerpo as Esquemas["ConfiguracionPC"]).niveles).toEqual([["Age", "Glucose", "Outcome"], ["BMI"]]);
  });

  it("restablece los niveles a la plantilla", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/configuracion", {
      "GET /proyectos/p1": { ...proyecto(null), objetivo: "Outcome" },
      "GET /proyectos/p1/configuracion-pc": {
        configuracion: { ...PLANTILLA, niveles: [["Age"], ["BMI", "Glucose"], ["Outcome"]], nombres_niveles: ["Demografía", "Medidas", "Diagnóstico"] },
        guardada: true,
      },
      "GET /proyectos/p1/configuracion-pc/plantilla": PLANTILLA,
      "POST /proyectos/p1/configuracion-pc/validar": validar,
    });

    expect(await screen.findByDisplayValue("Medidas")).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Restablecer" }));

    await waitFor(() => expect(screen.queryByDisplayValue("Medidas")).toBeNull());
    expect(screen.getByDisplayValue("Nivel 1")).toBeInTheDocument();
    expect(within(screen.getByTestId("nivel-0")).getByText("Glucose")).toBeInTheDocument();
    expect(within(screen.getByTestId("nivel-1")).getByText("Outcome")).toBeInTheDocument();
    expect(await screen.findByText("Hay cambios sin guardar.")).toBeInTheDocument();
    expect(sidecar.peticiones.some((p) => p.ruta.endsWith("/plantilla"))).toBe(true);
  });
});

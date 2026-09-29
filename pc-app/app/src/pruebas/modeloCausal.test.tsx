import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Esquemas } from "../api/cliente";
import {
  SOLICITUD_VACIA, aIntervenciones, cambio, conMecanismo, conMonotonia, disponerSubgrafo, fueraDeRango, mismaSolicitud,
} from "../estado/modeloCausal";
import { MODELO, bloqueante, simulacionModelo } from "./datosModeloCausal";
import { renderizar, respuesta, type Peticion } from "./utilidades";

const peticionesA = (peticiones: Peticion[], metodo: string, ruta: string) =>
  peticiones.filter((p) => p.metodo === metodo && p.ruta === ruta);

describe("Modelo causal (lógica de presentación)", () => {
  it("overrides: se agregan, se quitan con «auto» y se comparan sin importar el orden", () => {
    const a = conMonotonia(conMecanismo(SOLICITUD_VACIA, "Glucose", "complejo"), "BMI", "ninguna");
    const b = conMecanismo(conMonotonia(SOLICITUD_VACIA, "BMI", "ninguna"), "Glucose", "complejo");
    expect(mismaSolicitud(a, b)).toBe(true);
    expect(mismaSolicitud(conMecanismo(a, "Glucose", "auto"), conMonotonia(SOLICITUD_VACIA, "BMI", "ninguna"))).toBe(true);
    expect(mismaSolicitud(a, SOLICITUD_VACIA)).toBe(false);
  });

  it("intervenciones completas, ordenadas y sin las vacías", () => {
    expect(
      aIntervenciones({
        Glucose: { modo: "desplazar", valor: -20 },
        Age: { modo: "fijar", valor: 40 },
        BMI: { modo: "fijar", valor: null },
        zona: { modo: "ninguna", valor: "b" },
      }),
    ).toEqual([
      { variable: "Age", tipo: "fijar", valor: 40 },
      { variable: "Glucose", tipo: "desplazar", valor: -20 },
    ]);
  });

  it("extrapolación, formato de cambios y disposición del subgrafo", () => {
    const edad = MODELO.controles[0];
    expect(fueraDeRango(edad, 50, { modo: "desplazar", valor: 40 })).toBe(true);
    expect(fueraDeRango(edad, 50, { modo: "fijar", valor: 30 })).toBe(false);
    expect(cambio(0.032, "probabilidad")).toBe("+3,2 pp");
    expect(cambio(-1.5)).toBe("−1,5");
    const nodos = disponerSubgrafo(MODELO.modelo.subgrafo.variables, MODELO.modelo.subgrafo.padres);
    const columna = Object.fromEntries(nodos.map((n) => [n.variable, n.columna]));
    expect(columna).toEqual({ Age: 0, BMI: 0, "zona=b": 0, Glucose: 1, Outcome: 2 });
  });
});

describe("Modelo causal: aplicabilidad y construcción", () => {
  it("muestra los bloqueantes con su acción y lleva a donde se resuelven", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/modelo-causal", {
      ...simulacionModelo({ conModelo: false, problemas: [bloqueante] }),
      "GET /proyectos/p1/resultado/versiones": respuesta(409, { error: { codigo: "ETAPA_REQUERIDA", mensaje: "x" } }),
    });
    const lista = await screen.findByTestId("aplicabilidad");
    expect(within(lista).getByText(/Oriente la arista Pregnancies — Age en Resultados/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Construir modelo" })).toBeDisabled();
    await usuario.click(within(lista).getByRole("button", { name: "Ir a Resultados" }));
    await waitFor(() => expect(screen.queryByTestId("aplicabilidad")).toBeNull());
  });

  it("construye con los overrides elegidos (mecanismo y monotonía)", async () => {
    const usuario = userEvent.setup();
    const trabajo: Esquemas["Trabajo"] = {
      id: "t1", proyecto_id: "p1", tipo: "modelo_causal", estado: "en_curso", completadas: 0, total: 3, fallidas: 0,
      segundos_transcurridos: 0, segundos_restantes_estimados: null, mensaje: null, error: null, parametros: {},
      inicio: null, fin: null, detalles: null,
    };
    const sidecar = renderizar("/proyectos/p1/modelo-causal", {
      ...simulacionModelo(),
      "POST /proyectos/p1/modelo-causal": respuesta(202, trabajo),
      "GET /trabajos/t1": trabajo,
    });
    const tabla = await screen.findByTestId("tabla-mecanismos");
    expect(within(tabla).getByText("Regresión lineal")).toBeInTheDocument();
    expect(screen.queryByTestId("cambios-sin-aplicar")).toBeNull();

    await usuario.click(within(tabla).getByRole("combobox", { name: "Mecanismo de Glucose" }));
    await usuario.click(await screen.findByRole("option", { name: "Splines + Ridge", hidden: true }));
    const efectos = screen.getByTestId("efectos-objetivo");
    await usuario.click(within(efectos).getAllByText("Libre")[0]);
    expect(screen.getByTestId("cambios-sin-aplicar")).toBeInTheDocument();

    await usuario.click(screen.getByRole("button", { name: "Reconstruir con los cambios" }));
    await waitFor(() => expect(peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/modelo-causal")).toHaveLength(1));
    const [envio] = peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/modelo-causal");
    expect(envio.cuerpo).toEqual({ monotonia: { Glucose: "ninguna" }, mecanismos: { Glucose: "complejo" }, pesos_clase: false });
  });

  it("avisa si el modelo está desactualizado", async () => {
    const simulacion = simulacionModelo({ conModelo: false });
    renderizar("/proyectos/p1/modelo-causal", {
      ...simulacion,
      "GET /proyectos/p1": { ...(simulacion["GET /proyectos/p1"] as object), etapas: { analisis: "vigente", modelo_causal: "desactualizada" } },
    });
    expect(await screen.findByTestId("modelo-desactualizado")).toBeInTheDocument();
  });
});

describe("Modelo causal: evaluación y escenarios", () => {
  it("muestra el umbral, el Brier y el costo de la parsimonia", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/modelo-causal", simulacionModelo());
    await usuario.click(await screen.findByRole("tab", { name: "Evaluación" }));
    const panel = screen.getByTestId("panel-evaluacion");
    expect(within(panel).getByText(/Umbral de decisión: 35,0 %/)).toBeInTheDocument();
    expect(within(panel).getByText("Brier")).toBeInTheDocument();
    expect(within(panel).getByText("0,168")).toBeInTheDocument();
    expect(within(panel).getByTestId("costo-parsimonia")).toHaveTextContent("costo de la parsimonia");
    expect(within(panel).getByRole("img", { name: "Curva de calibración" })).toBeInTheDocument();
  });

  it("calcula el escenario con la fila de test y las intervenciones, y muestra la propagación", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/modelo-causal", simulacionModelo());
    await usuario.click(await screen.findByRole("tab", { name: "Escenarios" }));
    expect(await screen.findByTestId("resultado-escenario")).toHaveTextContent("40,0 %");
    const ruta = "/proyectos/p1/modelo-causal/contrafactual";
    expect(peticionesA(sidecar.peticiones, "POST", ruta)[0].cuerpo).toEqual({ caso: { indice_test: 7 }, intervenciones: [] });

    // La categoría «zona» es un solo control (solo se fija), nunca sus dummies sueltas.
    const controles = screen.getByTestId("controles-escenario");
    expect(within(controles).getByText("zona")).toBeInTheDocument();
    expect(within(controles).queryByText("zona=b")).toBeNull();
    const grupoZona = within(controles).getByRole("radiogroup", { name: "Intervención en zona" });
    expect(within(grupoZona).queryByText("Desplazar")).toBeNull();

    // Desplazar Age +40 sale del rango de train (21–81): extrapolación.
    const grupoEdad = within(controles).getByRole("radiogroup", { name: "Intervención en Age" });
    await usuario.click(within(grupoEdad).getByText("Desplazar"));
    fireEvent.change(screen.getByRole("textbox", { name: "Valor de Age" }), { target: { value: "40" } });
    await waitFor(() =>
      expect(peticionesA(sidecar.peticiones, "POST", ruta).at(-1)!.cuerpo).toEqual({
        caso: { indice_test: 7 },
        intervenciones: [{ variable: "Age", tipo: "desplazar", valor: 40 }],
      }),
    );
    expect(await screen.findByTestId("despues")).toHaveTextContent("48,0 %");
    expect(within(controles).getByText("extrapolación")).toBeInTheDocument();
    const traza = screen.getByTestId("traza");
    expect(within(traza).getByText("Age (+12)")).toBeInTheDocument();
    const grafo = screen.getByTestId("grafo-propagacion");
    expect(grafo.querySelector('[data-variable="Glucose"]')).toHaveAttribute("data-cambiada", "si");
    expect(grafo.querySelector('[data-variable="BMI"]')).toHaveAttribute("data-cambiada", "no");
  });
});

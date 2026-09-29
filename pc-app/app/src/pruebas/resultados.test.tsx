import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Esquemas } from "../api/cliente";
import { clavePar, conOrientacion, conUmbral, mismoAjuste, sinOrientacion } from "../estado/ajustes";
import { caminoAlObjetivo, datosAristas, disposicionInicial } from "../estado/grafo";
import { resultado, simulacion, variable, version } from "./datosResultados";
import { renderizar, type Peticion } from "./utilidades";

const peticionesA = (peticiones: Peticion[], metodo: string, ruta: string) =>
  peticiones.filter((p) => p.metodo === metodo && p.ruta === ruta);

// --- Lógica pura -------------------------------------------------------------------------------------

describe("Ajuste y grafo (lógica de presentación)", () => {
  it("compara ajustes sin importar el orden de las orientaciones", () => {
    const base = { umbral: 0.6, orientaciones: [] };
    const a = conOrientacion(conOrientacion(base, { origen: "A", destino: "B", justificacion: "x" }), { origen: "C", destino: "D", justificacion: "y" });
    const b = conOrientacion(conOrientacion(base, { origen: "C", destino: "D", justificacion: "y" }), { origen: "A", destino: "B", justificacion: "x" });
    expect(mismoAjuste(a, b)).toBe(true);
    // Reorientar el mismo par reemplaza la orientación anterior.
    const c = conOrientacion(a, { origen: "B", destino: "A", justificacion: "z" });
    expect(c.orientaciones.map((o) => `${o.origen}${o.destino}`)).toEqual(["CD", "BA"]);
    expect(mismoAjuste(sinOrientacion(sinOrientacion(a, "B", "A"), "C", "D"), base)).toBe(true);
    expect(conUmbral(base, 0.456).umbral).toBe(0.46);
    expect(conUmbral(base, 0.05).umbral).toBe(0.2);
  });

  it("aristas con id estable por par, disposición por niveles y camino al objetivo", () => {
    const [primera] = datosAristas(resultado({ orientaciones: [{ origen: "BMI", destino: "BloodPressure", justificacion: "j" }] }))
      .filter((a) => a.tipo === "manual");
    expect(primera.id).toBe(clavePar("BloodPressure", "BMI"));
    const { posiciones, titulos } = disposicionInicial(resultado().disposicion);
    expect(titulos.map((t) => t.titulo)).toEqual(["Demografía", "Medidas", "Laboratorio", "Diagnóstico"]);
    expect(posiciones.Outcome.x).toBeGreaterThan(posiciones.Glucose.x);
    expect(caminoAlObjetivo(variable("Age", "causa_indirecta", 0.2, false, ["Glucose"]), "Outcome")).toBe("Age → Glucose → Outcome");
    // Un nivel largo se reparte en subcolumnas de 8 bajo un título centrado.
    const largas = Array.from({ length: 20 }, (_, i) => `v${i}`);
    const partido = disposicionInicial([{ titulo: "Todas", variables: largas }, { titulo: "Objetivo", variables: ["y"] }]);
    expect(new Set(largas.map((v) => partido.subcolumna[v]))).toEqual(new Set(["0.0", "0.1", "0.2"]));
    expect(partido.titulos[0].x).toBe((partido.posiciones.v0.x + partido.posiciones.v16.x) / 2);
    expect(partido.posiciones.y.x).toBeGreaterThan(partido.posiciones.v16.x);
  });
});

// --- Cambios sin guardar ------------------------------------------------------------------------------

describe("Resultados: ajuste del umbral", () => {
  it("previsualiza con retardo, marca los cambios sin guardar y permite descartarlos o guardarlos", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/resultados", simulacion());

    expect(await screen.findByText("Versión 1", { selector: "p" })).toBeInTheDocument();
    expect(screen.queryByTestId("sin-guardar")).toBeNull();
    expect(screen.queryByTestId("umbral-bajo")).toBeNull();

    // Varios pasos seguidos del deslizante: una sola vista previa, con el último valor.
    const deslizante = screen.getByRole("slider");
    deslizante.focus();
    for (let i = 0; i < 15; i++) fireEvent.keyDown(deslizante, { key: "ArrowLeft" });
    expect(screen.getByTestId("sin-guardar")).toBeInTheDocument();
    expect(screen.getByTestId("umbral-bajo")).toHaveTextContent("Umbrales bajos incluyen más aristas espurias");
    expect(await screen.findByText("arista Insulin → Outcome")).toBeInTheDocument();
    const vistas = peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/resultado/reagregar");
    expect(vistas.map((p) => (p.cuerpo as Esquemas["SolicitudReagregar"]).umbral_frecuencia)).toEqual([0.45]);
    expect(screen.getByText("Vista previa sin guardar")).toBeInTheDocument();
    expect(screen.getAllByTestId("etiqueta-version").map((e) => e.textContent)).toContain("Ajustada: umbral 0,45, original 0,6");

    // Descartar vuelve a la versión guardada.
    await usuario.click(screen.getByRole("button", { name: "Descartar" }));
    expect(screen.queryByTestId("sin-guardar")).toBeNull();
    expect(screen.queryByText("arista Insulin → Outcome")).toBeNull();
    expect(screen.getByRole("slider")).toHaveAttribute("aria-valuenow", "0.6");

    // Guardar crea la versión 2 y la muestra; el indicador desaparece.
    screen.getByRole("slider").focus();
    for (let i = 0; i < 15; i++) fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowLeft" });
    await screen.findByText("arista Insulin → Outcome");
    const guardar = screen.getByRole("button", { name: "Guardar como versión nueva" });
    await waitFor(() => expect(guardar).toBeEnabled()); // no se guarda mientras se calcula la vista previa
    await usuario.click(guardar);
    await waitFor(() => expect(screen.queryByTestId("sin-guardar")).toBeNull());
    expect(await screen.findByText("Versión 2", { selector: "p" })).toBeInTheDocument();
    const [guardado] = peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/resultado/versiones");
    expect(guardado.cuerpo).toEqual({ umbral_frecuencia: 0.45, orientaciones_manuales: [], version_base: 1 });
    expect(screen.getByText("arista Insulin → Outcome")).toBeInTheDocument();
    expect(screen.getAllByTestId("etiqueta-version")[0]).toHaveTextContent("Ajustada: umbral 0,45, original 0,6");

    // El historial permite volver a la original.
    await usuario.click(screen.getByText("Historial de versiones"));
    await usuario.click(await screen.findByRole("button", { name: "Ver versión 1", hidden: true }));
    expect(await screen.findByText("Versión 1", { selector: "p" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("arista Insulin → Outcome")).toBeNull());
    expect(peticionesA(sidecar.peticiones, "PUT", "/proyectos/p1/resultado/version-actual").map((p) => p.cuerpo)).toEqual([{ version: 1 }]);
  });

  it("pide confirmación antes de cambiar de versión con cambios sin guardar", async () => {
    const usuario = userEvent.setup();
    const sim = simulacion();
    renderizar("/proyectos/p1/resultados", {
      ...sim,
      "GET /proyectos/p1/resultado/versiones": { version_actual: 1, umbral_original: 0.6, versiones: [version(1, 0.6), version(2, 0.5)] },
    });
    const deslizante = await screen.findByRole("slider");
    deslizante.focus();
    fireEvent.keyDown(deslizante, { key: "ArrowLeft" });
    await usuario.click(screen.getByText("Historial de versiones"));
    await usuario.click(await screen.findByRole("button", { name: "Ver versión 2", hidden: true }));

    const dialogo = await screen.findByRole("dialog", { name: "Cambios sin guardar" });
    await usuario.click(within(dialogo).getByRole("button", { name: "Seguir ajustando" }));
    expect(screen.getByTestId("sin-guardar")).toBeInTheDocument();
  });
});

// --- Orientación manual -------------------------------------------------------------------------------

describe("Resultados: orientación manual", () => {
  it("exige dirección y justificación, muestra el rechazo del núcleo y aplica la orientación válida", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/resultados", simulacion());

    // Desde el grafo: clic en la arista sin orientar.
    await usuario.click(await screen.findByText("arista BloodPressure — BMI"));
    const dialogo = await screen.findByRole("dialog", { name: "Orientar la arista BloodPressure — BMI" });
    const aplicar = within(dialogo).getByRole("button", { name: "Aplicar" });
    expect(aplicar).toBeDisabled();

    // Dirección contraria a los niveles: el núcleo la rechaza y el error aparece en el diálogo.
    await usuario.click(within(dialogo).getByRole("radio", { name: "BMI → BloodPressure" }));
    expect(aplicar).toBeDisabled(); // falta la justificación
    await usuario.type(within(dialogo).getByRole("textbox", { name: /Justificación/ }), "La presión se mide antes");
    expect(aplicar).toBeEnabled();
    await usuario.click(aplicar);
    expect(await within(dialogo).findByText(/contradice los niveles/)).toBeInTheDocument();
    expect(screen.queryByTestId("sin-guardar")).toBeNull();

    // Dirección válida: se cierra el diálogo y queda como cambio sin guardar.
    await usuario.click(within(dialogo).getByRole("radio", { name: "BloodPressure → BMI" }));
    await usuario.click(aplicar);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByTestId("sin-guardar")).toBeInTheDocument();
    expect(await screen.findByText("arista BloodPressure → BMI")).toBeInTheDocument();
    const ultima = peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/resultado/reagregar").at(-1)!;
    expect(ultima.cuerpo).toEqual({
      umbral_frecuencia: 0.6,
      orientaciones_manuales: [{ origen: "BloodPressure", destino: "BMI", justificacion: "La presión se mide antes" }],
    });
    expect(peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/resultado/reagregar")).toHaveLength(2); // sin repetir la vista previa
    expect(screen.getByText(/BloodPressure → BMI:/)).toBeInTheDocument(); // lista del ajuste

    // Desde la tabla de aristas, la orientación manual se puede quitar.
    await usuario.click(screen.getByRole("tab", { name: /Aristas/ }));
    await usuario.click(screen.getByRole("button", { name: "Orientar BloodPressure — BMI" }));
    const otra = await screen.findByRole("dialog");
    expect(within(otra).getByRole("radio", { name: "BloodPressure → BMI" })).toBeChecked();
    await usuario.click(within(otra).getByRole("button", { name: "Quitar la orientación manual" }));
    await waitFor(() => expect(screen.queryByTestId("sin-guardar")).toBeNull());
  });
});

// --- Caracterización, advertencias y configuración ---------------------------------------------------

describe("Resultados: pestañas", () => {
  it("filtra la caracterización por categoría y destaca las candidatas prescriptivas", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/resultados", simulacion());

    await usuario.click(await screen.findByRole("tab", { name: "Caracterización" }));
    const candidatas = screen.getByTestId("candidatas-prescriptivas");
    expect(within(candidatas).getByText("Glucose")).toBeInTheDocument();
    expect(within(candidatas).getByText("BMI")).toBeInTheDocument();
    const tabla = screen.getByTestId("tabla-caracterizacion");
    expect(within(tabla).getAllByRole("row")).toHaveLength(6); // encabezado + 5 variables

    await usuario.click(screen.getByRole("checkbox", { name: "Causa directa (2)" }));
    const filas = within(tabla).getAllByRole("row").slice(1).map((f) => within(f).getAllByRole("cell")[0].textContent);
    expect(filas).toEqual(["Age", "Insulin", "BloodPressure"]);

    await usuario.click(screen.getByRole("checkbox", { name: "Causa directa (2)" }));
    for (const nombre of ["Causa indirecta (1)", "Sin camino (1)", "Ambigua (1)"]) {
      await usuario.click(screen.getByRole("checkbox", { name: nombre }));
    }
    expect(within(tabla).getAllByRole("row").slice(1).map((f) => within(f).getAllByRole("cell")[0].textContent)).toEqual(["BMI", "Glucose"]);
    expect(within(tabla).getByText("Glucose → Outcome")).toBeInTheDocument();
  });

  it("sin candidatas muestra el mensaje explícito del núcleo", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/resultados", simulacion({ candidatas: false }));

    await usuario.click(await screen.findByRole("tab", { name: "Caracterización" }));
    expect(screen.getByTestId("candidatas-prescriptivas")).toHaveTextContent("No se indicaron variables modificables");
  });

  it("advertencias, configuración original con los ajustes de la versión y panel de la variable", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/resultados", simulacion());

    await usuario.click(await screen.findByText("nodo Insulin"));
    const panel = screen.getByTestId("panel-variable");
    expect(panel).toHaveTextContent("Sin camino");
    expect(panel).toHaveTextContent("45,0 % de las corridas (por debajo del umbral");

    await usuario.click(screen.getByRole("tab", { name: /Advertencias/ }));
    expect(screen.getByText("Aristas débiles con el objetivo")).toBeInTheDocument();
    expect(screen.getByText("Outcome — Insulin")).toBeInTheDocument();

    await usuario.click(screen.getByRole("tab", { name: "Configuración" }));
    expect(await screen.findByText("Configuración de PC (original)")).toBeInTheDocument();
    expect(screen.getByText("fisherz (recomendada: mv_fisherz)")).toBeInTheDocument();
    expect(screen.getByText("La prueba usada no es la recomendada.")).toBeInTheDocument();
    expect(screen.getByText("Umbral usado").nextSibling).toHaveTextContent("60 %");
    expect(screen.getByText("Umbral original").nextSibling).toHaveTextContent("60 %");
    expect(screen.getByText("Age, Insulin, BloodPressure")).toBeInTheDocument(); // nivel «Demografía»
  });
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Esquemas } from "../api/cliente";
import { completarCon, conSupuesto, confirmados, intervencionesDe, supuestosDe } from "../estado/prescripcion";
import { RESULTADO, configuracion, simulacionPrescripcion, sinPrescriptivas, supuestosSinConfirmar } from "./datosPrescripcion";
import { renderizar, type Peticion } from "./utilidades";

const peticionesA = (peticiones: Peticion[], metodo: string, ruta: string) =>
  peticiones.filter((p) => p.metodo === metodo && p.ruta === ruta);

describe("Prescripción (lógica de presentación)", () => {
  it("la declaración de supuestos guarda la fecha solo con las tres casillas marcadas", () => {
    let c = configuracion(false);
    c = conSupuesto(c, "BMI", "modificable_por_decision", true, () => "F1");
    c = conSupuesto(c, "BMI", "medida_antes_del_resultado", true, () => "F2");
    expect(supuestosDe(c, "BMI").confirmado_en).toBeNull();
    c = conSupuesto(c, "BMI", "no_define_el_objetivo", true, () => "F3");
    expect(supuestosDe(c, "BMI").confirmado_en).toBe("F3");
    expect(confirmados(supuestosDe(c, "BMI"))).toBe(true);
    c = conSupuesto(c, "BMI", "medida_antes_del_resultado", false);
    expect(confirmados(supuestosDe(c, "BMI"))).toBe(false);
    expect(supuestosDe(c, "BMI").confirmado_en).toBeNull();
  });

  it("completa las acciones de nuevas prescriptivas sin pisar las editadas", () => {
    const borrador = configuracion(false);
    borrador.acciones.BMI = { ...borrador.acciones.BMI, costo: 3 };
    const completada = configuracion(false);
    completada.acciones = {
      ...completada.acciones,
      Age: { variable: "Age", permitida: true, direccion: "ambas", minimo: 21, maximo: 81, cambio_maximo: 15, costo: 1, estados_permitidos: null },
    };
    const nuevo = completarCon(borrador, completada);
    expect(nuevo.acciones.BMI.costo).toBe(3);
    expect(Object.keys(nuevo.acciones)).toEqual(["BMI", "Glucose", "Age"]);
    expect(nuevo.supuestos?.Age?.confirmado_en).toBeNull();
  });

  it("una prescripción se convierte en intervenciones «fijar» del explorador", () => {
    expect(intervencionesDe(RESULTADO)).toEqual({ Glucose: { modo: "fijar", valor: 131 }, BMI: { modo: "fijar", valor: 30.1 } });
  });
});

describe("Prescripción: pantalla", () => {
  it("muestra siempre el aviso y los bloqueantes con su acción", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/prescripcion", simulacionPrescripcion({ problemas: [sinPrescriptivas] }));
    expect(await screen.findByTestId("aviso-prescripcion")).toHaveTextContent(
      "Recomendaciones basadas en datos observacionales. No reemplazan el criterio de un experto ni una validación experimental.",
    );
    const lista = await screen.findByTestId("aplicabilidad");
    expect(within(lista).getByText(/Con estos datos no hay variables prescriptivas/)).toBeInTheDocument();
    await usuario.click(await screen.findByRole("tab", { name: "Caso individual" }));
    await usuario.click(within(lista).getByRole("button", { name: "Ir a la configuración" }));
    expect(await screen.findByTestId("tabla-acciones")).toBeInTheDocument();
  });

  it("«Ir a la configuración» lleva a la sección donde se resuelve cada problema", async () => {
    const usuario = userEvent.setup();
    const desplazados: string[] = [];
    const espia = vi.spyOn(window.HTMLElement.prototype, "scrollIntoView").mockImplementation(function (this: HTMLElement) {
      desplazados.push(this.id);
    });
    try {
      renderizar("/proyectos/p1/prescripcion", simulacionPrescripcion({ problemas: [supuestosSinConfirmar, sinPrescriptivas] }));
      const lista = await screen.findByTestId("aplicabilidad");
      await screen.findByTestId("tabla-acciones");
      const botones = within(lista).getAllByRole("button", { name: "Ir a la configuración" });
      await usuario.click(botones[0]);
      await waitFor(() => expect(desplazados.at(-1)).toBe("seccion-supuestos"));
      await usuario.click(botones[1]);
      await waitFor(() => expect(desplazados.at(-1)).toBe("seccion-modificables"));
    } finally {
      espia.mockRestore();
    }
  });

  it("la declaración de supuestos se confirma por variable y se guarda con fecha", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/prescripcion", simulacionPrescripcion({ guardada: false, confirmada: false }));
    const bmi = await screen.findByTestId("supuestos-BMI");
    for (const casilla of within(bmi).getAllByRole("checkbox")) await usuario.click(casilla);
    expect(within(bmi).getByText(/Confirmado el/)).toBeInTheDocument();
    expect(screen.getByText(/Falta confirmar: Glucose/)).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Guardar configuración" }));
    await waitFor(() => expect(peticionesA(sidecar.peticiones, "PUT", "/proyectos/p1/prescripcion/configuracion")).toHaveLength(1));
    const cuerpo = peticionesA(sidecar.peticiones, "PUT", "/proyectos/p1/prescripcion/configuracion")[0]
      .cuerpo as Esquemas["ConfiguracionPrescripcion"];
    expect(cuerpo.supuestos?.BMI?.confirmado_en).toBeTruthy();
    expect(cuerpo.supuestos?.Glucose?.confirmado_en).toBeNull();
  });

  it("caso individual: acciones ordenadas, marcas, explicación y «Probar una variante»", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/prescripcion", simulacionPrescripcion());
    await usuario.click(await screen.findByRole("tab", { name: "Caso individual" }));
    const tarjeta = await screen.findByTestId("prescripcion-caso");
    expect(within(tarjeta).getByTestId("prescripcion-despues")).toHaveTextContent("25,0 %");
    expect(within(tarjeta).getByTestId("explicacion")).toHaveTextContent("Reducir Glucose de 148 a 131");
    expect(within(tarjeta).getByText("Requiere revisión")).toBeInTheDocument();
    const filas = within(within(tarjeta).getByTestId("acciones-prescritas")).getAllByRole("row").slice(1);
    expect(filas.map((f) => within(f).getAllByRole("cell")[0].textContent)).toEqual(["Glucose", "BMI"]);
    expect(peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/prescripcion/caso")[0].cuerpo).toEqual({ caso: { indice_test: 7 } });

    await usuario.click(within(tarjeta).getByRole("button", { name: "Probar una variante" }));
    await waitFor(() =>
      expect(peticionesA(sidecar.peticiones, "POST", "/proyectos/p1/modelo-causal/contrafactual").at(-1)?.cuerpo).toEqual({
        caso: { indice_test: 7 },
        intervenciones: [{ variable: "BMI", tipo: "fijar", valor: 30.1 }, { variable: "Glucose", tipo: "fijar", valor: 131 }],
      }),
    );
  });

  it("lote: tabla filtrable por estado", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/prescripcion", simulacionPrescripcion());
    await usuario.click(await screen.findByRole("tab", { name: "Lote" }));
    const tabla = await screen.findByTestId("tabla-lote");
    await waitFor(() => expect(within(tabla).getAllByRole("row")).toHaveLength(3));
    await usuario.click(screen.getByText("No alcanzable (1)"));
    await waitFor(() => expect(within(screen.getByTestId("tabla-lote")).getAllByRole("row")).toHaveLength(2));
    expect(peticionesA(sidecar.peticiones, "GET", "/proyectos/p1/prescripcion/lotes/1").at(-1)?.consulta.filtro).toBe("no_alcanzable");
  });

  it("evaluación: métricas, comparación de optimizadores y aviso de evaluación interna", async () => {
    const usuario = userEvent.setup();
    renderizar("/proyectos/p1/prescripcion", simulacionPrescripcion());
    await usuario.click(await screen.findByRole("tab", { name: "Evaluación" }));
    const panel = await screen.findByTestId("evaluacion-prescriptor");
    expect(within(panel).getByText(/evaluación INTERNA/)).toBeInTheDocument();
    const comparacion = within(panel).getByTestId("comparacion-optimizadores");
    expect(within(comparacion).getByText("Genético")).toBeInTheDocument();
    expect(within(comparacion).getByText(/McNemar exacta/)).toHaveTextContent("p = 1");
    expect(within(panel).getByRole("img", { name: "Éxito según el cambio máximo (% del rango)" })).toBeInTheDocument();
  });
});

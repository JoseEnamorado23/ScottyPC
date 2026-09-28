import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { comoNumero } from "../estado/borrador";
import {
  DATOS_TEMP,
  decisionesPara,
  proyecto,
  renderizar,
  respuesta,
  REVISION,
  TOKEN,
  type Peticion,
} from "./utilidades";

const previsualizar = (p: Peticion) => decisionesPara((p.cuerpo as { elecciones: Record<string, string> }).elecciones);
const sinDecisiones = respuesta(409, { error: { codigo: "ETAPA_NO_VIGENTE", mensaje: "No hay decisiones vigentes." } });

function simulacionBase(etapas: Record<string, "vigente" | "desactualizada">, guardadas: unknown = sinDecisiones) {
  return {
    "GET /proyectos/p1": proyecto(etapas),
    "GET /proyectos/p1/revision": REVISION,
    "GET /proyectos/p1/decisiones": guardadas,
    "POST /proyectos/p1/decisiones/previsualizar": previsualizar,
    "GET /proyectos/p1/datos": DATOS_TEMP,
  };
}

/** Decisiones ya guardadas con la conversión de temp (todo confirmado). */
const GUARDADAS = decisionesPara({ "mezcla:temp": "convertir_unidades", "ceros:glucosa": "conservar" });

describe("Revisión: hallazgos pendientes de confirmar", () => {
  it("bloquea el avance hasta que cada hallazgo que lo requiere tenga una elección explícita", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/revision", simulacionBase({ revision: "vigente" }));

    const continuar = await screen.findByRole("button", { name: "Continuar (faltan 2 por confirmar)" });
    expect(continuar).toBeDisabled();
    const ceros = screen.getByTestId("hallazgo-ceros:glucosa");
    const mezcla = screen.getByTestId("hallazgo-mezcla:temp");
    expect(within(ceros).getByText("Pendiente de confirmar")).toBeInTheDocument();
    // La sugerida aparece preseleccionada aunque falte confirmarla.
    expect(within(ceros).getByRole("radio", { name: "Conservar (sugerida)" })).toBeChecked();
    // Un hallazgo sin requiere_confirmacion no queda pendiente.
    expect(within(screen.getByTestId("hallazgo-dup")).queryByText("Pendiente de confirmar")).toBeNull();

    await usuario.click(within(ceros).getByRole("button", { name: "Confirmar: Conservar" }));
    expect(await screen.findByRole("button", { name: "Continuar (faltan 1 por confirmar)" })).toBeDisabled();
    expect(within(ceros).queryByText("Pendiente de confirmar")).toBeNull();

    await usuario.click(within(mezcla).getByRole("radio", { name: "Convertir unidades" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Continuar a decisiones" })).toBeEnabled());

    // La elección llega al núcleo por la previsualización (con retardo) y todas las peticiones llevan el token.
    await waitFor(() =>
      expect(
        sidecar.peticiones.some(
          (p) =>
            p.ruta.endsWith("/previsualizar") &&
            (p.cuerpo as { elecciones: Record<string, string> }).elecciones["mezcla:temp"] === "convertir_unidades",
        ),
      ).toBe(true),
    );
    expect(sidecar.peticiones.every((p) => p.token === TOKEN)).toBe(true);
  });

  it("también impide guardar desde la pantalla de decisiones", async () => {
    renderizar("/proyectos/p1/decisiones", simulacionBase({ revision: "vigente" }));

    expect(await screen.findByText("Hay 2 hallazgos pendientes de confirmar en la revisión.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar decisiones" })).toBeDisabled();
  });
});

describe("Decisiones: errores 422 por campo", () => {
  it("muestra cada error junto al campo de la ruta que devuelve el sidecar", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/decisiones", {
      ...simulacionBase({ revision: "vigente", decisiones: "vigente" }, GUARDADAS),
      "PUT /proyectos/p1/decisiones": respuesta(422, {
        error: {
          codigo: "DECISIONES_NO_VALIDAS",
          mensaje: "Hay decisiones no válidas.",
          detalles: [
            { campo: "conversiones.0.multiplicar", mensaje: "Debe ser un número." },
            { campo: "faltantes.glucosa.imputacion", mensaje: "Valor no permitido." },
          ],
        },
      }),
    });

    const multiplicar = await screen.findByLabelText("Multiplicar");
    await usuario.clear(multiplicar);
    await usuario.type(multiplicar, "abc");
    await usuario.click(screen.getByRole("button", { name: "Guardar decisiones" }));

    expect(await screen.findByText("Debe ser un número.")).toBeInTheDocument();
    expect(screen.getByLabelText("Multiplicar")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Restar")).not.toHaveAttribute("aria-invalid", "true");
    // Un campo sin editor en pantalla se lista con su ruta.
    expect(screen.getByText("faltantes.glucosa.imputacion")).toBeInTheDocument();
    expect(screen.getByText("Hay decisiones no válidas.")).toBeInTheDocument();
    // El valor no numérico se envía tal cual para que lo valide el servidor.
    const put = sidecar.peticiones.find((p) => p.metodo === "PUT")!;
    expect((put.cuerpo as { conversiones: { multiplicar: unknown }[] }).conversiones[0].multiplicar).toBe("abc");
  });

  it("previsualiza la conversión de unidades sobre valores de ejemplo (°F → °C)", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/decisiones", {
      ...simulacionBase({ revision: "vigente", decisiones: "vigente" }, GUARDADAS),
      "PUT /proyectos/p1/decisiones": (p: Peticion) => p.cuerpo,
    });

    const umbral = await screen.findByLabelText("Umbral");
    await usuario.clear(umbral);
    await usuario.type(umbral, "50");
    await usuario.clear(screen.getByLabelText("Restar"));
    await usuario.type(screen.getByLabelText("Restar"), "32");
    await usuario.clear(screen.getByLabelText("Multiplicar"));
    await usuario.type(screen.getByLabelText("Multiplicar"), "5/9");

    const vista = screen.getByTestId("vista-conversion-temp");
    expect(within(vista).getByText("30")).toBeInTheDocument(); // 86 °F → 30 °C
    expect(within(vista).getByText("sin cambio")).toBeInTheDocument(); // 20 ya está en °C
    expect(screen.getByLabelText("Multiplicar")).toHaveValue("5/9");

    await usuario.click(screen.getByRole("button", { name: "Guardar decisiones" }));
    await waitFor(() => expect(sidecar.peticiones.some((p) => p.metodo === "PUT")).toBe(true));
    const [conversion] = (sidecar.peticiones.find((p) => p.metodo === "PUT")!.cuerpo as {
      conversiones: { umbral: number; restar: number; multiplicar: number }[];
    }).conversiones;
    expect(conversion).toMatchObject({ umbral: 50, restar: 32 });
    expect(conversion.multiplicar).toBeCloseTo(5 / 9);
  });
});

describe("Advertencia de invalidación", () => {
  it("avisa qué etapas posteriores se desactualizarán y no guarda si se cancela", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/decisiones", {
      ...simulacionBase(
        { revision: "vigente", decisiones: "vigente", preparacion: "vigente", recomendacion: "vigente", configuracion_pc: "desactualizada" },
        GUARDADAS,
      ),
      "PUT /proyectos/p1/decisiones": (p: Peticion) => p.cuerpo,
    });
    const guardar = await screen.findByRole("button", { name: "Guardar decisiones" });
    await waitFor(() => expect(guardar).toBeEnabled());

    await usuario.click(guardar);
    const aviso = await screen.findByRole("dialog");
    expect(within(aviso).getByText("Preparación")).toBeInTheDocument();
    expect(within(aviso).getByText("Recomendación")).toBeInTheDocument();
    // Una etapa ya desactualizada no se vuelve a anunciar.
    expect(within(aviso).queryByText("Configuración PC")).toBeNull();

    await usuario.click(within(aviso).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(sidecar.peticiones.some((p) => p.metodo === "PUT")).toBe(false);

    await usuario.click(guardar);
    await usuario.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Guardar de todos modos" }));
    await waitFor(() => expect(sidecar.peticiones.some((p) => p.metodo === "PUT")).toBe(true));
  });

  it("guarda sin preguntar si no hay etapas posteriores vigentes", async () => {
    const usuario = userEvent.setup();
    const sidecar = renderizar("/proyectos/p1/decisiones", {
      ...simulacionBase({ revision: "vigente", decisiones: "vigente" }, GUARDADAS),
      "PUT /proyectos/p1/decisiones": (p: Peticion) => p.cuerpo,
    });
    const guardar = await screen.findByRole("button", { name: "Guardar decisiones" });
    await waitFor(() => expect(guardar).toBeEnabled());

    await usuario.click(guardar);

    await waitFor(() => expect(sidecar.peticiones.some((p) => p.metodo === "PUT")).toBe(true));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("comoNumero", () => {
  it("admite fracciones y coma decimal y deja el texto no numérico para el servidor", () => {
    expect(comoNumero("5/9")).toBeCloseTo(0.5556, 4);
    expect(comoNumero("0,5")).toBe(0.5);
    expect(comoNumero(" 32 ")).toBe(32);
    expect(comoNumero("abc")).toBe("abc");
    expect(comoNumero("")).toBe("");
    expect(comoNumero("1/0")).toBe("1/0");
  });
});

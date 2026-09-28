import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DATOS_TEMP, proyecto, renderizar } from "./utilidades";

describe("Datos del proyecto", () => {
  it("muestra la vista previa y la distribución del objetivo", async () => {
    renderizar("/proyectos/p1/datos", {
      "GET /proyectos/p1": proyecto({}),
      "GET /proyectos/p1/datos": DATOS_TEMP,
      "GET /proyectos/p1/distribucion": {
        columna: "clase", tipo: "categorias", total: 2, faltantes: 0, valores_distintos: 2, histograma: null,
        categorias: [{ valor: 1, conteo: 1, porcentaje: 50 }, { valor: 2, conteo: 1, porcentaje: 50 }],
      },
    });

    expect(await screen.findByText("86")).toBeInTheDocument();
    expect(await screen.findByText("2 filas · 2 valores distintos · 0 faltantes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revisar dataset" })).toBeEnabled();
  });
});

describe("formatoValor", () => {
  it("presenta evidencia anidada sin JSON", async () => {
    const { formatoValor } = await import("../estado/textos");
    expect(formatoValor([{ valor: 0, conteo: 500 }, { valor: 1, conteo: 268 }])).toBe("valor: 0 · conteo: 500; valor: 1 · conteo: 268");
    expect(formatoValor({ grupo_bajo: { minimo: 18 } })).toBe("grupo bajo: minimo: 18");
    expect(formatoValor([1, 2.5])).toBe("1, 2,5");
  });
});

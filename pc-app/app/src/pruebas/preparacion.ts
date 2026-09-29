import "@testing-library/jest-dom/vitest";

import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// jsdom no implementa estas API, que usa Mantine.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver ??= ResizeObserverFalso as unknown as typeof ResizeObserver;
window.HTMLElement.prototype.scrollIntoView ??= () => {};
// Textarea con autosize escucha la carga de fuentes.
if (!("fonts" in document)) {
  Object.defineProperty(document, "fonts", { value: { addEventListener: () => {}, removeEventListener: () => {} } });
}

// Esperas más holgadas: con todas las pruebas en paralelo el primer renderizado puede tardar.
configure({ asyncUtilTimeout: 3000 });

// Cytoscape necesita canvas, que jsdom no tiene: el grafo se sustituye por un doble.
vi.mock("../componentes/resultados/GrafoCausal", async () => ({
  GrafoCausal: (await import("./GrafoFalso")).GrafoFalso,
}));

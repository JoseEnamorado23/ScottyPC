import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router";

import { App } from "./App";
import { ErrorApi, ErrorSinRespuesta } from "./api/cliente";
import { Arranque } from "./componentes/Arranque";
import { ProveedorBorradores } from "./estado/borrador";

const consultas = new QueryClient({
  defaultOptions: {
    queries: {
      // Los errores de la API (4xx/5xx) y la falta de respuesta no se reintentan.
      retry: (intentos, error) => !(error instanceof ErrorApi || error instanceof ErrorSinRespuesta) && intentos < 2,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={consultas}>
        <Arranque>
          <ProveedorBorradores>
            <HashRouter>
              <App />
            </HashRouter>
          </ProveedorBorradores>
        </Arranque>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);

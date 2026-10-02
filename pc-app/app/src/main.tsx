import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "@mantine/dates/styles.css";
import "dayjs/locale/es";

import { Checkbox, MantineProvider, createTheme } from "@mantine/core";
import { DatesProvider } from "@mantine/dates";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router";

import { App } from "./App";
import { ErrorApi, ErrorSinRespuesta } from "./api/cliente";
import { Arranque } from "./componentes/Arranque";
import { ProveedorBorradores } from "./estado/borrador";
import { ProveedorBorradoresAnalisis } from "./estado/borradorAnalisis";
import { VigilanteTrabajos } from "./estado/trabajos";

const consultas = new QueryClient({
  defaultOptions: {
    queries: {
      // Los errores de la API (4xx/5xx) y la falta de respuesta no se reintentan.
      retry: (intentos, error) => !(error instanceof ErrorApi || error instanceof ErrorSinRespuesta) && intentos < 2,
      refetchOnWindowFocus: false,
    },
  },
});

const theme = createTheme({
  fontFamily: "'Fira Code', monospace",
  fontFamilyMonospace: "'Fira Code', monospace",
  headings: { fontFamily: "'Fira Code', monospace" },
  components: {
    Checkbox: Checkbox.extend({
      defaultProps: {
        color: "dark",
        radius: "sm",
        size: "sm",
      },
    }),
  },
});

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <DatesProvider settings={{ locale: "es", firstDayOfWeek: 1 }}>
        <Notifications />
        <QueryClientProvider client={consultas}>
          <Arranque>
            <ProveedorBorradores>
              <ProveedorBorradoresAnalisis>
                <VigilanteTrabajos>
                  <HashRouter>
                    <App />
                  </HashRouter>
                </VigilanteTrabajos>
              </ProveedorBorradoresAnalisis>
            </ProveedorBorradores>
          </Arranque>
        </QueryClientProvider>
      </DatesProvider>
    </MantineProvider>
  </StrictMode>,
);

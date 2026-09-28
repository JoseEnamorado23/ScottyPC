// Renderizado de pantallas con un sidecar simulado (fetch falso por método y ruta).
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { Rutas } from "../App";
import type { Esquemas } from "../api/cliente";
import { crearCliente } from "../api/cliente";
import { ProveedorApi } from "../api/contexto";
import { ProveedorBorradores } from "../estado/borrador";
import { ProveedorBorradoresAnalisis } from "../estado/borradorAnalisis";
import { VigilanteTrabajos } from "../estado/trabajos";

export const TOKEN = "token-de-prueba";

export interface Peticion {
  metodo: string;
  ruta: string;
  token: string | null;
  cuerpo: unknown;
}

type Manejador = (peticion: Peticion) => { estado?: number; cuerpo?: unknown } | unknown;

/** `{"GET /proyectos/p1": datos | (peticion) => datos | {estado, cuerpo}}` */
export type Simulacion = Record<string, Manejador | unknown>;

export const respuesta = (estado: number, cuerpo: unknown) => ({ __respuesta: true, estado, cuerpo });

export function sidecarFalso(simulacion: Simulacion) {
  const peticiones: Peticion[] = [];
  const fetch = async (entrada: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = entrada instanceof Request ? entrada : new Request(entrada, init);
    const url = new URL(request.url);
    const texto = await request.text();
    const peticion: Peticion = {
      metodo: request.method,
      ruta: url.pathname,
      token: request.headers.get("X-Token"),
      cuerpo: texto ? JSON.parse(texto) : null,
    };
    peticiones.push(peticion);
    const manejador = simulacion[`${peticion.metodo} ${peticion.ruta}`];
    if (manejador === undefined) {
      return new Response(JSON.stringify({ error: { codigo: "NO_ENCONTRADO", mensaje: `Sin simular: ${peticion.metodo} ${peticion.ruta}` } }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
    let resultado = typeof manejador === "function" ? (manejador as Manejador)(peticion) : manejador;
    let estado = 200;
    if (resultado && typeof resultado === "object" && "__respuesta" in resultado) {
      const r = resultado as unknown as { estado: number; cuerpo: unknown };
      estado = r.estado;
      resultado = r.cuerpo;
    }
    return new Response(estado === 204 ? null : JSON.stringify(resultado), {
      status: estado,
      headers: { "Content-Type": "application/json" },
    });
  };
  return { fetch, peticiones };
}

export function renderizar(ruta: string, simulacion: Simulacion) {
  const sidecar = sidecarFalso(simulacion);
  const cliente = crearCliente({ url: "http://127.0.0.1:9999", token: TOKEN, fetch: sidecar.fetch });
  const consultas = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <MantineProvider>
      <QueryClientProvider client={consultas}>
        <ProveedorApi valor={{ cliente, avisarSinRespuesta: () => {} }}>
          <ProveedorBorradores>
            <ProveedorBorradoresAnalisis>
              <VigilanteTrabajos>
                <MemoryRouter initialEntries={[ruta]}>
                  <Rutas />
                </MemoryRouter>
              </VigilanteTrabajos>
            </ProveedorBorradoresAnalisis>
          </ProveedorBorradores>
        </ProveedorApi>
      </QueryClientProvider>
    </MantineProvider>,
  );
  return sidecar;
}

// --- Datos de ejemplo --------------------------------------------------------------------------

export function proyecto(etapas: Record<string, "vigente" | "desactualizada">): Esquemas["Proyecto"] {
  return {
    id: "p1",
    nombre: "Dengue",
    archivo_original: "C:/Datos de prueba/dengue año.csv",
    sha256: "0".repeat(64),
    hoja: null,
    objetivo: "clase",
    etapa_actual: "decisiones",
    etapas,
    trabajo_activo: null,
    creado_en: "2026-09-27T10:00:00",
    actualizado_en: "2026-09-27T10:00:00",
  };
}

const hallazgo = (
  identificador: string,
  tipo: string,
  columna: string,
  severidad: "alta" | "media" | "baja",
  acciones: string[],
  sugerida: string,
): Esquemas["Hallazgo"] => ({
  tipo,
  columnas_involucradas: [columna],
  severidad,
  detalle: `Detalle de ${tipo} en ${columna}.`,
  evidencia: { proporcion: 0.25 },
  acciones_posibles: acciones,
  accion_sugerida: sugerida,
  identificador,
});

export const HALLAZGOS = [
  hallazgo("dup", "filas_duplicadas", "*", "media", ["eliminar_duplicados", "conservar"], "eliminar_duplicados"),
  hallazgo("ceros:glucosa", "ceros_sospechosos", "glucosa", "alta", ["conservar", "ceros_como_faltantes"], "conservar"),
  hallazgo("mezcla:temp", "posible_mezcla_unidades", "temp", "alta", ["conservar", "convertir_unidades"], "conservar"),
];
const CONFIRMAR = new Set(["ceros:glucosa", "mezcla:temp"]);

export const REVISION: Esquemas["Revision"] = {
  valido: true,
  validacion: { valido: true, errores: [], advertencias: [] },
  resumen: {},
  hallazgos: HALLAZGOS,
  perfiles_columnas: [
    { nombre: "temp", tipo_detectado: "numerica", faltantes: 0, porcentaje_faltantes: 0, valores_unicos: 40, minimo: 18, maximo: 89 },
  ],
  objetivo: "clase",
  informacion_objetivo: {},
};

/**
 * Doble del núcleo para las pruebas: refleja las elecciones recibidas. La lógica
 * real de acciones → decisiones está en Python (`aplicar_elecciones`).
 */
export function decisionesPara(elecciones: Record<string, string>): Esquemas["DecisionesUsuario"] {
  const acciones: Esquemas["DecisionesUsuario"]["acciones_hallazgos"] = {};
  for (const h of HALLAZGOS) {
    acciones[h.identificador] = {
      accion: elecciones[h.identificador] ?? h.accion_sugerida!,
      opciones: h.acciones_posibles,
      descripcion: `Descripción de ${h.identificador}.`,
      requiere_confirmacion: CONFIRMAR.has(h.identificador),
    };
  }
  const convertir = acciones["mezcla:temp"].accion === "convertir_unidades";
  return {
    eliminar_duplicados: acciones.dup.accion === "eliminar_duplicados",
    acciones_hallazgos: acciones,
    columnas_excluidas: [],
    faltantes: {},
    codificaciones: {},
    conversiones: convertir
      ? [{ columna: "temp", condicion: ">", umbral: 47, restar: 0, multiplicar: 1, descripcion: "Complete 'restar' y 'multiplicar'." }]
      : [],
    logaritmos: [],
    normalizar: false,
    columnas_fecha_disponibles: [],
    notas: [],
  };
}

export const DATOS_TEMP: Esquemas["DatosHoja"] = {
  hoja: null,
  hojas: null,
  filas: 2,
  columnas: ["temp", "clase"],
  vista_previa: [
    { temp: 20, clase: 1 },
    { temp: 86, clase: 2 },
  ],
};

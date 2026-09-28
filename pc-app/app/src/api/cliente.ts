// Cliente tipado del sidecar, generado a partir de /openapi.json (ver esquema.d.ts).
import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./esquema";

export type Esquemas = components["schemas"];
export type Cliente = ReturnType<typeof createClient<paths>>;

export interface ErrorCampo {
  campo: string;
  mensaje: string;
}

/** Error devuelto por la API con el formato uniforme `{error: {codigo, mensaje, detalles}}`. */
export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalles: unknown = null,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }

  /** Referencia del registro del servidor (solo errores 500). */
  get referencia(): string | null {
    const detalles = this.detalles as { referencia?: unknown } | null;
    return typeof detalles?.referencia === "string" ? detalles.referencia : null;
  }

  /** Errores por campo: `{"conversiones.0.multiplicar": "Debe ser un número."}`. */
  get porCampo(): Record<string, string> {
    const resultado: Record<string, string> = {};
    if (Array.isArray(this.detalles)) {
      for (const d of this.detalles as Partial<ErrorCampo>[]) {
        if (typeof d?.campo === "string" && typeof d.mensaje === "string") resultado[d.campo] = d.mensaje;
      }
    }
    return resultado;
  }
}

/** El motor no respondió (proceso detenido o colgado). */
export class ErrorSinRespuesta extends Error {
  constructor() {
    super("El motor de análisis no responde.");
    this.name = "ErrorSinRespuesta";
  }
}

export interface OpcionesCliente {
  url: string;
  token: string | null;
  fetch?: typeof globalThis.fetch;
  alPerderConexion?: () => void;
}

export function crearCliente({ url, token, fetch, alPerderConexion }: OpcionesCliente): Cliente {
  const base = fetch ?? globalThis.fetch.bind(globalThis);
  // El token viaja siempre en el encabezado X-Token, nunca en la URL.
  const conToken: typeof globalThis.fetch = async (entrada, init) => {
    try {
      return await base(entrada, init);
    } catch {
      alPerderConexion?.();
      throw new ErrorSinRespuesta();
    }
  };
  const cliente = createClient<paths>({ baseUrl: url, fetch: conToken });
  const autenticacion: Middleware = {
    onRequest({ request }) {
      if (token) request.headers.set("X-Token", token);
      return request;
    },
  };
  cliente.use(autenticacion);
  return cliente;
}

interface Respuesta<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Devuelve los datos o lanza `ErrorApi` con el mensaje en español del servidor. */
export async function datos<T>(peticion: Promise<Respuesta<T>>): Promise<T> {
  const { data, error, response } = await peticion;
  if (!response.ok) {
    const cuerpo = (error as { error?: Esquemas["CuerpoError"] } | undefined)?.error;
    throw new ErrorApi(
      response.status,
      cuerpo?.codigo ?? "ERROR_HTTP",
      cuerpo?.mensaje ?? `Error inesperado del servidor (${response.status}).`,
      cuerpo?.detalles ?? null,
    );
  }
  return data as T;
}

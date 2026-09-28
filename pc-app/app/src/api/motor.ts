// Conexión con el motor de análisis a través de los comandos de Tauri.
// Fuera de Tauri (`npm run dev` en un navegador) se usa el sidecar en modo
// desarrollo: `python -m pcapp_servidor --datos <carpeta> --modo-desarrollo --sin-token`.

export interface Conexion {
  url: string;
  token: string | null;
}

export interface FalloMotor {
  mensaje: string;
  carpeta_registros: string;
}

export type EstadoMotor =
  | { estado: "iniciando" }
  | { estado: "listo"; puerto: number; token: string }
  | ({ estado: "fallo" } & FalloMotor)
  | { estado: "apagado" };

const CONEXION_DESARROLLO: Conexion = { url: "http://127.0.0.1:8765", token: null };

export function enTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function comoFallo(error: unknown): FalloMotor {
  if (error && typeof error === "object" && "mensaje" in error) return error as FalloMotor;
  return { mensaje: String(error), carpeta_registros: "" };
}

async function invocar(comando: "obtener_conexion" | "reiniciar_motor"): Promise<Conexion> {
  if (!enTauri()) return CONEXION_DESARROLLO;
  const { invoke } = await import("@tauri-apps/api/core");
  try {
    return await invoke<Conexion>(comando);
  } catch (error) {
    throw comoFallo(error);
  }
}

export const obtenerConexion = () => invocar("obtener_conexion");
export const reiniciarMotor = () => invocar("reiniciar_motor");

/** Avisa de los cambios de estado del motor (p. ej., si se detiene). Devuelve la función para dejar de escuchar. */
export async function escucharEstadoMotor(alCambiar: (estado: EstadoMotor) => void): Promise<() => void> {
  if (!enTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen<EstadoMotor>("motor-estado", (evento) => alCambiar(evento.payload));
}

/** Diálogo nativo para elegir el dataset (CSV o Excel). */
export async function elegirArchivo(): Promise<string | null> {
  if (!enTauri()) {
    const ruta = window.prompt("Ruta completa del archivo CSV o Excel:");
    return ruta?.trim() || null;
  }
  const { open } = await import("@tauri-apps/plugin-dialog");
  const ruta = await open({
    multiple: false,
    directory: false,
    title: "Elegir dataset",
    filters: [
      { name: "Datos (CSV, Excel)", extensions: ["csv", "xlsx"] },
      { name: "CSV", extensions: ["csv"] },
      { name: "Excel", extensions: ["xlsx"] },
    ],
  });
  return typeof ruta === "string" ? ruta : null;
}

/**
 * Notificación del sistema operativo, solo si la ventana de la app no está en primer
 * plano (dentro de la app ya se muestra la notificación de siempre).
 */
export async function notificarSistema(titulo: string, cuerpo: string): Promise<void> {
  if (!enTauri()) return;
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    if (await getCurrentWindow().isFocused()) return;
    const notificacion = await import("@tauri-apps/plugin-notification");
    let permitido = await notificacion.isPermissionGranted();
    if (!permitido) permitido = (await notificacion.requestPermission()) === "granted";
    if (permitido) notificacion.sendNotification({ title: titulo, body: cuerpo });
  } catch {
    // Una notificación que no se puede mostrar no debe interrumpir la aplicación.
  }
}

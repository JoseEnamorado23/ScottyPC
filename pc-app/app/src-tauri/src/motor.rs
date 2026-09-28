//! Ciclo de vida del motor de análisis (el sidecar `pcapp_servidor`).
//!
//! El motor se lanza como proceso hijo e imprime una línea JSON al estar listo:
//! `{"evento":"listo","puerto":N,"token":"..."}` o `{"evento":"error","mensaje":"..."}`.
//! Solo cambia *cómo* se lanza (`OrigenMotor`); lectura del arranque, estado,
//! apagado y reinicio son comunes a desarrollo y a la aplicación empaquetada.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::watch;

const TIEMPO_ARRANQUE_POR_DEFECTO: Duration = Duration::from_secs(60);
const ESPERA_APAGADO: Duration = Duration::from_secs(5);
pub const EVENTO_ESTADO: &str = "motor-estado";

/// Cómo se lanza el motor.
#[derive(Debug, Clone)]
pub enum OrigenMotor {
    /// `python -m pcapp_servidor` con el intérprete indicado.
    Desarrollo { python: PathBuf },
    /// Ejecutable empaquetado junto a la aplicación (`externalBin`, fase 8).
    Empaquetado,
}

impl OrigenMotor {
    /// `PCAPP_PYTHON` si está definida; si no, el entorno virtual del repositorio
    /// en compilaciones de desarrollo y el ejecutable empaquetado en publicación.
    pub fn desde_entorno() -> Self {
        if let Some(python) = std::env::var_os("PCAPP_PYTHON").filter(|v| !v.is_empty()) {
            return OrigenMotor::Desarrollo { python: PathBuf::from(python) };
        }
        if cfg!(debug_assertions) {
            let venv = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..").join("sidecar").join(".venv");
            let python = if cfg!(windows) { venv.join("Scripts").join("python.exe") } else { venv.join("bin").join("python") };
            OrigenMotor::Desarrollo { python }
        } else {
            OrigenMotor::Empaquetado
        }
    }
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(tag = "estado", rename_all = "snake_case")]
pub enum EstadoMotor {
    Iniciando,
    Listo { puerto: u16, token: String },
    /// No arrancó (error, tiempo agotado) o terminó inesperadamente.
    Fallo { mensaje: String, carpeta_registros: String },
    Apagado,
}

#[derive(Debug, Clone, Serialize)]
pub struct Conexion {
    pub url: String,
    pub token: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct FalloMotor {
    pub mensaje: String,
    pub carpeta_registros: String,
}

#[derive(Deserialize)]
#[serde(tag = "evento", rename_all = "snake_case")]
enum LineaArranque {
    Listo { puerto: u16, token: String },
    Error { mensaje: String },
}

struct Proceso {
    generacion: u64,
    hijo: CommandChild,
    terminado: Arc<AtomicBool>,
}

pub struct GestorMotor {
    origen: OrigenMotor,
    datos: PathBuf,
    tiempo_arranque: Duration,
    estado: watch::Sender<EstadoMotor>,
    proceso: Mutex<Option<Proceso>>,
    /// Cada lanzamiento tiene su número; los eventos de procesos anteriores se ignoran.
    generacion: AtomicU64,
}

impl GestorMotor {
    pub fn new(origen: OrigenMotor, datos: PathBuf) -> Self {
        let tiempo_arranque = std::env::var("PCAPP_TIEMPO_ARRANQUE")
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .map(Duration::from_secs)
            .unwrap_or(TIEMPO_ARRANQUE_POR_DEFECTO);
        GestorMotor {
            origen,
            datos,
            tiempo_arranque,
            estado: watch::channel(EstadoMotor::Iniciando).0,
            proceso: Mutex::new(None),
            generacion: AtomicU64::new(0),
        }
    }

    pub fn carpeta_registros(&self) -> PathBuf {
        self.datos.join("logs")
    }

    fn fallo(&self, mensaje: impl Into<String>) -> EstadoMotor {
        EstadoMotor::Fallo { mensaje: mensaje.into(), carpeta_registros: self.carpeta_registros().display().to_string() }
    }

    fn fijar_estado(&self, app: &AppHandle, generacion: u64, estado: EstadoMotor) {
        if self.generacion.load(Ordering::SeqCst) != generacion {
            return;
        }
        self.estado.send_replace(estado.clone());
        let _ = app.emit(EVENTO_ESTADO, estado);
    }

    /// Lanza el motor y vigila su salida; no espera a que esté listo.
    pub fn iniciar(self: &Arc<Self>, app: &AppHandle) {
        let generacion = self.generacion.fetch_add(1, Ordering::SeqCst) + 1;
        self.fijar_estado(app, generacion, EstadoMotor::Iniciando);

        let comando = match &self.origen {
            OrigenMotor::Desarrollo { python } => app.shell().command(python).args(["-m", "pcapp_servidor"]),
            OrigenMotor::Empaquetado => {
                let mensaje = "La aplicación empaquetada aún no incluye el motor. Defina PCAPP_PYTHON con el intérprete que tiene instalado pcapp_servidor.";
                self.fijar_estado(app, generacion, self.fallo(mensaje));
                return;
            }
        };
        if let Err(error) = std::fs::create_dir_all(&self.datos) {
            self.fijar_estado(app, generacion, self.fallo(format!("No se pudo crear la carpeta de datos: {error}.")));
            return;
        }
        // Los argumentos se pasan como OsStr: rutas con espacios y acentos no se reinterpretan.
        let comando = comando
            .arg("--datos")
            .arg(self.datos.as_os_str())
            .arg("--pid-padre")
            .arg(std::process::id().to_string())
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .env("PYTHONUNBUFFERED", "1");

        let (mut eventos, hijo) = match comando.spawn() {
            Ok(resultado) => resultado,
            Err(error) => {
                let mensaje = match &self.origen {
                    OrigenMotor::Desarrollo { python } => {
                        format!("No se pudo ejecutar Python ({}): {error}.", python.display())
                    }
                    OrigenMotor::Empaquetado => format!("No se pudo ejecutar el motor: {error}."),
                };
                self.fijar_estado(app, generacion, self.fallo(mensaje));
                return;
            }
        };
        let terminado = Arc::new(AtomicBool::new(false));
        *self.proceso.lock().unwrap() = Some(Proceso { generacion, hijo, terminado: terminado.clone() });

        // Lectura de la salida durante toda la vida del proceso (el canal debe vaciarse siempre).
        let gestor = self.clone();
        let app_eventos = app.clone();
        tauri::async_runtime::spawn(async move {
            let mut listo = false;
            let mut ultima_stderr = String::new();
            while let Some(evento) = eventos.recv().await {
                match evento {
                    CommandEvent::Stdout(linea) if !listo => {
                        let linea = String::from_utf8_lossy(&linea);
                        match serde_json::from_str::<LineaArranque>(linea.trim()) {
                            Ok(LineaArranque::Listo { puerto, token }) => {
                                listo = true;
                                gestor.fijar_estado(&app_eventos, generacion, EstadoMotor::Listo { puerto, token });
                            }
                            Ok(LineaArranque::Error { mensaje }) => {
                                gestor.fijar_estado(&app_eventos, generacion, gestor.fallo(mensaje));
                            }
                            Err(_) => {}
                        }
                    }
                    CommandEvent::Stderr(linea) => {
                        let linea = String::from_utf8_lossy(&linea).trim().to_string();
                        if !linea.is_empty() {
                            ultima_stderr = linea;
                        }
                    }
                    CommandEvent::Terminated(salida) => {
                        terminado.store(true, Ordering::SeqCst);
                        let ya_fallo = matches!(*gestor.estado.borrow(), EstadoMotor::Fallo { .. });
                        if !ya_fallo {
                            let codigo = salida.code.map(|c| c.to_string()).unwrap_or_else(|| "desconocido".into());
                            let mut mensaje = if listo {
                                format!("El motor de análisis se detuvo inesperadamente (código {codigo}).")
                            } else {
                                format!("El motor de análisis terminó antes de estar listo (código {codigo}).")
                            };
                            if !ultima_stderr.is_empty() {
                                mensaje.push_str(&format!(" Último mensaje: {ultima_stderr}"));
                            }
                            gestor.fijar_estado(&app_eventos, generacion, gestor.fallo(mensaje));
                        }
                        break;
                    }
                    CommandEvent::Error(error) => {
                        gestor.fijar_estado(&app_eventos, generacion, gestor.fallo(format!("Error leyendo el motor: {error}.")));
                    }
                    _ => {}
                }
            }
        });

        // Tiempo máximo de arranque.
        let gestor = self.clone();
        let app_limite = app.clone();
        tauri::async_runtime::spawn(async move {
            let mut receptor = gestor.estado.subscribe();
            let espera = receptor.wait_for(|e| *e != EstadoMotor::Iniciando);
            if tokio::time::timeout(gestor.tiempo_arranque, espera).await.is_err() {
                gestor.fijar_estado(
                    &app_limite,
                    generacion,
                    gestor.fallo(format!(
                        "El motor de análisis no respondió en {} s.",
                        gestor.tiempo_arranque.as_secs()
                    )),
                );
                gestor.matar(generacion);
            }
        });
    }

    fn matar(&self, generacion: u64) {
        let mut proceso = self.proceso.lock().unwrap();
        if proceso.as_ref().is_some_and(|p| p.generacion == generacion) {
            if let Some(p) = proceso.take() {
                let _ = p.hijo.kill();
            }
        }
    }

    /// Espera a que el arranque en curso termine y devuelve la conexión o el fallo.
    pub async fn conexion(&self) -> Result<Conexion, FalloMotor> {
        let mut receptor = self.estado.subscribe();
        let estado = receptor
            .wait_for(|e| *e != EstadoMotor::Iniciando)
            .await
            .map(|e| e.clone())
            .unwrap_or(EstadoMotor::Apagado);
        match estado {
            EstadoMotor::Listo { puerto, token } => Ok(Conexion { url: format!("http://127.0.0.1:{puerto}"), token }),
            EstadoMotor::Fallo { mensaje, carpeta_registros } => Err(FalloMotor { mensaje, carpeta_registros }),
            _ => Err(FalloMotor {
                mensaje: "El motor de análisis está apagado.".into(),
                carpeta_registros: self.carpeta_registros().display().to_string(),
            }),
        }
    }

    /// Apagado ordenado: `POST /apagar` y, si el proceso no termina en unos
    /// segundos, se mata. Es bloqueante (se usa al cerrar la aplicación).
    pub fn apagar(&self) {
        // Invalida la generación actual: su terminación ya no se informa como fallo.
        self.generacion.fetch_add(1, Ordering::SeqCst);
        let estado = self.estado.send_replace(EstadoMotor::Apagado);
        let Some(proceso) = self.proceso.lock().unwrap().take() else { return };
        if let EstadoMotor::Listo { puerto, token } = estado {
            let _ = ureq::post(&format!("http://127.0.0.1:{puerto}/apagar"))
                .set("X-Token", &token)
                .timeout(Duration::from_secs(2))
                .call();
            let limite = Instant::now() + ESPERA_APAGADO;
            while Instant::now() < limite && !proceso.terminado.load(Ordering::SeqCst) {
                std::thread::sleep(Duration::from_millis(100));
            }
        }
        if !proceso.terminado.load(Ordering::SeqCst) {
            let _ = proceso.hijo.kill();
        }
    }
}

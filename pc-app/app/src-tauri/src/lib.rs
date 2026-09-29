mod imagen;
mod motor;

use std::sync::Arc;

use tauri::{AppHandle, Manager, RunEvent, State};

use motor::{Conexion, FalloMotor, GestorMotor, OrigenMotor};

/// URL y token del motor; espera si todavía está arrancando.
#[tauri::command]
async fn obtener_conexion(gestor: State<'_, Arc<GestorMotor>>) -> Result<Conexion, FalloMotor> {
    gestor.conexion().await
}

/// Apaga el motor (si sigue vivo) y lo vuelve a lanzar.
#[tauri::command]
async fn reiniciar_motor(app: AppHandle, gestor: State<'_, Arc<GestorMotor>>) -> Result<Conexion, FalloMotor> {
    let gestor = gestor.inner().clone();
    let apagando = gestor.clone();
    let _ = tauri::async_runtime::spawn_blocking(move || apagando.apagar()).await;
    gestor.iniciar(&app);
    gestor.conexion().await
}

pub fn run() {
    let aplicacion = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            let datos = app.path().app_data_dir()?;
            let gestor = Arc::new(GestorMotor::new(OrigenMotor::desde_entorno(), datos));
            gestor.iniciar(app.handle());
            app.manage(gestor);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![obtener_conexion, reiniciar_motor, imagen::guardar_imagen])
        .build(tauri::generate_context!())
        .expect("no se pudo construir la aplicación");

    aplicacion.run(|app, evento| {
        if let RunEvent::Exit = evento {
            if let Some(gestor) = app.try_state::<Arc<GestorMotor>>() {
                gestor.apagar();
            }
        }
    });
}

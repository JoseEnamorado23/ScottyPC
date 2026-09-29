//! Guardar la imagen del grafo sin dar permisos de escritura al frontend.
//!
//! Con `tauri-plugin-fs` + `fs:allow-write-file`, el frontend podría escribir en
//! cualquier ruta que haya devuelto un diálogo durante la sesión (el plugin de
//! diálogo añade al alcance de `fs` también el dataset elegido al abrir y la
//! carpeta elegida para exportar). Aquí el diálogo lo abre Rust y los bytes se
//! escriben solo en la ruta que el usuario elige en ese mismo diálogo.

use std::path::PathBuf;

use tauri::ipc::{InvokeBody, Request};
use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

const FIRMA_PNG: &[u8] = b"\x89PNG\r\n\x1a\n";

/// Nombre sugerido seguro: solo letras ASCII, dígitos, `-` y `_`, con extensión `.png`.
fn nombre_sugerido(nombre: Option<&str>) -> String {
    let base: String = nombre
        .unwrap_or("grafo")
        .trim_end_matches(".png")
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '_' })
        .take(80)
        .collect();
    format!("{}.png", if base.is_empty() { "grafo" } else { &base })
}

fn con_extension_png(mut ruta: PathBuf) -> PathBuf {
    let es_png = ruta
        .extension()
        .map(|e| e.eq_ignore_ascii_case("png"))
        .unwrap_or(false);
    if !es_png {
        let mut nombre = ruta.file_name().unwrap_or_default().to_os_string();
        nombre.push(".png");
        ruta.set_file_name(nombre);
    }
    ruta
}

/// Abre el diálogo «Guardar» y escribe la imagen PNG recibida (cuerpo binario de la
/// petición; encabezado opcional `nombre-sugerido`). Devuelve la ruta, o `None` si el
/// usuario cancela.
#[tauri::command]
pub async fn guardar_imagen(app: AppHandle, request: Request<'_>) -> Result<Option<String>, String> {
    let InvokeBody::Raw(datos) = request.body() else {
        return Err("Se esperaban los bytes de la imagen.".into());
    };
    if !datos.starts_with(FIRMA_PNG) {
        return Err("Los datos recibidos no son una imagen PNG.".into());
    }
    let nombre = nombre_sugerido(
        request
            .headers()
            .get("nombre-sugerido")
            .and_then(|valor| valor.to_str().ok()),
    );
    let elegida = app
        .dialog()
        .file()
        .set_title("Guardar imagen del grafo")
        .set_file_name(nombre)
        .add_filter("Imagen PNG", &["png"])
        .blocking_save_file();
    let Some(elegida) = elegida else {
        return Ok(None);
    };
    let ruta = con_extension_png(elegida.into_path().map_err(|error| error.to_string())?);
    std::fs::write(&ruta, datos)
        .map_err(|error| format!("No se pudo guardar la imagen en {}: {error}", ruta.display()))?;
    Ok(Some(ruta.display().to_string()))
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn nombre_sugerido_seguro() {
        assert_eq!(nombre_sugerido(None), "grafo.png");
        assert_eq!(nombre_sugerido(Some("Diabetes ñ v2.png")), "Diabetes___v2.png");
        assert_eq!(nombre_sugerido(Some("../../x")), "______x.png");
        assert_eq!(nombre_sugerido(Some("")), "grafo.png");
    }

    #[test]
    fn agrega_la_extension_png() {
        assert_eq!(con_extension_png(PathBuf::from("a/grafo")), PathBuf::from("a/grafo.png"));
        assert_eq!(con_extension_png(PathBuf::from("a/grafo.PNG")), PathBuf::from("a/grafo.PNG"));
        assert_eq!(con_extension_png(PathBuf::from("a/grafo.txt")), PathBuf::from("a/grafo.txt.png"));
    }
}

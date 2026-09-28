// Evita la consola adicional en Windows en compilaciones de publicación.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    pcapp_lib::run()
}

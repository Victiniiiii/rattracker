#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use tauri::command;
use tauri_plugin_dialog::DialogExt;

#[command]
async fn pick_file(app: tauri::AppHandle) -> Result<String, String> {
    match app.dialog().file().blocking_pick_file() {
        Some(path) => path.into_path()
            .map(|p| p.to_string_lossy().to_string())
            .map_err(|e| e.to_string()),
        None => Err("No file selected".into()),
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![pick_file])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
// src-tauri/src/lib.rs

use tauri_plugin_dialog::DialogExt;
use tauri::command;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_os::init())
        .invoke_handler(tauri::generate_handler![pick_file])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[command]
async fn pick_file(app: tauri::AppHandle) -> Result<String, String> {
    match app.dialog().file().blocking_pick_file() {
        Some(path) => path.into_path()
            .map(|p| p.to_string_lossy().to_string())
            .map_err(|e| e.to_string()),
        None => Err("No file selected".into()),
    }
}
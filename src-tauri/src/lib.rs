// src-tauri/src/lib.rs

use std::net::SocketAddr;
use std::sync::OnceLock;
use axum::{Router, extract::Query, http::{HeaderMap, HeaderValue, StatusCode, header}, response::IntoResponse, routing::get};
use serde::Deserialize;
use tauri::command;
use tauri_plugin_dialog::DialogExt;
use tokio::{fs::File, io::{AsyncReadExt, AsyncSeekExt}};

static SERVER_PORT: OnceLock<u16> = OnceLock::new();

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_os::init())
        .setup(|_app| {
            tauri::async_runtime::spawn(start_file_server());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![pick_file, get_server_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

async fn start_file_server() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    SERVER_PORT.set(port).unwrap();

    let app = Router::new().route("/file", get(serve_file));
    axum::serve(listener, app).await.unwrap();
}

#[derive(Deserialize)]
struct FileQuery {
    path: String,
}

async fn serve_file(Query(params): Query<FileQuery>, headers: HeaderMap) -> impl IntoResponse {
    let path = &params.path;

    let mut file = match File::open(path).await {
        Ok(f) => f,
        Err(_) => return (StatusCode::NOT_FOUND, HeaderMap::new(), vec![]).into_response(),
    };

    let file_size = match file.metadata().await {
        Ok(m) => m.len(),
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, HeaderMap::new(), vec![]).into_response(),
    };

    let mime = mime_from_path(path);

    let range_header = headers.get(header::RANGE).and_then(|v| v.to_str().ok()).and_then(parse_range);

    let mut resp_headers = HeaderMap::new();
    resp_headers.insert(header::CONTENT_TYPE, HeaderValue::from_static(mime));
    resp_headers.insert(header::ACCEPT_RANGES, HeaderValue::from_static("bytes"));
    resp_headers.insert("Access-Control-Allow-Origin", HeaderValue::from_static("*"));

    if let Some((start, end)) = range_header {
        let end = end.unwrap_or(file_size - 1).min(file_size - 1);
        let length = end - start + 1;

        file.seek(std::io::SeekFrom::Start(start)).await.unwrap();
        let mut buf = vec![0u8; length as usize];
        file.read_exact(&mut buf).await.unwrap();

        let range_val = format!("bytes {}-{}/{}", start, end, file_size);
        resp_headers.insert(header::CONTENT_RANGE, HeaderValue::from_str(&range_val).unwrap());
        resp_headers.insert(header::CONTENT_LENGTH, HeaderValue::from(length));

        (StatusCode::PARTIAL_CONTENT, resp_headers, buf).into_response()
    } else {
        let mut buf = Vec::with_capacity(file_size as usize);
        file.read_to_end(&mut buf).await.unwrap();

        resp_headers.insert(header::CONTENT_LENGTH, HeaderValue::from(file_size));

        (StatusCode::OK, resp_headers, buf).into_response()
    }
}

fn parse_range(range: &str) -> Option<(u64, Option<u64>)> {
    let range = range.strip_prefix("bytes=")?;
    let mut parts = range.splitn(2, '-');
    let start: u64 = parts.next()?.parse().ok()?;
    let end: Option<u64> = parts.next().and_then(|s| if s.is_empty() { None } else { s.parse().ok() });
    Some((start, end))
}

fn mime_from_path(path: &str) -> &'static str {
    if path.ends_with(".mp4") { "video/mp4" }
    else if path.ends_with(".webm") { "video/webm" }
    else if path.ends_with(".png") { "image/png" }
    else if path.ends_with(".jpg") || path.ends_with(".jpeg") { "image/jpeg" }
    else if path.ends_with(".csv") { "text/csv" }
    else if path.ends_with(".txt") { "text/plain" }
    else { "application/octet-stream" }
}

#[command]
async fn get_server_port() -> Result<u16, String> {
    SERVER_PORT.get().copied().ok_or_else(|| "Server not ready".into())
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
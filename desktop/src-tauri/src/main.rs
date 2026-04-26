use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, State};

struct BackendState {
    base_url: String,
    child: Mutex<Option<Child>>,
}

#[tauri::command]
fn get_backend_url(state: State<BackendState>) -> String {
    state.base_url.clone()
}

fn wait_for_backend(base_url: &str, timeout: Duration) -> Result<(), String> {
    let client = reqwest::blocking::Client::new();
    let started = Instant::now();
    let health_url = format!("{base_url}/health");
    while started.elapsed() < timeout {
        match client.get(&health_url).send() {
            Ok(res) if res.status().is_success() => return Ok(()),
            _ => std::thread::sleep(Duration::from_millis(400)),
        }
    }
    Err(format!("Backend did not become healthy within {:?}", timeout))
}

fn backend_binary_candidates(resource_dir: &Path) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    #[cfg(target_os = "windows")]
    {
        candidates.push(resource_dir.join("backend-dist").join("voice-german-backend.exe"));
    }
    #[cfg(not(target_os = "windows"))]
    {
        candidates.push(resource_dir.join("backend-dist").join("voice-german-backend"));
    }
    candidates
}

fn spawn_backend(app_handle: &tauri::AppHandle, port: u16) -> Result<(String, Child), String> {
    let backend_url = format!("http://127.0.0.1:{port}");
    let app_data_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to locate app data dir: {e}"))?;

    let backend_bin = if let Ok(custom_path) = std::env::var("VOICE_GERMAN_BACKEND_BIN") {
        PathBuf::from(custom_path)
    } else {
        let resource_dir = app_handle
            .path()
            .resource_dir()
            .map_err(|e| format!("Failed to locate bundled resources: {e}"))?;
        let candidates = backend_binary_candidates(&resource_dir);
        candidates
            .into_iter()
            .find(|candidate| candidate.exists())
            .ok_or_else(|| "Bundled backend binary not found.".to_string())?
    };

    std::fs::create_dir_all(app_data_dir.join("outputs")).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(app_data_dir.join("voice_samples")).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(app_data_dir.join("model_cache")).map_err(|e| e.to_string())?;

    let child = Command::new(backend_bin)
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(port.to_string())
        .arg("--output-dir")
        .arg(app_data_dir.join("outputs"))
        .arg("--sample-dir")
        .arg(app_data_dir.join("voice_samples"))
        .env("HF_HOME", app_data_dir.join("model_cache"))
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to launch backend: {e}"))?;

    Ok((backend_url, child))
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let backend_port = std::env::var("VOICE_GERMAN_BACKEND_PORT")
                .ok()
                .and_then(|p| p.parse::<u16>().ok())
                .unwrap_or(7860);

            let (base_url, child) = spawn_backend(app.handle(), backend_port)?;
            wait_for_backend(&base_url, Duration::from_secs(60))?;

            app.manage(BackendState {
                base_url,
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    if let Ok(mut lock) = state.child.lock() {
                        if let Some(child) = lock.as_mut() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}

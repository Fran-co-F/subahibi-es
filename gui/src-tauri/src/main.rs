// SPDX-License-Identifier: GPL-3.0-or-later
//! La ventana de tl-organizer.  Al arrancar lanza el backend de Python (`python -m tl_organizer servir`) en un puerto
//! libre de 127.0.0.1 con un token aleatorio, y se lo pasa a la interfaz con el comando `backend`.  Al cerrar, lo termina.
//!
//! Qué Python usa (en este orden):
//!   TL_ORGANIZER_PYTHON;  en desarrollo, el entorno env/ del repositorio si existe;  si no, python3 (python en Windows).
//! TL_ORGANIZER_SRC agrega una carpeta al PYTHONPATH (en desarrollo, src/ del repositorio, para no tener que instalar).
//! TL_ORGANIZER_PROYECTO abre ese proyecto al empezar.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

#[derive(Clone, serde::Serialize)]
struct Backend {
    url: String,
    token: String,
}

struct Estado {
    backend: Backend,
    proceso: Mutex<Option<Child>>,
}

#[tauri::command]
fn backend(estado: tauri::State<Estado>) -> Backend {
    estado.backend.clone()
}

fn token() -> String {
    // 128 bits de las claves aleatorias que el sistema le da a cada RandomState
    (0..2)
        .map(|i| {
            let mut h = RandomState::new().build_hasher();
            h.write_u64(i);
            format!("{:016x}", h.finish())
        })
        .collect()
}

fn repo() -> Option<PathBuf> {
    // en desarrollo: gui/src-tauri -> la raíz del repositorio
    if cfg!(debug_assertions) {
        let r = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        if r.join("src").join("tl_organizer").is_dir() {
            return r.canonicalize().ok();
        }
    }
    None
}

fn python() -> String {
    if let Ok(p) = std::env::var("TL_ORGANIZER_PYTHON") {
        return p;
    }
    if let Some(r) = repo() {
        for p in [r.join("env").join("bin").join("python"), r.join("env").join("Scripts").join("python.exe")] {
            if p.exists() {
                return p.to_string_lossy().into_owned();
            }
        }
    }
    if cfg!(windows) { "python".into() } else { "python3".into() }
}

fn lanzar(puerto: u16, token: &str) -> std::io::Result<Child> {
    let mut cmd = Command::new(python());
    cmd.args(["-m", "tl_organizer", "servir", "--puerto", &puerto.to_string()]);
    cmd.env("TL_ORGANIZER_TOKEN", token);
    let src = std::env::var("TL_ORGANIZER_SRC").ok().or_else(|| repo().map(|r| r.join("src").to_string_lossy().into_owned()));
    if let Some(src) = src {
        cmd.env("PYTHONPATH", src);
    }
    if let Ok(p) = std::env::var("TL_ORGANIZER_PROYECTO") {
        cmd.args(["--proyecto", &p]);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: sin consola aparte
    }
    cmd.spawn()
}

fn main() {
    let puerto = TcpListener::bind("127.0.0.1:0").and_then(|l| l.local_addr()).map(|a| a.port()).expect("sin puertos libres");
    let token = token();
    let proceso = match lanzar(puerto, &token) {
        Ok(c) => Some(c),
        Err(e) => {
            eprintln!("no se pudo lanzar el backend de Python ({}): {e}", python());
            None
        }
    };
    let estado = Estado { backend: Backend { url: format!("http://127.0.0.1:{puerto}"), token }, proceso: Mutex::new(proceso) };

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(estado)
        .invoke_handler(tauri::generate_handler![backend])
        .build(tauri::generate_context!())
        .expect("no se pudo crear la aplicación")
        .run(|app, evento| {
            if let RunEvent::Exit = evento {
                if let Some(mut c) = app.state::<Estado>().proceso.lock().unwrap().take() {
                    let _ = c.kill();
                    let _ = c.wait();
                }
            }
        });
}

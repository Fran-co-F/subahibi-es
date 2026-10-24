# Interfaz gráfica de tl-organizer

Svelte 5 + Vite, y Tauri 2 para la app de escritorio. La interfaz habla con la API local de Python
(`src/tl_organizer/nucleo/api.py`): la misma lógica que la línea de comandos, sin duplicar nada.

```
┌──────────── ventana (Tauri: WebKitGTK / WebView2 / WKWebView) ────────────┐
│  Svelte: Panel · Traducir · Revisar · Imágenes                            │
│        │ fetch + token                                                    │
│        ▼                                                                   │
│  python -m tl_organizer servir   (127.0.0.1, puerto libre, token aleatorio)│
└────────────────────────────────────────────────────────────────────────────┘
```

Al abrir la ventana, la parte de Rust (`src-tauri/src/main.rs`) elige un puerto libre y un token, lanza el backend de Python y se
los pasa a la interfaz; al cerrarla, lo termina. Sin Tauri, `tl-organizer gui` sirve la misma interfaz y abre el navegador.

## Pantallas

- **Panel**: avance (por estado y por archivo) y acciones: exportar, armar el parche o la carpeta jugable, instalar/desinstalar, cortar líneas.
- **Traducir**: escenarios con su avance; lista de filas (virtual: aguanta escenarios de miles de filas) con búsqueda en el escenario o en todo
  el proyecto y filtro por estado; editor de la fila con vista previa de la ventana de texto del juego (fuente, tamaño y ancho configurables,
  corte por letra como el motor o por palabra). Se guarda solo mientras escribís; **Ctrl+Enter** marca «traducido» y pasa a la siguiente,
  **Alt+↑/↓** se mueve, **Ctrl+S** guarda ya. Si una fila cambió también por fuera (una hoja, un `git pull`), aparece el conflicto con las dos versiones.
- **Revisar**: el control de calidad (`tl-organizer revisar`) agrupado por problema; un clic lleva a la fila.
- **Imágenes**: la galería; se arrastra la imagen traducida sobre su tarjeta (se valida el tamaño) y se elige el estado de las demás.

## Desarrollo

```
cd gui
npm install
npm run tauri dev          # ventana de escritorio (compila Rust la primera vez)
```
En desarrollo, la app usa `src/` y `env/` del repositorio (no hace falta instalar tl-organizer). Variables útiles:
`TL_ORGANIZER_PROYECTO=/ruta/al/juego` abre ese proyecto al empezar; `TL_ORGANIZER_PYTHON` elige el intérprete.

Sin Tauri: `npm run build` y después `tl-organizer gui` (sirve `gui/dist` y abre el navegador).
Con recarga en caliente en el navegador: `TL_ORGANIZER_TOKEN=t tl-organizer servir` y `VITE_API_URL=http://127.0.0.1:PUERTO VITE_API_TOKEN=t npm run dev`.

Requisitos de Tauri en Linux: WebKitGTK 4.1, libsoup 3, GTK 3 (en Arch: `webkit2gtk-4.1`; en Debian/Ubuntu: `libwebkit2gtk-4.1-dev`), Rust y Node.

## Prueba de la interfaz

`npm run prueba -- http://127.0.0.1:PUERTO` (con `TL_ORGANIZER_TOKEN=prueba tl-organizer servir` corriendo en un proyecto exportado)
recorre las cuatro pantallas en jsdom contra la API real: carga el panel, abre un escenario, edita y guarda una fila (y la deja como estaba),
busca en todo el proyecto, corre la revisión y salta a una fila, y abre la galería. Falla si hay errores de JavaScript.

## Distribuir

`npm run tauri build` genera el ejecutable y los paquetes del sistema (`.deb`, `.rpm`, AppImage, `.msi`, `.dmg` según la plataforma).
Por ahora la app necesita Python con tl-organizer instalado (`pip install tl-organizer` o `TL_ORGANIZER_PYTHON` apuntando a un entorno que lo tenga);
empaquetar el backend como un ejecutable aparte (PyInstaller, como *sidecar* de Tauri) queda para más adelante.

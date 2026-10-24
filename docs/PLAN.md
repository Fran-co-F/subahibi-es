# Plan de implementación: de *subahibi-es* a una herramienta para traducir cualquier VN

> Documento vivo. Cada fase termina con la herramienta usable y las pruebas en verde; el estado de cada tarea está
> en la sección [Estado](#estado). Rama de trabajo: `motores-genericos`.

## 0. Objetivo y principios

**Objetivo:** que traducir una novela visual sea lo mismo sin importar el motor: `init → exportar → traducir → build → instalar`,
con una interfaz gráfica linda y multiplataforma, y que soportar un juego o un motor nuevo sea lo más barato posible.

Principios (los que ya tiene el proyecto, más los nuevos):

1. **Núcleo agnóstico, motores como plugins, juegos como datos.** El núcleo no sabe qué es un `.arc` ni un `BGI.exe`.
   Un *motor* es código que entiende formatos; un *perfil de juego* es un archivo TOML que dice qué archivos tocar y con qué parámetros.
2. **Dos niveles para soportar algo nuevo, todo programático:**
   | Nivel | Qué se escribe | Cuándo alcanza |
   |---|---|---|
   | Perfil de juego (TOML) | Rutas, detección, opciones | Juego nuevo de un motor ya soportado |
   | Motor (clase Python) | Una subclase de `Motor`; por dentro puede usar código propio, bibliotecas o herramientas existentes envueltas | Motor nuevo |

   Para que escribir un motor sea barato hay un **kit** de piezas reutilizables (fase 3): clases base para los casos comunes
   (scripts de texto, tablas de cadenas, herramientas externas) que se heredan y se completan con unos pocos atributos y métodos.
3. **Nunca tocar los originales y que todo sea reversible** (ya está: respaldo, `instalar`/`desinstalar`).
4. **Sin material del juego en el repositorio** (imágenes, texto, exe, claves privadas de nadie).
5. **Regla de tres:** la interfaz `Motor` se considera estable recién cuando la usen 2–3 motores reales muy distintos.
6. **Cada cambio se verifica**: pruebas sintéticas en CI y una *prueba dorada* contra el juego real (salida idéntica byte a byte).

---

## 1. Arquitectura objetivo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Interfaces       CLI (argparse)        API local (HTTP/JSON)     GUI web     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Núcleo           proyecto · flujo (exportar/estado/build/instalar)           │
│  (nucleo/)        hojas/almacenamiento · wrap · alineación · galería · QA     │
│                   perfiles (TOML) · enlaces · imágenes PNG/BMP               │
├───────────────────────────── interfaz Motor ─────────────────────────────────┤
│  Motores          bgi/ (Ethornell)   kirikiri/   …   (plugins: entry points)  │
│  (motores/)       cada uno: formatos + perfiles de juegos (juegos/*.toml)     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Kit (motores/kit)  MotorTextoPlano · tabla de cadenas · MotorExterno ·        │
│                     contenedores · codificaciones (todo en Python)           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Conceptos

| Concepto | Qué es | Dónde vive |
|---|---|---|
| **Motor** | Clase Python que implementa la interfaz `Motor` y declara sus *capacidades* | `motores/<nombre>/` o un paquete aparte (entry point) |
| **Perfil de juego** | TOML: identidad, detección, archivos, opciones del motor, nombres de pantallas | `motores/<motor>/juegos/*.toml`, carpeta del usuario o `$SUBAHIBI_ES_PERFILES` |
| **Proyecto** | Una instalación del juego + `subahibi-es.json` + carpeta de trabajo | La carpeta del juego |
| **Unidad de traducción** | Una fila: id estable, original, traducción, estado, contexto | Hojas / almacenamiento del núcleo |
| **Recurso** | Una imagen de interfaz (u otro binario) que se reemplaza entero | Galería del núcleo |
| **Capacidad** | Lo que un motor sabe hacer: `texto`, `imagenes`, `parche_viejo`, `ejecutable`… | `Motor.capacidades` |

### 1.2 Árbol de paquetes (al terminar la fase 1)

```
src/subahibi_es/
  cli.py                 comandos generales; cada motor agrega los suyos
  nucleo/
    proyecto.py          Project, find, init, reset (la detección la delega en perfiles + motor)
    flujo.py             exportar, estado, build, instalar, desinstalar
    config.py            valores por defecto de los comandos sueltos
    perfiles.py          carga, validación y búsqueda de perfiles TOML
    hojas.py             XLSX/TSV (antes text/sheet.py) + recolectar filas
    texto.py             exportar filas a hojas (agrupa por archivo)
    wrap.py              saltos de línea
    alineacion.py        detección de zonas dudosas (correlación de largos)
    enlaces.py           enlaces simbólicos/duros/copia (build --jugable)
    imagenes.py          abrir PNG/BMP con alfa
    galeria/             index.py, _page.py, ocr.py
  motores/
    __init__.py          registro: motores incluidos + entry points «subahibi_es.motores»
    base.py              clase Motor, capacidades, errores
    bgi/
      __init__.py        MotorBGI
      arc.py dsc.py image.py scn.py          formatos
      exe_patch.py       parche del exe (las direcciones vienen del perfil)
      build.py oldpatch.py
      text/              extract.py export.py import_.py accents.py align.py
      images/            export.py import_.py
      cli.py             patch-exe, images export/import, text export/import
      juegos/subahibi-15th.toml
```

### 1.3 La interfaz `Motor`

```python
class Motor:
    nombre = "bgi"                      # el que se escribe en el perfil: motor = "bgi"
    descripcion = "Ethornell / BGI (Buriko General Interpreter)"
    capacidades = frozenset({"texto", "imagenes", "parche_viejo", "ejecutable"})
    carpetas_sueltas = ("Script", "Graphic", "Sound", "Voice")   # lo que el parche crea en el juego

    def __init__(self, perfil): ...                    # perfil ya validado; self.opciones = su sección [bgi]
    # detección y respaldo
    def identificar_ejecutable(self, datos) -> str | None        # versión conocida o None
    def versiones_conocidas(self) -> list[str]
    # exportar
    def exportar_imagenes(self, juego, destino) -> (n, omitidas)
    def textos(self, juego, parche_viejo=None, archivos=None) -> Iterable[(grupo, escenario, filas)]
    # armar
    def construir(self, juego, salida, filas, imagenes, estados, opciones, log) -> informe
    # opcional
    def registrar_comandos(self, sub, grupos)          # comandos sueltos propios del motor
```

El núcleo **pregunta por capacidades** antes de llamar (`if "imagenes" in motor.capacidades`), así un motor
que solo sabe texto funciona igual, y la GUI apaga lo que no corresponde.

### 1.4 El perfil de juego

```toml
id      = "subahibi-15th"
nombre  = "Subarashiki Hibi 15th Anniversary"
motor   = "bgi"

[deteccion]
requeridos  = ["BGI.exe", "sysgrp.arc", "sysprg.arc", "system.arc", "data01101.arc"]
ejecutable  = "BGI.exe"          # se respalda en init y tiene que ser una versión conocida

[texto]
archivos = ["data0*.arc"]

[imagenes]
archivos = ["sysgrp.arc"]

[galeria.pantallas]
SGTitle = "Pantalla de título"

[jugable]
enlazar_extensiones = [".arc", ".ico"]
enlazar             = ["BHVC.exe", "BGI.hvl"]
copiar_una_vez      = ["BGI.gdb", "UserData"]

[bgi]                            # sección propia del motor: solo la lee el motor
fuente = "SubaHibi07Inq"

[[bgi.ejecutables]]              # direcciones del parche de exe para cada versión conocida
sha256  = "993e…"
version = "1.685.3 (15th Anniversary, x86_64)"
hook    = 0x1400DF7FA
```

Regla: **el núcleo lee las secciones generales; cada motor lee la suya (`[bgi]`, `[kirikiri]`…)** y la valida con mensajes claros.
Soportar otra versión del exe = agregar un bloque `[[bgi.ejecutables]]`, sin tocar código.

### 1.5 Descubrimiento

- **Motores:** los incluidos (`motores/bgi`, …) más cualquier paquete instalado que declare
  ```toml
  [project.entry-points."subahibi_es.motores"]
  mimotor = "mipaquete:MiMotor"
  ```
  Instalar el paquete (`pip install subahibi-es-mimotor`) alcanza para que aparezca.
- **Perfiles**, en orden de prioridad (un id repetido lo gana el primero):
  1. `$SUBAHIBI_ES_PERFILES` (carpetas separadas por `os.pathsep`);
  2. carpeta del usuario: `~/.config/subahibi-es/juegos/` (Linux/macOS, respeta `XDG_CONFIG_HOME`) o `%APPDATA%\subahibi-es\juegos\`;
  3. los incluidos en cada motor (`motores/<motor>/juegos/*.toml`).
- **Detección en `init`:** se prueban todos los perfiles; gana el primero sin problemas. Si ninguno coincide, el error muestra el más parecido
  (el de menos problemas) y qué le falta.

---

## 2. Fases

### Fase 1 — Separar el núcleo del motor BGI *(esta rama; sin cambiar el comportamiento)*

Tareas:
1. Crear `nucleo/` y `motores/`; mover con `git mv` para conservar la historia.
2. `motores/base.py` (clase `Motor`, capacidades) y `motores/__init__.py` (registro + entry points).
3. `nucleo/perfiles.py`: lectura TOML (`tomllib`; `tomli` en Python 3.10), validación, orden de búsqueda.
4. Perfil `motores/bgi/juegos/subahibi-15th.toml` con todo lo que hoy está fijo en el código: archivos requeridos, `data0*.arc`,
   `sysgrp.arc`, nombres de pantallas, enlaces de `--jugable`, fuente por defecto **y las direcciones del parche del exe**.
5. `exe_patch` recibe los datos de la versión desde el perfil en vez de un diccionario fijo.
6. `nucleo/proyecto.py`: `init` detecta el perfil; el JSON guarda `perfil`, `motor` y `version`. Los proyectos viejos (sin `perfil`)
   se siguen abriendo: se asume `subahibi-15th`.
7. `nucleo/flujo.py`: `exportar`, `build`, `estado`, `instalar`, `desinstalar` hablan con el motor por la interfaz.
8. Exportar e importar texto: el núcleo escribe y lee las hojas; el motor solo produce y consume filas.
9. El CLI conserva **los mismos comandos y opciones**; los comandos propios de BGI los registra el motor.
10. Pruebas adaptadas a las rutas nuevas, más pruebas de perfiles, registro y detección.

**Criterio de aceptación:** `pytest` en verde y la prueba dorada (`init → exportar → build → build --jugable` sobre el juego real,
con el parche viejo e imágenes traducidas) produce **exactamente los mismos bytes** que `main`.

### Fase 2 — Modelo de datos genérico

- **Unidad de traducción** con campos generales:
  `id` (estable: archivo + clave + hash del original), `grupo`, `escenario`, `tipo` (mensaje, nombre, opción, interfaz…),
  `original`, `traduccion`, `estado`, `nota`, `contexto` (hablante, línea anterior/siguiente), `restricciones`
  (bytes máximos si el motor no puede reubicar, caracteres disponibles en la fuente) y `datos_motor` (lo que hoy son `pos`/`hash`).
- **Idiomas configurables** en el proyecto (`origen = "ja"`, `destino = "es"`). Las columnas `japones`/`espanol` pasan a `original`/`traduccion`;
  las hojas viejas se siguen leyendo (migración automática al exportar).
- **Almacenamiento:** un archivo de texto por escenario (JSON Lines o TSV) como fuente de verdad, con diferencias legibles en git.
  XLSX y **PO** como importar/exportar, para usar OmegaT, Weblate, Poedit, etc. (XLIFF solo si alguna herramienta lo pide: PO cubre las habituales.)
- **Códigos de control** del motor como marcadores protegidos (`{nombre}`, `[r]`, `\n`): el motor declara una expresión regular y el núcleo
  valida que la traducción conserve los mismos marcadores.
- **Control de calidad** (`subahibi-es revisar`): marcadores rotos, líneas que no entran, caracteres que la fuente no tiene, filas vacías con estado
  `traducido`, espacios dobles.
- Decisión pendiente: **nombre del proyecto** (el paquete `subahibi_es` y el comando se renombrarían acá, dejando `subahibi-es` como alias).

### Fase 3 — Kit para escribir motores en Python

Todo es código: un motor es una clase, y lo que se repite entre motores vive en `motores/kit/` como clases base y funciones.
Si ya existe una biblioteca o una herramienta que entiende un formato, el motor la usa por dentro: el *wrapper* es la propia clase.

1. **`MotorTextoPlano`**: para motores cuyos scripts son texto (KAG `.ks`, NScripter `0.txt`, Ren'Py `.rpy`, etc.). La subclase define, en Python,
   la codificación, los archivos y las expresiones regulares de diálogo, nombres y opciones (o sobrescribe `filas_de(texto)` si hace falta lógica);
   la clase base hace extraer, reinyectar (reemplazar el texto capturado) y escribir los archivos sueltos.
2. **Tabla de cadenas** (`kit/cadenas.py`): la estrategia que ya usa BGI, generalizada. Dado el binario original y dónde están los operandos que
   apuntan a cadenas, agrega las cadenas nuevas al final y reapunta, con la verificación de que no cambió nada más. BGI pasa a usarla.
3. **`MotorExterno`**: envuelve una herramienta de línea de comandos (VNTextPatch para texto, GARbro para archivos, u otra). La subclase dice cómo
   llamarla para extraer y para inyectar, y cómo leer/escribir su formato intermedio (JSON, XLSX…); la base maneja carpetas temporales, errores y
   Wine/Mono en Linux. Revisar licencias y que corran en Linux.
4. **Contenedores** (`kit/contenedores.py`): interfaz común para archivos tipo `.arc`/`.xp3` (listar, leer, y escribir archivos sueltos o reempaquetar),
   para que el núcleo y la galería no dependan de cada formato.
5. **Codificaciones** (`kit/codificaciones.py`): Shift-JIS/UTF-8/UTF-16 con detección, y tablas de sustitución de caracteres (como los acentos
   en katakana de BGI) reutilizables por cualquier motor sin modo UTF-8.
6. **Prueba de contrato** (`motores/contrato.py`): batería que se le corre a cualquier motor con datos sintéticos
   (extraer → reinyectar sin cambios → bytes idénticos; reinyectar una traducción → volver a extraer → aparece; original cambiado → error claro).

### Fase 4 — Segundo y tercer motor (validar la abstracción)

- **Kirikiri / KAG** (recomendado como segundo): archivos `.xp3` (zlib, a veces con cifrado propio de cada juego: un *hook* del perfil o un plugin
  provee el descifrado) y scripts `.ks` en texto (Shift-JIS o UTF-16LE). Hereda de `MotorTextoPlano` (fase 3) con un contenedor nuevo.
- **Tercero, a elegir según qué juegos interesen:** NScripter/ONScripter (`nscript.dat` con XOR), Ren'Py (puente con su sistema de traducción) o
  un motor de bytecode (Softpal, CatSystem2) con la tabla de cadenas del kit, o uno envuelto con `MotorExterno`.
- Todos pasan la prueba de contrato de la fase 3.
- Ajustar la interfaz `Motor` con lo aprendido y marcarla **estable (v1)**.

### Fase 5 — API local e interfaz gráfica

- **API:** `subahibi-es servir` levanta un servidor local (FastAPI o Starlette, solo en `127.0.0.1`) que expone el proyecto: estado, filas con filtros y
  paginación, guardar filas, galería, `exportar`/`build`/`instalar` como *tareas* con progreso (eventos SSE o WebSocket).
- **Frontend:** Svelte + Vite, compilado a archivos estáticos que van dentro del paquete Python. Pantallas:
  1. **Inicio:** proyectos recientes, "abrir carpeta del juego" (detección automática del perfil), crear perfil con un asistente.
  2. **Editor de texto:** tabla virtualizada (≈150 000 filas), filtros por estado/escenario/tipo, búsqueda, edición en línea, atajos de teclado,
     contexto (líneas vecinas, hablante), validación en vivo (marcadores, caracteres sin glifo).
  3. **Vista previa en contexto:** la ventana de texto dibujada en un `<canvas>` con la fuente y el ancho del juego, con los cortes de línea que haría el motor.
  4. **Galería:** la de hoy, migrada a componente (comparar original/traducida, arrastrar y soltar, estado por imagen) y guardando directo en el proyecto.
  5. **Avance:** el `estado -vv` con gráficos por archivo y escenario.
  6. **Build y prueba:** botón "armar y abrir el juego" (con Wine en Linux/macOS), registro de la tarea.
- **Ventana nativa:** `subahibi-es gui` abre la misma interfaz en una ventana con pywebview; si hace falta algo más integrado, Tauri más adelante.
- **Distribución:** ejecutables por sistema operativo con PyInstaller generados en GitHub Actions (Linux, Windows, macOS).
- **Rendimiento:** un índice SQLite (caché, se puede regenerar) sobre los archivos por escenario, para buscar y filtrar rápido.

### Fase 6 — Herramientas para soportar motores nuevos

- **Explorador de archivos** (`subahibi-es explorar` y luego en la GUI): lista el contenido de los contenedores que algún motor sabe abrir, vista
  hexadecimal y detección de cadenas (Shift-JIS, UTF-8, UTF-16) para ubicar "esto parece texto del juego" al empezar un motor nuevo.
- **Asistente de perfil:** a partir de una carpeta, propone motor y genera el TOML (archivos requeridos, hash del exe, contenedores encontrados).
- **`subahibi-es motor nuevo NOMBRE`:** genera el esqueleto de un plugin (paquete, entry point, clase `Motor`, perfil de ejemplo, prueba de contrato).
- **Guía "Cómo escribir un motor"** con el BGI como ejemplo comentado.

### Fase 7 — Calidad de traducción

- Glosario por proyecto (términos, nombres propios) con aviso de inconsistencias.
- Memoria de traducción: sugerir traducciones de líneas iguales o parecidas ya traducidas.
- Sugerencias automáticas (traducción automática o modelos de lenguaje) **opcionales**, siempre marcadas `revisar`.
- Colaboración: exportar/importar con Weblate o trabajar sobre git (los archivos por escenario lo hacen posible).

---

## 3. Pruebas

| Tipo | Qué cubre | Dónde corre |
|---|---|---|
| Unitarias sintéticas | Formatos, hojas, wrap, perfiles, registro | CI (Linux, Windows, macOS; Python 3.10 y 3.13) |
| Contrato de motores | Ida y vuelta de cada motor | CI |
| Galería (jsdom) | La página HTML | Local (opcional) |
| **Prueba dorada** (`tools/prueba_dorada.py`) | `init → exportar → build → build --jugable` sobre el juego real; compara hashes de toda la salida y el contenido de las hojas contra una referencia | Local (no hay juego en CI) |

Uso de la prueba dorada antes de fusionar una rama:
```
git worktree add /tmp/main main
python /tmp/main/tools/prueba_dorada.py JUEGO /tmp/dorada-main --parche-viejo ZIP          # referencia
python tools/prueba_dorada.py JUEGO /tmp/dorada-rama --parche-viejo ZIP --referencia /tmp/dorada-main
```
(La herramienta se agregó en la fase 1; para comparar contra una versión anterior a ella, copiarla al worktree.)

## 4. Riesgos y decisiones abiertas

Decisiones abiertas de la fase 2:
- **¿Dónde vive la traducción?** Hoy, en las hojas XLSX (cómodas, pero binarias: git no muestra diferencias y dos personas no pueden fusionar).
  Opciones: (a) seguir con XLSX y usar PO para colaborar; (b) archivos de texto por escenario como fuente de verdad y XLSX/PO como vistas.
  La (b) es mejor para la GUI y la colaboración, pero cambia la costumbre de trabajo: decidirlo antes de la fase 5.
- **Nombre del proyecto** generalizado.

Notas que dejó la fase 1:
- Las opciones de `build` y los comandos sueltos de cada motor se registran en el mismo `argparse`: con dos motores que definan
  la misma opción (`--fuente`) habrá conflicto. Resolverlo en la fase 4 (prefijar por motor, o armar el parser después de saber el motor del proyecto).
- Textos de la interfaz que todavía suponen japonés → español: columnas `japones`/`espanol`, etiquetas de la galería («tiene japonés»), mensajes
  de `exportar`. Van con los idiomas configurables de la fase 2.
- El nombre del archivo de proyecto (`subahibi-es.json`) y de la carpeta de trabajo cambian con el nombre del proyecto (fase 2), con compatibilidad hacia atrás.

- **Nombre** del proyecto generalizado (fase 2).
- **Licencia:** el núcleo es GPL-3.0-or-later; un plugin que importa el núcleo queda alcanzado por la GPL. Envolver herramientas externas por
  línea de comandos (`MotorExterno`) no tiene ese problema.
- **Archivos cifrados por juego** (XP3 y otros): las claves salen de la copia del usuario o de perfiles; no se distribuye material del juego.
- **Rendimiento en Python** con archivos grandes: medir; si hace falta, lectura perezosa y `mmap` antes de pensar en extensiones nativas.
- **Wine/Proton** para "abrir el juego" desde la GUI en Linux y macOS.

## Estado

- [x] **Fase 1** — núcleo / motor BGI / perfiles TOML
  - [x] `nucleo/` y `motores/` separados (`git mv`, historia conservada)
  - [x] interfaz `Motor` con capacidades; registro con motores incluidos + entry points
  - [x] perfiles TOML (usuario > incluidos), detección en `init`, proyectos viejos compatibles
  - [x] perfil `subahibi-15th` con todo lo que estaba fijo, incluidas las direcciones del exe
  - [x] CLI con los mismos comandos; `build` y los comandos sueltos toman opciones de cada motor
  - [x] pruebas: 33 (perfiles, registro, motor de prueba como plugin que hace todo el flujo)
  - [x] prueba dorada idéntica a `main` (3084 archivos, 98 983 filas, galería, `--jugable`, `patch-exe`, `text export`)
- [ ] **Fase 2** — modelo de datos genérico *(en curso)*
  - [x] filas con claves genéricas (`original`/`traduccion`); encabezados de las hojas según los idiomas del proyecto (`init --idioma`);
        las hojas existentes se siguen leyendo y con japonés → español no cambia nada
  - [x] `subahibi-es revisar`: controles generales + ganchos del motor (`marcadores`, `caracteres_invalidos`, `controles`); informe `revision.tsv`
  - [x] `text po-export` / `text po-import` (con `polib`), ida y vuelta probada sobre las 98 867 filas reales
  - [ ] contexto por fila (hablante, línea anterior/siguiente) — el motor BGI tiene que identificar el comando de nombre
  - [ ] almacenamiento por escenario como fuente de verdad (decisión abierta, ver sección 4)
  - [ ] nombre del proyecto (decisión abierta)
- [ ] Fase 3 — kit de motores: `MotorTextoPlano`, tabla de cadenas, `MotorExterno`, contenedores, codificaciones, prueba de contrato
- [ ] Fase 4 — Kirikiri y tercer motor, interfaz `Motor` v1
- [ ] Fase 5 — API local y GUI web
- [ ] Fase 6 — explorador de archivos, asistente de perfiles, generador de plugins
- [ ] Fase 7 — glosario, memoria de traducción, sugerencias

# subahibi-es

Herramientas para traducir **Subarashiki Hibi 15th Anniversary** (motor Ethornell / BGI, v1.685.3) al español: parchear el exe, traducir las imágenes
de interfaz, exportar el texto a hojas de cálculo, volver a armar los escenarios del juego y construir la carpeta del juego en español de una vez.

Licencia: **GPL-3.0-or-later**. Este repositorio contiene **solo herramientas**: no incluye imágenes, audio, exe, fuentes ni texto del juego, ni la
traducción. Todo se genera en tu equipo a partir de **tu copia del juego**.

## Qué hace

| Comando | Para qué sirve |
|---|---|
| `init` | Guarda las rutas del proyecto (`subahibi-es.json`) para no repetirlas. |
| `build` | **Arma la carpeta del juego en español de una vez**: enlaces a los `.arc`, `BGI.exe` parcheado, archivos sueltos, escenarios e imágenes. |
| `patch-exe` | Parchea una copia de `BGI.exe`: fuente, modo proporcional y modo UTF-8. |
| `images export` | `.arc` → PNG (lector propio de `.arc`, DSC e imágenes). |
| `images index` | Galería HTML **editable** original/español: qué falta, qué no hace falta; arrastrar imágenes, guardar TSV. OCR opcional. |
| `images import` | Coloca las imágenes traducidas donde el motor las busca. |
| `text export` | Escenarios → hojas XLSX (una por `.arc`, una hoja por escenario), con la traducción vieja precargada. |
| `text import` | Hojas → escenarios del juego (en UTF-8). |
| `text wrap` | Inserta saltos de línea manuales en límites de palabra para un ancho dado. |

## Instalación

```
pip install -e .              # Python >= 3.10; instala Pillow. -e: los cambios del código se ven sin reinstalar
pip install -e .[texto]       # añade openpyxl (hojas de cálculo; necesario para los comandos «text»)
pip install -e .[dev]         # añade pytest
```
Opcional: `tesseract` con datos `jpn` instalado en el sistema (`images index --ocr`).

**La fuente** que dibuja el juego (por defecto `SubaHibi07Inq`, la del parche viejo) **no** se distribuye aquí: hay que instalarla en el sistema
(en Wine, copiarla a `drive_c/windows/Fonts/`). Cualquier fuente con letras latinas sirve; ver «Fuente, tamaño y ancho del texto».

## Empezar rápido

```
subahibi-es init --juego CARPETA_DEL_JUEGO --juego-es CARPETA_ES --parche-viejo parche_en_español.zip \
                 --imagenes traduccion/Graphic/CVTD --texto trabajo/texto
subahibi-es build
```
`--parche-viejo` acepta el **.zip del parche tal cual** (o una carpeta ya extraída): de ahí salen el español que se precarga en las hojas, las
voces/gráficos/sonidos sueltos y, por exclusión, las imágenes de la interfaz vieja que hay que omitir. `build` no pisa tus datos de partida
(`BGI.gdb` y `UserData` se copian la primera vez). Por defecto aplica las filas `traducido` y `del parche`; con
`--estados "traducido,del parche,revisar"` aplica también las dudosas (útil para probar). Los argumentos de la línea de comandos siempre mandan sobre
`subahibi-es.json`. En Wine: `env WINEPREFIX=... wine BGI.exe` desde la carpeta en español.

## Referencia de comandos

### `patch-exe`
```
subahibi-es patch-exe BGI.exe BGI_es.exe [--fuente NOMBRE] [--sin-fuente] [--sin-proporcional] [--katakana]
subahibi-es patch-exe --verify BGI.exe          # versión conocida y si ya está parcheado
subahibi-es patch-exe --dry-run BGI.exe         # comprueba sin escribir
```
Solo se parchea un exe cuyo sha256 corresponde a una versión conocida (hoy, 1.685.3 x86-64). Cambios, todos documentados en `exe_patch.py`:
1. **Fuente:** las dos cadenas `MS Gothic` (inglés y japonés) pasan a `--fuente` (ASCII, 1 a 15 caracteres; por defecto `SubaHibi07Inq`).
2. **Modo proporcional:** `WindowSetFont` recibe siempre `proporcional = 1` (si no, el texto sale monoespaciado y el «...» se parte).
3. **Modo UTF-8:** el punto de entrada pasa por un desvío que llama a `Text_SetEncoding(1)` antes de arrancar (ver «Modo UTF-8»).

### `images`
```
subahibi-es images export CARPETA_DEL_JUEGO trabajo/originales            # sysgrp.arc por defecto; --arc para otros
subahibi-es images index trabajo/originales traduccion/Graphic/CVTD trabajo/indice --estado data/ui_status.tsv [--ocr]
subahibi-es images import mis_imagenes CARPETA_DEL_JUEGO CARPETA_ES        # PNG o BMP del mismo tamaño y nombre que la original
```
Una imagen suelta es un **BMP de 32 bits con alfa, del mismo tamaño y nombre que la entrada del `.arc`, sin extensión**, en `Graphic/CVTD/`; `import` valida
el nombre, el tamaño y la transparencia.

`trabajo/indice/index.html` (no necesita servidor) es **editable**: cada tarjeta tiene un selector de estado y una nota (se recuerdan en el navegador);
podés **arrastrar las imágenes traducidas** a la página (se asignan por nombre, o soltándolas sobre una tarjeta), con previsualización y aviso si el tamaño
no coincide; **Guardar ui_status.tsv** descarga las decisiones (lo que lee `--estado`; **Cargar TSV…** o arrastrar un `.tsv` las vuelve a cargar);
**Guardar imágenes…** las escribe en una carpeta (Chromium) o descarga un `.zip` para pasarlo a `images import`. `data/ui_status.tsv` guarda tus
decisiones manuales («este logo no se traduce»); ganan siempre sobre el OCR, que es solo una pista (~60% de aciertos, ~12% de falsos positivos).

### `text`
```
subahibi-es text export CARPETA_DEL_JUEGO trabajo/texto [--parche-viejo ZIP_O_CARPETA] [--tsv]
subahibi-es text wrap   trabajo/texto --max-caracteres 44 [--max-lineas 3]
subahibi-es text import CARPETA_DEL_JUEGO CARPETA_ES trabajo/texto [--estados "traducido,del parche,revisar"]
```
`text export` genera `data01101.xlsx`, … con una hoja por escenario y una fila por texto:

| columna | contenido |
|---|---|
| `clave` | `escenario:número` |
| `tipo` | `mensaje` (diálogo/narración), `epigrafe`, `fecha`, `titulo`, `eleccion` |
| `japones` | texto original (no se edita) |
| `espanol` | **la traducción**; si está vacía, el juego conserva el japonés |
| `estado` | `sin traducir`, `traducido`, `revisar`, `del parche` (lista desplegable) |
| `nota`, `pos`, `hash` | nota libre, posición en el escenario y huella del japonés (no tocar) |

- Se escribe el español normal (`¿ ¡ á é í ó ú ñ ü …`) y cualquier carácter Unicode que tenga la fuente. Un salto de línea dentro de una celda es un salto de línea del juego.
- **Precarga** (`--parche-viejo`): el español de la traducción vieja se alinea por orden con el japonés de la 15th. Si un escenario tiene distinta cantidad
  de filas, o las comillas de diálogo coinciden menos del 97% (señal de desalineación), todas sus filas quedan `revisar`.
- Se traducen mensajes, epígrafes, fechas, títulos y las opciones de elección (que se guardan junto al nombre de su imagen). El furigana no se exporta
  (la traducción vieja lo eliminó).
- `text import` rechaza filas cuyo `hash` no coincide con el juego. Cada escenario generado se vuelve a leer y se comprueba que solo cambiaron los
  operandos de las cadenas.
- `--tsv` en `export` escribe además un TSV por script (diferencias legibles); el import acepta `.xlsx` y `.tsv`.

#### `text wrap`: saltos de línea
El motor corta el texto solo cuando una letra no entra en la ventana, a mitad de palabra. `text wrap` inserta saltos manuales en los espacios, en la
columna `espanol`, para que ninguna línea pase de un ancho dado:
```
subahibi-es text wrap trabajo/texto --max-caracteres 44 --max-lineas 3
subahibi-es text wrap trabajo/texto --ancho 880 --fuente SubaHibi07Inq.ttf --tamano 29     # medido en píxeles con esa fuente
```
Respeta los saltos que ya hay (`--reflow` los descarta y vuelve a cortar), no parte palabras más largas que la línea, solo toca los mensajes con español
y estado `traducido`/`del parche`/`revisar` (`--estados`), y con `--max-lineas M` anota en `nota` los textos que pasen de M líneas (solo avisa). Reescribe
las hojas en el lugar dejando una copia `.bak`; con `--salida CARPETA` escribe copias nuevas.

## Fuente, tamaño y ancho del texto

**`--ancho`, `--fuente` y `--tamano` de `text wrap` solo sirven para medir** dónde cortar las líneas: no cambian cómo dibuja el juego. Lo que sí se puede
cambiar hoy y lo que no:

| Qué | Estado |
|---|---|
| **Fuente del juego** | Sí: `patch-exe --fuente NOMBRE` / `build --fuente NOMBRE` (ASCII, hasta 15 caracteres; instalada en el sistema). Es la misma para todo el juego. |
| **Tamaño y ancho de la letra, ventana** | Todavía no. Los fijan los programas de sistema (`sysprg.arc`: `scrmsg._bp`, `logwnd._bp`, …) al configurar cada ventana con `WindowSetFont(ventana, fuente, tamaño, ancho%, negrita, proporcional, reserva_ruby)`; hoy solo se fuerza `proporcional`. Cambiar tamaño/ancho global es posible parcheando esa función, pero afectaría a todas las ventanas (historial, configuración…) y falta una forma de reconocer la del mensaje. |
| **Tamaño por línea** | Posible en principio, no implementado. Los escenarios usan el comando `0x14C` para cambiar el tamaño desde ese punto (428 usos en 15 escenarios; el valor del medio es el tamaño: 24, 29, 30, 32, 34, 40…). Sus valores existentes se podrían editar; **agregar usos nuevos** exige insertar instrucciones y reubicar todas las direcciones del escenario, que el importador aún no hace. |

## Modo UTF-8

El motor de la 15th (v1.685) trae la instrucción de script `81 00` / `Text_SetEncoding` (0 = Shift-JIS, 1 = UTF-8; existe desde la 1.653).
`patch-exe` desvía el punto de entrada del exe para llamarla con 1 antes de arrancar, y `text import` / `build` reescriben **todas** las cadenas de
**todos** los escenarios en UTF-8 (también las japonesas sin traducir): en ese modo nada convierte las cadenas, y una escrita en la codificación equivocada
sale como basura. Así los acentos son letras normales de la fuente, sin katakana ni DLL. `--katakana` (en `patch-exe`, `text import` y `build`) deja el
procedimiento antiguo, útil solo para motores sin modo UTF-8.

**Limitaciones conocidas**
- Los programas de sistema (`sysprg.arc`) conservan unas 480 cadenas japonesas en Shift-JIS (nombres de parámetros y mensajes de error de depuración).
  En una partida normal no se muestran; si un script falla, el mensaje de error saldría ilegible.
- Las partidas guardadas de un idioma no cargan en el otro: no hay cambio de idioma a mitad de partida.
- Las imágenes con texto fuera de `sysgrp.arc` (botones de elección, tarjetas de título, CG con texto) no se exportan todavía: solo se leen imágenes crudas
  (DSC); `CompressedBG` no está implementado.

## Cómo funciona (resumen técnico)

- El motor da prioridad a los **archivos sueltos** sobre los `.arc`. Las rutas (`Script\CVTD`, `Graphic\CVTD`, `Voice\CVTD`…) están dentro de los
  programas del juego (`system.arc:ipl._bp`), no en el exe. Por eso el español va en una **carpeta aparte**, con los `.arc` enlazados, y la carpeta
  original queda en japonés.
- Las entradas de `sysgrp.arc` son DSC (`DSC FORMAT 1.00`) más una cabecera de 16 bytes y píxeles BGRA.
- Un escenario compilado (`BurikoCompiledScriptVer1.00`) es una cabecera, un flujo de palabras de 32 bits (algunas con operandos) y una tabla de
  cadenas; los operandos de cadena son desplazamientos desde el inicio del flujo. Por eso se reimporta sin reubicar nada: las cadenas nuevas van al final
  y solo cambia el operando de cada texto.
- `text/accents.py` (`á`=`ｧ`, `í`=`ｨ`, `ú`=`ｩ`, `é`=`ｪ`, `ó`=`ｫ`, `ü`=`ｯ`, `Á É Í Ó Ú`=`ｱ ｴ ｲ ｵ ｳ`, `Ü`=`ﾂ`, `ñ`=`ﾃ`, `Ñ`=`ﾆ`, `¡`=`ｷ`, `¿`=`ﾚ`) solo hace
  falta para **leer** la traducción vieja, que guardaba las tildes como katakana de ancho medio que una fuente especial dibujaba como letras (se verificó
  con sus 146.196 cadenas, ida y vuelta exacta).

## Estructura y pruebas

```
src/subahibi_es/   cli.py, config.py, build.py, oldpatch.py, exe_patch.py,
                   bgi/ (arc.py, dsc.py, image.py, scn.py), images/ (export, index, import_, ocr, _page),
                   text/ (extract, export, import_, sheet, align, accents, wrap)
data/ui_status.tsv decisiones manuales sobre las imágenes de interfaz
tools/             generar_ui.py y ui_lib.py: regeneran las imágenes de interfaz traducidas
tests/             pytest (datos sintéticos; con GAME_DIR=… también se prueba contra el juego real)
```
`pytest` corre sin archivos del juego; `tests/web/test_page.js` prueba la galería con jsdom (opcional, `npm install jsdom`).

## Créditos y agradecimientos

- **[OpenBGI](https://openbgi.net)** (reimplementación abierta del motor, GPL-2.0): su documentación de los formatos fue la referencia, incluido el modo UTF-8, y
  se usó como **referencia independiente** para comprobar que nuestro lector de `.arc`, DSC e imágenes produce bytes idénticos (el lector se escribió a partir
  de los propios archivos). Este proyecto no usa su código: su licencia GPL-2.0-only no es compatible con GPL-3.
- **ethornell-rs** (asukaminato0721): otra reimplementación del motor (no se consultó en detalle).
- **Taikutsu Translation** (parche en español de *Sakura no Uta*): su `d3d9.dll` con el «túnel SJIS» y su `sjis_ext.bin` fueron la pista para entender el
  problema de las tildes.
- **Operation Bellflower**, serie *Adventures in the Ethornell Engine* (especialmente «Dealing with Fonts»): el método para el modo proporcional y los
  parámetros de fuente. Allí mismo se acredita la investigación previa de **ArcusMaximus** sobre el formato de los programas de sistema.
- **El equipo de traducción** del parche original en español, cuya traducción y cuya fuente `SubaHibi07Inq` hacen posible todo esto.

Este proyecto no está afiliado a los autores del juego ni del motor. Hace falta una copia legítima del juego.

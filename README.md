# subahibi-es

Herramientas para traducir **Subarashiki Hibi 15th Anniversary** (motor Ethornell / BGI, v1.685.3) al español: exportan el texto a hojas de cálculo y las
imágenes de interfaz a una galería, y arman los archivos que hay que copiar al juego.

Licencia: **GPL-3.0-or-later**. Este repositorio contiene **solo herramientas**: no incluye imágenes, audio, exe, fuentes ni texto del juego, ni la
traducción. Todo se genera en tu equipo a partir de **tu copia del juego**. Hace falta una copia legítima.

---

# Guía paso a paso

Se trabaja **dentro de la carpeta donde está instalado el juego**. El programa nunca modifica los archivos originales: crea una carpeta de trabajo
al lado y guarda una copia del `BGI.exe` original.

```
init  →  exportar  →  (traducir)  →  build  →  instalar          …y al final, si querés:  desinstalar  /  reset
```

## 0. Qué necesitás

- **Python 3.10 o más nuevo** y `pip`.
- **El juego instalado** (la carpeta con `BGI.exe`, `sysgrp.arc`, `data01101.arc`…), versión 1.685.3 (la 15th Anniversary).
- **La fuente del parche viejo** (`SubaHibi07Inq`) instalada en el sistema. Viene con la traducción anterior y no se distribuye acá. (En Wine, copiarla a
  `drive_c/windows/Fonts/`.) Se puede usar otra con `build --fuente NOMBRE`.
- Opcional: el **`.zip` del parche en español anterior**. Con él las hojas arrancan con ~94% del texto ya cargado y el juego recupera sus voces y gráficos sueltos.
- Opcional: `tesseract` con datos `jpn` (solo si querés que la galería de imágenes te sugiera cuáles tienen japonés).

## 1. Instalar la herramienta

```
pip install -e ".[texto]"
```
(`-e` significa que si actualizás el código no hace falta reinstalar. `.[texto]` agrega el soporte de hojas de cálculo.)

## 2. Crear el proyecto — `init`

Abrí una terminal **en la carpeta de instalación del juego** y ejecutá:

```
cd "C:\Juegos\Subarashiki Hibi 15th"          # o la ruta de tu instalación
subahibi-es init --parche-viejo "C:\Descargas\parche_espanol.zip"
```
(El `--parche-viejo` es opcional; se puede agregar después repitiendo `init --parche-viejo ARCHIVO.zip`.) También funciona `subahibi-es init RUTA` desde otro lado.

Qué hace: **comprueba que la carpeta sea el juego** (un `BGI.exe` de una versión conocida y los `.arc` esperados; si no, te dice qué falta), crea `subahibi-es.json`
(el archivo que *es* el proyecto) y estas carpetas dentro de `subahibi-es-trabajo/`, y guarda una copia del `BGI.exe` original:

| Carpeta (dentro de `subahibi-es-trabajo/`) | Para qué sirve |
|---|---|
| `texto/` | Las hojas Excel/LibreOffice donde se traduce. |
| `imagenes/traducidas/` | Las imágenes de interfaz ya traducidas (PNG o BMP). |
| `imagenes/indice/` | La galería `index.html`. |
| `imagenes/estado.tsv` | Tus decisiones sobre cada imagen («esta no se traduce»). |
| `originales/` | PNG de la interfaz original (los crea `exportar`). |
| `backup/` | El `BGI.exe` original y copias de seguridad. |
| `salida/` | **Lo que hay que copiar al juego** (lo crea `build`). |

Desde ese momento **todos los comandos funcionan sin pasar rutas**, ejecutados desde la carpeta del juego o desde cualquiera de sus subcarpetas.
`subahibi-es estado` te muestra en qué punto estás.

## 3. Exportar — `exportar`

```
subahibi-es exportar
```
Hace todo el volcado sin que tengas que crear nada:
1. Saca las **imágenes de interfaz** del juego a PNG.
2. **Genera las imágenes traducidas** que ya sabe hacer (botones del título y del menú, diálogos), usando una fuente latina del sistema (Noto Sans, DejaVu, Segoe UI o Arial; si no hay ninguna, `SUBAHIBI_FONT=/ruta/fuente.ttf`).
3. Arma la **galería** `imagenes/indice/index.html`.
4. Exporta el **texto** a hojas (`texto/data01101.xlsx`, …; una hoja por escenario), con la traducción vieja precargada si diste el `.zip`.

**Es seguro repetirlo:** si ya hay hojas **no las pisa** (hay trabajo de traducción adentro). Para exportar de cero: `exportar --forzar` (guarda antes una copia en `backup/`).

## 4. Traducir

### El texto
Abrí las hojas de `texto/` con LibreOffice, Excel o Google Sheets. Cada fila es un texto del juego:

| Columna | Qué es |
|---|---|
| `japones` | El original. **No se edita.** |
| `espanol` | **La traducción.** Si está vacía, el juego se queda con el japonés. |
| `estado` | `sin traducir` (falta), `del parche` (ya lo traía el parche viejo), `revisar` (dudoso: revisalo y pasalo a `traducido`), `traducido` (listo). |
| `tipo`, `nota`, `clave`, `pos`, `hash` | Informativas (la nota es libre; no toques `clave`, `pos` ni `hash`). |

- Escribí el español normal: `¿ ¡ á é í ó ú ñ ü` y cualquier carácter que tenga la fuente.
- Un salto de línea dentro de una celda es un salto de línea del juego.
- **`build` aplica por defecto las filas `traducido` y `del parche`.** Las `revisar` se dejan en japonés hasta que las confirmes.

Opcional, **saltos de línea automáticos** para que ninguna línea pase de un ancho (corta en límites de palabra):
```
subahibi-es text wrap --max-caracteres 44 --max-lineas 3
```
(Reescribe las hojas dejando una copia `.bak`. Los saltos que ya había se respetan; `--reflow` los rehace.)

### Las imágenes
Abrí `subahibi-es-trabajo/imagenes/indice/index.html` en el navegador (doble clic). Es una galería con las imágenes originales y su estado (traducida, pendiente, a decidir…):
- Cada tarjeta tiene un **selector de estado** y una nota.
- **Arrastrá tus imágenes traducidas** a la página (se asignan por nombre de archivo, o soltándolas sobre una tarjeta). Tienen que tener **el mismo nombre y el mismo tamaño** que el original; la página avisa si no.
- **Guardar imágenes…** las escribe en una carpeta (elegí `imagenes/traducidas/`; en Chrome/Edge) o descarga un `.zip` (descomprimilo ahí).
- **Guardar ui_status.tsv** descarga tus decisiones: guardalo como `imagenes/estado.tsv` (reemplazando el existente) y volvé a ejecutar `exportar` para refrescar la galería.

## 5. Armar el parche — `build`

```
subahibi-es build
```
Crea en `subahibi-es-trabajo/salida/` **exactamente lo que hay que copiar al juego**: el `BGI.exe` parcheado, los escenarios con tu texto, las imágenes traducidas y los
archivos sueltos del parche viejo. La carpeta `salida/` se rehace entera cada vez. Si aparece «N filas no se aplicaron por su estado», son las `revisar`/`sin traducir`;
para probar con las `revisar` incluidas: `subahibi-es build --estados "traducido,del parche,revisar"`.

## 6. Probar — `instalar` / `desinstalar`

```
subahibi-es instalar         # copia salida/ sobre el juego (guarda copia de lo que pisa)
… jugás …
subahibi-es desinstalar      # deja el juego exactamente como estaba
```
Con `instalar` el juego queda **en español** (el `BGI.exe` y los archivos sueltos pasan a ser los del parche). `desinstalar` borra lo agregado y restaura lo que se pisó;
sigue funcionando con el parche instalado, porque el `BGI.exe` original se toma del respaldo. En Wine: `env WINEPREFIX=… wine BGI.exe` desde la carpeta del juego.

*Sin tocar la instalación:* `subahibi-es build --jugable` arma `subahibi-es-trabajo/jugable/`, una carpeta de prueba completa con enlaces a los archivos del juego, para ejecutarla aparte.

## 7. Entregar el parche a otras personas

Comprimí **el contenido de `subahibi-es-trabajo/salida/`** (no la carpeta en sí) en un `.zip`. Quien lo reciba lo descomprime **sobre la carpeta de instalación de su juego**
(aceptando reemplazar `BGI.exe`) e instala la fuente. Para volver al original, le alcanza con restaurar su `BGI.exe` y borrar las carpetas `Script`, `Graphic`, `Sound` y `Voice` agregadas
(si guarda una copia del `BGI.exe` original antes de pisarlo, mejor).

## 8. Limpiar — `reset`

```
subahibi-es reset            # borra el proyecto (subahibi-es.json); la carpeta de trabajo se conserva
subahibi-es reset --todo     # borra también subahibi-es-trabajo/ (pide confirmación; --si para no preguntar)
```
`reset` **nunca toca los archivos del juego**. Si el parche está instalado, primero hay que `desinstalar` (o forzar con `--forzar`).

## Resumen

| Comando | Cuándo |
|---|---|
| `init [carpeta] [--parche-viejo zip]` | Una vez, en la carpeta del juego. |
| `exportar` | Una vez (y `--forzar` para rehacer); prepara todo para traducir. |
| `estado` | Cuando quieras ver el avance. |
| `text wrap …` | Opcional, para ajustar saltos de línea. |
| `build` | Cada vez que quieras generar el parche con lo traducido. |
| `instalar` / `desinstalar` | Para probar en el juego y volver atrás. |
| `reset [--todo]` | Para empezar de nuevo. |

## Problemas comunes

- **«esta carpeta no parece la instalación…» al hacer `init`:** el mensaje dice qué falta (`BGI.exe` de otra versión, algún `.arc`). Tiene que ser la 15th Anniversary 1.685.3 **sin parches**.
- **«no encuentro un BGI.exe original»:** el `BGI.exe` del juego ya fue reemplazado y no hay respaldo; restaurá el original (reinstalá el juego o verificá archivos) o ejecutá `desinstalar`.
- **El juego se ve en japonés:** no se instaló el parche (`instalar`), o se copió sin el `BGI.exe` de `salida/`.
- **Salen signos raros en vez de letras:** falta instalar la fuente (`SubaHibi07Inq`) o se mezclaron archivos de otro parche. El juego corre en UTF-8: **todos** los escenarios y el exe tienen que ser los de `salida/`.
- **«no se generaron las imágenes traducidas (falta una fuente latina)»:** instalá Noto Sans o DejaVu, o definí `SUBAHIBI_FONT=/ruta/fuente.ttf`, y volvé a `exportar`.
- **Perdí un cambio en una hoja:** `exportar` nunca pisa hojas; si usaste `--forzar`, la versión anterior está en `backup/texto-<fecha>/`.
- **Windows:** `instalar` y `build` copian archivos (no usan enlaces). Solo `build --jugable` intenta enlaces simbólicos (en Windows exigen el modo desarrollador); si no puede, copia y avisa.

---

# Referencia

## Comandos sueltos
Los comandos de la guía usan el proyecto. Estos hacen una sola cosa y aceptan rutas explícitas (con proyecto, las rutas por defecto salen de él):

```
subahibi-es patch-exe BGI.exe BGI_es.exe [--fuente NOMBRE] [--sin-fuente] [--sin-proporcional] [--katakana]
subahibi-es patch-exe --verify BGI.exe          # versión conocida y si ya está parcheado
subahibi-es images export [CARPETA_DEL_JUEGO] [SALIDA] [--arc sysgrp …]      # .arc → PNG
subahibi-es images generar [ORIGINALES] [SALIDA]                              # genera las imágenes traducidas conocidas
subahibi-es images index [ORIGINALES] [TRADUCIDAS] [SALIDA] [--estado TSV] [--ocr]
subahibi-es images import [ORIGEN] [CARPETA_DEL_JUEGO] [SALIDA]               # coloca imágenes traducidas en Graphic/CVTD
subahibi-es text export [CARPETA_DEL_JUEGO] [SALIDA] [--parche-viejo ZIP] [--tsv]
subahibi-es text import [CARPETA_DEL_JUEGO] [SALIDA] [HOJAS…] [--estados "traducido,del parche,revisar"]
subahibi-es text wrap [HOJAS…] --max-caracteres N [--max-lineas M] [--ancho PX --fuente TTF --tamano PX] [--reflow] [--salida CARPETA]
```
La variable de entorno `SUBAHIBI_ES_PROJECT=/ruta/al/juego` fuerza qué proyecto usar (si no, se busca `subahibi-es.json` desde la carpeta actual hacia arriba).
`build --fuente NOMBRE` y `patch-exe --fuente NOMBRE` cambian la fuente que usa el juego (ASCII, hasta 15 caracteres; instalada en el sistema).

**`patch-exe`** solo parchea un `BGI.exe` cuyo sha256 corresponde a una versión conocida (hoy, 1.685.3 x86-64). Cambios, todos documentados en `exe_patch.py`:
1. **Fuente:** las dos cadenas `MS Gothic` (inglés y japonés) pasan a `--fuente` (por defecto `SubaHibi07Inq`).
2. **Modo proporcional:** `WindowSetFont` recibe siempre `proporcional = 1` (si no, el texto sale monoespaciado y el «...» se parte).
3. **Modo UTF-8:** el punto de entrada pasa por un desvío que llama a `Text_SetEncoding(1)` antes de arrancar.

**Galería (`index.html`):** no necesita servidor. Las decisiones del selector de estado se recuerdan en el navegador; una página estática no puede escribir en tu disco, por eso se guarda con los botones.
`imagenes/estado.tsv` (copia editable de `src/subahibi_es/data/ui_status.tsv`) manda siempre sobre el OCR, que es solo una pista (~60% de aciertos, ~12% de falsos positivos).

## El texto: cómo se trata
- Se traducen mensajes, epígrafes, fechas, títulos y las opciones de elección (que se guardan junto al nombre de su imagen). El furigana no se exporta (la traducción vieja lo eliminó).
- **Precarga** (`--parche-viejo`): el español de la traducción vieja se alinea por orden con el japonés de la 15th. Si un escenario tiene distinta cantidad de filas, o las comillas de
  diálogo coinciden menos del 97% (señal de desalineación), todas sus filas quedan `revisar`.
- `text import` rechaza filas cuyo `hash` no coincide con el juego. Cada escenario generado se vuelve a leer y se comprueba que solo cambiaron los operandos de las cadenas.
- `--tsv` en `text export` escribe además un TSV por script (diferencias legibles); el import acepta `.xlsx` y `.tsv`.

**`text wrap`**: el motor corta el texto solo cuando una letra no entra en la ventana, a mitad de palabra. `text wrap` inserta saltos manuales en los espacios, en la columna `espanol`, para que
ninguna línea pase de un ancho dado (en caracteres, o en píxeles con `--ancho --fuente --tamano`). No parte palabras más largas que la línea, solo toca los mensajes con español y estado
`traducido`/`del parche`/`revisar`, y con `--max-lineas M` solo avisa (anota en `nota`) los textos que pasen de M líneas.

## Fuente, tamaño y ancho del texto

`--ancho`, `--fuente` y `--tamano` de `text wrap` **solo sirven para medir**. Lo que se puede cambiar hoy:

| Qué | Estado |
|---|---|
| **Fuente del juego** | Sí: `--fuente NOMBRE` en `build` / `patch-exe` (la misma para todo el juego). |
| **Tamaño y ancho de la letra, ventana** | Todavía no. Los fijan los programas de sistema (`sysprg.arc`) con `WindowSetFont(ventana, fuente, tamaño, ancho%, negrita, proporcional, reserva_ruby)`; hoy solo se fuerza `proporcional`. Cambiar el tamaño global afectaría a todas las ventanas (historial, configuración…). |
| **Tamaño por línea** | Posible, no implementado. Los escenarios usan el comando `0x14C` para cambiar el tamaño desde ese punto (428 usos en 15 escenarios; valor del medio = tamaño: 24, 29, 30, 32, 34, 40…). Sus valores se podrían editar; agregar usos nuevos exige insertar instrucciones y reubicar direcciones, que el importador aún no hace. |

## Modo UTF-8

El motor de la 15th (v1.685) trae la instrucción de script `81 00` / `Text_SetEncoding` (0 = Shift-JIS, 1 = UTF-8; existe desde la 1.653). `patch-exe` desvía el punto de entrada del exe para llamarla con 1 antes
de arrancar, y `build` reescribe **todas** las cadenas de **todos** los escenarios en UTF-8 (también las japonesas sin traducir): en ese modo nada convierte las cadenas, y una escrita en la codificación
equivocada sale como basura. Así los acentos son letras normales de la fuente, sin katakana ni DLL. `--katakana` deja el procedimiento antiguo (acentos como katakana de ancho medio), útil solo para motores sin modo UTF-8.

## Limitaciones conocidas
- Los programas de sistema (`sysprg.arc`) conservan unas 480 cadenas japonesas en Shift-JIS (nombres de parámetros y mensajes de error de depuración). En una partida normal no se muestran; si un script falla, el mensaje saldría ilegible.
- Las partidas guardadas de un idioma no cargan en el otro: no hay cambio de idioma a mitad de partida.
- Faltan imágenes de interfaz por traducir (la pantalla de configuración y la de teclas) y las imágenes con texto fuera de `sysgrp.arc` (botones de elección, tarjetas de título, CG con texto): solo se leen imágenes crudas (DSC); `CompressedBG` no está implementado.

## Cómo funciona (resumen técnico)
- El motor da prioridad a los **archivos sueltos** sobre los `.arc`; las rutas (`Script\CVTD`, `Graphic\CVTD`, `Voice\CVTD`…) están dentro de los programas del juego (`system.arc:ipl._bp`), no en el exe.
  Una imagen suelta es un **BMP de 32 bits con alfa, del mismo tamaño y nombre que la entrada del `.arc`, sin extensión**.
- Las entradas de `sysgrp.arc` son DSC (`DSC FORMAT 1.00`) más una cabecera de 16 bytes y píxeles BGRA.
- Un escenario compilado (`BurikoCompiledScriptVer1.00`) es una cabecera, un flujo de palabras de 32 bits (algunas con operandos) y una tabla de cadenas; los operandos de cadena son desplazamientos
  desde el inicio del flujo. Por eso se reimporta sin reubicar nada: las cadenas nuevas van al final y solo cambia el operando de cada texto.
- `text/accents.py` (`á`=`ｧ`, `í`=`ｨ`, `ú`=`ｩ`, `é`=`ｪ`, `ó`=`ｫ`, `ü`=`ｯ`, `Á É Í Ó Ú`=`ｱ ｴ ｲ ｵ ｳ`, `Ü`=`ﾂ`, `ñ`=`ﾃ`, `Ñ`=`ﾆ`, `¡`=`ｷ`, `¿`=`ﾚ`) solo hace falta para **leer** la traducción vieja,
  que guardaba las tildes como katakana de ancho medio que una fuente especial dibujaba como letras (verificado con sus 146.196 cadenas, ida y vuelta exacta).

## Estructura y pruebas

```
src/subahibi_es/   cli.py, project.py, workflow.py, build.py, config.py, oldpatch.py, exe_patch.py,
                   bgi/ (arc, dsc, image, scn), images/ (export, generate, render, index, import_, ocr, _page),
                   text/ (extract, export, import_, sheet, align, accents, wrap), data/ui_status.tsv
tests/             pytest (datos sintéticos; con GAME_DIR=… también contra el juego real); tests/web/ prueba la galería con jsdom
```
`pip install -e ".[texto,dev]"` y `pytest`. GitHub Actions corre las pruebas en Linux, Windows y macOS.

## Créditos y agradecimientos

- **[OpenBGI](https://openbgi.net)** (reimplementación abierta del motor, GPL-2.0): su documentación de los formatos fue la referencia, incluido el modo UTF-8, y se usó como **referencia independiente** para comprobar que nuestro
  lector de `.arc`, DSC e imágenes produce bytes idénticos (el lector se escribió a partir de los propios archivos). Este proyecto no usa su código: su licencia GPL-2.0-only no es compatible con GPL-3.
- **ethornell-rs** (asukaminato0721): otra reimplementación del motor (no se consultó en detalle).
- **Taikutsu Translation** (parche en español de *Sakura no Uta*): su `d3d9.dll` con el «túnel SJIS» y su `sjis_ext.bin` fueron la pista para entender el problema de las tildes.
- **Operation Bellflower**, serie *Adventures in the Ethornell Engine* (especialmente «Dealing with Fonts»): el método para el modo proporcional y los parámetros de fuente. Allí mismo se acredita la
  investigación previa de **ArcusMaximus** sobre el formato de los programas de sistema.
- **El equipo de traducción** del parche original en español, cuya traducción y cuya fuente `SubaHibi07Inq` hacen posible todo esto.

Este proyecto no está afiliado a los autores del juego ni del motor.

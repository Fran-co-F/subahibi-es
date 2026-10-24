# Cómo escribir un motor

Un **motor** es una clase de Python que entiende los archivos de una familia de juegos. Un **perfil** es un TOML que describe un juego
concreto de ese motor. El núcleo de tl-organizer (proyecto, traducción en `traduccion/`, hojas, PO, `revisar`, `build`, `instalar`…) funciona igual
para todos: el motor solo tiene que **sacar las filas de texto** y **volver a meter las traducciones**.

## 1. Elegí el camino

| Si los scripts del juego… | Heredá de | Tenés que escribir |
|---|---|---|
| son archivos de texto (KAG `.ks`, NScripter, Ren'Py…) | `kit.MotorTextoPlano` | dónde están, la codificación y unas expresiones regulares |
| ya los extrae/inserta una herramienta (VNTextPatch, una utilidad de la comunidad…) | `kit.MotorExterno` | cómo llamarla y cómo leer/escribir su formato intermedio |
| son binarios (bytecode con una tabla de cadenas, formato propio…) | `Motor` | el lector/escritor; `kit.TablaDeCadenas` resuelve la parte de reinyectar sin reubicar |

En los tres casos se usa el resto del kit (`tl_organizer.motores.kit`): `Carpeta`/`Zip`/`Contenedor` para los archivos empaquetados,
`decodificar`/`Sustitucion` para las codificaciones y `escribir_suelto` para dejar los archivos traducidos en la salida.

## 2. Scripts de texto: `MotorTextoPlano`

```python
from tl_organizer.motores.kit import MotorTextoPlano

class MotorKAG(MotorTextoPlano):
    nombre = "kag"                                   # el que se pone en el perfil: motor = "kag"
    descripcion = "KiriKiri / KAG"
    archivos = ("scenario/*.ks",)                    # el perfil puede cambiarlo: [texto] archivos = [...]
    codificaciones = ("utf-16", "cp932")             # orden de prueba al leer (un BOM manda)
    patrones = {                                     # tipo -> expresión regular (re.M) con un grupo «texto»
        "nombre":  r"^#(?P<texto>[^\n:]+)",
        "mensaje": r"^(?P<texto>[^\[@*;#\s][^\n]*?)(?=\[p\]|\[l\]|$)",
    }
    ignorar = r"^\s*(;|@|\*)"                        # líneas que nunca tienen texto
    salto_de_linea = "[r]"                           # cómo escribe el formato un salto dentro de un texto
    marcador = r"\[[a-z]+[^\]]*\]"                   # etiquetas que la traducción tiene que conservar (revisar)
```

(Las expresiones son ilustrativas: cada juego KAG usa sus propias macros, así que se ajustan mirando sus scripts.)
Con eso ya funcionan `exportar`, `build`, `revisar` y la prueba de contrato. Para lo que no entra en expresiones regulares se
sobrescribe `segmentos(texto, escenario) -> [(inicio, fin, tipo)]`; para scripts dentro de un `.xp3` u otro paquete, `contenedor(juego)`.
El perfil puede cambiar `codificaciones`, `codificacion_salida`, `salto_de_linea` y `carpeta_salida` en la sección `[kag]`.

## 3. Envolver una herramienta: `MotorExterno`

```python
import json, os
from tl_organizer.motores.kit import MotorExterno
from tl_organizer.nucleo import hojas

class MotorConHerramienta(MotorExterno):
    nombre = "herramienta"
    programa = "Herramienta.exe"                     # se busca en el PATH; el perfil puede dar la ruta: [herramienta] programa = "…"

    def comando_extraer(self, juego, carpeta):
        return ["extract", juego, carpeta]

    def leer_extraido(self, carpeta):                # -> (grupo, escenario, filas)
        for f in sorted(os.listdir(carpeta)):
            esc = os.path.splitext(f)[0]
            datos = json.load(open(os.path.join(carpeta, f), encoding="utf-8"))
            yield "scripts", esc, [dict(clave=f"{esc}:{n:05d}", tipo="mensaje", original=d["text"], traduccion="",
                                        estado="sin traducir", nota="", pos=n, hash=hojas.jp_hash(d["text"].encode()))
                                   for n, d in enumerate(datos, 1)]

    def escribir_para_insertar(self, carpeta, filas_del_juego, traducciones):
        for esc, filas in filas_del_juego.items():   # traducciones: {clave: texto}, ya validadas por la base
            json.dump([{"text": traducciones.get(f["clave"], f["original"])} for f in filas],
                      open(os.path.join(carpeta, esc + ".json"), "w", encoding="utf-8"), ensure_ascii=False)

    def comando_insertar(self, juego, carpeta, salida):
        return ["insert", juego, carpeta, salida]
```

La base maneja las carpetas temporales, encuentra el programa, lo lanza con **Wine** si es un `.exe` fuera de Windows
(`lanzador = ["mono"]` o `[]` en el perfil para cambiarlo), muestra el final de su salida si falla, y antes de insertar comprueba
cada fila contra lo que hay en el juego (estado aplicable, mismo original).

## 4. Formatos binarios: `Motor` + `TablaDeCadenas`

```python
from tl_organizer.motores.base import Motor, TEXTO
from tl_organizer.motores.kit import TablaDeCadenas, escribir_suelto

class MotorBinario(Motor):
    nombre = "binario"
    capacidades = frozenset({TEXTO})

    def textos(self, juego, parche_viejo=None, archivos=None):
        ...  # leer cada script, ubicar las cadenas de texto -> (grupo, escenario, filas) con pos = dónde está el operando

    def construir(self, juego, salida, filas=None, imagenes=None, estados=("traducido", "del parche"), opciones=None,
                  parche_viejo=None, ejecutable=None, log=print):
        ...  # por escenario:
        #   tabla = TablaDeCadenas(cola_original, inicio=inicio_de_la_tabla)
        #   por cada fila aplicable (estado en 'estados', mismo hash): nuevo = tabla.agregar(texto.encode(...))
        #   datos = reapuntar(codigo, {posicion_del_operando: nuevo}) + tabla.bytes()
        #   verificar_operandos(original, datos, posiciones)      # no cambió nada más
        #   escribir_suelto(salida, ruta_del_script, datos)
        return {"texto": {"scripts": n, "cambiadas": n, "omitidas": n, "errores": [(clave, motivo)]}}
```

El motor BGI (`motores/bgi/`) es un ejemplo completo de este camino: lector de `.arc`, descompresor DSC, escenarios con tabla de
cadenas, imágenes y parche de exe.

## 5. Lo que el núcleo espera de las filas

Cada fila es un diccionario con `clave, tipo, original, traduccion, estado, nota, pos, hash`:

- **clave**: `«escenario»:«número»`, estable entre exportaciones (así se reconoce la fila en `traduccion/`, en las hojas, en los PO y en git);
- **tipo**: libre (`mensaje`, `nombre`, `opcion`…); `wrap` y algunos controles de `revisar` miran `mensaje`;
- **estado** al exportar: `sin traducir`, o `del parche` si el motor precarga una traducción anterior;
- **pos** y **hash**: lo que el motor necesite para volver a encontrar el texto y saber que el original no cambió.

## 6. Capacidades y métodos opcionales

| Capacidad | Métodos |
|---|---|
| `texto` | `textos()`, y `construir()` aplica las filas |
| `imagenes` | `exportar_imagenes()`, y `construir()` coloca las imágenes traducidas |
| `ejecutable` | `identificar_ejecutable()`, `versiones_conocidas()` (el exe se reconoce y se respalda en `init`) |
| `parche_viejo` | `textos(juego, parche_viejo)` precarga una traducción anterior |

Opcionales: `releer()` (para la prueba de contrato), `marcadores()`, `caracteres_invalidos()` y `controles()` (para `revisar`),
`argumentos_build()`/`opciones_build()` (opciones de `build`), `registrar_comandos()` (comandos sueltos propios).

## 7. El perfil y el registro

```toml
# mi_paquete/juegos/mi-juego.toml
id = "mi-juego"
nombre = "Mi juego"
motor = "kag"
[deteccion]
requeridos = ["data.xp3"]
[texto]
idioma = "ja"
[kag]
codificacion_salida = "utf-16"
```

```toml
# pyproject.toml del paquete del motor
[project.entry-points."tl_organizer.motores"]
kag = "mi_paquete:MotorKAG"

[tool.setuptools.package-data]
"*" = ["juegos/*.toml"]
```

`pip install` del paquete alcanza: `tl-organizer init` en la carpeta del juego reconoce el perfil y usa el motor. Para probar un perfil
sin empaquetarlo, ponelo en `~/.config/tl-organizer/juegos/` (o en una carpeta de `TL_ORGANIZER_PERFILES`).

## 8. La prueba de contrato

```python
from tl_organizer.motores import contrato
from tl_organizer.nucleo import perfiles

def test_contrato(tmp_path):
    juego = armar_juego_sintetico(tmp_path)          # unos pocos archivos chicos, sin material del juego real
    motor = MotorKAG(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "kag"}))
    assert contrato.verificar(motor, str(juego), str(tmp_path / "t"), traduccion=lambda f: "Hola") == []
```

Verifica las filas, la ida y vuelta sin traducciones (el juego muestra exactamente lo mismo), que lo traducido aparezca y que lo que está
en `revisar` o tiene el hash de otra versión no se aplique. En `tests/test_basico.py` hay tres ejemplos: el motor BGI, un motor de texto
plano de juguete (`MotorJuguete`) y una herramienta externa simulada (`MotorHerramienta`).

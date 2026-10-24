# SPDX-License-Identifier: GPL-3.0-or-later
"""MotorExterno: base para envolver una herramienta de línea de comandos que ya sabe extraer e insertar el texto.

Si existe una herramienta para un motor (VNTextPatch, una utilidad de la comunidad, un script propio…), el motor es la clase
que la llama: dice cómo invocarla y cómo leer/escribir su formato intermedio, y la base se ocupa de las carpetas temporales,
de encontrar el programa, de lanzarlo con Wine si es un .exe fuera de Windows y de los errores.

    class MotorConHerramienta(MotorExterno):
        nombre = "herramienta"
        programa = "Herramienta.exe"
        def comando_extraer(self, juego, carpeta):          return ["extract", juego, carpeta]
        def leer_extraido(self, carpeta):                    ...  # -> (grupo, escenario, filas)
        def escribir_para_insertar(self, carpeta, filas_del_juego, traducciones): ...
        def comando_insertar(self, juego, carpeta, salida):  return ["insert", juego, carpeta, salida]

En el perfil, sección del motor:  programa = "/ruta/a/Herramienta.exe" (o una lista: ["python", "script.py"]),
lanzador = ["wine"] (o ["mono"], o [] para ninguno).
"""
import os
import shutil
import subprocess
import tempfile

from ..base import ESTADOS_LISTOS, TEXTO, Motor, MotorError


class MotorExterno(Motor):
    capacidades = frozenset({TEXTO})
    programa = ""                 # nombre (se busca en el PATH), ruta, o lista [programa, args fijos…]
    lanzador = None               # None: «wine» para un .exe fuera de Windows; o una lista explícita

    # ------------------------------------------------------------ lo que define la subclase
    def comando_extraer(self, juego, carpeta):
        raise NotImplementedError

    def leer_extraido(self, carpeta):
        """Genera (grupo, escenario, filas) a partir de lo que dejó la herramienta en 'carpeta'."""
        raise NotImplementedError

    def escribir_para_insertar(self, carpeta, filas_del_juego, traducciones):
        """Escribe en 'carpeta' lo que la herramienta necesita para insertar.
        filas_del_juego: {escenario: [filas]} recién extraídas (los originales); traducciones: {clave: texto} ya validadas
        (estado aplicable y mismo original que en el juego)."""
        raise NotImplementedError

    def comando_insertar(self, juego, carpeta, salida):
        raise NotImplementedError

    # ------------------------------------------------------------ mecánica
    def ejecutable(self):
        """La línea de comandos base: [lanzador…, programa, args fijos…]."""
        prog = self.opciones.get("programa", self.programa)
        prog = list(prog) if isinstance(prog, (list, tuple)) else [prog]
        if not prog or not prog[0]:
            raise MotorError(f"motor «{self.nombre}»: no se indicó el programa (opción «programa» en la sección [{self.nombre}] del perfil)")
        encontrado = prog[0] if os.path.exists(prog[0]) else shutil.which(prog[0])
        if not encontrado:
            raise MotorError(f"motor «{self.nombre}»: no encuentro «{prog[0]}» (indicá la ruta en «programa», sección [{self.nombre}] del perfil)")
        lanz = self.opciones.get("lanzador", self.lanzador)
        if lanz is None:
            lanz = ["wine"] if encontrado.lower().endswith(".exe") and os.name != "nt" else []
        return list(lanz) + [encontrado] + prog[1:]

    def ejecutar(self, args, cwd=None):
        cmd = self.ejecutable() + [str(a) for a in args]
        try:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace")
        except OSError as e:
            raise MotorError(f"no se pudo ejecutar {cmd[0]}: {e}")
        if r.returncode:
            cola = "\n".join((r.stderr or r.stdout).strip().splitlines()[-15:])
            raise MotorError(f"«{' '.join(cmd)}» terminó con error {r.returncode}:\n{cola}")
        return r

    def textos(self, juego, parche_viejo=None, archivos=None):
        with tempfile.TemporaryDirectory(prefix="tl-organizer-") as tmp:
            self.ejecutar(self.comando_extraer(juego, tmp))
            datos = list(self.leer_extraido(tmp))
        yield from datos

    def construir(self, juego, salida, filas=None, imagenes=None, estados=ESTADOS_LISTOS, opciones=None,
                  parche_viejo=None, ejecutable=None, log=print):
        """Extrae el texto actual del juego para validar cada fila (mismo original), y le pasa a la herramienta solo lo aplicable."""
        os.makedirs(salida, exist_ok=True)
        del_juego = {esc: fs for _g, esc, fs in self.textos(juego)}
        hashes = {f["clave"]: f["hash"] for fs in del_juego.values() for f in fs}
        rep = dict(scripts=0, cambiadas=0, omitidas=0, errores=[])
        traducciones = {}
        for esc, fs in (filas or {}).items():
            for r in fs:
                t = (r.get("traduccion") or "").replace("\r", "")
                if not t:
                    continue
                if r.get("estado") not in estados:
                    rep["omitidas"] += 1
                elif r["clave"] not in hashes:
                    rep["errores"].append((r["clave"], "no existe en el juego"))
                elif str(r.get("hash")) != hashes[r["clave"]]:
                    rep["errores"].append((r["clave"], "el original no coincide con el del juego (hash distinto)"))
                else:
                    traducciones[r["clave"]] = t
        if traducciones:
            with tempfile.TemporaryDirectory(prefix="tl-organizer-") as tmp:
                self.escribir_para_insertar(tmp, del_juego, traducciones)
                self.ejecutar(self.comando_insertar(juego, tmp, salida))
            rep["cambiadas"] = len(traducciones)
            rep["scripts"] = len({k.rsplit(":", 1)[0] for k in traducciones})
        return {"texto": rep}

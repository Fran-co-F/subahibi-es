# SPDX-License-Identifier: GPL-3.0-or-later
"""Contenedores: archivos que guardan otros archivos (.arc, .xp3, .zip…) o simplemente una carpeta.

Todos se usan igual: nombres(), leer(nombre), `nombre in contenedor`.  Un formato nuevo es una subclase de Contenedor
que implementa esos dos métodos.  Para escribir, casi todos los motores prefieren archivos sueltos que tapan los del
contenedor (escribir_suelto); reempaquetar es propio de cada formato y es opcional.
"""
import fnmatch
import os
import zipfile


class Contenedor:
    ruta = ""

    def nombres(self):
        """Nombres de los archivos que contiene (rutas relativas con «/»)."""
        raise NotImplementedError

    def leer(self, nombre):
        """Contenido de un archivo, como bytes."""
        raise NotImplementedError

    def __contains__(self, nombre):
        return nombre in set(self.nombres())

    def __iter__(self):
        return iter(self.nombres())

    def buscar(self, *patrones):
        """Los nombres que coinciden con alguno de los patrones (fnmatch, sin distinguir mayúsculas)."""
        pats = [p.lower() for p in patrones]
        return [n for n in self.nombres() if any(fnmatch.fnmatch(n.lower(), p) for p in pats)]


class Carpeta(Contenedor):
    """Una carpeta como contenedor (los nombres son rutas relativas con «/», recorriendo subcarpetas)."""

    def __init__(self, ruta):
        self.ruta = ruta

    def nombres(self):
        out = []
        for root, dirs, files in os.walk(self.ruta):
            dirs.sort()
            for f in sorted(files):
                out.append(os.path.relpath(os.path.join(root, f), self.ruta).replace(os.sep, "/"))
        return out

    def leer(self, nombre):
        with open(os.path.join(self.ruta, *nombre.split("/")), "rb") as f:
            return f.read()


class Zip(Contenedor):
    def __init__(self, ruta):
        self.ruta = ruta
        self._zip = zipfile.ZipFile(ruta)

    def nombres(self):
        return [n for n in self._zip.namelist() if not n.endswith("/")]

    def leer(self, nombre):
        return self._zip.read(nombre)


def escribir_suelto(salida, nombre, datos):
    """Escribe salida/<nombre> (con «/» como separador), creando las carpetas que hagan falta."""
    path = os.path.join(salida, *nombre.split("/"))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(datos)
    return path

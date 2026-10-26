# SPDX-License-Identifier: GPL-3.0-or-later
"""Acceso a la traducción vieja (el .zip del parche, o una carpeta ya extraída).

Dentro hay archivos sueltos bajo Script/CVTD, Graphic/CVTD, Sound/CVTD y Voice/CVTD (posiblemente dentro de una
carpeta raíz).  Los de Script/CVTD son escenarios (para precargar el español) o imágenes (botones de elección y otras).
"""
import os
import re
import zipfile
from . import scn, sueltos

LOOSE = re.compile(r"(?:^|/)(Script|Graphic|Sound|Voice)/CVTD/([^/]+)$")


class OldPatch:
    def __init__(self, path):
        self.path = path
        self._zip = zipfile.ZipFile(path) if os.path.isfile(path) and zipfile.is_zipfile(path) else None
        if self._zip is None and not os.path.isdir(path):
            raise SystemExit(f"no encuentro la traducción vieja en {path} (ni .zip ni carpeta)")

    def files(self):
        """[(carpeta, nombre, ruta_interna)] de los archivos sueltos."""
        out = []
        if self._zip:
            for n in self._zip.namelist():
                m = LOOSE.search(n.replace("\\", "/"))
                if m and not n.endswith("/"):
                    out.append((m.group(1), m.group(2), n))
        else:
            for root, _d, fs in os.walk(self.path):
                rel = os.path.relpath(root, self.path).replace("\\", "/")
                for f in fs:
                    m = LOOSE.search((rel + "/" + f).lstrip("./"))
                    if m:
                        out.append((m.group(1), m.group(2), os.path.join(root, f)))
        return out

    def read(self, inner, n=None):
        if self._zip:
            with self._zip.open(inner) as f:
                return f.read() if n is None else f.read(n)
        with open(inner, "rb") as f:
            return f.read() if n is None else f.read(n)

    def scenarios(self):
        """{nombre: bytes} de los escenarios (Script/CVTD cuyo contenido es un escenario compilado)."""
        out = {}
        for kind, name, inner in self.files():
            if kind == "Script" and scn.is_scenario(self.read(inner, 32)):
                out[name] = self.read(inner)
        return out

    def copy_loose(self, dest, skip=lambda kind, name, head: False, modo="carpetas"):
        """Copia los archivos sueltos a dest/<carpeta>/CVTD/ (o a dest con modo="raiz", ver sueltos.py).  skip(kind, nombre, primeros_bytes) -> True para omitir.
        Devuelve {'copiados': n, 'omitidos': [(carpeta, nombre)]}."""
        copied, skipped = 0, []
        for kind, name, inner in self.files():
            head = self.read(inner, 32)
            if skip(kind, name, head):
                skipped.append((kind, name)); continue
            d = sueltos.carpeta(dest, kind, modo)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, name), "wb") as f:
                f.write(self.read(inner))
            copied += 1
        return dict(copiados=copied, omitidos=skipped)

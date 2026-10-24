# SPDX-License-Identifier: GPL-3.0-or-later
"""Perfiles de juego: un archivo TOML por juego que dice qué motor usa y qué archivos tocar (ver docs/PLAN.md, 1.4).

    id = "subahibi-15th"          nombre = "Subarashiki Hibi 15th Anniversary"          motor = "bgi"
    [deteccion]   requeridos = [...], ejecutable = "BGI.exe"
    [texto]       archivos = [patrones]           [imagenes]  archivos = [patrones]
    [galeria]     pantallas = {prefijo = "nombre"}
    [jugable]     enlazar_extensiones, enlazar, copiar_una_vez
    [<motor>]     sección propia del motor: solo la lee y valida el motor

Se buscan, en orden de prioridad (si un id se repite gana el primero que aparece):
  1. las carpetas de $SUBAHIBI_ES_PERFILES (separadas por os.pathsep);
  2. la carpeta del usuario: $XDG_CONFIG_HOME/subahibi-es/juegos (por defecto ~/.config/…) o %APPDATA%\\subahibi-es\\juegos;
  3. los perfiles incluidos en cada motor (motores/<motor>/juegos/*.toml).
"""
import glob
import os

try:
    import tomllib
except ModuleNotFoundError:                  # Python 3.10
    import tomli as tomllib

ENV = "SUBAHIBI_ES_PERFILES"
SECCIONES = ("deteccion", "texto", "imagenes", "galeria", "jugable")     # las que lee el núcleo


class PerfilError(Exception):
    pass


class Perfil:
    def __init__(self, datos, ruta=None):
        self.datos = datos
        self.ruta = ruta
        donde = ruta or "perfil"
        for k in ("id", "nombre", "motor"):
            if not isinstance(datos.get(k), str) or not datos[k].strip():
                raise PerfilError(f"{donde}: falta «{k}» (texto)")
        for k in SECCIONES + (self.motor,):
            if not isinstance(datos.get(k, {}), dict):
                raise PerfilError(f"{donde}: «{k}» debería ser una sección [{k}]")

    def __repr__(self):
        return f"Perfil({self.id!r}, motor={self.motor!r})"

    @property
    def id(self):
        return self.datos["id"]

    @property
    def nombre(self):
        return self.datos["nombre"]

    @property
    def motor(self):
        return self.datos["motor"]

    def seccion(self, nombre):
        return self.datos.get(nombre, {})

    def lista(self, seccion, clave, defecto=()):
        """Una lista de textos de una sección, o 'defecto' si no está."""
        v = self.seccion(seccion).get(clave)
        if v is None:
            return list(defecto)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise PerfilError(f"{self.ruta or self.id}: [{seccion}] {clave} debería ser una lista de textos")
        return v

    @property
    def requeridos(self):
        return self.lista("deteccion", "requeridos")

    @property
    def ejecutable(self):
        """El ejecutable del juego (se respalda en init) o None si el juego no tiene uno que reconocer."""
        return self.seccion("deteccion").get("ejecutable")


def leer(ruta):
    try:
        with open(ruta, "rb") as f:
            datos = tomllib.load(f)
    except OSError as e:
        raise PerfilError(f"{ruta}: no se puede leer: {e}")
    except tomllib.TOMLDecodeError as e:
        raise PerfilError(f"{ruta}: TOML inválido: {e}")
    return Perfil(datos, ruta)


def carpeta_de_usuario():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "subahibi-es", "juegos")


def carpetas():
    """Carpetas donde se buscan perfiles, en orden de prioridad."""
    from .. import motores
    out = [d for d in os.environ.get(ENV, "").split(os.pathsep) if d]
    out.append(carpeta_de_usuario())
    out += [cls.carpeta_perfiles() for _n, cls in motores.clases()]
    return out


def buscar():
    """Todos los perfiles, sin ids repetidos, en orden de prioridad."""
    out, vistos = [], set()
    for d in carpetas():
        for ruta in sorted(glob.glob(os.path.join(d, "*.toml"))):
            p = leer(ruta)
            if p.id not in vistos:
                vistos.add(p.id)
                out.append(p)
    return out


def obtener(id_):
    for p in buscar():
        if p.id == id_:
            return p
    raise PerfilError(f"no encuentro el perfil de juego «{id_}»; perfiles disponibles: "
                      + (", ".join(p.id for p in buscar()) or "ninguno"))

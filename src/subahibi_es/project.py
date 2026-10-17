# SPDX-License-Identifier: GPL-3.0-or-later
"""El proyecto: una carpeta de instalación del juego con un subahibi-es.json y una carpeta de trabajo.

`init` valida que la carpeta sea el juego, crea el JSON y las carpetas de trabajo y guarda una copia del BGI.exe
original.  Los demás comandos buscan el JSON en la carpeta actual o en las de arriba (como git), así que se pueden
ejecutar desde cualquier lugar de la instalación sin pasar rutas.  Nunca se modifican los archivos originales del juego.
"""
import datetime
import json
import os
import shutil

from . import exe_patch

NAME = "subahibi-es.json"
WORK = "subahibi-es-trabajo"
REQUIRED = ("BGI.exe", "sysgrp.arc", "sysprg.arc", "system.arc", "data01101.arc")
SUBDIRS = {                      # nombre -> ruta dentro de la carpeta de trabajo
    "originales": "originales",           # PNG de la interfaz original
    "texto": "texto",                     # hojas XLSX para traducir
    "imagenes": "imagenes",               # estado.tsv de las imágenes
    "traducidas": os.path.join("imagenes", "traducidas"),   # imágenes ya traducidas (PNG/BMP)
    "indice": os.path.join("imagenes", "indice"),           # galería index.html
    "backup": "backup",                   # BGI.exe original y copias de lo que se pisó al instalar
    "salida": "salida",                   # lo que hay que copiar al juego
    "jugable": "jugable",                 # carpeta de prueba con enlaces (build --jugable)
}


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, root, cfg):
        self.root = os.path.abspath(root)
        self.cfg = cfg

    def dir(self, name):
        return os.path.join(self.root, WORK, SUBDIRS[name])

    @property
    def json_path(self):
        return os.path.join(self.root, NAME)

    @property
    def parche_viejo(self):
        return self.cfg.get("parche_viejo")

    @property
    def estado_tsv(self):
        return os.path.join(self.dir("imagenes"), "estado.tsv")

    def original_exe(self):
        """Ruta de un BGI.exe sin parchear: el de la instalación o, si ya está instalado el parche, el respaldo."""
        for p in (os.path.join(self.root, "BGI.exe"), os.path.join(self.dir("backup"), "BGI.exe")):
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    if exe_patch.identify(f.read())[1]:
                        return p
        raise ProjectError("no encuentro un BGI.exe original (ni en la instalación ni en el respaldo): "
                           "ejecutá «subahibi-es desinstalar» o restaurá el BGI.exe original del juego")


def find(start=None):
    """El proyecto que contiene 'start' (por defecto, la carpeta actual) o None."""
    env = os.environ.get("SUBAHIBI_ES_PROJECT")
    cur = os.path.abspath(env if env else (start or os.getcwd()))
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        j = os.path.join(cur, NAME)
        if os.path.isfile(j):
            try:
                with open(j, encoding="utf-8") as f:
                    return Project(cur, json.load(f))
            except (OSError, ValueError) as e:
                raise ProjectError(f"{j} no se puede leer: {e}")
        nxt = os.path.dirname(cur)
        if nxt == cur:
            return None
        cur = nxt


def require(start=None):
    p = find(start)
    if p is None:
        raise ProjectError("no hay un proyecto acá: ejecutá «subahibi-es init» dentro de la carpeta de instalación del juego")
    return p


def validate_game(folder):
    """-> (version | None, [problemas]).  Es el juego si hay un BGI.exe de una versión conocida y los .arc esperados."""
    problems = []
    for f in REQUIRED:
        if not os.path.isfile(os.path.join(folder, f)):
            problems.append(f"falta {f}")
    version = None
    exe = os.path.join(folder, "BGI.exe")
    if os.path.isfile(exe):
        with open(exe, "rb") as f:
            sha, build = exe_patch.identify(f.read())
        if build:
            version = build["version"]
        else:
            backup = os.path.join(folder, WORK, SUBDIRS["backup"], "BGI.exe")
            if os.path.isfile(backup):
                with open(backup, "rb") as f:
                    b2 = exe_patch.identify(f.read())[1]
                if b2:
                    version = b2["version"]
            if version is None:
                problems.append(f"BGI.exe no es una versión conocida (sha256 {sha[:16]}…); versiones compatibles: "
                                + "; ".join(v["version"] for v in exe_patch.KNOWN_BUILDS.values()))
    return version, problems


def init(folder, parche_viejo=None, log=print):
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise ProjectError(f"no existe la carpeta {folder}")
    existing = os.path.join(folder, NAME)
    if os.path.exists(existing):
        if not parche_viejo:
            raise ProjectError(f"ya hay un proyecto en {folder} ({NAME}); para cambiar el parche viejo usá "
                               "«init --parche-viejo ARCHIVO.zip»; para empezar de nuevo, «subahibi-es reset»")
        parche_viejo = os.path.abspath(parche_viejo)
        if not os.path.exists(parche_viejo):
            raise ProjectError(f"no existe {parche_viejo}")
        proj = require(folder)
        proj.cfg["parche_viejo"] = parche_viejo
        with open(proj.json_path, "w", encoding="utf-8") as f:
            json.dump(proj.cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return proj, False
    version, problems = validate_game(folder)
    if problems:
        raise ProjectError("esta carpeta no parece la instalación de Subarashiki Hibi 15th Anniversary:\n  - " + "\n  - ".join(problems))
    if parche_viejo:
        parche_viejo = os.path.abspath(parche_viejo)
        if not os.path.exists(parche_viejo):
            raise ProjectError(f"no existe {parche_viejo}")
    proj = Project(folder, {
        "version_del_proyecto": 1,
        "motor": version,
        "parche_viejo": parche_viejo,
        "creado": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    for name in SUBDIRS:
        if name != "jugable":
            os.makedirs(proj.dir(name), exist_ok=True)
    exe = os.path.join(folder, "BGI.exe")
    backup = os.path.join(proj.dir("backup"), "BGI.exe")
    with open(exe, "rb") as f:
        if exe_patch.identify(f.read())[1] and not os.path.exists(backup):
            shutil.copy2(exe, backup)              # copia del BGI.exe original
    if not os.path.exists(proj.estado_tsv):
        shutil.copy2(os.path.join(os.path.dirname(__file__), "data", "ui_status.tsv"), proj.estado_tsv)
    with open(proj.json_path, "w", encoding="utf-8") as f:
        json.dump(proj.cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return proj, True


def reset(proj, todo=False):
    """Borra el JSON del proyecto; con todo=True, también la carpeta de trabajo.  Nunca toca los archivos del juego."""
    removed = []
    os.remove(proj.json_path)
    removed.append(proj.json_path)
    if todo:
        work = os.path.join(proj.root, WORK)
        if os.path.isdir(work):
            shutil.rmtree(work)
            removed.append(work)
    return removed

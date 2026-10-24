# SPDX-License-Identifier: GPL-3.0-or-later
"""El proyecto: una carpeta de instalación del juego con un subahibi-es.json y una carpeta de trabajo.

`init` reconoce el juego con los perfiles (perfiles.py), crea el JSON y las carpetas de trabajo y guarda una copia del
ejecutable original.  Los demás comandos buscan el JSON en la carpeta actual o en las de arriba (como git), así que se pueden
ejecutar desde cualquier lugar de la instalación sin pasar rutas.  Nunca se modifican los archivos originales del juego.

El JSON guarda el perfil, el motor y la versión detectada.  Los proyectos de antes de los perfiles (version_del_proyecto 1:
«motor» era la versión del exe y no había «perfil») se siguen abriendo con el perfil PERFIL_LEGADO.
"""
import datetime
import hashlib
import json
import os
import shutil

from .. import motores
from . import perfiles

NAME = "subahibi-es.json"
WORK = "subahibi-es-trabajo"
VERSION = 2
PERFIL_LEGADO = "subahibi-15th"
SUBDIRS = {                      # nombre -> ruta dentro de la carpeta de trabajo
    "originales": "originales",           # PNG de la interfaz original
    "texto": "texto",                     # hojas XLSX para traducir
    "imagenes": "imagenes",               # estado.tsv de las imágenes
    "traducidas": os.path.join("imagenes", "traducidas"),   # imágenes ya traducidas (PNG/BMP)
    "indice": os.path.join("imagenes", "indice"),           # galería index.html
    "backup": "backup",                   # ejecutable original y copias de lo que se pisó al instalar
    "salida": "salida",                   # lo que hay que copiar al juego
    "jugable": "jugable",                 # carpeta de prueba con enlaces (build --jugable)
}


ESTADO_PLANTILLA = """\
# Decisiones sobre las imágenes de interfaz: las usa la galería (imagenes/indice/index.html).
# Una regla por línea, con TABULADORES entre las columnas:
#     patrón<TAB>estado<TAB>nota
#   patrón: nombre de la imagen; admite * ? [..]  (por ejemplo SGTitle99000*)
#   estado: pendiente (hay que traducirla) | decidir | revisar | sin_japones (no tiene texto japonés)
# Gana la primera regla que coincida. Las imágenes que pongas en imagenes/traducidas/ se marcan solas como traducidas.
# Ejemplo (sacale el # del principio para usarlo):
# SGTitle99000*\tdecidir\tel logo es parte de la ilustración
"""


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, root, cfg, perfil=None):
        self.root = os.path.abspath(root)
        self.cfg = cfg
        self._perfil = perfil
        self._motor = None

    @property
    def perfil(self):
        if self._perfil is None:
            self._perfil = perfiles.obtener(self.cfg.get("perfil") or PERFIL_LEGADO)
        return self._perfil

    @property
    def motor(self):
        if self._motor is None:
            self._motor = motores.crear(self.perfil)
        return self._motor

    @property
    def version(self):
        """Versión del juego detectada en init (en los proyectos viejos estaba guardada como «motor»)."""
        return self.cfg.get("version") if "perfil" in self.cfg else self.cfg.get("motor")

    def dir(self, name):
        return os.path.join(self.root, WORK, SUBDIRS[name])

    @property
    def json_path(self):
        return os.path.join(self.root, NAME)

    @property
    def parche_viejo(self):
        """Ruta del parche viejo; si en el JSON está guardada relativa al proyecto, se resuelve desde la carpeta del juego."""
        p = self.cfg.get("parche_viejo")
        return p if (not p or os.path.isabs(p)) else os.path.join(self.root, *p.split("/"))

    @property
    def estado_tsv(self):
        return os.path.join(self.dir("imagenes"), "estado.tsv")

    def original_exe(self):
        """Ruta del ejecutable sin parchear: el de la instalación o, si ya está instalado el parche, el respaldo.
        None si el perfil no declara un ejecutable."""
        exe = self.perfil.ejecutable
        if not exe:
            return None
        for p in (os.path.join(self.root, exe), os.path.join(self.dir("backup"), exe)):
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    if self.motor.identificar_ejecutable(f.read()):
                        return p
        raise ProjectError(f"no encuentro un {exe} original (ni en la instalación ni en el respaldo): "
                           f"ejecutá «subahibi-es desinstalar» o restaurá el {exe} original del juego")


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


def validate_game(folder, perfil, motor):
    """-> (version | None, [problemas]).  Es el juego del perfil si están sus archivos requeridos y, si declara un
    ejecutable, es una versión conocida (la instalada o, si ya tiene el parche, la del respaldo)."""
    problems = []
    for f in perfil.requeridos:
        if not os.path.isfile(os.path.join(folder, f)):
            problems.append(f"falta {f}")
    version = None
    name = perfil.ejecutable
    exe = os.path.join(folder, name) if name else None
    if exe and os.path.isfile(exe):
        with open(exe, "rb") as f:
            data = f.read()
        version = motor.identificar_ejecutable(data)
        if version is None:
            backup = os.path.join(folder, WORK, SUBDIRS["backup"], name)
            if os.path.isfile(backup):
                with open(backup, "rb") as f:
                    version = motor.identificar_ejecutable(f.read())
            if version is None:
                problems.append(f"{name} no es una versión conocida (sha256 {hashlib.sha256(data).hexdigest()[:16]}…); "
                                "versiones compatibles: " + "; ".join(motor.versiones_conocidas()))
    return version, problems


def detect(folder):
    """-> (perfil, motor, version) del primer perfil que coincide con la carpeta, o ProjectError con lo que le falta
    al más parecido."""
    candidates = []
    for perfil in perfiles.buscar():
        try:
            motor = motores.crear(perfil)
        except motores.MotorError as e:
            candidates.append((1, perfil, [str(e)]))
            continue
        version, problems = validate_game(folder, perfil, motor)
        if not problems:
            return perfil, motor, version
        candidates.append((len(problems), perfil, problems))
    if not candidates:
        raise ProjectError("no hay perfiles de juego instalados (ver docs/PLAN.md, «El perfil de juego»)")
    _n, perfil, problems = min(candidates, key=lambda c: c[0])
    head = (f"esta carpeta no parece la instalación de {perfil.nombre}" if len(candidates) == 1 else
            f"esta carpeta no coincide con ninguno de los {len(candidates)} juegos conocidos; el más parecido es {perfil.nombre}")
    raise ProjectError(head + ":\n  - " + "\n  - ".join(problems))


def _guardable(path, root):
    """La ruta tal como se guarda en el JSON: relativa (con /) si el archivo está dentro del proyecto, si no, absoluta."""
    path = os.path.abspath(path)
    rel = os.path.relpath(path, root) if os.path.splitdrive(path)[0] == os.path.splitdrive(root)[0] else path
    return rel.replace(os.sep, "/") if not rel.startswith("..") and not os.path.isabs(rel) else path


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
        proj.cfg["parche_viejo"] = _guardable(parche_viejo, proj.root)
        with open(proj.json_path, "w", encoding="utf-8") as f:
            json.dump(proj.cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return proj, False
    perfil, motor, version = detect(folder)
    if parche_viejo:
        parche_viejo = os.path.abspath(parche_viejo)
        if not os.path.exists(parche_viejo):
            raise ProjectError(f"no existe {parche_viejo}")
    proj = Project(folder, {
        "version_del_proyecto": VERSION,
        "perfil": perfil.id,
        "motor": perfil.motor,
        "version": version,
        "parche_viejo": _guardable(parche_viejo, folder) if parche_viejo else None,
        "creado": datetime.datetime.now().isoformat(timespec="seconds"),
    }, perfil)
    for name in SUBDIRS:
        if name != "jugable":
            os.makedirs(proj.dir(name), exist_ok=True)
    if perfil.ejecutable:
        exe = os.path.join(folder, perfil.ejecutable)
        backup = os.path.join(proj.dir("backup"), perfil.ejecutable)
        with open(exe, "rb") as f:
            if motor.identificar_ejecutable(f.read()) and not os.path.exists(backup):
                shutil.copy2(exe, backup)          # copia del ejecutable original
    if not os.path.exists(proj.estado_tsv):
        with open(proj.estado_tsv, "w", encoding="utf-8", newline="\n") as f:
            f.write(ESTADO_PLANTILLA)
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
            w = os.path.realpath(work)
            try:
                dentro = os.path.commonpath([os.path.realpath(os.getcwd()), w]) == w
            except ValueError:             # otro disco
                dentro = False
            if dentro:
                os.chdir(proj.root)        # Windows no deja borrar la carpeta actual del proceso
            shutil.rmtree(work)
            removed.append(work)
    return removed

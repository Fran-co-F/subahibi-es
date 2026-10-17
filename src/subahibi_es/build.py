# SPDX-License-Identifier: GPL-3.0-or-later
"""Arma la carpeta del juego en español a partir de tu copia del juego, el parche viejo y tus traducciones."""
import os
import shutil
from .bgi.arc import Arc
from . import exe_patch, oldpatch
from .text import export, import_
from .images import import_ as images_import

LINK_PATTERNS = (".arc",)
LINK_NAMES = ("BHVC.exe", "BGI.hvl")
COPY_ONCE = ("BGI.gdb", "UserData")          # datos del jugador: se copian la primera vez y no se pisan


def _link(src, dst):
    if os.path.lexists(dst):
        if os.path.islink(dst) and os.readlink(dst) == src:
            return
        os.remove(dst)
    os.symlink(src, dst)


def build(game, out, old=None, texto=None, imagenes=None, estados=import_.APLICAR, voces=True, utf8=False, font_name=exe_patch.DEFAULT_FONT, log=print):
    rep = {}
    os.makedirs(out, exist_ok=True)
    game, out = os.path.abspath(game), os.path.abspath(out)
    # 1) .arc y archivos fijos: enlaces; datos del jugador: copia única
    n = 0
    for f in sorted(os.listdir(game)):
        src = os.path.join(game, f)
        if os.path.isfile(src) and (f.lower().endswith(LINK_PATTERNS) or f in LINK_NAMES or f.lower().endswith(".ico")):
            _link(src, os.path.join(out, f)); n += 1
    for f in COPY_ONCE:
        src, dst = os.path.join(game, f), os.path.join(out, f)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
    rep["enlaces"] = n
    # 2) exe parcheado
    with open(os.path.join(game, "BGI.exe"), "rb") as f:
        data = f.read()
    try:
        patched = exe_patch.patch(data, utf8=utf8, font_name=font_name)
    except exe_patch.PatchError as e:
        raise SystemExit(f"error: {e}")
    with open(os.path.join(out, "BGI.exe"), "wb") as f:
        f.write(patched)
    # 3) archivos sueltos del parche viejo, sin lo que se regenera o ya no sirve
    if old:
        ui_old = set(Arc(os.path.join(game, "sysgrp.arc")).names())      # imágenes de la interfaz vieja: tapan las nuevas
        from .bgi import scn

        def skip(kind, name, head):
            if kind == "Script" and scn.is_scenario(head):
                return True                      # los escenarios se rehacen sobre los de la 15th
            if kind == "Voice" and not voces:
                return True
            return name in ui_old                # interfaz vieja

        r = oldpatch.OldPatch(old).copy_loose(out, skip)
        rep["sueltos"] = r["copiados"]
        rep["omitidos_ui_vieja"] = sum(1 for k, nm in r["omitidos"] if nm in ui_old)
    # 4) escenarios
    if texto:
        t = import_.import_text(game, [texto], out, estados, utf8)
    elif old:
        olds = export.load_old(old)
        data_rows = {}
        for _arc, name, jp in export.scenarios(game):
            if name in olds:
                data_rows[name] = export.script_rows(name, jp, olds[name])
        t = import_.apply_rows(game, data_rows, out, estados, utf8)
    elif utf8:
        t = import_.apply_rows(game, {}, out, estados, utf8)
    else:
        t = None
    rep["texto"] = t
    # 5) imágenes traducidas
    if imagenes:
        arcs = [os.path.join(game, "sysgrp.arc")]
        placed, warns, errs = images_import.import_images(imagenes, arcs, out)
        rep["imagenes"] = dict(colocadas=len(placed), avisos=warns, errores=errs)
    return rep

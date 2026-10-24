# SPDX-License-Identifier: GPL-3.0-or-later
"""Arma la carpeta del juego traducido a partir de tu copia del juego, el parche viejo y tus traducciones."""
import os
from .arc import Arc
from . import exe_patch, oldpatch
from .text import export, import_
from .images import import_ as images_import


def build(game, out, old=None, filas=None, imagenes=None, estados=import_.APLICAR, voces=True, utf8=True, font_name=None,
          exe=None, exe_name="BGI.exe", builds=None, data_arcs=export.DATA_ARCS, ui_arcs=("sysgrp.arc",), log=print):
    """filas: {escenario: [filas]} de las hojas, o None si no hay hojas.  exe: ruta del ejecutable original;
    builds: versiones conocidas del exe ({sha256: datos}, ver exe_patch.desde_perfil).  data_arcs: patrones de los .arc
    con escenarios; ui_arcs: los .arc con las imágenes de interfaz."""
    rep = {}
    os.makedirs(out, exist_ok=True)
    game, out = os.path.abspath(game), os.path.abspath(out)
    ui_paths = [os.path.join(game, a) for a in ui_arcs]
    # 1) exe parcheado
    with open(exe or os.path.join(game, exe_name), "rb") as f:
        data = f.read()
    try:
        patched = exe_patch.patch(data, builds or {}, font=bool(font_name), utf8=utf8, font_name=font_name)
    except exe_patch.PatchError as e:
        raise SystemExit(f"error: {e}")
    with open(os.path.join(out, exe_name), "wb") as f:
        f.write(patched)
    log(f"{exe_name} parcheado (" + (f"fuente «{font_name}», " if font_name else "sin cambiar la fuente, ")
        + ("modo UTF-8" if utf8 else "modo katakana") + ")")
    # 2) archivos sueltos del parche viejo, sin lo que se regenera o ya no sirve
    if old:
        ui_old = set()                            # imágenes de la interfaz vieja: tapan las nuevas
        for p in ui_paths:
            ui_old.update(Arc(p).names())
        from . import scn

        def skip(kind, name, head):
            if kind == "Script" and scn.is_scenario(head):
                return True                      # los escenarios se rehacen sobre los de la 15th
            if kind == "Voice" and not voces:
                return True
            return name in ui_old                # interfaz vieja

        r = oldpatch.OldPatch(old).copy_loose(out, skip)
        rep["sueltos"] = r["copiados"]
        rep["omitidos_ui_vieja"] = sum(1 for k, nm in r["omitidos"] if nm in ui_old)
        log(f"{rep['sueltos']} archivos sueltos del parche viejo ({rep['omitidos_ui_vieja']} imágenes de la interfaz vieja omitidas)")
    # 3) escenarios
    if filas is not None:
        t = import_.apply_rows(game, filas, out, estados, utf8, data_arcs)
    elif old:
        olds = export.load_old(old)
        data_rows = {}
        for _arc, name, jp in export.scenarios(game, patrones=data_arcs):
            if name in olds:
                data_rows[name] = export.script_rows(name, jp, olds[name])
        t = import_.apply_rows(game, data_rows, out, estados, utf8, data_arcs)
    elif utf8:
        t = import_.apply_rows(game, {}, out, estados, utf8, data_arcs)
    else:
        t = None
    rep["texto"] = t
    # 4) imágenes traducidas
    if imagenes:
        placed, warns, errs = images_import.import_images(imagenes, ui_paths, out)
        rep["imagenes"] = dict(colocadas=len(placed), avisos=warns, errores=errs)
    return rep

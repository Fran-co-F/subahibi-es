# SPDX-License-Identifier: GPL-3.0-or-later
"""Coloca imágenes traducidas (PNG o BMP) donde el motor las busca: Graphic/CVTD/<NOMBRE>.

El motor da prioridad a los archivos sueltos sobre los .arc; el archivo suelto es un BMP de
32 bits con alfa, del mismo tamaño y con el mismo nombre que la entrada del .arc, sin extensión.
"""
import os
from PIL import Image
from ..arc import Arc
from .. import dsc, image, sueltos as sueltos_mod
from ....nucleo.imagenes import open_any

LOOSE_DIR = os.path.join("Graphic", "CVTD")        # ruta fijada por los programas del juego (system.arc:ipl._bp)
EXTS = (".png", ".bmp")


def _reference_sizes(arcs, wanted):
    """{nombre: (ancho, alto)} leyendo solo las entradas pedidas de los .arc."""
    out = {}
    for arc_path in arcs:
        arc = Arc(arc_path)
        for n in wanted:
            if n in arc and n not in out:
                raw = arc.read(n)
                data = dsc.decode(raw) if dsc.is_dsc(raw) else raw
                if image.is_raw_image(data):
                    out[n] = image.to_pil(data).size
    return out


def import_images(src_dir, arcs, out_game_dir, log=print, sueltos="carpetas"):
    """Devuelve (colocadas, avisos, errores)."""
    files = {}
    for f in sorted(os.listdir(src_dir)):
        stem, ext = os.path.splitext(f)
        if ext.lower() in EXTS:
            files[stem] = os.path.join(src_dir, f)
        elif not ext and os.path.isfile(os.path.join(src_dir, f)):
            files[f] = os.path.join(src_dir, f)          # ya es un archivo suelto (sin extensión)
    ref = _reference_sizes(arcs, list(files))
    dest = sueltos_mod.carpeta(out_game_dir, "Graphic", sueltos)
    os.makedirs(dest, exist_ok=True)
    placed, warns, errs = [], [], []
    for name, path in files.items():
        if name not in ref:
            errs.append((name, "no existe como imagen en los .arc indicados (nombre mal escrito)")); continue
        im = open_any(path)
        if im.size != ref[name]:
            errs.append((name, f"tamaño {im.size[0]}x{im.size[1]} distinto del original {ref[name][0]}x{ref[name][1]}")); continue
        if path.lower().endswith(".png"):           # los BMP de 32 bits se leen con su alfa tal cual
            mode = Image.open(path).mode
            if mode not in ("RGBA", "LA", "PA"):
                warns.append((name, f"modo {mode}: la imagen no tiene transparencia"))
        im.save(os.path.join(dest, name), format="BMP")
        placed.append(name)
    return placed, warns, errs

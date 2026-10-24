# SPDX-License-Identifier: GPL-3.0-or-later
"""Exporta las imágenes de interfaz de los .arc del juego a PNG."""
import os
from ..arc import Arc
from .. import dsc, image


def export_arc(arc_path, out_dir, log=print):
    """Escribe <out_dir>/<entrada>.png para cada entrada que sea una imagen cruda (tras DSC).
    Devuelve (exportadas, omitidas) donde omitidas es una lista de (nombre, motivo)."""
    arc = Arc(arc_path)
    os.makedirs(out_dir, exist_ok=True)
    done, skipped = 0, []
    for name in arc.names():
        raw = arc.read(name)
        try:
            data = dsc.decode(raw) if dsc.is_dsc(raw) else raw
        except ValueError as e:
            skipped.append((name, f"DSC: {e}")); continue
        if not image.is_raw_image(data):
            skipped.append((name, "no es una imagen cruda (¿CompressedBG u otro formato?)")); continue
        image.to_pil(data).save(os.path.join(out_dir, name + ".png"))
        done += 1
    return done, skipped

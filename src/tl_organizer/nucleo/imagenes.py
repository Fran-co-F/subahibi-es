# SPDX-License-Identifier: GPL-3.0-or-later
"""Lectura de las imágenes que entrega quien traduce (PNG o BMP), con su transparencia."""
import struct
from PIL import Image


def open_any(path):
    """Abre PNG/BMP como RGBA.  Pillow descarta el alfa de los BMP de 32 bits sin máscaras
    (justo el formato de los archivos sueltos del motor), así que esos se leen a mano."""
    with open(path, "rb") as f:
        head = f.read(54)
    if head[:2] == b"BM" and len(head) >= 54:
        hdr, w, h, planes, bpp, comp = struct.unpack_from("<IiiHHI", head, 14)
        if hdr == 40 and bpp == 32 and comp == 0:
            with open(path, "rb") as f:
                data = f.read()
            off = struct.unpack_from("<I", data, 10)[0]
            top_down = h < 0
            h = abs(h)
            return Image.frombuffer("RGBA", (w, h), data[off:off + w * h * 4], "raw", "BGRA", 0, 1 if top_down else -1)
    return Image.open(path).convert("RGBA")

# SPDX-License-Identifier: GPL-3.0-or-later
"""Imágenes 'crudas' de BGI (lo que queda tras la capa DSC).

  u16 ancho, u16 alto, u32 bits por píxel (24 o 32), 8 bytes a cero, y los píxeles BGR(A)
  de arriba abajo, sin relleno por fila.
"""
import struct
from PIL import Image


def is_raw_image(data):
    if len(data) < 16:
        return False
    w, h, bpp = struct.unpack_from("<HHI", data, 0)
    return (bpp in (24, 32) and w and h and data[8:16] == b"\0" * 8
            and len(data) == 16 + w * h * bpp // 8)


def to_pil(data):
    w, h, bpp = struct.unpack_from("<HHI", data, 0)
    if bpp == 32:
        return Image.frombuffer("RGBA", (w, h), data[16:], "raw", "BGRA", 0, 1)
    return Image.frombuffer("RGB", (w, h), data[16:], "raw", "BGR", 0, 1).convert("RGBA")


def from_pil(im, bpp=32):
    im = im.convert("RGBA")
    w, h = im.size
    body = im.tobytes("raw", "BGRA" if bpp == 32 else "BGR")
    return struct.pack("<HHI", w, h, bpp) + b"\0" * 8 + body


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

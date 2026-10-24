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


# SPDX-License-Identifier: GPL-3.0-or-later
"""Detección opcional de texto japonés en una imagen con Tesseract (programa externo).

Es solo una pista: Tesseract inventa kana en fondos decorativos, así que se exige una confianza
mínima por palabra y un mínimo de caracteres.  Lo que se decide a mano (data/ui_status.tsv) manda.
"""
import os
import re
import shutil
import subprocess
import tempfile
from PIL import Image

CJK = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")


def available():
    return shutil.which("tesseract") is not None


def japanese_chars(png_path, min_conf=60):
    """Cantidad de caracteres japoneses reconocidos con confianza >= min_conf.
    Las imágenes con alfa se pasan sobre gris; las chicas se amplían x3 y las tiras anchas se recortan a
    su primer estado (los tres estados repiten el texto); los fondos grandes se dejan a su tamaño."""
    im = Image.open(png_path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (110, 110, 120, 255))
    bg.alpha_composite(im)
    bg = bg.convert("L")
    w, h = bg.size
    if h <= 120 and w > 700:                       # tira de varios estados
        bg = bg.crop((0, 0, 700, h)); w = 700
    small = max(w, h) <= 700 or h <= 120
    if small:
        bg = bg.resize((w * 3, h * 3), Image.LANCZOS)
    with tempfile.TemporaryDirectory() as tmp:       # (NamedTemporaryFile no se puede reabrir por nombre en Windows)
        path = os.path.join(tmp, "img.png")
        bg.save(path)
        out = subprocess.run(["tesseract", path, "stdout", "-l", "jpn", "--psm", "6" if small else "11", "tsv"],
                             capture_output=True, text=True,
                             env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout
    n = 0
    for line in out.splitlines()[1:]:
        c = line.split("\t")
        if len(c) >= 12 and c[10].lstrip("-").replace(".", "").isdigit() and float(c[10]) >= min_conf:
            n += len(CJK.findall(c[11]))
    return n


def has_japanese(png_path, min_chars=2):
    return japanese_chars(png_path) >= min_chars

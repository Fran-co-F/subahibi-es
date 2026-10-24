# SPDX-License-Identifier: GPL-3.0-or-later
"""Índice (HTML + CSV) que compara las imágenes originales con las traducidas y dice qué falta.

Estados: traducida, pendiente (tiene japonés), decidir, revisar, sin_japones, sin_clasificar.
La clasificación sale de (1) existir la imagen traducida, (2) el archivo de decisiones manuales
(TSV: patrón<TAB>estado<TAB>nota; los patrones aceptan * ? [..]), y (3) con --ocr, de Tesseract.
Lo manual gana siempre sobre el OCR.  El OCR es solo una pista (acierta ~60% de lo que tiene japonés y
marca ~12% de más): lo que ve queda como "revisar" y lo que no ve como "sin_clasificar", nunca "sin_japones".
"""
import csv
import fnmatch
import os
import re
from collections import Counter
from PIL import Image
from ..imagenes import open_any
from . import ocr as _ocr
from . import _page

ETIQUETAS = {"traducida": "Traducida", "pendiente": "Pendiente (tiene japonés)", "decidir": "A decidir",
             "revisar": "Revisar", "sin_japones": "Sin japonés", "sin_clasificar": "Sin clasificar"}
COLORES = {"traducida": "#2e8b57", "pendiente": "#c0392b", "decidir": "#b9770e", "revisar": "#7d3c98",
           "sin_japones": "#566573", "sin_clasificar": "#2874a6"}



def read_status(path):
    rules = []
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip() or line.startswith("#"):
                    continue
                p = line.split("\t")
                if len(p) >= 2 and p[1] in ETIQUETAS:
                    rules.append((p[0], p[1], p[2] if len(p) > 2 else ""))
    return rules


def _thumb(im, maxw=1100, maxh=500):
    s = min(1, maxw / im.size[0], maxh / im.size[1])
    return im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS) if s < 1 else im


def build(originals, translated, out_dir, status_file=None, use_ocr=False, log=print, pantallas=None):
    """pantallas: {prefijo del nombre: nombre de la pantalla} para la columna «pantalla» de estado.csv (del perfil)."""
    pantallas = pantallas or {}
    names = sorted(f[:-4] for f in os.listdir(originals) if f.lower().endswith(".png"))
    tr = {}
    if translated and os.path.isdir(translated):
        for f in os.listdir(translated):
            tr[os.path.splitext(f)[0]] = os.path.join(translated, f)
    rules = read_status(status_file)
    if use_ocr and not _ocr.available():
        log("aviso: --ocr pedido pero 'tesseract' no está instalado; se omite")
        use_ocr = False
    for sub in ("img/jp", "img/es"):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
    pend = [n for n in names if n not in tr and not any(fnmatch.fnmatch(n, r[0]) for r in rules)]
    ocr_res = {}
    if use_ocr and pend:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            ocr_res = dict(zip(pend, ex.map(lambda n: _ocr.has_japanese(os.path.join(originals, n + ".png")), pend)))
    rows = []
    for n in names:
        src = os.path.join(originals, n + ".png")
        im = Image.open(src).convert("RGBA")
        st, nota = None, ""
        if n in tr:
            st = "traducida"
        else:
            for pat, s, note in rules:
                if fnmatch.fnmatch(n, pat):
                    st, nota = s, note
                    break
        if st is None:
            if use_ocr:
                st, nota = (("revisar", "el OCR cree ver japonés (confirmar a mano)") if ocr_res.get(n)
                            else ("sin_clasificar", "el OCR no vio japonés (puede fallar con texto fino o de bajo contraste)"))
            else:
                st = "sin_clasificar"
        _thumb(im).save(os.path.join(out_dir, "img/jp", n + ".webp"), quality=88, method=4)
        if n in tr:
            _thumb(open_any(tr[n])).save(os.path.join(out_dir, "img/es", n + ".webp"), quality=88, method=4)
        rows.append(dict(n=n, g=re.match(r"[A-Za-z]+", n).group(0), w=im.size[0], h=im.size[1], st=st, note=nota, tr=n in tr))
    with open(os.path.join(out_dir, "estado.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["imagen", "pantalla", "ancho", "alto", "estado", "nota"])
        for r in rows:
            w.writerow([r["n"], pantallas.get(r["g"], r["g"]), r["w"], r["h"], r["st"], r["note"]])
    _write_html(rows, tr, out_dir)
    return Counter(r["st"] for r in rows)


def _write_html(rows, tr, out_dir):
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(_page.render(rows, ETIQUETAS, COLORES))

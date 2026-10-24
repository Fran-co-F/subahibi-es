# SPDX-License-Identifier: GPL-3.0-or-later
"""Saltos de línea manuales en la columna de la traducción de las hojas: corte en límites de palabra.

El motor corta el texto solo cuando una letra no entra en la ventana, a mitad de palabra.  Este módulo parte
las líneas en los espacios para que ninguna pase del ancho dado (en caracteres o en píxeles con la fuente del juego).
Los saltos de línea que ya hay se respetan (cada tramo se ajusta por separado); con reflow=True se descartan primero.
"""
import os


def wrap_text(text, fits, reflow=False):
    """fits(linea) -> True si la línea entra.  Devuelve el texto con '\\n' en los cortes."""
    if reflow:
        trailing = text.endswith("\n")
        text = " ".join(p for p in text.split("\n") if p.strip()) + ("\n" if trailing else "")
    out = []
    for seg in text.split("\n"):
        lines, cur = [], ""
        for w in seg.split(" "):
            if cur == "":
                cur = w
            elif fits(cur + " " + w):
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        out.append("\n".join(lines))
    return "\n".join(out)


def make_fits(max_chars=None, width_px=None, font_path=None, size=None):
    """Función de medida: por caracteres, por píxeles con la fuente (o ambas)."""
    if width_px:
        if not (font_path and size and os.path.exists(font_path)):
            raise SystemExit("para medir en píxeles hacen falta --fuente (un .ttf existente) y --tamano")
        from PIL import ImageFont
        font = ImageFont.truetype(font_path, size)
    def fits(line):
        if max_chars and len(line) > max_chars:
            return False
        if width_px and font.getlength(line) > width_px:
            return False
        return True
    return fits


def wrap_rows(rows, fits, estados=("traducido", "del parche", "revisar"), reflow=False, max_lines=None):
    """Aplica wrap_text a las filas con español y estado en 'estados'.  Devuelve (cambiadas, con_demasiadas_lineas)."""
    changed = overflow = 0
    for r in rows:
        es = r.get("traduccion") or ""
        if not es or r.get("estado") not in estados or r.get("tipo") != "mensaje":
            continue
        new = wrap_text(es, fits, reflow)
        if new != es:
            r["traduccion"] = new
            changed += 1
        if max_lines and len([l for l in new.split("\n") if l != ""]) > max_lines:
            overflow += 1
            if "líneas" not in (r.get("nota") or ""):
                r["nota"] = (r.get("nota") + "; " if r.get("nota") else "") + f"más de {max_lines} líneas"
    return changed, overflow

# SPDX-License-Identifier: GPL-3.0-or-later
"""Reimporta las hojas de traducción: arma los escenarios del juego con el español.

Método: parche binario de cadenas.  Del escenario original (japonés, de la 15th) no se toca ningún token
salvo el operando de los 'str' de los textos traducidos, que pasan a apuntar a cadenas nuevas agregadas al
final de la tabla de cadenas.  Como los operandos son desplazamientos desde el inicio del flujo y las
cadenas nuevas van al final, nada se reubica: saltos, exportaciones y demás operandos quedan intactos.
"""
import os
from ..bgi import scn
from . import accents, extract, sheet
from .export import scenarios

APLICAR = ("traducido", "del parche")


class ImportError_(Exception):
    pass


def collect(paths):
    """{script: [filas]} a partir de archivos .xlsx / .tsv o carpetas con ellos."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith((".xlsx", ".tsv")):
                    files.append(os.path.join(p, f))
            tsvdir = os.path.join(p, "tsv")
            if os.path.isdir(tsvdir):
                files += [os.path.join(tsvdir, f) for f in sorted(os.listdir(tsvdir)) if f.endswith(".tsv")]
        else:
            files.append(p)
    out = {}
    for f in files:
        sheets = sheet.read_xlsx(f) if f.lower().endswith(".xlsx") else {os.path.basename(f): sheet.read_tsv(f)}
        for rows in sheets.values():
            for r in rows:
                script = r["clave"].rsplit(":", 1)[0]
                out.setdefault(script, {})[r["clave"]] = r      # la última gana si una fila está repetida
    return {k: list(v.values()) for k, v in out.items()}


def build_script(name, jp_bytes, rows, estados=APLICAR, utf8=False):
    """-> (bytes del escenario nuevo | None si no cambia nada, informe dict).
    utf8=True: el motor corre en modo UTF-8, así que TODAS las cadenas del escenario se reescriben en UTF-8
    (las no traducidas pasan de Shift-JIS a UTF-8) y el español se escribe tal cual, sin la tabla de katakana."""
    sc = scn.parse(jp_bytes)
    by_pos = {r.pos: r for r in extract.rows(sc, all_store=True)}
    tok_at = {t.pos: i for i, t in enumerate(sc.tokens)}
    new_tail, cache, errs = bytearray(sc.tail), {}, []
    touched = set()                              # índices de tokens 'str' que cambian de operando
    changed = skipped = unconverted = 0

    def put(raw):
        if raw not in cache:
            cache[raw] = sc.strings_start + len(new_tail)
            new_tail.extend(raw + b"\0")
        return cache[raw]

    if utf8:                                      # 1) todo el escenario a UTF-8
        for i, t in enumerate(sc.tokens):
            if t.op != scn.TOK_STR:
                continue
            raw = sc.string_at(t.args[0])
            if all(b < 0x80 for b in raw):
                continue
            try:
                conv = raw.decode("cp932").encode("utf-8")
            except UnicodeDecodeError:
                unconverted += 1
                continue
            t.args = (put(conv),)
            touched.add(i)
    for r in rows:                                # 2) las traducciones
        es = (r.get("espanol") or "").replace("\r", "")
        if not es:
            continue
        if r.get("estado") not in estados:
            skipped += 1
            continue
        try:
            pos = int(r["pos"])
        except (TypeError, ValueError):
            errs.append((r["clave"], "falta 'pos'")); continue
        row = by_pos.get(pos)
        if row is None:
            errs.append((r["clave"], f"no hay texto en la posición {pos}: ¿hoja de otra versión?")); continue
        if sheet.jp_hash(row.raw) != r.get("hash"):
            errs.append((r["clave"], "el texto japonés no coincide con el del juego (hash distinto)")); continue
        if utf8:
            raw = es.encode("utf-8")
        else:
            bad = accents.unencodable(es)
            if bad:
                errs.append((r["clave"], "caracteres que el juego no puede mostrar: " + " ".join(bad))); continue
            raw = accents.encode(es)
        if b"\0" in raw:
            errs.append((r["clave"], "el texto contiene un carácter nulo")); continue
        i = tok_at[pos]
        sc.tokens[i].args = (put(raw),)
        touched.add(i)
        changed += 1
    if not touched:
        return None, dict(cambiadas=0, omitidas=skipped, errores=errs, sin_convertir=unconverted)
    sc.tail = bytes(new_tail)
    out = scn.serialize(sc)
    # comprobación: se lee de nuevo y, salvo los operandos de las cadenas reapuntadas, los tokens son idénticos
    orig, chk = scn.parse(jp_bytes), scn.parse(out, strings_start=sc.strings_start)
    if len(chk.tokens) != len(orig.tokens) or chk.head != orig.head:
        raise ImportError_(f"{name}: el escenario resultante no se puede leer igual")
    diff = set()
    for i, (a, b) in enumerate(zip(orig.tokens, chk.tokens)):
        if (a.pos, a.op) != (b.pos, b.op):
            raise ImportError_(f"{name}: cambió la estructura de tokens en {a.pos}")
        if a.args != b.args:
            if a.op != scn.TOK_STR:
                raise ImportError_(f"{name}: cambió un operando que no es una cadena (pos {a.pos})")
            diff.add(i)
    if diff != touched:
        raise ImportError_(f"{name}: {len(diff)} operandos distintos, se esperaban {len(touched)}")
    return out, dict(cambiadas=changed, omitidas=skipped, errores=errs, sin_convertir=unconverted)


def apply_rows(game_dir, data, out_game_dir, estados=APLICAR, utf8=False):
    """data = {escenario: [filas]}.  Escribe out_game_dir/Script/CVTD/<escenario> para los que cambian.
    Con utf8=True se escriben TODOS los escenarios del juego (también los sin traducir), porque el motor en
    modo UTF-8 necesita todas las cadenas en UTF-8."""
    dest = os.path.join(out_game_dir, "Script", "CVTD")
    os.makedirs(dest, exist_ok=True)
    total = dict(scripts=0, cambiadas=0, omitidas=0, errores=[], sin_convertir=0)
    seen = set()
    for _arc, name, jp in scenarios(game_dir):
        if name not in data and not utf8:
            continue
        seen.add(name)
        out, rep = build_script(name, jp, data.get(name, []), estados, utf8)
        total["omitidas"] += rep["omitidas"]
        total["sin_convertir"] += rep["sin_convertir"]
        total["errores"] += [(f"{name}: {k}", v) for k, v in rep["errores"]]
        if out is None:
            continue
        with open(os.path.join(dest, name), "wb") as f:
            f.write(out)
        total["scripts"] += 1
        total["cambiadas"] += rep["cambiadas"]
    for name in sorted(set(data) - seen):
        total["errores"].append((name, "no existe un escenario con ese nombre en el juego"))
    return total


def import_text(game_dir, sheet_paths, out_game_dir, estados=APLICAR, utf8=False, log=print):
    return apply_rows(game_dir, collect(sheet_paths), out_game_dir, estados, utf8)

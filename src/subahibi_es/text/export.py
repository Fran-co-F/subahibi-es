# SPDX-License-Identifier: GPL-3.0-or-later
"""Exporta el texto de los escenarios del juego a hojas de traducción."""
import glob
import os
from ..bgi.arc import Arc
from ..bgi import dsc, scn
from . import accents, align, extract, sheet

MAX_COMPRESSED = 2_000_000       # los escenarios son chicos; evita descomprimir imágenes enormes


def scenarios(game_dir, arcs=None):
    """Genera (nombre_arc, nombre_script, bytes) de los escenarios de los .arc del juego."""
    paths = ([os.path.join(game_dir, a if a.endswith(".arc") else a + ".arc") for a in arcs]
             if arcs else sorted(glob.glob(os.path.join(game_dir, "data0*.arc"))))
    for p in paths:
        arc = Arc(p)
        for e in arc.entries:
            if e.size > MAX_COMPRESSED:
                continue
            raw = arc.read(e.name)
            try:
                d = dsc.decode(raw) if dsc.is_dsc(raw) else raw
            except ValueError:
                continue
            if scn.is_scenario(d):
                yield os.path.splitext(os.path.basename(p))[0], e.name, d


def load_old(path):
    """Escenarios de la traducción vieja: un .zip del parche o una carpeta ya extraída."""
    from ..oldpatch import OldPatch
    olds = OldPatch(path).scenarios()
    if not olds:
        raise SystemExit(f"no encontré escenarios en {path}")
    return olds


def script_rows(name, jp_bytes, old_bytes=None):
    """Filas (dicts de la hoja) de un escenario; con old_bytes precarga la traducción vieja alineada.

    Las filas precargadas quedan «del parche», salvo las que están en una zona donde el largo del japonés y el del español
    dejan de correlacionarse (señal de que la alineación se corrió): esas quedan «revisar»."""
    sj = scn.parse(jp_bytes)
    rj = extract.rows(sj, all_store=True)
    mapping = {}
    re_ = []
    if old_bytes is not None:
        se = scn.parse(old_bytes)
        re_ = extract.rows(se, all_store=True)
        mapping, _agree, _exact = align.align(sj, rj, se, re_)
    out, n = [], 0
    for i, r in enumerate(rj):
        if (r.kind == "eleccion" and not r.has_japanese) or not r.raw:
            continue          # opciones sin texto japonés y cadenas vacías: nada que traducir
        n += 1
        es, st = "", "sin traducir"
        if i in mapping:
            # el parche viejo termina muchas líneas con un TAB que el original no tiene: es invisible en la hoja y no aporta nada
            es, st = accents.decode(re_[mapping[i]].raw).rstrip("\t"), "del parche"
        out.append(dict(clave=f"{name}:{n:05d}", tipo=r.kind, japones=r.raw.decode("cp932", "replace"),
                        espanol=es, estado=st, nota="", pos=r.pos, hash=sheet.jp_hash(r.raw)))
    pairs = [k for k, r in enumerate(out) if r["tipo"] == "mensaje" and r["espanol"]]
    for k in align.doubtful([len(out[k]["japones"]) for k in pairs], [len(out[k]["espanol"]) for k in pairs]):
        out[pairs[k]]["estado"], out[pairs[k]]["nota"] = "revisar", "alineación dudosa: el largo no se parece al del original"
    return out


def export_text(game_dir, out_dir, arcs=None, old=None, tsv=False, xlsx=True, log=print):
    os.makedirs(out_dir, exist_ok=True)
    olds = load_old(old) if old else {}
    by_arc, total, prefilled, sin_texto = {}, 0, 0, []
    for arc, name, data in scenarios(game_dir, arcs):
        rows = script_rows(name, data, olds.get(name))
        if not rows:                      # guiones de configuración o de finales: no hay nada que traducir
            sin_texto.append(name)
            continue
        by_arc.setdefault(arc, {})[sheet.safe_name(name)] = rows
        total += len(rows)
        prefilled += sum(1 for r in rows if r["estado"] != "sin traducir")
        if tsv:
            os.makedirs(os.path.join(out_dir, "tsv"), exist_ok=True)
            sheet.write_tsv(os.path.join(out_dir, "tsv", sheet.safe_name(name) + ".tsv"), rows)
    if xlsx:
        for arc, sheets in by_arc.items():
            sheet.write_xlsx(os.path.join(out_dir, arc + ".xlsx"), sheets)
    return dict(scripts=sum(len(v) for v in by_arc.values()), arcs=len(by_arc), filas=total, precargadas=prefilled,
                sin_texto=sin_texto)

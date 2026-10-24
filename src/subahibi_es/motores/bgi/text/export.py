# SPDX-License-Identifier: GPL-3.0-or-later
"""Saca las filas de texto de los escenarios del juego (las hojas las escribe nucleo/texto.py)."""
import glob
import os
from ..arc import Arc
from .. import dsc, scn
from ....nucleo import alineacion, hojas
from . import accents, align, extract

MAX_COMPRESSED = 2_000_000       # los escenarios son chicos; evita descomprimir imágenes enormes
DATA_ARCS = ("data0*.arc",)      # dónde están los escenarios si el perfil no dice otra cosa ([texto] archivos)


def arc_paths(game_dir, arcs=None, patrones=DATA_ARCS):
    """Rutas de los .arc: los nombrados en 'arcs' (con o sin .arc) o, si no, los que coinciden con 'patrones'."""
    if arcs:
        return [os.path.join(game_dir, a if a.endswith(".arc") else a + ".arc") for a in arcs]
    out = []
    for pat in patrones:
        for p in sorted(glob.glob(os.path.join(game_dir, pat))):
            if p not in out:
                out.append(p)
    return out


def scenarios(game_dir, arcs=None, patrones=DATA_ARCS):
    """Genera (nombre_arc, nombre_script, bytes) de los escenarios de los .arc del juego."""
    for p in arc_paths(game_dir, arcs, patrones):
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
                        espanol=es, estado=st, nota="", pos=r.pos, hash=hojas.jp_hash(r.raw)))
    return alineacion.marcar_dudosas(out)


def textos(game_dir, old=None, arcs=None, patrones=DATA_ARCS):
    """Genera (nombre_arc, nombre_script, filas) para cada escenario (ver Motor.textos)."""
    olds = load_old(old) if old else {}
    for arc, name, data in scenarios(game_dir, arcs, patrones):
        yield arc, name, script_rows(name, data, olds.get(name))

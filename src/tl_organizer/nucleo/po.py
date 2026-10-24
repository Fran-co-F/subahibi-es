# SPDX-License-Identifier: GPL-3.0-or-later
"""Intercambio con herramientas de traducción (Poedit, OmegaT, Weblate, Lokalize…) en formato PO de gettext.

Exportar: un .po por grupo, generado desde la traducción (almacen.py).  Cada fila es una entrada:
    msgctxt = clave          msgid = original          msgstr = traducción
    #. tipo, estado y base (la huella de la fila al exportar)       # nota (comentario de quien traduce: se puede editar)
    estado «revisar» = marca «fuzzy» (dudosa)
Importar: lo que cambió vuelve a la traducción con la fusión a tres bandas de Almacen.aplicar() (si la fila también cambió
en traduccion/ desde que se exportó, es un conflicto y no se pisa).  El estado queda:
    «revisar» si la entrada está marcada fuzzy; si no, se conserva «traducido»/«del parche» cuando la traducción no cambió,
    y pasa a «traducido» cuando cambió.  Una entrada sin traducción no cambia nada (no borra lo que ya había).
    Si el original de la entrada no coincide con el del proyecto (otra versión del juego), la entrada se rechaza.
`msgfmt -c` (y Poedit al guardar) avisa cuando el original y la traducción no empiezan o terminan igual con un salto de
línea: son las mismas filas que `tl-organizer revisar` lista como «saltos».
Necesita la biblioteca polib (pip install ".[po]").
"""
import datetime
import glob
import os
import re

from .almacen import huella

_COMENTARIO = re.compile(r"estado: (?P<estado>[^;\n]*)(?:.*?base: (?P<base>\w+))?", re.S)


def _polib():
    try:
        import polib
    except ImportError:
        raise SystemExit("falta la biblioteca polib: pip install \"polib>=1.2\" (o pip install -e \".[po]\")")
    return polib


def exportar(almacen, destino, proyecto="", estados=None):
    """Un .po por grupo.  estados: solo las filas con esos estados (por defecto, todas).
    -> {"archivos": n, "entradas": n, "omitidas": n}"""
    polib = _polib()
    os.makedirs(destino, exist_ok=True)
    rep = {"archivos": 0, "entradas": 0, "omitidas": 0}
    fecha = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M%z")
    for grupo, escenarios in almacen.leer().items():
        po = polib.POFile(wrapwidth=0)
        po.metadata = {
            "Project-Id-Version": proyecto or grupo,
            "PO-Revision-Date": fecha,
            "Last-Translator": "",
            "Language-Team": "",
            "Language": almacen.idiomas[1],
            "X-Source-Language": almacen.idiomas[0],
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
        }
        for rows in escenarios.values():
            for r in rows:
                if not r["original"] or (estados and r["estado"] not in estados):
                    rep["omitidas"] += 1           # un msgid vacío está reservado para la cabecera del PO
                    continue
                e = polib.POEntry(msgctxt=r["clave"], msgid=r["original"], msgstr=r["traduccion"],
                                  comment=f"tipo: {r['tipo']}; estado: {r['estado']}; base: {huella(r)}", tcomment=r["nota"])
                if r["estado"] == "revisar":
                    e.flags.append("fuzzy")
                po.append(e)
                rep["entradas"] += 1
        po.save(os.path.join(destino, grupo + ".po"))
        rep["archivos"] += 1
    return rep


def _estado(actual, nueva):
    """Estado final de una fila importada (ver la explicación del módulo)."""
    if nueva["estado"] == "revisar":
        return "revisar"
    if nueva["traduccion"] == actual["traduccion"] and actual["estado"] in ("traducido", "del parche"):
        return actual["estado"]
    return "traducido"


def importar(paths, almacen):
    """Vuelca en la traducción lo cambiado en los .po (archivos o carpetas).  -> informe de Almacen.aplicar()."""
    polib = _polib()
    files = []
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, "*.po"))) if os.path.isdir(p) else [p]
    cambios = {}
    for f in files:
        for e in polib.pofile(f, wrapwidth=0):
            if not e.msgctxt or e.obsolete or not e.msgstr:
                continue                                    # sin traducción: no borra nada
            m = _COMENTARIO.search(e.comment or "")
            estado_exp, base = (m.group("estado").strip(), m.group("base")) if m else (None, None)
            fuzzy = "fuzzy" in e.flags
            nota = e.tcomment or ""
            if base and estado_exp is not None and fuzzy == (estado_exp == "revisar") and \
                    huella({"traduccion": e.msgstr, "estado": estado_exp, "nota": nota}) == base:
                continue                                    # la entrada no se tocó desde que se exportó
            fila = {"original": e.msgid, "traduccion": e.msgstr, "estado": "revisar" if fuzzy else "traducido", "nota": nota}
            cambios[e.msgctxt] = (fila, base)
    return almacen.aplicar(cambios, conservar_estado=_estado)

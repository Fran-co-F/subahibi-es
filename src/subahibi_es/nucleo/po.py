# SPDX-License-Identifier: GPL-3.0-or-later
"""Intercambio con herramientas de traducción (Poedit, OmegaT, Weblate, Lokalize…) en formato PO de gettext.

Exportar: un .po por hoja XLSX.  Cada fila es una entrada:
    msgctxt = clave          msgid = original          msgstr = traducción
    #. tipo y estado (informativos)       # nota (comentario de quien traduce: se puede editar)
    estado «revisar» = marca «fuzzy» (dudosa)
Importar: la traducción y la nota vuelven a las hojas (con una copia .bak de cada hoja la primera vez).  El estado queda:
    «revisar» si la entrada está marcada fuzzy; si no, se conserva «traducido»/«del parche» cuando la traducción no cambió,
    y pasa a «traducido» cuando cambió.  Una entrada sin traducción no cambia nada (no borra lo que ya había en la hoja).
    Si el original de la entrada no coincide con el de la hoja (otra versión del juego), la entrada se rechaza.
`msgfmt -c` (y Poedit al guardar) avisa cuando el original y la traducción no empiezan o terminan igual con un salto de
línea: son las mismas filas que `subahibi-es revisar` lista como «saltos».
Necesita la biblioteca polib (pip install ".[po]").
"""
import datetime
import glob
import os
import shutil

from . import hojas


def _polib():
    try:
        import polib
    except ImportError:
        raise SystemExit("falta la biblioteca polib: pip install \"polib>=1.2\" (o pip install -e \".[po]\")")
    return polib


def _comentario(fila):
    return f"tipo: {fila.get('tipo', '')}; estado: {fila.get('estado', '')}"


def exportar(hojas_dir, destino, idiomas=hojas.IDIOMAS, proyecto="", estados=None):
    """Un .po por cada XLSX de hojas_dir.  estados: solo las filas con esos estados (por defecto, todas).
    -> {"archivos": n, "entradas": n, "omitidas": n}"""
    polib = _polib()
    os.makedirs(destino, exist_ok=True)
    rep = {"archivos": 0, "entradas": 0, "omitidas": 0}
    fecha = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M%z")
    for h in sorted(glob.glob(os.path.join(hojas_dir, "*.xlsx"))):
        po = polib.POFile(wrapwidth=0)
        po.metadata = {
            "Project-Id-Version": proyecto or os.path.basename(h),
            "PO-Revision-Date": fecha,
            "Last-Translator": "",
            "Language-Team": "",
            "Language": idiomas[1],
            "X-Source-Language": idiomas[0],
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
        }
        for rows in hojas.read_xlsx(h).values():
            for r in rows:
                if not r["original"] or (estados and r["estado"] not in estados):
                    rep["omitidas"] += 1           # un msgid vacío está reservado para la cabecera del PO
                    continue
                e = polib.POEntry(msgctxt=r["clave"], msgid=r["original"], msgstr=r["traduccion"].replace("\r", ""),
                                  comment=_comentario(r), tcomment=r["nota"])
                if r["estado"] == "revisar":
                    e.flags.append("fuzzy")
                po.append(e)
                rep["entradas"] += 1
        po.save(os.path.join(destino, os.path.splitext(os.path.basename(h))[0] + ".po"))
        rep["archivos"] += 1
    return rep


def _leer(paths):
    """{clave: entrada} de los .po indicados (archivos o carpetas)."""
    polib = _polib()
    files = []
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, "*.po"))) if os.path.isdir(p) else [p]
    out = {}
    for f in files:
        for e in polib.pofile(f, wrapwidth=0):
            if e.msgctxt and not e.obsolete:
                out[e.msgctxt] = e
    return out


def importar(paths, hojas_dir, idiomas=hojas.IDIOMAS):
    """Vuelca en las hojas lo traducido en los .po.  -> {"actualizadas", "sin_cambios", "desconocidas", "errores": [(clave, motivo)]}"""
    entradas = _leer(paths)
    rep = {"actualizadas": 0, "sin_cambios": 0, "desconocidas": 0, "errores": []}
    vistas = set()
    for h in sorted(glob.glob(os.path.join(hojas_dir, "*.xlsx"))):
        sheets = hojas.read_xlsx(h)
        cambio = False
        for rows in sheets.values():
            for r in rows:
                e = entradas.get(r["clave"])
                if e is None:
                    continue
                vistas.add(r["clave"])
                if e.msgid != r["original"]:
                    rep["errores"].append((r["clave"], "el original del .po no coincide con el de la hoja (¿otra versión del juego?)"))
                    continue
                nueva, nota = e.msgstr, e.tcomment or ""
                if not nueva:
                    rep["sin_cambios"] += 1
                    continue
                if "fuzzy" in e.flags:
                    estado = "revisar"
                elif nueva == r["traduccion"] and r["estado"] in ("traducido", "del parche"):
                    estado = r["estado"]
                else:
                    estado = "traducido"
                if (nueva, estado, nota) == (r["traduccion"], r["estado"], r["nota"]):
                    rep["sin_cambios"] += 1
                    continue
                r.update(traduccion=nueva, estado=estado, nota=nota)
                rep["actualizadas"] += 1
                cambio = True
        if cambio:
            if not os.path.exists(h + ".bak"):
                shutil.copy2(h, h + ".bak")
            hojas.write_xlsx(h, sheets, idiomas)
    rep["desconocidas"] = len(set(entradas) - vistas)
    return rep

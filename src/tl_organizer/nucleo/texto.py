# SPDX-License-Identifier: GPL-3.0-or-later
"""Texto: escribir en hojas las filas que da el motor y leerlas de vuelta (el formato de las hojas está en hojas.py)."""
import os

from . import hojas


def exportar(fuente, out_dir, tsv=False, xlsx=True, idiomas=hojas.IDIOMAS):
    """fuente: iterable de (grupo, escenario, filas), lo que genera Motor.textos().
    Escribe un XLSX por grupo (una hoja por escenario) y, con tsv=True, además un TSV por escenario en out_dir/tsv.
    Los escenarios sin filas no tienen hoja, y un grupo sin hojas no tiene XLSX."""
    os.makedirs(out_dir, exist_ok=True)
    by_grupo, total, prefilled, sin_texto = {}, 0, 0, []
    for grupo, name, rows in fuente:
        if not rows:                      # guiones de configuración o de finales: no hay nada que traducir
            sin_texto.append(name)
            continue
        by_grupo.setdefault(grupo, {})[hojas.safe_name(name)] = rows
        total += len(rows)
        prefilled += sum(1 for r in rows if r["estado"] != "sin traducir")
        if tsv:
            os.makedirs(os.path.join(out_dir, "tsv"), exist_ok=True)
            hojas.write_tsv(os.path.join(out_dir, "tsv", hojas.safe_name(name) + ".tsv"), rows, idiomas)
    if xlsx:
        for grupo, sheets in by_grupo.items():
            hojas.write_xlsx(os.path.join(out_dir, grupo + ".xlsx"), sheets, idiomas)
    return dict(scripts=sum(len(v) for v in by_grupo.values()), arcs=len(by_grupo), filas=total, precargadas=prefilled,
                sin_texto=sin_texto)


def agrupar(fuente):
    """fuente: iterable de (grupo, escenario, filas) (Motor.textos()) -> ({grupo: {escenario: filas}}, informe).
    Los escenarios sin filas se omiten (y se informan en «sin_texto»)."""
    datos, total, prefilled, sin_texto = {}, 0, 0, []
    for grupo, name, rows in fuente:
        if not rows:
            sin_texto.append(name)
            continue
        datos.setdefault(grupo, {})[name] = rows
        total += len(rows)
        prefilled += sum(1 for r in rows if r["estado"] != "sin traducir")
    return datos, dict(scripts=sum(len(v) for v in datos.values()), arcs=len(datos), filas=total, precargadas=prefilled,
                       sin_texto=sin_texto)


def recolectar(paths):
    """{escenario: [filas]} a partir de archivos .xlsx / .tsv o carpetas con ellos (y su subcarpeta tsv/)."""
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
        sheets = hojas.read_xlsx(f) if f.lower().endswith(".xlsx") else {os.path.basename(f): hojas.read_tsv(f)}
        for rows in sheets.values():
            for r in rows:
                script = r["clave"].rsplit(":", 1)[0]
                out.setdefault(script, {})[r["clave"]] = r      # la última gana si una fila está repetida
    return {k: list(v.values()) for k, v in out.items()}

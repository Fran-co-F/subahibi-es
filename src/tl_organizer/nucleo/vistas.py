# SPDX-License-Identifier: GPL-3.0-or-later
"""Las hojas XLSX como vistas de la traducción (la fuente de verdad está en almacen.py).

generar() escribe un XLSX por grupo con una hoja por escenario y la columna oculta «base» (la huella de cada fila al
generarla).  importar() devuelve al almacén lo editado en las hojas, con la fusión a tres bandas de Almacen.aplicar().

Para no leer las 11 hojas en cada comando, <hojas>/.vistas.json recuerda la firma (fecha y tamaño) de cada hoja y de los
TSV de su grupo cuando se generó o se trajo: una hoja que nadie tocó no se lee, y si lo que cambió fue traduccion/
(git pull, wrap…) se informa como desactualizada para regenerarla.
"""
import glob
import hashlib
import json
import os

from . import hojas
from .almacen import huella

ESTADO = ".vistas.json"


def _firma(path):
    st = os.stat(path)
    return [st.st_mtime_ns, st.st_size]


def _firma_grupo(almacen, grupo):
    d = os.path.join(almacen.carpeta, grupo)
    partes = sorted((f, *_firma(os.path.join(d, f))) for f in os.listdir(d)) if os.path.isdir(d) else []
    return hashlib.sha1(repr(partes).encode()).hexdigest()[:12]


def _leer_estado(carpeta):
    try:
        with open(os.path.join(carpeta, ESTADO), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_estado(carpeta, estado):
    with open(os.path.join(carpeta, ESTADO), "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=0, sort_keys=True)


def generar(almacen, carpeta, grupos=None, log=print):
    """Escribe <carpeta>/<grupo>.xlsx para cada grupo (o solo los de 'grupos').  -> grupos que no se pudieron escribir
    (por ejemplo, una hoja abierta en Excel en Windows)."""
    os.makedirs(carpeta, exist_ok=True)
    estado = _leer_estado(carpeta)
    fallidos = []
    for grupo, escenarios in almacen.leer().items():
        if grupos is not None and grupo not in grupos:
            continue
        path = os.path.join(carpeta, grupo + ".xlsx")
        try:
            hojas.write_xlsx(path, {hojas.safe_name(e): rows for e, rows in escenarios.items()}, almacen.idiomas, huella)
        except PermissionError:
            fallidos.append(grupo)
            log(f"aviso: no pude actualizar {path} (¿está abierta? cerrala y corré «tl-organizer text hojas»)")
            continue
        estado[grupo] = {"xlsx": _firma(path), "tsv": _firma_grupo(almacen, grupo)}
    _guardar_estado(carpeta, estado)
    return fallidos


def importar(almacen, carpeta):
    """Lo editado en <carpeta>/*.xlsx vuelve al almacén.  -> el informe de Almacen.aplicar()."""
    estado = _leer_estado(carpeta)
    cambios, leidas, desactualizadas = {}, {}, set()
    for path in sorted(glob.glob(os.path.join(carpeta, "*.xlsx"))):
        if os.path.basename(path).startswith("~$"):
            continue                                   # archivo de bloqueo de Excel
        grupo = os.path.splitext(os.path.basename(path))[0]
        anterior = estado.get(grupo, {})
        if anterior.get("xlsx") == _firma(path):       # nadie tocó la hoja desde que se generó o se trajo
            if anterior.get("tsv") != _firma_grupo(almacen, grupo):
                desactualizadas.add(grupo)
            continue
        leidas[grupo] = path
        for rows in hojas.read_xlsx(path).values():
            for r in rows:
                cambios[r["clave"]] = (r, r.get("base") or None)
    rep = (almacen.aplicar(cambios) if cambios else
           {"actualizadas": 0, "conflictos": [], "errores": [], "desconocidas": 0, "grupos": set(), "desactualizadas": set()})
    rep["desactualizadas"] |= desactualizadas
    # las hojas leídas que quedaron al día (sin conflictos ni cambios pendientes) no se vuelven a leer
    con_conflicto = {k.rsplit(":", 1)[0] for k, _ in rep["conflictos"]}
    escenarios = {g: set(e) for g, e in almacen.escenarios().items()}
    for grupo, path in leidas.items():
        if grupo in escenarios and not (escenarios[grupo] & con_conflicto) and grupo not in rep["grupos"] | rep["desactualizadas"]:
            estado[grupo] = {"xlsx": _firma(path), "tsv": _firma_grupo(almacen, grupo)}
    if leidas:
        _guardar_estado(carpeta, estado)
    return rep

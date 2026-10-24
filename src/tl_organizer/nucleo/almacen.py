# SPDX-License-Identifier: GPL-3.0-or-later
"""Dónde vive la traducción: un archivo TSV por escenario, en <trabajo>/traduccion/<grupo>/<escenario>.tsv.

Es la fuente de verdad del proyecto.  Texto plano, una fila por línea (los saltos de línea dentro de un texto se escriben \\n),
en el orden del juego: git muestra exactamente qué fila cambió y dos personas pueden fusionar su trabajo.
traduccion/indice.tsv guarda el orden de los grupos y escenarios y el nombre real de cada escenario.

Las hojas XLSX (hojas/) y los .po (po/) son vistas que se generan desde acá (vistas.py, po.py).  Cada fila de una vista lleva la
«huella» de cómo estaba la fila al generarla; al volver, aplicar() hace una fusión a tres bandas por fila:
    la vista no cambió la fila                      -> nada
    la vista la cambió y acá sigue como estaba      -> se aplica
    las dos la cambiaron (por ejemplo, tras un git pull) y quedaron distintas -> conflicto: no se pisa, se informa
"""
import hashlib
import os

from . import hojas

EDITABLES = ("traduccion", "estado", "nota")       # lo que se edita en una vista; lo demás sale del juego
INDICE = "indice.tsv"


def huella(fila):
    """Resumen corto de lo editable de una fila (para saber si cambió desde que se generó una vista)."""
    raw = "\x1f".join((fila.get(k) or "").replace("\r", "") for k in EDITABLES)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


class Almacen:
    def __init__(self, carpeta, idiomas=hojas.IDIOMAS):
        self.carpeta = carpeta
        self.idiomas = idiomas

    def existe(self):
        return os.path.isfile(os.path.join(self.carpeta, INDICE))

    def _indice(self):
        """[(grupo, escenario, archivo)] en el orden del juego."""
        out = []
        with open(os.path.join(self.carpeta, INDICE), encoding="utf-8") as f:
            for ln in f.read().split("\n")[1:]:
                if ln:
                    grupo, esc, arch = ln.split("\t")
                    out.append((grupo, esc, arch))
        return out

    def escenarios(self):
        """{grupo: [escenarios]} (solo el índice, sin leer las filas)."""
        out = {}
        for grupo, esc, _arch in self._indice():
            out.setdefault(grupo, []).append(esc)
        return out

    def leer(self):
        """{grupo: {escenario: [filas]}} en el orden del juego."""
        out = {}
        for grupo, esc, arch in self._indice():
            out.setdefault(grupo, {})[esc] = hojas.read_tsv(os.path.join(self.carpeta, grupo, arch))
        return out

    def filas_por_escenario(self):
        return {esc: rows for g in self.leer().values() for esc, rows in g.items()}

    def escribir(self, datos):
        """Escribe todo: datos = {grupo: {escenario: [filas]}} (reemplaza lo que hubiera)."""
        import shutil
        if os.path.isdir(self.carpeta):
            shutil.rmtree(self.carpeta)
        os.makedirs(self.carpeta)
        indice = []
        for grupo, escenarios in datos.items():
            os.makedirs(os.path.join(self.carpeta, grupo), exist_ok=True)
            for esc, rows in escenarios.items():
                arch = hojas.safe_name(esc) + ".tsv"
                hojas.write_tsv(os.path.join(self.carpeta, grupo, arch), rows, self.idiomas)
                indice.append((grupo, esc, arch))
        with open(os.path.join(self.carpeta, INDICE), "w", encoding="utf-8", newline="\n") as f:
            f.write("grupo\tescenario\tarchivo\n")
            for t in indice:
                f.write("\t".join(t) + "\n")

    def guardar(self, grupo, escenario, filas):
        """Reescribe un escenario que ya existe."""
        for g, esc, arch in self._indice():
            if (g, esc) == (grupo, escenario):
                hojas.write_tsv(os.path.join(self.carpeta, g, arch), filas, self.idiomas)
                return
        raise KeyError(f"{grupo}/{escenario} no está en el índice")

    def aplicar(self, cambios, conservar_estado=None):
        """Fusión a tres bandas.  cambios: {clave: (fila_de_la_vista, huella_base | None)}; sin base, la vista manda.
        conservar_estado(fila_actual, fila_vista) -> estado, opcional, para decidir el estado final (lo usa po.py).
        -> {"actualizadas": n, "conflictos": [(clave, detalle)], "errores": [(clave, motivo)], "desconocidas": n,
            "grupos": {grupos modificados}, "desactualizadas": {grupos cuya vista ya no coincide con lo de acá}}"""
        rep = {"actualizadas": 0, "conflictos": [], "errores": [], "desconocidas": 0, "grupos": set(), "desactualizadas": set()}
        vistas = set()
        datos = self.leer()
        for grupo, escenarios in datos.items():
            for esc, rows in escenarios.items():
                cambio = False
                for r in rows:
                    c = cambios.get(r["clave"])
                    if c is None:
                        continue
                    vistas.add(r["clave"])
                    v, base = c
                    if v.get("original") is not None and v["original"].replace("\r", "") != r["original"]:
                        rep["errores"].append((r["clave"], "el original no coincide con el del proyecto (¿otra versión del juego?)"))
                        continue
                    nueva = {k: (v.get(k) or "").replace("\r", "") for k in EDITABLES}
                    if conservar_estado:
                        nueva["estado"] = conservar_estado(r, nueva)
                    hv, hs = huella(nueva), huella(r)
                    if hv == hs or (base is not None and hv == base):
                        if base is not None and hs != base:
                            rep["desactualizadas"].add(grupo)  # cambió acá (git pull, wrap…): la vista muestra lo viejo
                        continue                               # igual a lo actual, o la vista no la tocó
                    if base is not None and hs != base:
                        rep["conflictos"].append((r["clave"], f"cambió en la vista y también en traduccion/ (vista: «{nueva['traduccion'][:40]}», "
                                                               f"actual: «{r['traduccion'][:40]}»)"))
                        continue
                    r.update(nueva)
                    rep["actualizadas"] += 1
                    cambio = True
                if cambio:
                    self.guardar(grupo, esc, rows)
                    rep["grupos"].add(grupo)
        rep["desconocidas"] = len(set(cambios) - vistas)
        return rep

# SPDX-License-Identifier: GPL-3.0-or-later
"""Motor Ethornell / BGI (Buriko General Interpreter).

Formatos: arc.py (BURIKO ARC20), dsc.py (DSC FORMAT 1.00), image.py (imágenes crudas), scn.py (escenarios compilados),
exe_patch.py (parche del exe).  Opciones del perfil, sección [bgi]:

    fuente = "NOMBRE"                fuente que usa el juego parcheado (si falta, no se cambia la fuente)
    [[bgi.ejecutables]]              versiones conocidas del exe con las direcciones del parche (ver exe_patch.py)

Valores por defecto si el perfil no los indica: [texto] archivos = ["data0*.arc"], [imagenes] archivos = ["sysgrp.arc"].
"""
import os
import re

from ..base import EJECUTABLE, IMAGENES, PARCHE_VIEJO, TEXTO, ESTADOS_LISTOS, Motor, MotorError
from . import exe_patch

DATA_ARCS = ("data0*.arc",)
UI_ARCS = ("sysgrp.arc",)
ETIQUETA = re.compile(r"<[^<>\n]*>")          # etiquetas en el texto, como el furigana <r lectura>…</r>


class MotorBGI(Motor):
    nombre = "bgi"
    descripcion = "Ethornell / BGI (Buriko General Interpreter)"
    capacidades = frozenset({TEXTO, IMAGENES, EJECUTABLE, PARCHE_VIEJO})
    carpetas_sueltas = ("Script", "Graphic", "Sound", "Voice")     # el motor prioriza estos archivos sueltos sobre los .arc

    def validar_perfil(self):
        try:
            self.builds = {}
            for d in self.opciones.get("ejecutables", []):
                b = exe_patch.desde_perfil(d)
                self.builds[b["sha256"]] = b
        except exe_patch.PatchError as e:
            raise MotorError(f"{self.perfil.ruta or self.perfil.id}: {e}")
        fuente = self.opciones.get("fuente")
        if fuente is not None:
            try:
                exe_patch.font_slot(fuente)
            except exe_patch.PatchError as e:
                raise MotorError(f"{self.perfil.ruta or self.perfil.id}: [bgi] {e}")

    @property
    def fuente(self):
        return self.opciones.get("fuente")

    @property
    def data_arcs(self):
        return tuple(self.perfil.lista("texto", "archivos", DATA_ARCS))

    @property
    def ui_arcs(self):
        return tuple(self.perfil.lista("imagenes", "archivos", UI_ARCS))

    # ------------------------------------------------------------ ejecutable
    def identificar_ejecutable(self, datos):
        b = exe_patch.identify(datos, self.builds)[1]
        return b["version"] if b else None

    def versiones_conocidas(self):
        return [b["version"] for b in self.builds.values()]

    # ------------------------------------------------------------ exportar
    def exportar_imagenes(self, juego, destino):
        from .images import export
        from .text.export import arc_paths
        total, skipped = 0, []
        for p in arc_paths(juego, patrones=self.ui_arcs):
            n, s = export.export_arc(p, destino)
            total += n
            skipped += s
        return total, skipped

    def textos(self, juego, parche_viejo=None, archivos=None):
        from .text import export
        return export.textos(juego, parche_viejo, archivos, self.data_arcs)

    # ------------------------------------------------------------ armar
    def construir(self, juego, salida, filas=None, imagenes=None, estados=ESTADOS_LISTOS, opciones=None,
                  parche_viejo=None, ejecutable=None, log=print):
        from . import build
        op = opciones or {}
        return build.build(juego, salida, parche_viejo, filas, imagenes, estados, voces=op.get("voces", True),
                           utf8=op.get("utf8", True), font_name=op.get("fuente") or self.fuente, exe=ejecutable,
                           exe_name=self.perfil.ejecutable, builds=self.builds,
                           data_arcs=self.data_arcs, ui_arcs=self.ui_arcs, log=log)

    def releer(self, juego, salida):
        """Los textos que mostraría el juego con salida/Script/CVTD encima (los escenarios sueltos tapan los del .arc)."""
        from . import scn
        from .text import accents, export, extract

        def texto(raw):
            try:
                return raw.decode("utf-8")              # modo UTF-8 (también vale para el japonés convertido)
            except UnicodeDecodeError:
                return accents.decode(raw)              # modo katakana o escenario sin tocar (Shift-JIS)
        for arc, name, jp in export.scenarios(juego, patrones=self.data_arcs):
            filas = export.script_rows(name, jp)
            suelto = os.path.join(salida, "Script", "CVTD", name)
            if os.path.exists(suelto):
                with open(suelto, "rb") as f:
                    nuevo = scn.parse(f.read(), strings_start=scn.parse(jp).strings_start)
                por_pos = {r.pos: r.raw for r in extract.rows(nuevo, all_store=True)}
                for f in filas:
                    f["original"] = texto(por_pos[f["pos"]])
            yield arc, name, filas

    # ------------------------------------------------------------ control de calidad
    def marcadores(self, texto):
        return ETIQUETA.findall(texto)

    def caracteres_invalidos(self, texto, opciones=None):
        """En modo UTF-8 (el de siempre) solo el carácter nulo; en modo katakana, todo lo que no entra en Shift-JIS."""
        malos = ["\0"] if "\0" in texto else []
        if not (opciones or {}).get("utf8", True):
            from .text import accents
            malos += accents.unencodable(texto)
        return malos

    # ------------------------------------------------------------ línea de comandos
    @classmethod
    def argumentos_build(cls, p):
        p.add_argument("--sin-voz", action="store_true", help="no incluir Voice/CVTD del parche viejo")
        p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
        p.add_argument("--fuente", metavar="NOMBRE", help="nombre de la fuente del juego (ASCII, hasta 15 caracteres; debe estar "
                       "instalada); por defecto, la del perfil del juego")

    @classmethod
    def opciones_build(cls, a):
        return dict(voces=not a.sin_voz, utf8=not a.katakana, fuente=a.fuente)

    @classmethod
    def registrar_comandos(cls, sub, grupos):
        from . import cli
        cli.registrar(sub, grupos)

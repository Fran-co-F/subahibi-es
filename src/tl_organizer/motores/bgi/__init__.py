# SPDX-License-Identifier: GPL-3.0-or-later
"""Motor Ethornell / BGI (Buriko General Interpreter).

Formatos: arc.py (BURIKO ARC20), dsc.py (DSC FORMAT 1.00), image.py (imágenes crudas), scn.py (escenarios compilados),
exe_patch.py (parche del exe).  Opciones del perfil, sección [bgi]:

    fuente = "NOMBRE"                fuente que usa el juego parcheado (si falta, no se cambia la fuente)
    [[bgi.ejecutables]]              versiones conocidas del exe con las direcciones del parche (ver exe_patch.py)

    modo = "utf8" | "katakana"       cómo se guarda el texto: UTF-8 (motor 1.653 o posterior, con Text_SetEncoding) o
                                     Shift-JIS con los acentos como katakana de ancho medio (necesita una fuente que los
                                     dibuje como letras, como SubaHibi07Inq).  Por defecto, utf8.
    proporcional = "exe" | "programas" | "no"
                                     texto proporcional con un desvío en el exe ([[bgi.ejecutables]] con «hook») o
                                     parcheando los programas de sistema (sysprg.py; versiones viejas).  Por defecto, exe.
    programas = ["sysprg.arc"]       dónde están los programas de sistema
    sueltos = "carpetas" | "raiz"    dónde busca el motor los archivos sueltos que tapan a los .arc: <Tipo>/CVTD
                                     (lo habitual) o la carpeta del juego (ver sueltos.py).  Por defecto, carpetas.

Valores por defecto si el perfil no los indica: [texto] archivos = ["data0*.arc"], [imagenes] archivos = ["sysgrp.arc"].
"""
import os
import re

from ..base import EJECUTABLE, IMAGENES, PARCHE_VIEJO, TEXTO, ESTADOS_LISTOS, Motor, MotorError
from . import exe_patch, sueltos

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
        if self.opciones.get("modo", "utf8") not in ("utf8", "katakana"):
            raise MotorError(f"{self.perfil.ruta or self.perfil.id}: [bgi] modo tiene que ser «utf8» o «katakana»")
        if self.opciones.get("proporcional", "exe") not in ("exe", "programas", "no"):
            raise MotorError(f"{self.perfil.ruta or self.perfil.id}: [bgi] proporcional tiene que ser «exe», «programas» o «no»")
        if self.sueltos not in sueltos.MODOS:
            raise MotorError(f"{self.perfil.ruta or self.perfil.id}: [bgi] sueltos tiene que ser «carpetas» o «raiz»")
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
    def sueltos(self):
        return self.opciones.get("sueltos", sueltos.CARPETAS)

    @property
    def utf8(self):
        """Modo por defecto del perfil (las opciones de build pueden cambiarlo)."""
        return self.opciones.get("modo", "utf8") == "utf8"

    def _utf8(self, opciones):
        v = (opciones or {}).get("utf8")
        return self.utf8 if v is None else v

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

    def entradas(self, juego):
        from .arc import Arc
        nombres = set()
        for p in sorted(os.listdir(juego)):
            if p.lower().endswith(".arc"):
                try:
                    nombres.update(Arc(os.path.join(juego, p)).names())
                except (OSError, ValueError):
                    pass
        return nombres

    # ------------------------------------------------------------ armar
    def construir(self, juego, salida, filas=None, imagenes=None, estados=ESTADOS_LISTOS, opciones=None,
                  parche_viejo=None, ejecutable=None, log=print):
        from . import build
        op = opciones or {}
        return build.build(juego, salida, parche_viejo, filas, imagenes, estados, voces=op.get("voces", True),
                           utf8=self._utf8(op), font_name=op.get("fuente") or self.fuente, exe=ejecutable,
                           exe_name=self.perfil.ejecutable, builds=self.builds,
                           data_arcs=self.data_arcs, ui_arcs=self.ui_arcs,
                           proporcional=self.opciones.get("proporcional", "exe"),
                           sys_arcs=tuple(self.opciones.get("programas", ["sysprg.arc"])), sueltos=self.sueltos, log=log)

    def releer(self, juego, salida):
        """Los textos que mostraría el juego con los escenarios sueltos de 'salida' encima (tapan los del .arc)."""
        from . import scn
        from .text import accents, export, extract

        def texto(raw):
            try:
                return raw.decode("utf-8")              # modo UTF-8 (también vale para el japonés convertido)
            except UnicodeDecodeError:
                return accents.decode(raw)              # modo katakana o escenario sin tocar (Shift-JIS)
        for arc, name, jp in export.scenarios(juego, patrones=self.data_arcs):
            filas = export.script_rows(name, jp)
            suelto = os.path.join(sueltos.carpeta(salida, "Script", self.sueltos), name)
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
        if not self._utf8(opciones):
            from .text import accents
            malos += accents.unencodable(texto)
        return malos

    # ------------------------------------------------------------ línea de comandos
    @classmethod
    def argumentos_build(cls, p):
        p.add_argument("--sin-voz", action="store_true", help="no incluir Voice/CVTD del parche viejo")
        p.add_argument("--katakana", dest="utf8", action="store_const", const=False,
                       help="sin UTF-8: acentos como katakana de ancho medio (por defecto, el modo del perfil)")
        p.add_argument("--utf8", dest="utf8", action="store_const", const=True, help="forzar el modo UTF-8")
        p.add_argument("--fuente", metavar="NOMBRE", help="nombre de la fuente del juego (ASCII, hasta 15 caracteres; debe estar "
                       "instalada); por defecto, la del perfil del juego")

    @classmethod
    def opciones_build(cls, a):
        return dict(voces=not a.sin_voz, utf8=a.utf8, fuente=a.fuente)

    @classmethod
    def registrar_comandos(cls, sub, grupos):
        from . import cli
        cli.registrar(sub, grupos)

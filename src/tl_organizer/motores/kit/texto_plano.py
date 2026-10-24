# SPDX-License-Identifier: GPL-3.0-or-later
"""MotorTextoPlano: base para motores cuyos scripts son archivos de texto (KAG .ks, NScripter 0.txt, Ren'Py .rpy…).

Una subclase dice, en Python, dónde están los scripts y cómo se reconoce el texto; la base hace el resto: extraer las
filas, reinyectar la traducción en el mismo lugar (reemplazando solo el texto reconocido), escribir los scripts
traducidos como archivos sueltos y volver a leerlos (releer, para la prueba de contrato).

    class MotorMiFormato(MotorTextoPlano):
        nombre = "miformato"
        archivos = ("scenario/*.txt",)
        patrones = {                                   # tipo -> expresión regular (re.M) con un grupo «texto»
            "nombre":  r"^【(?P<texto>[^】]+)】",
            "mensaje": r"^(?:【[^】]+】)?「(?P<texto>[^」]*)」",
            "opcion":  r"^@choice (?P<texto>.+)$",
        }
        ignorar = r"^\\s*(;|//)"                       # líneas que nunca tienen texto (comentarios…)
        salto_de_linea = "[r]"                         # cómo escribe el formato un salto dentro de un texto

Para casos que no entran en expresiones regulares, sobrescribir segmentos(texto, escenario) -> [(inicio, fin, tipo)].
Para scripts dentro de un archivo empaquetado, sobrescribir contenedor(juego) (ver kit/contenedores.py).
Opciones que el perfil puede cambiar en la sección del motor: codificaciones, codificacion_salida, salto_de_linea, carpeta_salida.
"""
import os
import re

from ...nucleo import hojas
from ..base import ESTADOS_LISTOS, TEXTO, Motor, MotorError
from .codificaciones import CodificacionError, decodificar, no_codificables
from .contenedores import Carpeta, escribir_suelto

OPCIONES_DEL_PERFIL = ("codificaciones", "codificacion_salida", "salto_de_linea", "carpeta_salida")


class MotorTextoPlano(Motor):
    capacidades = frozenset({TEXTO})
    archivos = ("*.txt",)                 # patrones de los scripts dentro del contenedor ([texto] archivos del perfil manda)
    codificaciones = ("utf-8", "cp932")   # en qué orden se prueban al leer (un BOM manda)
    codificacion_salida = None            # None: la misma con la que se leyó cada archivo
    patrones = {}                         # tipo -> expresión regular con un grupo «texto»
    ignorar = None                        # expresión regular: líneas que no tienen texto
    salto_de_linea = None                 # cómo se escribe un salto dentro de un texto; None = el formato no lo admite
    marcador = None                       # expresión regular de los códigos de control dentro del texto (para revisar)
    carpeta_salida = ""                   # dónde van los scripts traducidos dentro de la salida ("" = misma ruta que en el juego)

    def validar_perfil(self):
        for k in OPCIONES_DEL_PERFIL:
            if k in self.opciones:
                setattr(self, k, tuple(self.opciones[k]) if k == "codificaciones" else self.opciones[k])
        try:
            self._patrones = [(tipo, re.compile(rx, re.M)) for tipo, rx in self.patrones.items()]
            self._ignorar = re.compile(self.ignorar) if self.ignorar else None
            self._marcador = re.compile(self.marcador) if self.marcador else None
        except re.error as e:
            raise MotorError(f"motor «{self.nombre}»: expresión regular inválida: {e}")

    # ------------------------------------------------------------ dónde están los scripts
    def contenedor(self, juego):
        return Carpeta(juego)

    def scripts(self, juego):
        """Genera (nombre, bytes) de cada script, en orden."""
        c = self.contenedor(juego)
        for nombre in c.buscar(*self.perfil.lista("texto", "archivos", self.archivos)):
            yield nombre, c.leer(nombre)

    def escenario_de(self, nombre):
        return os.path.splitext(nombre)[0]

    def grupo_de(self, nombre):
        return nombre.split("/")[0] if "/" in nombre else "scripts"

    def ruta_salida(self, nombre):
        return f"{self.carpeta_salida.strip('/')}/{nombre}" if self.carpeta_salida else nombre

    # ------------------------------------------------------------ reconocer el texto
    def segmentos(self, texto, escenario):
        """[(inicio, fin, tipo)] de los textos traducibles, en orden y sin solaparse."""
        encontrados = []
        for orden, (tipo, rx) in enumerate(self._patrones):
            for m in rx.finditer(texto):
                g = "texto" if "texto" in rx.groupindex else 0
                ini, fin = m.span(g)
                if ini < 0 or fin <= ini:
                    continue
                if self._ignorar:
                    fin_linea = texto.find("\n", ini)
                    linea = texto[texto.rfind("\n", 0, ini) + 1:fin_linea if fin_linea >= 0 else len(texto)]
                    if self._ignorar.search(linea):
                        continue
                encontrados.append((ini, orden, fin, tipo))
        out, hasta = [], -1
        for ini, _orden, fin, tipo in sorted(encontrados):
            if ini >= hasta:
                out.append((ini, fin, tipo))
                hasta = fin
        return out

    def desescapar(self, s):
        return s.replace(self.salto_de_linea, "\n") if self.salto_de_linea else s

    def escapar(self, s):
        if "\n" in s:
            if not self.salto_de_linea:
                raise ValueError("este formato no admite saltos de línea dentro de un texto")
            s = s.replace("\n", self.salto_de_linea)
        return s

    def _filas(self, texto, escenario):
        filas = []
        for n, (ini, fin, tipo) in enumerate(self.segmentos(texto, escenario), 1):
            original = self.desescapar(texto[ini:fin])
            filas.append(dict(clave=f"{escenario}:{n:05d}", tipo=tipo, original=original, traduccion="", estado="sin traducir",
                              nota="", pos=ini, hash=hojas.jp_hash(original.encode("utf-8"))))
        return filas

    def textos(self, juego, parche_viejo=None, archivos=None):
        for nombre, datos in self.scripts(juego):
            texto, _cod = decodificar(datos, self.codificaciones)
            yield self.grupo_de(nombre), self.escenario_de(nombre), self._filas(texto, self.escenario_de(nombre))

    # ------------------------------------------------------------ armar
    def construir(self, juego, salida, filas=None, imagenes=None, estados=ESTADOS_LISTOS, opciones=None,
                  parche_viejo=None, ejecutable=None, log=print):
        filas = filas or {}
        rep = dict(scripts=0, cambiadas=0, omitidas=0, errores=[])
        vistos = set()
        for nombre, datos in self.scripts(juego):
            esc = self.escenario_de(nombre)
            vistos.add(esc)
            if esc not in filas:
                continue
            texto, cod = decodificar(datos, self.codificaciones)
            cod_out = self.codificacion_salida or cod
            segs = {ini: (fin, self.desescapar(texto[ini:fin])) for ini, fin, _t in self.segmentos(texto, esc)}
            reemplazos = []
            for r in filas[esc]:
                t = (r.get("traduccion") or "").replace("\r", "")
                if not t:
                    continue
                if r.get("estado") not in estados:
                    rep["omitidas"] += 1
                    continue
                try:
                    ini = int(r["pos"])
                except (KeyError, TypeError, ValueError):
                    rep["errores"].append((r["clave"], "falta 'pos'")); continue
                if ini not in segs:
                    rep["errores"].append((r["clave"], f"no hay texto en la posición {ini}: ¿hoja de otra versión?")); continue
                fin, original = segs[ini]
                if hojas.jp_hash(original.encode("utf-8")) != r.get("hash"):
                    rep["errores"].append((r["clave"], "el original no coincide con el del juego (hash distinto)")); continue
                try:
                    nuevo = self.escapar(t)
                except ValueError as e:
                    rep["errores"].append((r["clave"], str(e))); continue
                malos = no_codificables(nuevo, cod_out)
                if malos:
                    rep["errores"].append((r["clave"], f"caracteres que {cod_out} no tiene: " + " ".join(malos))); continue
                reemplazos.append((ini, fin, nuevo))
            if not reemplazos:
                continue
            for ini, fin, nuevo in sorted(reemplazos, reverse=True):
                texto = texto[:ini] + nuevo + texto[fin:]
            try:
                datos_nuevos = texto.encode(cod_out)
            except UnicodeEncodeError as e:
                rep["errores"].append((esc, f"no se pudo escribir en {cod_out}: {e}")); continue
            escribir_suelto(salida, self.ruta_salida(nombre), datos_nuevos)
            rep["scripts"] += 1
            rep["cambiadas"] += len(reemplazos)
        for esc in sorted(set(filas) - vistos):
            rep["errores"].append((esc, "no existe un script con ese nombre en el juego"))
        return {"texto": rep}

    def releer(self, juego, salida):
        """Como textos(), pero viendo el juego con la salida encima (lo que mostraría el juego con el parche puesto)."""
        for nombre, datos in self.scripts(juego):
            p = os.path.join(salida, *self.ruta_salida(nombre).split("/"))
            if os.path.exists(p):
                with open(p, "rb") as f:
                    datos = f.read()
            try:
                texto, _cod = decodificar(datos, (self.codificacion_salida,) + tuple(self.codificaciones)
                                          if self.codificacion_salida else self.codificaciones)
            except CodificacionError as e:
                raise MotorError(f"{p}: {e}")
            yield self.grupo_de(nombre), self.escenario_de(nombre), self._filas(texto, self.escenario_de(nombre))

    # ------------------------------------------------------------ control de calidad
    def marcadores(self, texto):
        return self._marcador.findall(texto) if self._marcador else []

    def caracteres_invalidos(self, texto, opciones=None):
        malos = ["\n"] if "\n" in texto and not self.salto_de_linea else []
        if self.codificacion_salida:
            malos += no_codificables(texto.replace("\n", ""), self.codificacion_salida)
        return malos

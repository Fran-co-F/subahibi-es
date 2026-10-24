# SPDX-License-Identifier: GPL-3.0-or-later
"""La interfaz entre el núcleo y un motor (ver docs/PLAN.md, sección 1.3).

Un motor es una subclase de `Motor` que entiende los formatos de una familia de juegos.  Se crea con un perfil de juego
(nucleo/perfiles.py) y lee las opciones de su propia sección del perfil (`[bgi]` para el motor «bgi»).  Declara en
`capacidades` lo que sabe hacer; el núcleo pregunta antes de llamar, así que un motor implementa solo los métodos de sus
capacidades:

  texto         textos(), y en construir() aplica las filas traducidas
  imagenes      exportar_imagenes(), y en construir() coloca las imágenes traducidas
  ejecutable    identificar_ejecutable() / versiones_conocidas(): el exe se reconoce, se respalda y se parchea
  parche_viejo  sabe precargar una traducción anterior y reusar sus archivos
"""
import os
import sys

TEXTO = "texto"
IMAGENES = "imagenes"
EJECUTABLE = "ejecutable"
PARCHE_VIEJO = "parche_viejo"

ESTADOS_LISTOS = ("traducido", "del parche")      # lo que `build` aplica por defecto


class MotorError(Exception):
    pass


class Motor:
    nombre = ""                       # el que se escribe en el perfil: motor = "<nombre>"
    descripcion = ""
    capacidades = frozenset()
    carpetas_sueltas = ()             # carpetas que el parche crea dentro del juego (se limpian al desinstalar)

    def __init__(self, perfil):
        self.perfil = perfil
        self.opciones = perfil.seccion(self.nombre)
        self.validar_perfil()

    def validar_perfil(self):
        """Comprueba la sección propia del perfil; lanza MotorError con un mensaje claro si algo está mal."""

    @classmethod
    def carpeta_perfiles(cls):
        """Carpeta con los perfiles de juego incluidos en el motor: juegos/ al lado del módulo que define la clase."""
        return os.path.join(os.path.dirname(sys.modules[cls.__module__].__file__), "juegos")

    # ------------------------------------------------------------ ejecutable
    def identificar_ejecutable(self, datos):
        """Versión conocida del ejecutable del juego (bytes) o None."""
        return None

    def versiones_conocidas(self):
        return []

    # ------------------------------------------------------------ exportar
    def exportar_imagenes(self, juego, destino):
        """Escribe en destino un PNG por imagen de interfaz.  -> (exportadas, [(nombre, motivo_de_omisión)])"""
        raise NotImplementedError

    def textos(self, juego, parche_viejo=None, archivos=None):
        """Genera (grupo, escenario, filas) con las filas de cada escenario (ver nucleo/hojas.py, COLUMNS).
        grupo = el archivo del juego que contiene el escenario (una hoja XLSX por grupo).  La clave de cada fila tiene que
        ser «<escenario>:<número>» y ser estable entre exportaciones: así se reconoce la fila en las vistas y en git."""
        raise NotImplementedError

    # ------------------------------------------------------------ armar
    def construir(self, juego, salida, filas=None, imagenes=None, estados=ESTADOS_LISTOS, opciones=None,
                  parche_viejo=None, ejecutable=None, log=print):
        """Escribe en salida lo que hay que copiar al juego.
        filas: {escenario: [filas]} leídas de las hojas, o None si no hay hojas.  imagenes: carpeta de imágenes traducidas o None.
        opciones: las que devolvió opciones_build().  ejecutable: ruta del ejecutable original.  -> informe (dict)."""
        raise NotImplementedError

    # ------------------------------------------------------------ control de calidad (nucleo/revisar.py)
    def marcadores(self, texto):
        """Códigos de control del motor dentro de un texto (etiquetas, variables…), en orden.  La traducción tiene que
        conservar los mismos que el original; las etiquetas <x>…</x> además tienen que estar balanceadas."""
        return []

    def caracteres_invalidos(self, texto, opciones=None):
        """Caracteres de 'texto' que el juego no puede guardar o mostrar (opciones: las de build)."""
        return []

    def controles(self):
        """Controles de calidad propios del motor: funciones control(fila, ctx) -> [(nivel, código, detalle)]."""
        return []

    # ------------------------------------------------------------ línea de comandos
    @classmethod
    def argumentos_build(cls, parser):
        """Agrega a `build` las opciones propias del motor."""

    @classmethod
    def opciones_build(cls, args):
        """Las opciones de `build` (argparse.Namespace) que le interesan al motor, como dict para construir()."""
        return {}

    @classmethod
    def registrar_comandos(cls, sub, grupos):
        """Agrega los comandos sueltos del motor.  sub: los subcomandos de primer nivel; grupos: {"images": …, "text": …}."""

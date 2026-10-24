# SPDX-License-Identifier: GPL-3.0-or-later
"""Codificaciones de texto de los juegos: detección y tablas de sustitución de caracteres.

decodificar() prueba BOM, UTF-8 y Shift-JIS (o las que se le pasen) y devuelve el texto y la codificación con la que volver
a escribirlo.  Sustitucion sirve a los motores sin un modo Unicode: una fuente especial dibuja ciertos caracteres que la
codificación sí tiene (por ejemplo, katakana de ancho medio en Shift-JIS) como las letras que faltan (á, ñ, ¿…).
"""

BOMS = ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"))
CANDIDATAS = ("utf-8", "cp932")


class CodificacionError(ValueError):
    pass


def decodificar(datos, candidatas=CANDIDATAS):
    """-> (texto, codificación).  Un BOM manda; si no, la primera candidata que decodifica sin errores."""
    for bom, nombre in BOMS:
        if datos.startswith(bom):
            return datos.decode(nombre), nombre
    for nombre in candidatas:
        try:
            return datos.decode(nombre), nombre
        except UnicodeDecodeError:
            continue
    raise CodificacionError("no se pudo decodificar con " + ", ".join(candidatas))


def no_codificables(texto, codificacion):
    """Caracteres de 'texto' que no existen en 'codificacion', sin repetir y en orden de aparición."""
    malos = []
    for ch in texto:
        if ch not in malos:
            try:
                ch.encode(codificacion)
            except UnicodeEncodeError:
                malos.append(ch)
    return malos


def codificar(texto, codificacion):
    """Como str.encode, pero el error dice qué caracteres no entran."""
    try:
        return texto.encode(codificacion)
    except UnicodeEncodeError:
        raise CodificacionError(f"caracteres que {codificacion} no tiene: " + " ".join(no_codificables(texto, codificacion)))


class Sustitucion:
    """Tabla carácter real -> carácter que se guarda en el juego (y que la fuente dibuja como el real)."""

    def __init__(self, tabla, codificacion):
        self.tabla = dict(tabla)
        self.codificacion = codificacion
        self._ida = str.maketrans(self.tabla)
        self._vuelta = str.maketrans({v: k for k, v in self.tabla.items()})

    def al_juego(self, texto):
        return texto.translate(self._ida)

    def del_juego(self, texto):
        return texto.translate(self._vuelta)

    def codificar(self, texto):
        return codificar(self.al_juego(texto), self.codificacion)

    def decodificar(self, datos):
        return self.del_juego(datos.decode(self.codificacion))

    def no_codificables(self, texto):
        return no_codificables(self.al_juego(texto), self.codificacion)

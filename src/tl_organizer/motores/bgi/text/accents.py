# SPDX-License-Identifier: GPL-3.0-or-later
"""Letras con tilde del español <-> katakana de ancho medio.

El juego usa Shift-JIS (cp932), que no tiene á é í ó ú ñ ¿ ¡.  La fuente del parche (SubaHibi07Inq)
dibuja ciertos katakana de ancho medio (bytes 0xA1-0xDF) como esas letras, así que el texto en español
se guarda con esos bytes.  La tabla sale de los glifos de la fuente y se comprobó contra los más de
77.000 usos del texto del parche original (así, ¿Qué, está, -ción, ¡No, último, muñeca, Ángel, vergüenza...).
(La mecánica de la tabla es genérica: motores/kit/codificaciones.py, Sustitucion.)
"""
from ...kit.codificaciones import Sustitucion

# letra -> carácter Unicode cuyo byte cp932 es el que la fuente dibuja como esa letra
TO_GAME = {
    "á": "ｧ", "í": "ｨ", "ú": "ｩ", "é": "ｪ", "ó": "ｫ", "ü": "ｯ",
    "Á": "ｱ", "Í": "ｲ", "Ú": "ｳ", "É": "ｴ", "Ó": "ｵ", "Ü": "ﾂ",
    "ñ": "ﾃ", "Ñ": "ﾆ", "¡": "ｷ", "¿": "ﾚ",
}
FROM_GAME = {v: k for k, v in TO_GAME.items()}
ACENTOS = Sustitucion(TO_GAME, "cp932")


def to_game(text):
    """Texto en español -> texto con las letras sustituidas (aún sin codificar)."""
    return ACENTOS.al_juego(text)


def from_game(text):
    """Inverso de to_game: para mostrar el texto del parche con sus letras normales."""
    return ACENTOS.del_juego(text)


def encode(text):
    """Español -> bytes cp932 del juego.  Lanza UnicodeEncodeError con el carácter que no existe."""
    return to_game(text).encode("cp932")


def decode(raw):
    """Bytes cp932 del juego -> español legible."""
    return ACENTOS.decodificar(raw)


def unencodable(text):
    """Caracteres de 'text' que no se pueden guardar en el juego (para avisar al traductor)."""
    return ACENTOS.no_codificables(text)

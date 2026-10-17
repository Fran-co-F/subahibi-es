# SPDX-License-Identifier: GPL-3.0-or-later
"""Letras con tilde del español <-> katakana de ancho medio.

El juego usa Shift-JIS (cp932), que no tiene á é í ó ú ñ ¿ ¡.  La fuente del parche (SubaHibi07Inq)
dibuja ciertos katakana de ancho medio (bytes 0xA1-0xDF) como esas letras, así que el texto en español
se guarda con esos bytes.  La tabla sale de los glifos de la fuente y se comprobó contra los más de
77.000 usos del texto del parche original (así, ¿Qué, está, -ción, ¡No, último, muñeca, Ángel, vergüenza...).
"""

# letra -> carácter Unicode cuyo byte cp932 es el que la fuente dibuja como esa letra
TO_GAME = {
    "á": "ｧ", "í": "ｨ", "ú": "ｩ", "é": "ｪ", "ó": "ｫ", "ü": "ｯ",
    "Á": "ｱ", "Í": "ｲ", "Ú": "ｳ", "É": "ｴ", "Ó": "ｵ", "Ü": "ﾂ",
    "ñ": "ﾃ", "Ñ": "ﾆ", "¡": "ｷ", "¿": "ﾚ",
}
FROM_GAME = {v: k for k, v in TO_GAME.items()}
_ENC = str.maketrans(TO_GAME)
_DEC = str.maketrans(FROM_GAME)


def to_game(text):
    """Texto en español -> texto con las letras sustituidas (aún sin codificar)."""
    return text.translate(_ENC)


def from_game(text):
    """Inverso de to_game: para mostrar el texto del parche con sus letras normales."""
    return text.translate(_DEC)


def encode(text):
    """Español -> bytes cp932 del juego.  Lanza UnicodeEncodeError con el carácter que no existe."""
    return to_game(text).encode("cp932")


def decode(raw):
    """Bytes cp932 del juego -> español legible."""
    return from_game(raw.decode("cp932"))


def unencodable(text):
    """Caracteres de 'text' que no se pueden guardar en el juego (para avisar al traductor)."""
    bad = []
    for ch in to_game(text):
        try:
            ch.encode("cp932")
        except UnicodeEncodeError:
            if ch not in bad:
                bad.append(ch)
    return bad

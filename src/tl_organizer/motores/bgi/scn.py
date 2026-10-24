# SPDX-License-Identifier: GPL-3.0-or-later
"""Lector/escritor de escenarios compilados ('BurikoCompiledScriptVer1.00').

Contenedor (observado en los archivos del juego):
  0x00  "BurikoCompiledScriptVer1.00\\0"
  0x1c  u32 tamaño del resto de la cabecera (el flujo de tokens empieza en 0x1c + este valor)
  0x20  u32 cantidad de importaciones, luego los nombres terminados en NUL
        u32 cantidad de exportaciones, luego (nombre NUL, u32 desplazamiento)
  ...   relleno de ceros hasta un múltiplo de 16
  flujo de tokens: palabras de 32 bits; algunas llevan operandos (ver OPERANDS)
  tabla de cadenas: cadenas Shift-JIS terminadas en NUL, al final del archivo

Un operando de cadena o de código es un desplazamiento en bytes desde el inicio del flujo de
tokens.  El flujo termina en la frontera de palabra donde empieza la tabla de cadenas (la primera cadena
referenciada puede quedar 1-3 bytes más allá).
"""
import struct
from dataclasses import dataclass, field

MAGIC = b"BurikoCompiledScriptVer1.00\0"

# token -> cantidad de palabras de operando.  Observado: 0x00 push, 0x01 addr, 0x02 local,
# 0x03 str, 0x08 load, 0x09 store, 0x0a store2, 0x19 jcc llevan 1 (0x3f args también, según la
# documentación del formato); 0x7f (marca de línea) lleva 2.  El resto, 0.
OPERANDS = {0x00: 1, 0x01: 1, 0x02: 1, 0x03: 1, 0x08: 1, 0x09: 1, 0x0A: 1, 0x19: 1, 0x3F: 1, 0x7F: 2}
TOK_STR = 0x03


class ScnError(Exception):
    pass


def is_scenario(data):
    return data[:len(MAGIC)] == MAGIC


@dataclass
class Token:
    pos: int                 # desplazamiento en bytes dentro del flujo
    op: int
    args: tuple = ()


@dataclass
class Scenario:
    head: bytes                              # cabecera completa (hasta el inicio del flujo)
    tokens: list = field(default_factory=list)
    strings_start: int = 0                   # desplazamiento (en el flujo) donde empieza la tabla de cadenas
    tail: bytes = b""                        # tabla de cadenas original

    def string_at(self, off):
        end = self.tail.index(b"\0", off - self.strings_start)
        return self.tail[off - self.strings_start:end]


def parse(data, strings_start=None):
    """Lee un escenario.  El inicio de la tabla de cadenas se deduce de la cadena más baja a la que apunta
    algún token; en un archivo cuyos textos fueron reapuntados (nuestra salida) esa cadena ya no está
    referenciada, y entonces hay que indicarlo con 'strings_start' (se conoce por el original)."""
    if not is_scenario(data):
        raise ScnError("no es un escenario BGI")
    start = 0x1C + struct.unpack_from("<I", data, 0x1C)[0]
    stream = data[start:]
    toks, pos, min_str = [], 0, None
    n = len(stream)
    while True:
        # la tabla de cadenas empieza en la última frontera de palabra <= la primera cadena referenciada
        if strings_start is not None:
            if pos >= strings_start:
                break
        elif min_str is not None and pos >= (min_str & ~3):
            break
        if pos + 4 > n:
            raise ScnError("el flujo de tokens se acabó sin llegar a la tabla de cadenas")
        op = struct.unpack_from("<I", stream, pos)[0]
        k = OPERANDS.get(op, 0)
        args = struct.unpack_from("<%dI" % k, stream, pos + 4) if k else ()
        toks.append(Token(pos, op, args))
        if op == TOK_STR:
            min_str = args[0] if min_str is None else min(min_str, args[0])
        pos += 4 + 4 * k
    end = strings_start if strings_start is not None else (min_str & ~3)
    if pos != end:
        raise ScnError(f"el flujo termina en {pos} pero la tabla de cadenas debería empezar en {end}")
    return Scenario(head=data[:start], tokens=toks, strings_start=pos, tail=stream[pos:])


def serialize(sc):
    """Vuelve a armar el archivo: cabecera + tokens + tabla de cadenas."""
    out = bytearray(sc.head)
    for t in sc.tokens:
        out += struct.pack("<I", t.op)
        for a in t.args:
            out += struct.pack("<I", a)
    out += sc.tail
    return bytes(out)

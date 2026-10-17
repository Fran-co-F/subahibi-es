# SPDX-License-Identifier: GPL-3.0-or-later
"""Descompresor del formato 'DSC FORMAT 1.00' (Huffman de 512 símbolos + LZ).

Formato (observado en los archivos del juego):
  0x00  "DSC FORMAT 1.00\\0"
  0x10  u32 clave         (semilla del generador que cifra la tabla)
  0x14  u32 tamaño descomprimido
  0x18  u32 cantidad de símbolos a decodificar
  0x20  512 bytes: profundidad de código de cada símbolo, sumada a un flujo pseudoaleatorio
  0x220 datos: bits de arriba abajo; símbolo < 256 = byte literal;
        símbolo >= 256 = copia de (símbolo-256+2) bytes desde 12 bits+2 atrás.
"""
import struct

MAGIC = b"DSC FORMAT 1.00\0"


def _stream(key):
    """Generador de bytes que se resta a la tabla de profundidades."""
    key &= 0xFFFFFFFF
    while True:
        lo = (20021 * (key & 0xFFFF)) & 0xFFFFFFFF
        hi = (20021 * (key >> 16) + 346 * key + (lo >> 16)) & 0xFFFFFFFF
        key = (((hi << 16) & 0xFFFFFFFF) + (lo & 0xFFFF) + 1) & 0xFFFFFFFF
        yield hi & 0xFF


def is_dsc(data):
    return data[:16] == MAGIC


def decode(data):
    if not is_dsc(data):
        raise ValueError("no es un bloque DSC")
    key, size, count = struct.unpack_from("<III", data, 16)
    gen = _stream(key)
    depth = [(data[0x20 + i] - next(gen)) & 0xFF for i in range(512)]
    # código canónico: ordenado por (profundidad, símbolo)
    syms = sorted((d, s) for s, d in enumerate(depth) if d)
    table = {}                      # (profundidad, código) -> símbolo
    code = 0
    prev = syms[0][0]
    for d, s in syms:
        code <<= (d - prev)
        prev = d
        table[(d, code)] = s
        code += 1
    out = bytearray()
    pos = 0x220
    acc = nbits = 0
    maxd = max(depth)

    def getbits(n):
        nonlocal acc, nbits, pos
        while nbits < n:
            acc = (acc << 8) | (data[pos] if pos < len(data) else 0)
            pos += 1
            nbits += 8
        nbits -= n
        v = (acc >> nbits) & ((1 << n) - 1)
        acc &= (1 << nbits) - 1
        return v

    for _ in range(count):
        c = 0
        for d in range(1, maxd + 1):
            c = (c << 1) | getbits(1)
            s = table.get((d, c))
            if s is not None:
                break
        else:
            raise ValueError("código Huffman inválido")
        if s < 256:
            out.append(s)
        else:
            n = (s & 0xFF) + 2
            off = getbits(12) + 2
            for _i in range(n):
                out.append(out[-off])
    if len(out) != size:
        raise ValueError(f"tamaño inesperado: {len(out)} != {size}")
    return bytes(out)

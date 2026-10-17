# SPDX-License-Identifier: GPL-3.0-or-later
"""Parche del BGI.exe de la 15th Anniversary (fuente + modo proporcional).

No se distribuye ningún exe: se parchean unos pocos bytes de una copia del exe del usuario,
y solo si su sha256 corresponde a una versión conocida (ver KNOWN_BUILDS).

Cambios (v1.685.3, x86_64):

 1) Fuente.  El motor busca "MS Gothic" (inglés y japonés) para dibujar el texto.  Se cambian
    esas cadenas por "SubaHibi07Inq", la fuente que remapea los katakana de ancho medio
    a letras con tilde.  Cada cadena tiene 16 bytes de espacio.
 3) (opcional, utf8=True) Modo UTF-8: el exe de la 15th trae la instrucción `81 00` / Text_SetEncoding; se
    desvía el punto de entrada hacia un hueco de relleno que llama Text_SetEncoding(1) y sigue con el arranque.
 2) Modo proporcional.  WindowSetFont(ventana, fuente, tamaño, ancho, negrita, proporcional,
    reserva_ruby) recibe 'proporcional'; se fuerza a 1 con un desvío (JMP) a un hueco de
    relleno (INT3) justo antes de la función, porque no hay sitio para una constante:
       hook : mov [rsp+0x28],esi ; mov r8d,r12d   (7 bytes)  ->  jmp cave ; nop ; nop
       cave : mov dword [rsp+0x28],1 ; mov r8d,r12d ; jmp back
"""
import hashlib
import struct

DEFAULT_FONT = "SubaHibi07Inq"                       # cada cadena del exe tiene 16 bytes de espacio: hasta 15 caracteres
FONT_NAME = DEFAULT_FONT.encode().ljust(16, b"\x00")

KNOWN_BUILDS = {
    "993e9803a4335ff752dd7b4fd7b5036c3200c88c74fbde05d29b5123be5bd29c": {
        "version": "1.685.3 (15th Anniversary, x86_64)",
        "text_va": 0x140001000, "text_raw": 0x400,        # sección .text
        "font": [(0x17C740, b"MS Gothic\x00"),              # (offset en archivo, contenido esperado)
                 (0x17C750, b"\x82l\x82r \x83S\x83V\x83b\x83N\x00")],
        "hook": 0x1400DF7FA, "hook_bytes": "89742428458bc4",
        "cave": 0x1400DF76C, "back": 0x1400DF801,
        # modo UTF-8: el punto de entrada pasa por un desvío que llama a Text_SetEncoding(1)
        "entry_field": 0x150, "entry_rva": 0x11D74, "image_base": 0x140000000,
        "utf8_cave": 0x140001DF0, "set_encoding": 0x1400F74C0,
    },
}


class PatchError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def identify(data):
    """(sha256, datos_de_build | None)"""
    h = sha256(data)
    return h, KNOWN_BUILDS.get(h)


def font_slot(name):
    """Nombre de fuente como los 16 bytes que ocupan en el exe (ASCII, hasta 15 caracteres)."""
    raw = name.encode("ascii", "strict") if name.isascii() else b""
    if not raw or len(raw) > 15:
        raise PatchError(f"el nombre de la fuente debe ser ASCII y tener 1 a 15 caracteres: {name!r}")
    return raw.ljust(16, b"\x00")


def is_patched(data):
    """True si el exe ya lleva un cambio de fuente (la original es 'MS Gothic')."""
    for b in KNOWN_BUILDS.values():
        if all(data[o:o + 16] != old.ljust(16, b"\x00") for o, old in b["font"]):
            return True
    return False


def patch(data, font=True, proportional=True, utf8=False, font_name=DEFAULT_FONT):
    """Devuelve una copia parcheada de 'data' (bytes) o lanza PatchError.
    utf8=True activa el modo UTF-8 del motor desde el arranque (hay que entregar todo el texto en UTF-8)."""
    h, b = identify(data)
    if b is None:
        raise PatchError(
            f"exe desconocido (sha256 {h}). Este parche es para: "
            + "; ".join(v["version"] for v in KNOWN_BUILDS.values()))
    d = bytearray(data)
    off = lambda va: va - b["text_va"] + b["text_raw"]
    if font:
        slot = font_slot(font_name)
        for o, old in b["font"]:
            if d[o:o + len(old)] != old:
                raise PatchError(f"contenido inesperado en 0x{o:x}")
            d[o:o + 16] = slot
    if proportional:
        hook, cave, back = b["hook"], b["cave"], b["back"]
        if d[off(hook):off(hook) + 7].hex() != b["hook_bytes"]:
            raise PatchError("el código de WindowSetFont no es el esperado")
        if any(x != 0xCC for x in d[off(cave):off(cave) + 20]):
            raise PatchError("el hueco de relleno no está libre")
        code = bytes.fromhex("c744242801000000") + bytes.fromhex("458bc4")
        code += b"\xe9" + struct.pack("<i", back - (cave + len(code) + 5))
        d[off(cave):off(cave) + len(code)] = code
        d[off(hook):off(hook) + 7] = b"\xe9" + struct.pack("<i", cave - (hook + 5)) + b"\x90\x90"
    if utf8:
        cave, setter, base = b["utf8_cave"], b["set_encoding"], b["image_base"]
        if any(x != 0xCC for x in d[off(cave):off(cave) + 16]):
            raise PatchError("el hueco para el modo UTF-8 no está libre")
        f = b["entry_field"]
        if struct.unpack_from("<I", d, f)[0] != b["entry_rva"]:
            raise PatchError("el punto de entrada no es el esperado")
        stub = b"\xb9\x01\x00\x00\x00"                                    # mov ecx, 1
        stub += b"\xe8" + struct.pack("<i", setter - (cave + 10))            # call Text_SetEncoding
        stub += b"\xe9" + struct.pack("<i", base + b["entry_rva"] - (cave + 15))   # jmp entrada original
        d[off(cave):off(cave) + len(stub)] = stub
        struct.pack_into("<I", d, f, cave - base)
    return bytes(d)

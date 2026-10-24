# SPDX-License-Identifier: GPL-3.0-or-later
"""Parche del ejecutable de BGI (fuente + modo proporcional + modo UTF-8).

No se distribuye ningún exe: se parchean unos pocos bytes de una copia del exe del usuario, y solo si su sha256
corresponde a una versión conocida.  Las versiones conocidas y sus direcciones están en los perfiles de juego
([[bgi.ejecutables]], ver juegos/*.toml); desde_perfil() las convierte al diccionario que usa este módulo.

Cambios (ejemplo: v1.685.3, x86_64):

 1) Fuente.  El motor busca "MS Gothic" (inglés y japonés) para dibujar el texto.  Se cambian
    esas cadenas por la fuente del perfil (por ejemplo "SubaHibi07Inq", la del parche viejo).
    Cada cadena tiene 16 bytes de espacio.
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


class PatchError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def desde_perfil(d):
    """Un bloque [[bgi.ejecutables]] del perfil -> diccionario de versión (con 'font' como [(desplazamiento, bytes)])."""
    for k in ("sha256", "version"):
        if not isinstance(d.get(k), str):
            raise PatchError(f"[[bgi.ejecutables]]: falta «{k}»")
    b = dict(d)
    try:
        b["font"] = [(f["offset"], bytes.fromhex(f["original"])) for f in d.get("font", [])]
    except (KeyError, TypeError, ValueError) as e:
        raise PatchError(f"[[bgi.ejecutables]] {d['version']}: «font» mal escrito ({e})")
    return b


def identify(data, builds):
    """(sha256, datos_de_build | None).  builds: {sha256: datos_de_build}."""
    h = sha256(data)
    return h, builds.get(h)


def font_slot(name):
    """Nombre de fuente como los 16 bytes que ocupan en el exe (ASCII, hasta 15 caracteres)."""
    raw = name.encode("ascii", "strict") if name.isascii() else b""
    if not raw or len(raw) > 15:
        raise PatchError(f"el nombre de la fuente debe ser ASCII y tener 1 a 15 caracteres: {name!r}")
    return raw.ljust(16, b"\x00")


def is_patched(data, builds):
    """True si el exe ya lleva un cambio de fuente (la original es 'MS Gothic')."""
    for b in builds.values():
        if all(data[o:o + 16] != old.ljust(16, b"\x00") for o, old in b["font"]):
            return True
    return False


def patch(data, builds, font=True, proportional=True, utf8=False, font_name=None):
    """Devuelve una copia parcheada de 'data' (bytes) o lanza PatchError.  builds: {sha256: datos_de_build}.
    utf8=True activa el modo UTF-8 del motor desde el arranque (hay que entregar todo el texto en UTF-8)."""
    h, b = identify(data, builds)
    if b is None:
        raise PatchError(
            f"exe desconocido (sha256 {h}). Este parche es para: "
            + ("; ".join(v["version"] for v in builds.values()) or "ninguna versión (no hay perfiles con [[bgi.ejecutables]])"))
    if font and not font_name:
        raise PatchError("falta el nombre de la fuente (opción --fuente o «fuente» en la sección [bgi] del perfil)")
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

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
    """Un bloque [[bgi.ejecutables]] del perfil -> diccionario de versión.
    'font': [(desplazamiento, bytes originales, tamaño del lugar)]; 'parches': [(desplazamiento, original, nuevo, para)]
    (cambios de bytes verificados; para = "fuente" se aplican junto con el cambio de fuente)."""
    for k in ("sha256", "version"):
        if not isinstance(d.get(k), str):
            raise PatchError(f"[[bgi.ejecutables]]: falta «{k}»")
    b = dict(d)
    try:
        b["font"] = [(f["offset"], bytes.fromhex(f["original"]), int(f.get("tamano", 16))) for f in d.get("font", [])]
        b["parches"] = [(p["offset"], bytes.fromhex(p["original"]), bytes.fromhex(p["nuevo"]), p.get("para", "fuente"))
                        for p in d.get("parches", [])]
    except (KeyError, TypeError, ValueError) as e:
        raise PatchError(f"[[bgi.ejecutables]] {d['version']}: «font» o «parches» mal escrito ({e})")
    for o, orig, nuevo, _para in b["parches"]:
        if len(orig) != len(nuevo):
            raise PatchError(f"[[bgi.ejecutables]] {d['version']}: el parche en 0x{o:x} cambia el largo")
    return b


def tiene_proporcional(b):
    """La versión trae el desvío de exe para el modo proporcional (si no, se hace en los programas de sistema)."""
    return "hook" in b


def tiene_utf8(b):
    """La versión trae Text_SetEncoding (modo UTF-8; existe desde la 1.653)."""
    return "utf8_cave" in b


def identify(data, builds):
    """(sha256, datos_de_build | None).  builds: {sha256: datos_de_build}."""
    h = sha256(data)
    return h, builds.get(h)


def font_slot(name, tamano=16):
    """Nombre de fuente como los bytes que ocupa en el exe (ASCII, hasta tamano-1 caracteres)."""
    raw = name.encode("ascii", "strict") if name.isascii() else b""
    if not raw or len(raw) > tamano - 1:
        raise PatchError(f"el nombre de la fuente debe ser ASCII y tener 1 a {tamano - 1} caracteres: {name!r}")
    return raw.ljust(tamano, b"\x00")


def is_patched(data, builds):
    """True si el exe ya lleva un cambio de fuente (la original es 'MS Gothic')."""
    for b in builds.values():
        if b["font"] and all(data[o:o + t] != old.ljust(t, b"\x00") for o, old, t in b["font"]):
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
    if proportional and not tiene_proporcional(b):
        raise PatchError(f"{b['version']}: esta versión no tiene desvío de exe para el modo proporcional "
                         "(se hace en los programas de sistema: proporcional = \"programas\" en el perfil)")
    if utf8 and not tiene_utf8(b):
        raise PatchError(f"{b['version']}: esta versión del motor no tiene modo UTF-8 (Text_SetEncoding existe desde la 1.653); "
                         "usá el modo katakana (--katakana, o modo = \"katakana\" en la sección [bgi] del perfil)")
    d = bytearray(data)
    off = lambda va: va - b["text_va"] + b["text_raw"]

    def cambiar(o, orig, nuevo):
        if d[o:o + len(orig)] != orig:
            raise PatchError(f"contenido inesperado en 0x{o:x} (esperaba {orig.hex()}, hay {bytes(d[o:o + len(orig)]).hex()})")
        d[o:o + len(nuevo)] = nuevo
    if font:
        for o, old, t in b["font"]:
            cambiar(o, old, old)                       # verifica el original
            d[o:o + t] = font_slot(font_name, t)
        for o, orig, nuevo, para in b["parches"]:
            if para == "fuente":
                cambiar(o, orig, nuevo)
    for o, orig, nuevo, para in b["parches"]:
        if para == "siempre":
            cambiar(o, orig, nuevo)
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

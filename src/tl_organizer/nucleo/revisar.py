# SPDX-License-Identifier: GPL-3.0-or-later
"""Control de calidad de las traducciones (tl-organizer revisar).

Cada control es una función  control(fila, ctx) -> iterable de (nivel, código, detalle).  nivel: «error» (el texto se
verá mal o no se puede aplicar) o «aviso» (conviene mirarlo).  Los controles generales están en CONTROLES; el motor
agrega lo que solo él sabe: Motor.marcadores() (códigos de control que la traducción tiene que conservar),
Motor.caracteres_invalidos() (lo que el juego no puede mostrar) y Motor.controles() (controles propios).
"""
import re
from collections import Counter
from dataclasses import dataclass, field

ESTADOS = ("traducido", "del parche", "revisar")       # filas que se revisan (las que tienen traducción y se usan o se usarán)
ERROR, AVISO = "error", "aviso"

# caracteres que delatan texto sin traducir, según el idioma del original
ESCRITURA = {
    "ja": re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]"),     # kana, kanji, kana de ancho medio
    "zh": re.compile(r"[㐀-鿿]"),
    "ko": re.compile(r"[가-힯ᄀ-ᇿ]"),
}
ESTILO = {"ja": "ー・"}           # signos del original que se usan a propósito en la traducción («Tomo nii-saーn»)
_ETIQUETA = re.compile(r"<\s*(/?)\s*([A-Za-z][\w-]*)")


@dataclass
class Problema:
    clave: str
    nivel: str
    codigo: str
    detalle: str
    original: str = ""
    traduccion: str = ""


@dataclass
class Contexto:
    idiomas: tuple = ("ja", "es")
    motor: object = None
    fits: object = None                # fits(linea) -> bool (ver wrap.make_fits), o None para no medir
    max_lineas: int = None
    opciones: dict = field(default_factory=dict)


def _ver(ch):
    return {"\t": "TAB", "\r": "CR", "\x00": "NUL"}.get(ch, f"U+{ord(ch):04X}")


# ---------------------------------------------------------------- controles generales

def vacia(fila, ctx):
    if fila["estado"] == "traducido" and not fila["traduccion"].strip():
        yield AVISO, "vacia", "estado «traducido» pero sin traducción (el juego mostrará el original)"


def igual_al_original(fila, ctx):
    t = fila["traduccion"]
    if t and t == fila["original"] and ESCRITURA.get(ctx.idiomas[0], re.compile("(?!)")).search(t):
        yield AVISO, "sin_traducir", "la traducción es igual al original"


def restos_del_original(fila, ctx):
    rx = ESCRITURA.get(ctx.idiomas[0])
    t = fila["traduccion"]
    if rx and t and t != fila["original"]:
        restos = sorted(set(rx.findall(t)) - set(ESTILO.get(ctx.idiomas[0], "")))
        if restos:
            yield AVISO, "restos", "caracteres del idioma original en la traducción: " + "".join(restos[:12])


def control(fila, ctx):
    t = fila["traduccion"]
    ya = set(ctx.motor.caracteres_invalidos(t, ctx.opciones)) if ctx.motor is not None and t else set()   # los informa «caracteres»
    malos = sorted({ch for ch in t if ord(ch) < 32 and ch != "\n"} - ya)
    if malos:
        yield AVISO, "control", "caracteres de control invisibles: " + ", ".join(_ver(c) for c in malos)


def espacios(fila, ctx):
    t = fila["traduccion"]
    if not t:
        return
    if re.search(r"[^\s] {2,}[^\s]", t):
        yield AVISO, "espacios", "espacios dobles"
    o = fila["original"]
    if t != t.strip(" ") and o == o.strip(" "):
        yield AVISO, "espacios", "espacios al principio o al final que el original no tiene"


def saltos(fila, ctx):
    """Un salto de línea al principio o al final del original suele ser parte del formato del juego (y msgfmt -c lo exige)."""
    o, t = fila["original"], fila["traduccion"]
    if not t:
        return
    for donde, f in (("al principio", str.startswith), ("al final", str.endswith)):
        if f(o, "\n") != f(t, "\n"):
            yield AVISO, "saltos", f"salto de línea {donde}: " + ("el original lo tiene y la traducción no" if f(o, "\n") else "la traducción lo tiene y el original no")


def puntuacion_es(fila, ctx):
    if ctx.idiomas[1] != "es" or not fila["traduccion"]:
        return
    t = fila["traduccion"]
    for abre, cierra in (("¿", "?"), ("¡", "!")):
        if t.count(abre) > t.count(cierra):
            yield AVISO, "puntuacion", f"«{abre}» sin su «{cierra}»"


def _clave_marcador(mk):
    """Las etiquetas se comparan por su nombre (el argumento, como la lectura de <r よみ>, cambia al traducir)."""
    e = _ETIQUETA.match(mk)
    return f"<{e.group(1)}{e.group(2).lower()}>" if e else mk


def marcadores(fila, ctx):
    m = ctx.motor
    if m is None or not fila["traduccion"]:
        return
    mo = Counter(map(_clave_marcador, m.marcadores(fila["original"])))
    mt = Counter(map(_clave_marcador, m.marcadores(fila["traduccion"])))
    if mo != mt:
        faltan, sobran = list((mo - mt).elements()), list((mt - mo).elements())
        partes = ([("faltan " + " ".join(faltan))] if faltan else []) + ([("no están en el original: " + " ".join(sobran))] if sobran else [])
        yield AVISO, "marcadores", "; ".join(partes)
    pila = []
    for mk in m.marcadores(fila["traduccion"]):
        e = _ETIQUETA.match(mk)
        if not e:
            continue
        cierre, nombre = e.group(1) == "/", e.group(2).lower()
        if not cierre:
            pila.append(nombre)
        elif pila and pila[-1] == nombre:
            pila.pop()
        else:
            yield ERROR, "etiquetas", f"«{mk}» cierra algo que no está abierto"
            return
    if pila:
        yield ERROR, "etiquetas", "sin cerrar: " + " ".join(f"<{n}>" for n in pila)


def caracteres(fila, ctx):
    m = ctx.motor
    if m is not None and fila["traduccion"]:
        malos = m.caracteres_invalidos(fila["traduccion"], ctx.opciones)
        if malos:
            yield ERROR, "caracteres", "el juego no puede mostrar: " + " ".join(_ver(c) if ord(c) < 32 else c for c in malos)


def largo(fila, ctx):
    t = fila["traduccion"]
    if not t or fila["tipo"] != "mensaje":
        return
    lineas = [l for l in t.split("\n")]
    if ctx.fits:
        largas = [l for l in lineas if not ctx.fits(l)]
        if largas:
            yield AVISO, "largo", f"{len(largas)} línea(s) más larga(s) que el ancho: «{largas[0][:40]}…»"
    if ctx.max_lineas and len([l for l in lineas if l]) > ctx.max_lineas:
        yield AVISO, "lineas", f"{len([l for l in lineas if l])} líneas (máximo {ctx.max_lineas})"


CONTROLES = [vacia, igual_al_original, restos_del_original, control, espacios, saltos, puntuacion_es, marcadores, caracteres, largo]


# ---------------------------------------------------------------- revisión

def revisar_filas(filas, ctx, estados=ESTADOS, controles=None):
    """-> [Problema] de las filas con estado en 'estados'."""
    controles = list(controles if controles is not None else CONTROLES)
    if ctx.motor is not None:
        controles += list(ctx.motor.controles())
    out = []
    for f in filas:
        if f.get("estado") not in estados:
            continue
        f = dict(f, original=f.get("original") or "", traduccion=(f.get("traduccion") or "").replace("\r", ""))
        for c in controles:
            for nivel, codigo, detalle in c(f, ctx):
                out.append(Problema(f["clave"], nivel, codigo, detalle, f["original"], f["traduccion"]))
    return sorted(out, key=lambda p: p.nivel != ERROR)        # primero los errores (orden estable dentro de cada nivel)


def escribir_tsv(path, problemas):
    from .hojas import _esc
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("clave\tnivel\tcodigo\tdetalle\toriginal\ttraduccion\n")
        for p in problemas:
            f.write("\t".join(_esc(x) for x in (p.clave, p.nivel, p.codigo, p.detalle, p.original, p.traduccion)) + "\n")

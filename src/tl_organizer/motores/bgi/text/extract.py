# SPDX-License-Identifier: GPL-3.0-or-later
"""Filas de texto traducible dentro de un escenario compilado.

Un texto es una cadena (token 'str') que consume un comando de texto.  El comando que la consume es
el primer token que no sea push / str / marca de línea después de ella.
"""
from dataclasses import dataclass
from ..scn import TOK_STR

# comando -> tipo (observado en los 130 escenarios de la 15th Anniversary)
KINDS = {
    0x140: "mensaje",     # línea de diálogo / narración
    0x143: "epigrafe",    # líneas sueltas del prólogo (cita)
    0x11C: "fecha",       # rótulo de fecha / hora
    0x118: "titulo",      # título de capítulo
}
STORE = 0x09              # asignación: las opciones de elección se guardan así (id de imagen + texto)
IGNORED = (0x00, TOK_STR, 0x7F)   # push, str, marca de línea: no cuentan como comando consumidor


@dataclass
class Row:
    tok: int              # índice del token 'str' dentro de Scenario.tokens
    pos: int              # desplazamiento (bytes) del token dentro del flujo
    kind: str
    raw: bytes            # cadena original (cp932), sin el NUL

    @property
    def has_japanese(self):
        return any(b >= 0x81 for b in self.raw)


def consumer(tokens, i):
    """Comando (op) que consume el token 'str' en la posición i, o None."""
    j = i + 1
    n = len(tokens)
    while j < n and tokens[j].op in IGNORED:
        j += 1
    return tokens[j].op if j < n else None


def rows(sc, all_store=False):
    """Filas de texto de un Scenario.  Las elecciones (asignaciones de cadena) solo se incluyen si tienen
    japonés, salvo all_store=True, que devuelve todas (sirve para alinear con otra versión)."""
    out = []
    for i, t in enumerate(sc.tokens):
        if t.op != TOK_STR:
            continue
        c = consumer(sc.tokens, i)
        if c in KINDS:
            kind = KINDS[c]
        elif c == STORE:
            kind = "eleccion"
        else:
            continue
        r = Row(i, t.pos, kind, sc.string_at(t.args[0]))
        if kind == "eleccion" and not all_store and not r.has_japanese:
            continue
        out.append(r)
    return out

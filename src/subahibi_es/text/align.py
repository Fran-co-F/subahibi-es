# SPDX-License-Identifier: GPL-3.0-or-later
"""Alineación de las filas de un escenario japonés con las de la traducción del parche viejo.

Con la misma cantidad de filas de un tipo se alinean por orden.  Si no, se usa difflib sobre una 'firma' de
cada fila: su tipo, rasgos del texto que sobreviven a la traducción (diálogo entre comillas, pensamiento
entre paréntesis, salto de línea interno) y los comandos que la rodean.
"""
from difflib import SequenceMatcher
from ..bgi.scn import TOK_STR
from . import accents

WINDOW = 40              # filas por ventana al comprobar que la traducción sigue alineada con el original
CORR_MIN = 0.6           # correlación mínima de largos (japonés vs español); bien alineado da ~0,9, corrido una fila ~0


def quote_jp(raw):
    t = raw.decode("cp932", "replace")
    return "q" if t[:1] in "「『" else "p" if t[:1] in "（(" else "n"


def quote_es(raw):
    t = accents.decode(raw)
    return "q" if t[:1] in "\"“" else "p" if t[:1] == "(" else "n"


def _ctx(tokens, row, span=4):
    sig, i = [], row.tok - 1
    while i >= 0 and len(sig) < span:
        if tokens[i].op not in (0x7F, TOK_STR, 0x00):
            sig.append(tokens[i].op)
        i -= 1
    return tuple(sig)


def align(sc_a, rows_a, sc_b, rows_b):
    """a = japonés, b = español.  Devuelve (mapa {i_en_a: i_en_b}, acuerdo 0..1, exacta)
    exacta=True si todas las filas se alinearon por orden; acuerdo = fracción con el mismo tipo de comillas."""
    mapping, exact = {}, True
    for kind in {r.kind for r in rows_a} | {r.kind for r in rows_b}:
        ia = [i for i, r in enumerate(rows_a) if r.kind == kind]
        ib = [i for i, r in enumerate(rows_b) if r.kind == kind]
        if len(ia) == len(ib):
            mapping.update(zip(ia, ib))
            continue
        exact = False
        sa = [(kind, quote_jp(rows_a[i].raw), b"\n" in rows_a[i].raw, _ctx(sc_a.tokens, rows_a[i])) for i in ia]
        sb = [(kind, quote_es(rows_b[i].raw), b"\n" in rows_b[i].raw, _ctx(sc_b.tokens, rows_b[i])) for i in ib]
        for blk in SequenceMatcher(None, sa, sb, autojunk=False).get_matching_blocks():
            for k in range(blk.size):
                mapping[ia[blk.a + k]] = ib[blk.b + k]
    msg = [(i, j) for i, j in mapping.items() if rows_a[i].kind == "mensaje"]
    agree = (sum(1 for i, j in msg if quote_jp(rows_a[i].raw) == quote_es(rows_b[j].raw)) / len(msg)) if msg else 1.0
    return mapping, agree, exact


def _corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 1.0


def doubtful(jp_lens, es_lens, window=WINDOW, corr_min=CORR_MIN):
    """Posiciones (índices) de los pares cuyo largo japonés/español no se parece, señal de que la alineación se corrió.

    Se mira por ventanas deslizantes (mitad de solape): una traducción bien alineada mantiene los largos correlacionados
    (~0,9) en todo el escenario, y un desfase de una sola fila los deja sin relación (~0).  Con menos de `window` pares se
    evalúa el conjunto entero (y con menos de 10 no se puede juzgar: no se marca nada).  Es una medida de los largos,
    no del sentido: sirve para encontrar zonas sospechosas, no para validar traducciones."""
    n = len(jp_lens)
    if n < 10:
        return set()
    if n < window:
        return set(range(n)) if _corr(jp_lens, es_lens) < corr_min else set()
    bad = set()
    for i in range(0, n - window + 1, window // 2):
        if _corr(jp_lens[i:i + window], es_lens[i:i + window]) < corr_min:
            bad.update(range(i, i + window))
    return bad

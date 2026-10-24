# SPDX-License-Identifier: GPL-3.0-or-later
"""Detección de zonas donde una traducción precargada dejó de estar alineada con el original.

No depende del motor: solo mira los largos del original y de la traducción de cada fila.
"""

WINDOW = 40              # filas por ventana al comprobar que la traducción sigue alineada con el original
CORR_MIN = 0.6           # correlación mínima de largos (original vs traducción); bien alineado da ~0,9, corrido una fila ~0
NOTA_DUDOSA = "alineación dudosa: el largo no se parece al del original"


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


def marcar_dudosas(filas, tipo="mensaje"):
    """Pasa a «revisar» (con una nota) las filas precargadas de 'tipo' que caen en una zona dudosa (ver doubtful)."""
    pares = [k for k, r in enumerate(filas) if r["tipo"] == tipo and r["traduccion"]]
    for k in doubtful([len(filas[k]["original"]) for k in pares], [len(filas[k]["traduccion"]) for k in pares]):
        filas[pares[k]]["estado"], filas[pares[k]]["nota"] = "revisar", NOTA_DUDOSA
    return filas

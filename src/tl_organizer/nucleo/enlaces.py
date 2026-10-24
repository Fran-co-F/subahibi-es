# SPDX-License-Identifier: GPL-3.0-or-later
"""build --jugable: una carpeta de prueba con enlaces a los archivos del juego, para ejecutarla sin tocar la instalación."""
import os
import shutil


def _link(src, dst):
    """Deja en dst un acceso a src.  Intenta, en orden: enlace simbólico (Linux/macOS; en Windows pide administrador o
    modo desarrollador), enlace duro (mismo volumen) y, si nada de eso se puede, copia.  Devuelve el método usado."""
    if os.path.lexists(dst):
        if os.path.islink(dst) and os.readlink(dst) == src:
            return "enlace simbólico"
        if not os.path.islink(dst) and os.path.exists(dst):
            try:
                if os.path.samefile(src, dst):
                    return "enlace duro"
                a, b = os.stat(src), os.stat(dst)
                if a.st_size == b.st_size and a.st_mtime_ns == b.st_mtime_ns:
                    return "copia"                    # una copia anterior, igual que el original
            except OSError:
                pass
        os.remove(dst)
    try:
        os.symlink(src, dst)
        return "enlace simbólico"
    except (OSError, NotImplementedError):
        pass
    try:
        os.link(src, dst)
        return "enlace duro"
    except OSError:
        pass
    shutil.copy2(src, dst)
    return "copia"


def link_game(game, out, perfil):
    """Enlaza los archivos fijos del juego en out y copia (una vez) los datos del jugador, según la sección [jugable]
    del perfil: enlazar_extensiones, enlazar (nombres exactos) y copiar_una_vez."""
    exts = tuple(e.lower() for e in perfil.lista("jugable", "enlazar_extensiones"))
    names = perfil.lista("jugable", "enlazar")
    n, metodos = 0, {}
    for f in sorted(os.listdir(game)):
        src = os.path.join(game, f)
        if f == perfil.ejecutable:
            continue           # el motor escribe ahí el exe parcheado: a través de un enlace pisaría el original
        if os.path.isfile(src) and ((exts and f.lower().endswith(exts)) or f in names):
            m = _link(src, os.path.join(out, f))
            n += 1
            metodos[m] = metodos.get(m, 0) + 1
    for f in perfil.lista("jugable", "copiar_una_vez"):
        src, dst = os.path.join(game, f), os.path.join(out, f)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
    return n, metodos

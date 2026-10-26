# SPDX-License-Identifier: GPL-3.0-or-later
"""Dónde busca el motor los archivos sueltos que tapan a los de los .arc.

La mayoría de las versiones los busca en <Tipo>/CVTD/ (Script, Graphic, Sound, Voice), rutas que fija
system.arc:ipl._bp.  Otras los buscan directamente en la carpeta del juego: DESIRE remaster (1.642.1) nunca abre
Script\\CVTD aunque su ipl._bp nombre esa carpeta (comprobado con una traza de Wine).  Perfil: [bgi] sueltos.
"""
import os

CARPETAS, RAIZ = "carpetas", "raiz"
MODOS = (CARPETAS, RAIZ)


def carpeta(base, tipo, modo=CARPETAS):
    """Carpeta (dentro de 'base') donde van los sueltos de 'tipo' («Script», «Graphic», «Sound» o «Voice»)."""
    return base if modo == RAIZ else os.path.join(base, tipo, "CVTD")

# SPDX-License-Identifier: GPL-3.0-or-later
"""Valores por defecto de los comandos, derivados del proyecto (ver proyecto.py).

Los argumentos de la línea de comandos siempre mandan sobre estos valores.  Claves: juego, juego_es, parche_viejo,
imagenes, texto, originales, indice, estado, idiomas.
"""
import sys

from . import hojas, proyecto as project


def load():
    proj = project.find()
    if proj is None:
        return {"idiomas": hojas.IDIOMAS}
    return {
        "juego": proj.root,
        "juego_es": proj.dir("salida"),          # lo que hay que copiar al juego
        "parche_viejo": proj.parche_viejo,
        "imagenes": proj.dir("traducidas"),
        "texto": proj.dir("texto"),
        "originales": proj.dir("originales"),
        "indice": proj.dir("indice"),
        "estado": proj.estado_tsv,
        "idiomas": proj.idiomas,
    }


def need(value, key, what):
    """Argumento de la línea de comandos o, si falta, el valor del proyecto."""
    v = value or load().get(key)
    if not v:
        sys.exit(f"falta {what}: indicalo, o ejecutá «subahibi-es init» dentro de la carpeta de instalación del juego")
    return v


def lista(texto):
    """«a, b,c» -> ("a", "b", "c")"""
    return tuple(x.strip() for x in texto.split(","))

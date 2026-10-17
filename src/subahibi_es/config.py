# SPDX-License-Identifier: GPL-3.0-or-later
"""Valores por defecto de los comandos, derivados del proyecto (ver project.py).

Los argumentos de la línea de comandos siempre mandan sobre estos valores.  Claves: juego, juego_es, parche_viejo,
imagenes, texto, originales, indice, estado.
"""
from . import project


def load():
    proj = project.find()
    if proj is None:
        return {}
    return {
        "juego": proj.root,
        "juego_es": proj.dir("salida"),          # lo que hay que copiar al juego
        "parche_viejo": proj.parche_viejo,
        "imagenes": proj.dir("traducidas"),
        "texto": proj.dir("texto"),
        "originales": proj.dir("originales"),
        "indice": proj.dir("indice"),
        "estado": proj.estado_tsv,
    }

# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuración del proyecto: rutas que se repiten en todos los comandos (subahibi-es.json).

Se busca en la carpeta actual, o en la ruta de la variable SUBAHIBI_ES_CONFIG.  Los argumentos de la línea de
comandos siempre mandan sobre la configuración.  Claves: juego, juego_es, parche_viejo, imagenes, texto.
"""
import json
import os

NAME = "subahibi-es.json"
KEYS = ("juego", "juego_es", "parche_viejo", "imagenes", "texto")


def path():
    return os.environ.get("SUBAHIBI_ES_CONFIG") or os.path.join(os.getcwd(), NAME)


def load():
    try:
        with open(path(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(values):
    cfg = load()
    cfg.update({k: os.path.abspath(v) for k, v in values.items() if v and k in KEYS})
    with open(path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return cfg

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Genera las imágenes de interfaz en español a partir de las originales (PNG extraídas de sysgrp.arc).

Preparación (una vez):
    subahibi-es images export CARPETA_DEL_JUEGO dump              # -> dump/*.png
Uso:
    python3 tools/generar_ui.py dump  salida/Graphic/CVTD

Requiere: Pillow y la fuente Noto Sans (ver ui_lib.py: REG / LIGHT).
Para añadir una imagen: agregar su nombre y texto a TITULO / MENU (botones con 3 estados y
una descripción pequeña) o a DIALOGOS (línea principal centrada), o escribir un caso nuevo
con las funciones de ui_lib (clear, put, bright_bbox, save_bmp).
Los textos están también en ../traducciones.tsv
"""
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_lib import *

BLANCO, CREMA = (255, 255, 255), (255, 252, 210)

# --- botones en tira (3 estados: normal | resaltado | presionado); la descripción va en los estados 2 y 3
MENU = {   # texto alineado a la izquierda, y mínima de la descripción = 46
 'SGMenu000000': 'Guardar la partida', 'SGMenu000100': 'Cargar una partida',
 'SGMenu000200': 'Abrir el historial de texto', 'SGMenu000300': 'Iniciar la reproducción automática',
 'SGMenu000400': 'Iniciar el salto de texto', 'SGMenu000500': 'Abrir la configuración',
 'SGMenu000600': 'Abrir la configuración de teclas', 'SGMenu000700': 'Ocultar la ventana de mensajes',
 'SGMenu000800': 'Volver al título', 'SGMenu000900': 'Salir del juego', 'SGMenu001000': 'Cargar el guardado rápido',
 'SGCnfgWnd000900': 'Abrir la configuración de teclas'}
TITULO = { # texto centrado, y mínima = 40
 'SGTitle000000': 'Comenzar el juego', 'SGTitle000100': 'Cargar una partida', 'SGTitle000200': 'Abrir el menú de extras',
 'SGTitle000300': 'Abrir la configuración', 'SGTitle000400': 'Salir del juego', 'SGTitle000500': 'Comenzar la ruta adicional',
 'SGTitle001000': 'Abrir la galería de CG', 'SGTitle001100': 'Abrir la galería de escenas',
 'SGTitle001200': 'Abrir la galería de música', 'SGTitle001400': 'Volver al nivel anterior'}
# --- diálogos de confirmación (se borra la línea japonesa y se escribe la española; el subtítulo inglés queda)
DIALOGOS = {
 'SGDialog990000': '¿Terminar el juego?', 'SGDialog990100': '¿Volver a la pantalla de título?',
 'SGDialog990300': '¿Sobrescribir la partida guardada?', 'SGDialog990400': '¿Cargar el guardado rápido?',
 'SGDialog990500': '¿Cargar la partida guardada?', 'SGDialog990700': 'Guardado rápido realizado'}

def tira(src, out, name, texto, ymin, align, estados=3, size=10):
    im = Image.open(os.path.join(src, name + '.png')).convert('RGBA'); W = im.size[0] // estados; reemplazos = []
    for st in range(1, estados):
        bb = bright_bbox(im, (W*st + 2, ymin, W*st + W - 2, im.size[1]), 40, 330)
        if bb: reemplazos.append(bb)
    for bb in reemplazos:
        clear(im, (bb[0]-3, bb[1]-3, bb[2]+4, bb[3]+4)); cy = (bb[1]+bb[3]) / 2
        if align == 'left': put(im, texto, bb[0], cy, size, BLANCO)
        else: put(im, texto, (bb[0]+bb[2]) / 2, cy, size, BLANCO, align='center')
    save_bmp(im, os.path.join(out, name))

def dialogo(src, out, name, texto):
    im = Image.open(os.path.join(src, name + '.png')).convert('RGBA'); px = im.load()
    bb = bright_bbox(im, (300, 446, 980, 480), 200, 330)          # línea japonesa principal
    cx, cy = (bb[0]+bb[2]) / 2, (bb[1]+bb[3]) / 2
    for y in range(bb[1]-5, bb[3]+6):                              # rellena con el fondo (mediana de la fila)
        col = [tuple(px[x, y]) for x in range(bb[0]-90, bb[0]-30)]
        med = tuple(int(statistics.median(c[i] for c in col)) for i in range(4))
        for x in range(bb[0]-8, bb[2]+9): px[x, y] = med
    put(im, texto, cx, cy, 20, CREMA, align='center', track=3.0, shadow=True, sh_off=(1, 1), sh_blur=0.9, sh_alpha=200)
    save_bmp(im, os.path.join(out, name))

if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    src, out = sys.argv[1:]; os.makedirs(out, exist_ok=True)
    for n, t in MENU.items(): tira(src, out, n, t, 46, 'left')
    for n, t in TITULO.items(): tira(src, out, n, t, 40, 'center')
    for n, t in DIALOGOS.items(): dialogo(src, out, n, t)
    print('listo:', len(MENU) + len(TITULO) + len(DIALOGOS), 'imágenes en', out)

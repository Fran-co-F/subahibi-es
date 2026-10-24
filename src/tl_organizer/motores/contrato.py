# SPDX-License-Identifier: GPL-3.0-or-later
"""Prueba de contrato: lo que todo motor de texto tiene que cumplir para que el núcleo pueda confiar en él.

Se usa desde las pruebas del motor, con un juego sintético chico:

    from tl_organizer.motores import contrato
    assert contrato.verificar(MiMotor(perfil), carpeta_del_juego, tmp_path) == []

Comprueba:
  1. textos(): filas completas, claves únicas con la forma «<escenario>:<número>», estados válidos;
  2. ida y vuelta sin traducciones: construir() y releer() devuelven exactamente los mismos textos originales;
  3. con traducciones: lo «traducido» aparece en el juego; lo que está en «revisar» (no se aplica por defecto) y una fila con
     el hash cambiado (de otra versión del juego) no, y esta última se informa como error.
Los pasos 2 y 3 necesitan Motor.releer(juego, salida); con exigir_releer=False, un motor que no lo tiene solo hace el 1.
"""
import copy
import os

from ..nucleo import hojas
from .base import ESTADOS_LISTOS


def _ok(t):
    return isinstance(t, str)


def verificar(motor, juego, trabajo, traduccion=lambda fila: "Prueba 123", opciones=None, exigir_releer=True):
    """-> lista de problemas (vacía si el motor cumple)."""
    p = []
    datos = list(motor.textos(juego))
    if not any(filas for _g, _e, filas in datos):
        return ["textos() no devolvió ninguna fila"]
    claves = set()
    filas_por_esc = {}
    for grupo, esc, filas in datos:
        if not grupo or not esc:
            p.append(f"grupo o escenario vacío: {grupo!r} / {esc!r}")
        for f in filas:
            faltan = [c for c in hojas.COLUMNS if c not in f]
            if faltan:
                p.append(f"{f.get('clave')}: faltan columnas {faltan}"); continue
            if f["clave"] in claves:
                p.append(f"{f['clave']}: clave repetida")
            claves.add(f["clave"])
            if not str(f["clave"]).startswith(f"{esc}:"):
                p.append(f"{f['clave']}: la clave tiene que empezar con «{esc}:»")
            if f["estado"] not in hojas.ESTADOS:
                p.append(f"{f['clave']}: estado inválido {f['estado']!r}")
            if not _ok(f["original"]) or not f["original"]:
                p.append(f"{f['clave']}: original vacío o que no es texto")
        if filas:
            filas_por_esc[esc] = filas
    if p:
        return p
    try:
        list(motor.releer(juego, os.path.join(trabajo, "_vacia")))
    except NotImplementedError:
        return ["el motor no implementa releer(): sin él no se puede verificar la ida y vuelta"] if exigir_releer else []

    def releer(salida):
        return {f["clave"]: f["original"] for _g, _e, filas in motor.releer(juego, salida) for f in filas}

    originales = {f["clave"]: f["original"] for filas in filas_por_esc.values() for f in filas}
    # 2) sin traducciones
    s1 = os.path.join(trabajo, "contrato-sin-traducir")
    motor.construir(juego, s1, copy.deepcopy(filas_por_esc), None, ESTADOS_LISTOS, opciones or {}, None, None, lambda *a: None)
    vuelta = releer(s1)
    distintas = [k for k in originales if vuelta.get(k) != originales[k]]
    if distintas:
        p.append(f"ida y vuelta sin traducciones: {len(distintas)} textos distintos (por ejemplo {distintas[0]}: "
                 f"{originales[distintas[0]]!r} -> {vuelta.get(distintas[0])!r})")
    # 3) con traducciones: en cada escenario, la 1.ª fila traducida, la 2.ª en «revisar», la 3.ª con hash de otra versión
    filas = copy.deepcopy(filas_por_esc)
    esperado, hash_malo = {}, []
    for esc, fs in filas.items():
        for i, f in enumerate(fs[:3]):
            f["traduccion"] = traduccion(f)
            if i == 0:
                f["estado"] = "traducido"; esperado[f["clave"]] = f["traduccion"]
            elif i == 1:
                f["estado"] = "revisar"
            else:
                f["estado"], f["hash"] = "traducido", "00000000"; hash_malo.append(f["clave"])
    s2 = os.path.join(trabajo, "contrato-traducido")
    rep = motor.construir(juego, s2, filas, None, ESTADOS_LISTOS, opciones or {}, None, None, lambda *a: None)
    vuelta = releer(s2)
    for k, t in esperado.items():
        if vuelta.get(k) != t:
            p.append(f"{k}: se esperaba la traducción {t!r} y el juego muestra {vuelta.get(k)!r}")
    for k in set(originales) - set(esperado):
        if vuelta.get(k) != originales[k]:
            p.append(f"{k}: no se tenía que aplicar (revisar, hash de otra versión o sin traducir) y cambió a {vuelta.get(k)!r}")
    errores = {k for k, _ in ((rep or {}).get("texto") or {}).get("errores", [])}
    for k in hash_malo:
        if not any(k in e for e in errores):
            p.append(f"{k}: una fila con el hash de otra versión del juego tiene que informarse como error")
    return p

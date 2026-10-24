# SPDX-License-Identifier: GPL-3.0-or-later
"""Registro de motores.

Los motores incluidos están en INCLUIDOS.  Cualquier paquete instalado puede agregar el suyo declarando un entry point:

    [project.entry-points."tl_organizer.motores"]
    mimotor = "mipaquete:MiMotor"

(si el nombre coincide con uno incluido, gana el incluido).  Los módulos se importan recién cuando se piden.
"""
from importlib import import_module
from importlib.metadata import entry_points

from .base import Motor, MotorError

GRUPO = "tl_organizer.motores"
INCLUIDOS = {
    "bgi": "tl_organizer.motores.bgi:MotorBGI",
}


def disponibles():
    """{nombre: referencia «módulo:Clase»} de todos los motores: los incluidos y los instalados como plugins."""
    refs = {ep.name: ep.value for ep in entry_points(group=GRUPO)}
    refs.update(INCLUIDOS)
    return dict(sorted(refs.items()))


def clase(nombre):
    ref = disponibles().get(nombre)
    if ref is None:
        raise MotorError(f"motor desconocido «{nombre}»; disponibles: {', '.join(disponibles())}")
    mod, _, attr = ref.partition(":")
    try:
        cls = getattr(import_module(mod), attr)
    except (ImportError, AttributeError) as e:
        raise MotorError(f"no se pudo cargar el motor «{nombre}» ({ref}): {e}")
    if not (isinstance(cls, type) and issubclass(cls, Motor)):
        raise MotorError(f"«{ref}» no es una subclase de Motor")
    return cls


def clases():
    """[(nombre, clase)] de los motores que se pueden cargar (los que fallan se omiten)."""
    out = []
    for nombre in disponibles():
        try:
            out.append((nombre, clase(nombre)))
        except MotorError:
            pass
    return out


def crear(perfil):
    """El motor del perfil, listo para usar."""
    return clase(perfil.motor)(perfil)

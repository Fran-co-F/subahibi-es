# SPDX-License-Identifier: GPL-3.0-or-later
"""Comandos sueltos del motor BGI: patch-exe, images export/import, text export/import.

Con un proyecto BGI usan su perfil (versiones del exe, .arc de texto e imágenes, fuente); sin proyecto, los valores
por defecto del motor y las versiones de exe de todos los perfiles BGI.
"""
import os
import sys

from ...nucleo import config, perfiles, proyecto as project
from ...nucleo.config import lista, need
from . import exe_patch


def _motor():
    """El motor del proyecto si es BGI; si no, uno genérico con las versiones de exe de todos los perfiles BGI."""
    from . import MotorBGI
    proj = project.find()
    if proj is not None and proj.perfil.motor == MotorBGI.nombre:
        return proj.motor
    builds, fuentes = {}, {}
    for p in perfiles.buscar():
        if p.motor == MotorBGI.nombre:
            m = MotorBGI(p)
            for sha, b in m.builds.items():
                builds.setdefault(sha, b)
                fuentes.setdefault(sha, m.fuente)
    m = MotorBGI(perfiles.Perfil({"id": "bgi", "nombre": "juego BGI", "motor": MotorBGI.nombre}))
    m.builds, m.fuentes_por_exe = builds, fuentes
    return m


def _arc_paths(game, names):
    out = []
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(game, n if n.endswith(".arc") else n + ".arc")
        if not os.path.exists(p):
            sys.exit(f"no existe {p}")
        out.append(p)
    return out


def cmd_patch_exe(a):
    if not a.verify and not a.dry_run and not a.salida:
        a._parser.error("patch-exe necesita 'salida' (o --verify / --dry-run)")
    with open(a.entrada, "rb") as f:
        data = f.read()
    m = _motor()
    h, b = exe_patch.identify(data, m.builds)
    if a.verify:
        print(f"sha256 {h}")
        print("versión:", b["version"] if b else "desconocida")
        print("parcheado:", "sí" if exe_patch.is_patched(data, m.builds) else "no")
        return 0 if b else 1
    fuente = a.fuente or getattr(m, "fuentes_por_exe", {}).get(h) or m.fuente
    try:
        out = exe_patch.patch(data, m.builds, font=not a.sin_fuente,
                              proportional=not a.sin_proporcional and bool(b) and exe_patch.tiene_proporcional(b),
                              utf8=not a.katakana and bool(b) and exe_patch.tiene_utf8(b), font_name=fuente)
    except exe_patch.PatchError as e:
        sys.exit(f"error: {e}")
    if a.dry_run:
        print("ok (no se escribió nada):", b["version"])
        return 0
    with open(a.salida, "wb") as f:
        f.write(out)
    print("escrito", a.salida, "sha256", exe_patch.sha256(out))
    return 0


def cmd_images_export(a):
    from .images import export
    juego = need(a.juego, "juego", "la carpeta del juego")
    salida = need(a.salida, "originales", "la carpeta de salida")
    total = 0
    for p in _arc_paths(juego, a.arc or _motor().ui_arcs):
        n, skipped = export.export_arc(p, salida)
        total += n
        print(f"{os.path.basename(p)}: {n} imágenes exportadas, {len(skipped)} omitidas")
        for name, why in skipped[:5]:
            print("   omitida:", name, "-", why)
    print("total:", total, "->", salida)
    return 0


def cmd_images_import(a):
    from .images import import_
    juego = need(a.juego, "juego", "la carpeta del juego")
    salida = need(a.salida, "juego_es", "la carpeta de salida")
    placed, warns, errs = import_.import_images(need(a.origen, "imagenes", "la carpeta de imágenes traducidas"),
                                                _arc_paths(juego, a.arc or _motor().ui_arcs), salida)
    for n, w in warns:
        print("aviso:", n, "-", w)
    for n, e in errs:
        print("ERROR:", n, "-", e)
    print(f"{len(placed)} colocadas en {os.path.join(salida, import_.LOOSE_DIR)}; {len(errs)} con error")
    return 1 if errs else 0


def cmd_text_export(a):
    from ...nucleo import texto
    cfg = config.load()
    juego = need(a.juego, "juego", "la carpeta del juego")
    salida = a.salida or "texto"
    m = _motor()
    r = texto.exportar(m.textos(juego, a.parche_viejo or cfg.get("parche_viejo"), a.arc), salida, tsv=a.tsv, xlsx=not a.sin_xlsx,
                       idiomas=cfg["idiomas"])
    print(f"{r['scripts']} escenarios en {r['arcs']} .arc -> {r['filas']} filas "
          f"({r['precargadas']} precargadas desde la traducción vieja) en {salida}; "
          f"{len(r['sin_texto'])} escenarios sin texto no tienen hoja")
    return 0


def cmd_text_import(a):
    from ...nucleo import texto
    from .text import import_
    if a.hojas:
        filas = texto.recolectar(a.hojas)
    else:
        from ...nucleo import flujo
        proj = project.require()
        flujo.sincronizar(proj)
        filas = proj.almacen.filas_por_escenario()
    m = _motor()
    r = import_.apply_rows(need(a.juego, "juego", "la carpeta del juego"), filas, need(a.salida, "juego_es", "la carpeta de salida"),
                           lista(a.estados), m.utf8 and not a.katakana, m.data_arcs)
    for k, v in r["errores"][:30]:
        print("ERROR:", k, "-", v)
    if len(r["errores"]) > 30:
        print(f"... y {len(r['errores']) - 30} errores más")
    print(f"{r['scripts']} escenarios escritos, {r['cambiadas']} textos cambiados, "
          f"{r['omitidas']} filas omitidas por su estado, {len(r['errores'])} errores")
    return 1 if r["errores"] else 0


def registrar(sub, grupos):
    p = sub.add_parser("patch-exe", help="(suelto, BGI) parchea una copia del exe")
    p.add_argument("entrada"); p.add_argument("salida", nargs="?")
    p.add_argument("--verify", action="store_true", help="solo informa versión y si ya está parcheado")
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--sin-fuente", action="store_true")
    p.add_argument("--sin-proporcional", action="store_true")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.add_argument("--fuente", metavar="NOMBRE", help="nombre de la fuente (ASCII, hasta 15 caracteres; debe estar instalada); "
                   "por defecto, la del perfil del juego")
    p.set_defaults(f=cmd_patch_exe, _parser=p)

    im = grupos["images"]
    p = im.add_parser("export", help="(BGI) exporta los .arc a PNG")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?")
    p.add_argument("--arc", nargs="+", help="por defecto, los del perfil (sysgrp)")
    p.set_defaults(f=cmd_images_export)
    p = im.add_parser("import", help="(BGI) coloca imágenes traducidas en Graphic/CVTD")
    p.add_argument("origen", nargs="?"); p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?")
    p.add_argument("--arc", nargs="+", help="por defecto, los del perfil (sysgrp)"); p.set_defaults(f=cmd_images_import)

    tx = grupos["text"]
    p = tx.add_parser("export", help="(BGI) exporta el texto a hojas XLSX (una por .arc, una hoja por script)")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?", help="por defecto, «texto» en la carpeta actual")
    p.add_argument("--arc", nargs="+", help="solo estos .arc (por defecto, los del perfil: data0*.arc)")
    p.add_argument("--parche-viejo", metavar="ZIP_O_CARPETA", help="traducción vieja: precarga el español; por defecto, la del proyecto")
    p.add_argument("--tsv", action="store_true", help="además, un TSV por script (para git/diff)")
    p.add_argument("--sin-xlsx", action="store_true"); p.set_defaults(f=cmd_text_export)

    p = tx.add_parser("import", help="(BGI) arma los escenarios del juego con el español de las hojas")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?", help="carpeta donde escribe Script/CVTD/")
    p.add_argument("hojas", nargs="*", help=".xlsx / .tsv o carpetas con ellos (por defecto, la traducción del proyecto)")
    p.add_argument("--estados", default="traducido,del parche",
                   help="estados que se aplican (por defecto: traducido,del parche; agregar 'revisar' para probar todo)")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.set_defaults(f=cmd_text_import)

# SPDX-License-Identifier: GPL-3.0-or-later
"""Interfaz de línea de comandos: subahibi-es <comando>."""
import argparse
import os
import sys

from . import config, exe_patch


def _arc_paths(game, names):
    out = []
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(game, n if n.endswith(".arc") else n + ".arc")
        if not os.path.exists(p):
            sys.exit(f"no existe {p}")
        out.append(p)
    return out


def need(value, key, what):
    """Argumento de la línea de comandos o, si falta, el de la configuración (subahibi-es.json)."""
    v = value or config.load().get(key)
    if not v:
        sys.exit(f"falta {what}: indicalo o guardalo con «subahibi-es init --{key.replace('_', '-')} RUTA»")
    return v


def cmd_init(a):
    cfg = config.save(dict(juego=a.juego, juego_es=a.juego_es, parche_viejo=a.parche_viejo,
                           imagenes=a.imagenes, texto=a.texto))
    print("configuración en", config.path())
    for k in config.KEYS:
        print(f"  {k:13} {cfg.get(k, '(sin definir)')}")
    return 0


def cmd_build(a):
    from . import build
    r = build.build(need(a.juego, "juego", "la carpeta del juego"), need(a.salida, "juego_es", "la carpeta de salida"),
                    a.parche_viejo or config.load().get("parche_viejo"), a.texto or config.load().get("texto"),
                    a.imagenes or config.load().get("imagenes"),
                    tuple(x.strip() for x in a.estados.split(",")), not a.sin_voz, not a.katakana, a.fuente)
    print(f"{r['enlaces']} archivos enlazados; BGI.exe parcheado")
    if "sueltos" in r:
        print(f"{r['sueltos']} archivos sueltos del parche viejo ({r['omitidos_ui_vieja']} imágenes de la interfaz vieja omitidas)")
    t = r["texto"]
    if t:
        for k, v in t["errores"][:20]:
            print("ERROR:", k, "-", v)
        print(f"{t['scripts']} escenarios generados, {t['cambiadas']} textos, {len(t['errores'])} errores"
              + (f", {t['sin_convertir']} cadenas que no se pudieron pasar a UTF-8" if t.get("sin_convertir") else ""))
    if "imagenes" in r:
        im = r["imagenes"]
        for n, e in im["errores"]:
            print("ERROR imagen:", n, "-", e)
        print(f"{im['colocadas']} imágenes traducidas colocadas")
    return 0


def cmd_patch_exe(a):
    data = open(a.entrada, "rb").read()
    h, b = exe_patch.identify(data)
    if a.verify:
        print(f"sha256 {h}")
        print("versión:", b["version"] if b else "desconocida")
        print("parcheado:", "sí" if exe_patch.is_patched(data) else "no")
        return 0 if b else 1
    try:
        out = exe_patch.patch(data, font=not a.sin_fuente, proportional=not a.sin_proporcional, utf8=not a.katakana, font_name=a.fuente)
    except exe_patch.PatchError as e:
        sys.exit(f"error: {e}")
    if a.dry_run:
        print("ok (no se escribió nada):", b["version"]); return 0
    open(a.salida, "wb").write(out)
    print("escrito", a.salida, "sha256", exe_patch.sha256(out))
    return 0


def cmd_images_export(a):
    from .images import export
    total = 0
    for p in _arc_paths(a.juego, a.arc):
        n, skipped = export.export_arc(p, a.salida)
        total += n
        print(f"{os.path.basename(p)}: {n} imágenes exportadas, {len(skipped)} omitidas")
        for name, why in skipped[:5]:
            print("   omitida:", name, "-", why)
    print("total:", total, "->", a.salida)
    return 0


def cmd_images_index(a):
    from .images import index
    cnt = index.build(a.originales, a.traducidas, a.salida, a.estado, a.ocr)
    for k, v in sorted(cnt.items()):
        print(f"{k:15} {v}")
    print("índice:", os.path.join(a.salida, "index.html"))
    return 0


def cmd_images_import(a):
    from .images import import_
    placed, warns, errs = import_.import_images(a.origen, _arc_paths(a.juego, a.arc), a.salida)
    for n, w in warns:
        print("aviso:", n, "-", w)
    for n, e in errs:
        print("ERROR:", n, "-", e)
    print(f"{len(placed)} colocadas en {os.path.join(a.salida, import_.LOOSE_DIR)}; {len(errs)} con error")
    return 1 if errs else 0


def cmd_text_export(a):
    from .text import export
    cfg = config.load()
    juego = need(a.juego, "juego", "la carpeta del juego")
    salida = a.salida or cfg.get("texto") or "trabajo/texto"
    r = export.export_text(juego, salida, a.arc, a.parche_viejo or cfg.get("parche_viejo"), tsv=a.tsv, xlsx=not a.sin_xlsx)
    a.salida = salida
    print(f"{r['scripts']} escenarios en {r['arcs']} .arc -> {r['filas']} filas "
          f"({r['precargadas']} precargadas desde la traducción vieja) en {a.salida}")
    return 0


def cmd_text_import(a):
    from .text import import_
    estados = tuple(x.strip() for x in a.estados.split(","))
    cfg = config.load()
    r = import_.import_text(need(a.juego, "juego", "la carpeta del juego"), a.hojas or [need(None, "texto", "las hojas")],
                            need(a.salida, "juego_es", "la carpeta de salida"), estados, not a.katakana)
    for k, v in r["errores"][:30]:
        print("ERROR:", k, "-", v)
    if len(r["errores"]) > 30:
        print(f"... y {len(r['errores']) - 30} errores más")
    print(f"{r['scripts']} escenarios escritos, {r['cambiadas']} textos cambiados, "
          f"{r['omitidas']} filas omitidas por su estado, {len(r['errores'])} errores")
    return 1 if r["errores"] else 0


def cmd_text_wrap(a):
    import shutil
    from .text import sheet, wrap
    if not (a.max_caracteres or a.ancho):
        sys.exit("indicá --max-caracteres N y/o --ancho PX (con --fuente y --tamano)")
    fits = wrap.make_fits(a.max_caracteres, a.ancho, a.fuente, a.tamano)
    estados = tuple(x.strip() for x in a.estados.split(","))
    files = []
    for p in a.hojas or [need(None, "texto", "las hojas")]:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.lower().endswith(".xlsx")]
        else:
            files.append(p)
    tot_c = tot_o = 0
    for f in files:
        dst = os.path.join(a.salida, os.path.basename(f)) if a.salida else f
        if a.salida:
            os.makedirs(a.salida, exist_ok=True)
        elif not a.sin_copia and not os.path.exists(f + ".bak"):
            shutil.copy2(f, f + ".bak")
        if f.lower().endswith(".xlsx"):
            sheets = sheet.read_xlsx(f)
            for rows in sheets.values():
                c, o = wrap.wrap_rows(rows, fits, estados, a.reflow, a.max_lineas); tot_c += c; tot_o += o
            sheet.write_xlsx(dst, sheets)
        else:
            rows = sheet.read_tsv(f)
            c, o = wrap.wrap_rows(rows, fits, estados, a.reflow, a.max_lineas); tot_c += c; tot_o += o
            sheet.write_tsv(dst, rows)
    print(f"{tot_c} textos con saltos de línea nuevos en {len(files)} archivo(s)"
          + (f"; {tot_o} con más de {a.max_lineas} líneas (marcados en «nota»)" if a.max_lineas else "")
          + ("" if a.salida or a.sin_copia else "; copia de seguridad: <archivo>.bak"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="subahibi-es", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("patch-exe", help="parchea BGI.exe (fuente y modo proporcional)")
    p.add_argument("entrada"); p.add_argument("salida", nargs="?")
    p.add_argument("--verify", action="store_true", help="solo informa versión y si ya está parcheado")
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--sin-fuente", action="store_true")
    p.add_argument("--sin-proporcional", action="store_true")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.add_argument("--fuente", default="SubaHibi07Inq", metavar="NOMBRE", help="nombre de la fuente que usa el juego (ASCII, hasta 15 caracteres; debe estar instalada)")
    p.set_defaults(f=cmd_patch_exe)

    im = sub.add_parser("images", help="imágenes de interfaz").add_subparsers(dest="sub", required=True)
    p = im.add_parser("export", help="exporta los .arc a PNG")
    p.add_argument("juego"); p.add_argument("salida"); p.add_argument("--arc", nargs="+", default=["sysgrp"])
    p.set_defaults(f=cmd_images_export)
    p = im.add_parser("index", help="índice HTML/CSV: original vs traducida y qué falta")
    p.add_argument("originales"); p.add_argument("traducidas"); p.add_argument("salida")
    p.add_argument("--estado", help="TSV de decisiones manuales"); p.add_argument("--ocr", action="store_true")
    p.set_defaults(f=cmd_images_index)
    p = im.add_parser("import", help="coloca imágenes traducidas en Graphic/CVTD")
    p.add_argument("origen"); p.add_argument("juego"); p.add_argument("salida")
    p.add_argument("--arc", nargs="+", default=["sysgrp"]); p.set_defaults(f=cmd_images_import)

    tx = sub.add_parser("text", help="texto de los escenarios").add_subparsers(dest="sub", required=True)
    p = tx.add_parser("export", help="exporta el texto a hojas XLSX (una por .arc, una hoja por script)")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?", help="por defecto: «texto» de la configuración o trabajo/texto")
    p.add_argument("--arc", nargs="+", help="solo estos .arc (por defecto, todos los data0*.arc)")
    p.add_argument("--parche-viejo", metavar="CARPETA", help="traducción vieja: el .zip del parche o una carpeta (precarga el español); por defecto, la de la configuración")
    p.add_argument("--tsv", action="store_true", help="además, un TSV por script (para git/diff)")
    p.add_argument("--sin-xlsx", action="store_true"); p.set_defaults(f=cmd_text_export)

    p = tx.add_parser("import", help="arma los escenarios del juego con el español de las hojas")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?", help="carpeta del juego en español (escribe Script/CVTD/)")
    p.add_argument("hojas", nargs="*", help=".xlsx / .tsv o carpetas con ellos (por defecto, «texto» de la configuración)")
    p.add_argument("--estados", default="traducido,del parche",
                   help="estados que se aplican (por defecto: traducido,del parche; agregar 'revisar' para probar todo)")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio (usar con el exe parcheado con --katakana)")
    p.set_defaults(f=cmd_text_import)

    p = sub.add_parser("init", help="guarda las rutas del proyecto en subahibi-es.json (las demás órdenes las usan por defecto)")
    for k in config.KEYS:
        p.add_argument("--" + k.replace("_", "-"), metavar="RUTA", help=k)
    p.set_defaults(f=cmd_init)

    p = sub.add_parser("build", help="arma la carpeta del juego en español (enlaces, exe parcheado, sueltos, escenarios, imágenes)")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?")
    p.add_argument("--parche-viejo", metavar="ZIP_O_CARPETA"); p.add_argument("--texto", metavar="CARPETA", help="hojas ya traducidas (si no, se usa el español del parche viejo)")
    p.add_argument("--imagenes", metavar="CARPETA", help="imágenes traducidas (PNG/BMP) a colocar")
    p.add_argument("--estados", default="traducido,del parche", help="estados que se aplican (por defecto traducido,del parche)")
    p.add_argument("--sin-voz", action="store_true", help="no copiar Voice/CVTD del parche viejo")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.add_argument("--fuente", default="SubaHibi07Inq", metavar="NOMBRE", help="nombre de la fuente del juego (ASCII, hasta 15 caracteres)")
    p.set_defaults(f=cmd_build)

    p = tx.add_parser("wrap", help="inserta saltos de línea manuales en las hojas, cortando en límites de palabra")
    p.add_argument("hojas", nargs="*", help=".xlsx / .tsv o carpetas (por defecto, «texto» de la configuración)")
    p.add_argument("--max-caracteres", type=int, metavar="N", help="largo máximo de línea en caracteres")
    p.add_argument("--ancho", type=int, metavar="PX", help="ancho máximo en píxeles (medido con --fuente y --tamano)")
    p.add_argument("--fuente", metavar="TTF"); p.add_argument("--tamano", type=int, metavar="PX")
    p.add_argument("--max-lineas", type=int, metavar="M", help="solo avisa: anota en «nota» los textos que pasen de M líneas")
    p.add_argument("--estados", default="traducido,del parche,revisar", help="estados a procesar")
    p.add_argument("--reflow", action="store_true", help="primero descarta los saltos manuales existentes y vuelve a cortar")
    p.add_argument("--salida", metavar="CARPETA", help="escribir las hojas nuevas acá (por defecto, en el lugar con copia .bak)")
    p.add_argument("--sin-copia", action="store_true"); p.set_defaults(f=cmd_text_wrap)

    a = ap.parse_args(argv)
    if a.cmd == "patch-exe" and not a.verify and not a.dry_run and not a.salida:
        ap.error("patch-exe necesita 'salida' (o --verify / --dry-run)")
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())

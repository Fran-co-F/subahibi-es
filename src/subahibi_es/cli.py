# SPDX-License-Identifier: GPL-3.0-or-later
"""Interfaz de línea de comandos: subahibi-es <comando>.

Flujo normal (dentro de la carpeta de instalación del juego):  init -> exportar -> (traducir) -> build -> instalar.
"""
import argparse
import glob
import os
import shutil
import sys

from . import config, exe_patch, project, workflow


# ---------------------------------------------------------------- utilidades

def _arc_paths(game, names):
    out = []
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(game, n if n.endswith(".arc") else n + ".arc")
        if not os.path.exists(p):
            sys.exit(f"no existe {p}")
        out.append(p)
    return out


def need(value, key, what):
    """Argumento de la línea de comandos o, si falta, el valor del proyecto (ver config.py)."""
    v = value or config.load().get(key)
    if not v:
        sys.exit(f"falta {what}: indicalo, o ejecutá «subahibi-es init» dentro de la carpeta de instalación del juego")
    return v


def _estados(texto):
    return tuple(x.strip() for x in texto.split(","))


# ---------------------------------------------------------------- comandos del proyecto

def cmd_init(a):
    proj, creado = project.init(a.carpeta or os.getcwd(), a.parche_viejo)
    if not creado:
        print(f"parche viejo actualizado: {proj.parche_viejo}")
        return 0
    print(f"proyecto creado en {proj.root}")
    print(f"  juego detectado:    {proj.cfg['motor']}")
    print(f"  carpeta de trabajo: {os.path.join(proj.root, project.WORK)}")
    print(f"  parche viejo:       {proj.parche_viejo or '(sin configurar; agregalo con «subahibi-es init --parche-viejo ARCHIVO.zip»)'}")
    print("  copia del BGI.exe original guardada en la carpeta de trabajo (backup)")
    print("\nsiguiente paso:  subahibi-es exportar")
    return 0


def cmd_estado(a):
    workflow.estado(project.require())
    return 0


def cmd_exportar(a):
    workflow.exportar(project.require(), forzar=a.forzar, ocr=a.ocr)
    proj = project.require()
    print("\nahora podés traducir:")
    print(f"  - texto:      abrí las hojas de {proj.dir('texto')} (LibreOffice, Excel…) y completá la columna «espanol»")
    print(f"  - imágenes:   abrí {os.path.join(proj.dir('indice'), 'index.html')} en el navegador; guardá las traducidas en {proj.dir('traducidas')}")
    print("cuando termines (o para probar):  subahibi-es build")
    return 0


def cmd_build(a):
    from . import build
    proj = project.require()
    exe = proj.original_exe()
    out = a.salida or (proj.dir("jugable") if a.jugable else proj.dir("salida"))
    if not a.salida and not a.jugable and os.path.isdir(out):
        shutil.rmtree(out)                     # la carpeta «salida» es solo nuestra: se rehace entera
    texto = proj.dir("texto") if glob.glob(os.path.join(proj.dir("texto"), "*.xlsx")) else None
    imagenes = proj.dir("traducidas") if os.path.isdir(proj.dir("traducidas")) and os.listdir(proj.dir("traducidas")) else None
    r = build.build(proj.root, out, proj.parche_viejo, texto, imagenes, _estados(a.estados), not a.sin_voz,
                    not a.katakana, a.fuente, full=a.jugable, exe=exe)
    print(f"BGI.exe parcheado (fuente «{a.fuente}»" + (", modo UTF-8" if not a.katakana else ", modo katakana") + ")")
    if a.jugable:
        mt = ", ".join(f"{v} por {k}" for k, v in r["metodos_enlace"].items())
        print(f"{r['enlaces']} archivos del juego enlazados ({mt})")
        if "copia" in r["metodos_enlace"]:
            print("aviso: se copiaron archivos porque no se pudo enlazar: ocupan espacio extra en disco "
                  "(en Windows, activá el modo desarrollador para usar enlaces simbólicos)")
    if "sueltos" in r:
        print(f"{r['sueltos']} archivos sueltos del parche viejo ({r['omitidos_ui_vieja']} imágenes de la interfaz vieja omitidas)")
    t = r["texto"]
    if t:
        for k, v in t["errores"][:20]:
            print("ERROR:", k, "-", v)
        print(f"{t['scripts']} escenarios generados, {t['cambiadas']} textos traducidos, {len(t['errores'])} errores"
              + (f"; {t['omitidas']} filas no se aplicaron por su estado (usá --estados para incluirlas)" if t["omitidas"] else "")
              + (f"; {t['sin_convertir']} cadenas que no se pudieron pasar a UTF-8" if t.get("sin_convertir") else ""))
    if "imagenes" in r:
        im = r["imagenes"]
        for n, e in im["errores"]:
            print("ERROR imagen:", n, "-", e)
        print(f"{im['colocadas']} imágenes traducidas colocadas")
    print(f"\nlisto: {out}")
    if a.jugable:
        print("es una carpeta de prueba con enlaces a los archivos del juego: se ejecuta tal cual, sin tocar la instalación")
    else:
        print("lo que hay que copiar al juego está ahí: copiá su contenido sobre la carpeta de instalación\n"
              "(o ejecutá «subahibi-es instalar», que lo hace y guarda copia de lo que pisa)")
    return 0


def cmd_instalar(a):
    workflow.instalar(project.require())
    return 0


def cmd_desinstalar(a):
    workflow.desinstalar(project.require())
    return 0


def cmd_reset(a):
    proj = project.require()
    if os.path.exists(os.path.join(proj.dir("backup"), "instalado.json")) and not a.forzar:
        sys.exit("el parche está instalado en el juego: ejecutá primero «subahibi-es desinstalar» (o usá --forzar)")
    if a.todo and not a.si:
        work = os.path.join(proj.root, project.WORK)
        print(f"se va a BORRAR la carpeta de trabajo {work}")
        print("incluye las hojas de texto, las imágenes traducidas y los respaldos. Los archivos del juego no se tocan.")
        if not sys.stdin.isatty() or input("escribí SI para continuar: ").strip() != "SI":
            sys.exit("cancelado")
    removed = project.reset(proj, todo=a.todo)
    for r in removed:
        print("borrado:", r)
    if not a.todo:
        print(f"la carpeta de trabajo ({project.WORK}) se conserva; para borrarla también: «subahibi-es reset --todo»")
    return 0


# ---------------------------------------------------------------- comandos sueltos (usan el proyecto como valor por defecto)

def cmd_patch_exe(a):
    with open(a.entrada, "rb") as f:
        data = f.read()
    h, b = exe_patch.identify(data)
    if a.verify:
        print(f"sha256 {h}")
        print("versión:", b["version"] if b else "desconocida")
        print("parcheado:", "sí" if exe_patch.is_patched(data) else "no")
        return 0 if b else 1
    try:
        out = exe_patch.patch(data, font=not a.sin_fuente, proportional=not a.sin_proporcional,
                              utf8=not a.katakana, font_name=a.fuente)
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
    for p in _arc_paths(juego, a.arc):
        n, skipped = export.export_arc(p, salida)
        total += n
        print(f"{os.path.basename(p)}: {n} imágenes exportadas, {len(skipped)} omitidas")
        for name, why in skipped[:5]:
            print("   omitida:", name, "-", why)
    print("total:", total, "->", salida)
    return 0


def cmd_images_generar(a):
    from .images import generate, render
    if not render.fonts_available():
        sys.exit("falta una fuente latina: instalá Noto Sans o DejaVu, o definí SUBAHIBI_FONT=/ruta/fuente.ttf")
    n = generate.generate(need(a.originales, "originales", "la carpeta de PNG originales"),
                          need(a.salida, "imagenes", "la carpeta de salida"))
    print(f"{n} imágenes generadas en {need(a.salida, 'imagenes', '')}")
    return 0


def cmd_images_index(a):
    from .images import index
    salida = need(a.salida, "indice", "la carpeta de salida")
    cnt = index.build(need(a.originales, "originales", "la carpeta de PNG originales"),
                      need(a.traducidas, "imagenes", "la carpeta de imágenes traducidas"), salida,
                      a.estado or config.load().get("estado"), a.ocr)
    for k, v in sorted(cnt.items()):
        print(f"{k:15} {v}")
    print("índice:", os.path.join(salida, "index.html"))
    return 0


def cmd_images_import(a):
    from .images import import_
    juego = need(a.juego, "juego", "la carpeta del juego")
    salida = need(a.salida, "juego_es", "la carpeta de salida")
    placed, warns, errs = import_.import_images(need(a.origen, "imagenes", "la carpeta de imágenes traducidas"),
                                                _arc_paths(juego, a.arc), salida)
    for n, w in warns:
        print("aviso:", n, "-", w)
    for n, e in errs:
        print("ERROR:", n, "-", e)
    print(f"{len(placed)} colocadas en {os.path.join(salida, import_.LOOSE_DIR)}; {len(errs)} con error")
    return 1 if errs else 0


def cmd_text_export(a):
    from .text import export
    cfg = config.load()
    juego = need(a.juego, "juego", "la carpeta del juego")
    salida = a.salida or cfg.get("texto") or "texto"
    r = export.export_text(juego, salida, a.arc, a.parche_viejo or cfg.get("parche_viejo"), tsv=a.tsv, xlsx=not a.sin_xlsx)
    print(f"{r['scripts']} escenarios en {r['arcs']} .arc -> {r['filas']} filas "
          f"({r['precargadas']} precargadas desde la traducción vieja) en {salida}")
    return 0


def cmd_text_import(a):
    from .text import import_
    r = import_.import_text(need(a.juego, "juego", "la carpeta del juego"), a.hojas or [need(None, "texto", "las hojas")],
                            need(a.salida, "juego_es", "la carpeta de salida"), _estados(a.estados), not a.katakana)
    for k, v in r["errores"][:30]:
        print("ERROR:", k, "-", v)
    if len(r["errores"]) > 30:
        print(f"... y {len(r['errores']) - 30} errores más")
    print(f"{r['scripts']} escenarios escritos, {r['cambiadas']} textos cambiados, "
          f"{r['omitidas']} filas omitidas por su estado, {len(r['errores'])} errores")
    return 1 if r["errores"] else 0


def cmd_text_wrap(a):
    from .text import sheet, wrap
    if not (a.max_caracteres or a.ancho):
        sys.exit("indicá --max-caracteres N y/o --ancho PX (con --fuente y --tamano)")
    fits = wrap.make_fits(a.max_caracteres, a.ancho, a.fuente, a.tamano)
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
                c, o = wrap.wrap_rows(rows, fits, _estados(a.estados), a.reflow, a.max_lineas)
                tot_c += c
                tot_o += o
            sheet.write_xlsx(dst, sheets)
        else:
            rows = sheet.read_tsv(f)
            c, o = wrap.wrap_rows(rows, fits, _estados(a.estados), a.reflow, a.max_lineas)
            tot_c += c
            tot_o += o
            sheet.write_tsv(dst, rows)
    print(f"{tot_c} textos con saltos de línea nuevos en {len(files)} archivo(s)"
          + (f"; {tot_o} con más de {a.max_lineas} líneas (marcados en «nota»)" if a.max_lineas else "")
          + ("" if a.salida or a.sin_copia else "; copia de seguridad: <archivo>.bak"))
    return 0


# ---------------------------------------------------------------- argumentos

def _parser():
    ap = argparse.ArgumentParser(prog="subahibi-es", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="comando")

    p = sub.add_parser("init", help="crea el proyecto en la carpeta de instalación del juego")
    p.add_argument("carpeta", nargs="?", help="carpeta de instalación del juego (por defecto, la actual)")
    p.add_argument("--parche-viejo", metavar="ARCHIVO.zip", help="el parche en español anterior (.zip o carpeta): precarga el texto y trae voces/gráficos sueltos")
    p.set_defaults(f=cmd_init)

    p = sub.add_parser("estado", help="muestra el proyecto y el avance de la traducción")
    p.set_defaults(f=cmd_estado)

    p = sub.add_parser("exportar", help="vuelca todo lo que hay que traducir (imágenes, galería, hojas de texto)")
    p.add_argument("--forzar", action="store_true", help="exportar de nuevo aunque ya haya hojas (se guarda una copia de las anteriores)")
    p.add_argument("--ocr", action="store_true", help="la galería usa OCR (Tesseract) como pista de qué imágenes tienen japonés")
    p.set_defaults(f=cmd_exportar)

    p = sub.add_parser("build", help="crea en «salida» lo que hay que copiar al juego")
    p.add_argument("--estados", default="traducido,del parche", help="estados que se aplican (por defecto traducido,del parche; agregá «revisar» para probar todo)")
    p.add_argument("--sin-voz", action="store_true", help="no incluir Voice/CVTD del parche viejo")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.add_argument("--fuente", default=exe_patch.DEFAULT_FONT, metavar="NOMBRE", help="nombre de la fuente del juego (ASCII, hasta 15 caracteres; debe estar instalada)")
    p.add_argument("--jugable", action="store_true", help="arma una carpeta de prueba con enlaces a los archivos del juego, para ejecutarla sin tocar la instalación")
    p.add_argument("--salida", metavar="CARPETA", help="otra carpeta de salida (no se borra)")
    p.set_defaults(f=cmd_build)

    p = sub.add_parser("instalar", help="copia «salida» sobre el juego (guarda copia de lo que pisa)")
    p.set_defaults(f=cmd_instalar)
    p = sub.add_parser("desinstalar", help="deshace «instalar»: restaura el juego como estaba")
    p.set_defaults(f=cmd_desinstalar)

    p = sub.add_parser("reset", help="borra el proyecto (el JSON; con --todo, también la carpeta de trabajo)")
    p.add_argument("--todo", action="store_true", help="borra también la carpeta de trabajo (hojas, imágenes traducidas, respaldos)")
    p.add_argument("--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--forzar", action="store_true", help="aunque el parche esté instalado")
    p.set_defaults(f=cmd_reset)

    p = sub.add_parser("patch-exe", help="(suelto) parchea una copia de BGI.exe")
    p.add_argument("entrada"); p.add_argument("salida", nargs="?")
    p.add_argument("--verify", action="store_true", help="solo informa versión y si ya está parcheado")
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--sin-fuente", action="store_true")
    p.add_argument("--sin-proporcional", action="store_true")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.add_argument("--fuente", default=exe_patch.DEFAULT_FONT, metavar="NOMBRE", help="nombre de la fuente (ASCII, hasta 15 caracteres; debe estar instalada)")
    p.set_defaults(f=cmd_patch_exe)

    im = sub.add_parser("images", help="(suelto) imágenes de interfaz").add_subparsers(dest="sub", required=True, metavar="subcomando")
    p = im.add_parser("export", help="exporta los .arc a PNG")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?"); p.add_argument("--arc", nargs="+", default=["sysgrp"])
    p.set_defaults(f=cmd_images_export)
    p = im.add_parser("generar", help="genera las imágenes de interfaz traducidas (botones del título/menú y diálogos)")
    p.add_argument("originales", nargs="?"); p.add_argument("salida", nargs="?"); p.set_defaults(f=cmd_images_generar)
    p = im.add_parser("index", help="índice HTML/CSV: original vs traducida y qué falta")
    p.add_argument("originales", nargs="?"); p.add_argument("traducidas", nargs="?"); p.add_argument("salida", nargs="?")
    p.add_argument("--estado", help="TSV de decisiones manuales"); p.add_argument("--ocr", action="store_true")
    p.set_defaults(f=cmd_images_index)
    p = im.add_parser("import", help="coloca imágenes traducidas en Graphic/CVTD")
    p.add_argument("origen", nargs="?"); p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?")
    p.add_argument("--arc", nargs="+", default=["sysgrp"]); p.set_defaults(f=cmd_images_import)

    tx = sub.add_parser("text", help="(suelto) texto de los escenarios").add_subparsers(dest="sub", required=True, metavar="subcomando")
    p = tx.add_parser("export", help="exporta el texto a hojas XLSX (una por .arc, una hoja por script)")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?", help="por defecto, la carpeta «texto» del proyecto")
    p.add_argument("--arc", nargs="+", help="solo estos .arc (por defecto, todos los data0*.arc)")
    p.add_argument("--parche-viejo", metavar="ZIP_O_CARPETA", help="traducción vieja: precarga el español; por defecto, la del proyecto")
    p.add_argument("--tsv", action="store_true", help="además, un TSV por script (para git/diff)")
    p.add_argument("--sin-xlsx", action="store_true"); p.set_defaults(f=cmd_text_export)

    p = tx.add_parser("import", help="arma los escenarios del juego con el español de las hojas")
    p.add_argument("juego", nargs="?"); p.add_argument("salida", nargs="?", help="carpeta donde escribe Script/CVTD/")
    p.add_argument("hojas", nargs="*", help=".xlsx / .tsv o carpetas con ellos (por defecto, la carpeta «texto» del proyecto)")
    p.add_argument("--estados", default="traducido,del parche",
                   help="estados que se aplican (por defecto: traducido,del parche; agregar 'revisar' para probar todo)")
    p.add_argument("--katakana", action="store_true", help="modo antiguo: sin UTF-8, acentos como katakana de ancho medio")
    p.set_defaults(f=cmd_text_import)

    p = tx.add_parser("wrap", help="inserta saltos de línea manuales en las hojas, cortando en límites de palabra")
    p.add_argument("hojas", nargs="*", help=".xlsx / .tsv o carpetas (por defecto, la carpeta «texto» del proyecto)")
    p.add_argument("--max-caracteres", type=int, metavar="N", help="largo máximo de línea en caracteres")
    p.add_argument("--ancho", type=int, metavar="PX", help="ancho máximo en píxeles (medido con --fuente y --tamano)")
    p.add_argument("--fuente", metavar="TTF"); p.add_argument("--tamano", type=int, metavar="PX")
    p.add_argument("--max-lineas", type=int, metavar="M", help="solo avisa: anota en «nota» los textos que pasen de M líneas")
    p.add_argument("--estados", default="traducido,del parche,revisar", help="estados a procesar")
    p.add_argument("--reflow", action="store_true", help="primero descarta los saltos manuales existentes y vuelve a cortar")
    p.add_argument("--salida", metavar="CARPETA", help="escribir las hojas nuevas acá (por defecto, en el lugar con copia .bak)")
    p.add_argument("--sin-copia", action="store_true"); p.set_defaults(f=cmd_text_wrap)
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")       # consolas de Windows con otra página de códigos
    ap = _parser()
    a = ap.parse_args(argv)
    if a.cmd == "patch-exe" and not a.verify and not a.dry_run and not a.salida:
        ap.error("patch-exe necesita 'salida' (o --verify / --dry-run)")
    try:
        return a.f(a)
    except project.ProjectError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    sys.exit(main())

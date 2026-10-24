# SPDX-License-Identifier: GPL-3.0-or-later
"""Interfaz de línea de comandos: tl-organizer <comando>.

Flujo normal (dentro de la carpeta de instalación del juego):  init -> exportar -> (traducir) -> build -> instalar.
"""
import argparse
import os
import shutil
import sys

from . import motores
from .nucleo import config, flujo as workflow, hojas, perfiles, proyecto as project
from .nucleo.config import lista as _estados, need


# ---------------------------------------------------------------- comandos del proyecto

def cmd_init(a):
    proj, creado = project.init(a.carpeta or os.getcwd(), a.parche_viejo, destino=a.idioma)
    if not creado:
        print(f"parche viejo actualizado: {proj.parche_viejo}")
        return 0
    print(f"proyecto creado en {proj.root}")
    print(f"  juego detectado:    {proj.perfil.nombre}" + (f" ({proj.version})" if proj.version else ""))
    print(f"  carpeta de trabajo: {proj.work}")
    print(f"  idiomas:            {proj.idiomas[0]} -> {proj.idiomas[1]}")
    print(f"  parche viejo:       {proj.parche_viejo or '(sin configurar; agregalo con «tl-organizer init --parche-viejo ARCHIVO.zip»)'}")
    if proj.perfil.ejecutable:
        print(f"  copia del {proj.perfil.ejecutable} original guardada en la carpeta de trabajo (backup)")
    print("\nsiguiente paso:  tl-organizer exportar")
    return 0


def cmd_estado(a):
    workflow.estado(project.require(), nivel=a.verbose)
    return 0


def cmd_exportar(a):
    workflow.exportar(project.require(), forzar=a.forzar, ocr=a.ocr)
    proj = project.require()
    print("\nahora podés traducir:")
    print(f"  - texto:      abrí las hojas de {proj.dir('hojas')} (LibreOffice, Excel…) y completá la columna «{hojas.nombre_idioma(proj.idiomas[1])}»")
    print(f"  - imágenes:   abrí {os.path.join(proj.dir('indice'), 'index.html')} en el navegador; guardá las traducidas en {proj.dir('traducidas')}")
    print("cuando termines (o para probar):  tl-organizer build")
    return 0


def cmd_build(a):
    proj = project.require()
    proj.original_exe()                        # antes de borrar nada: si no hay un exe original, avisa y no sigue
    out = a.salida or (proj.dir("jugable") if a.jugable else proj.dir("salida"))
    if not a.salida and not a.jugable and os.path.isdir(out):
        shutil.rmtree(out)                     # la carpeta «salida» es solo nuestra: se rehace entera
    r = workflow.build(proj, out, _estados(a.estados), type(proj.motor).opciones_build(a), jugable=a.jugable)
    if a.jugable:
        mt = ", ".join(f"{v} por {k}" for k, v in r["metodos_enlace"].items())
        print(f"{r['enlaces']} archivos del juego enlazados ({mt})")
        if "copia" in r["metodos_enlace"]:
            print("aviso: se copiaron archivos porque no se pudo enlazar: ocupan espacio extra en disco "
                  "(en Windows, activá el modo desarrollador para usar enlaces simbólicos)")
    t = r.get("texto")
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
              "(o ejecutá «tl-organizer instalar», que lo hace y guarda copia de lo que pisa)")
    return 0


def cmd_revisar(a):
    from collections import Counter
    from .nucleo import wrap
    proj = project.require()
    workflow.sincronizar(proj)
    if not proj.almacen.existe():
        sys.exit("todavía no hay traducción: ejecutá «tl-organizer exportar»")
    fits = wrap.make_fits(a.max_caracteres, a.ancho, a.fuente, a.tamano) if (a.max_caracteres or a.ancho) else None
    probs = workflow.revisar(proj, _estados(a.estados), fits, a.max_lineas)
    if a.solo:
        probs = [p for p in probs if p.codigo in _estados(a.solo)]
    errores = sum(1 for p in probs if p.nivel == "error")
    if not probs:
        print("sin problemas")
    else:
        print(f"{'problema':<14} {'nivel':<6} {'filas':>6}")
        for (codigo, nivel), n in sorted(Counter((p.codigo, p.nivel) for p in probs).items(), key=lambda x: (x[0][1], -x[1])):
            print(f"{codigo:<14} {nivel:<6} {n:>6}")
        print("")
        lim = None if a.verbose else 20
        for p in probs[:lim]:
            print(f"{p.nivel.upper():6} {p.clave:<24} {p.codigo}: {p.detalle}")
        if lim and len(probs) > lim:
            print(f"… y {len(probs) - lim} más (-v para verlos todos)")
    print(f"\ninforme completo (para abrir con LibreOffice/Excel): {proj.informe_revision}")
    return 1 if errores else 0


def cmd_text_po_export(a):
    from .nucleo import po
    proj = project.require()
    dest = a.salida or proj.dir("po")
    workflow.sincronizar(proj)
    if not proj.almacen.existe():
        sys.exit("todavía no hay traducción: ejecutá «tl-organizer exportar»")
    r = po.exportar(proj.almacen, dest, proj.perfil.nombre, _estados(a.estados) if a.estados else None)
    print(f"{r['entradas']} entradas en {r['archivos']} archivos .po -> {dest}"
          + (f" ({r['omitidas']} filas omitidas)" if r["omitidas"] else ""))
    print("abrilos con Poedit, OmegaT, Lokalize o Weblate; para volver a las hojas:  tl-organizer text po-import")
    return 0


def cmd_text_po_import(a):
    from .nucleo import po
    proj = project.require()
    workflow.sincronizar(proj)
    r = po.importar(a.archivos or [proj.dir("po")], proj.almacen)
    workflow.actualizar_vistas(proj, r["grupos"])
    for k, v in r["errores"][:20]:
        print("ERROR:", k, "-", v)
    for k, v in r["conflictos"][:20]:
        print("CONFLICTO:", k, "-", v)
    print(f"{r['actualizadas']} filas actualizadas, {len(r['conflictos'])} conflictos, {len(r['errores'])} errores"
          + (f", {r['desconocidas']} entradas que no están en el proyecto" if r["desconocidas"] else ""))
    return 1 if r["errores"] or r["conflictos"] else 0


def cmd_text_hojas(a):
    proj = project.require()
    workflow.sincronizar(proj)
    if not proj.almacen.existe():
        sys.exit("todavía no hay traducción: ejecutá «tl-organizer exportar»")
    if a.forzar:
        workflow.actualizar_vistas(proj)
    print(f"hojas al día en {proj.dir('hojas')}")
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
        sys.exit("el parche está instalado en el juego: ejecutá primero «tl-organizer desinstalar» (o usá --forzar)")
    if a.todo and not a.si:
        work = proj.work
        print(f"se va a BORRAR la carpeta de trabajo {work}")
        print("incluye las hojas de texto, las imágenes traducidas y los respaldos. Los archivos del juego no se tocan.")
        if not sys.stdin.isatty() or input("escribí SI para continuar: ").strip() != "SI":
            sys.exit("cancelado")
    removed = project.reset(proj, todo=a.todo)
    for r in removed:
        print("borrado:", r)
    if not a.todo:
        print(f"la carpeta de trabajo ({proj.work_name}) se conserva; para borrarla también: «tl-organizer reset --todo»")
    return 0


# ---------------------------------------------------------------- comandos sueltos (usan el proyecto como valor por defecto)

def cmd_images_index(a):
    from .nucleo.galeria import index
    proj = project.find()
    salida = need(a.salida, "indice", "la carpeta de salida")
    cnt = index.build(need(a.originales, "originales", "la carpeta de PNG originales"),
                      need(a.traducidas, "imagenes", "la carpeta de imágenes traducidas"), salida,
                      a.estado or config.load().get("estado"), a.ocr,
                      pantallas=proj.perfil.seccion("galeria").get("pantallas") if proj else None)
    for k, v in sorted(cnt.items()):
        print(f"{k:15} {v}")
    print("índice:", os.path.join(salida, "index.html"))
    return 0


def _wrap_proyecto(a, fits):
    """text wrap sin archivos: sobre la traducción del proyecto (traduccion/), y después se regeneran las hojas."""
    from .nucleo import wrap
    proj = project.require()
    workflow.sincronizar(proj)
    alm = proj.almacen
    if not alm.existe():
        sys.exit("todavía no hay traducción: ejecutá «tl-organizer exportar»")
    copia = os.path.join(proj.dir("backup"), "traduccion-antes-de-wrap")
    if not a.sin_copia and not os.path.exists(copia):
        shutil.copytree(alm.carpeta, copia)
    tot_c = tot_o = 0
    grupos = set()
    for grupo, escenarios in alm.leer().items():
        for esc, rows in escenarios.items():
            c, o = wrap.wrap_rows(rows, fits, _estados(a.estados), a.reflow, a.max_lineas)
            tot_c += c
            tot_o += o
            if c or o:
                alm.guardar(grupo, esc, rows)
                grupos.add(grupo)
    workflow.actualizar_vistas(proj, grupos)
    print(f"{tot_c} textos con saltos de línea nuevos"
          + (f"; {tot_o} con más de {a.max_lineas} líneas (marcados en «nota»)" if a.max_lineas else "")
          + ("" if a.sin_copia else f"; copia de la traducción de antes del primer wrap: {copia}"))
    return 0


def cmd_text_wrap(a):
    from .nucleo import hojas as sheet, wrap
    if not (a.max_caracteres or a.ancho):
        sys.exit("indicá --max-caracteres N y/o --ancho PX (con --fuente y --tamano)")
    fits = wrap.make_fits(a.max_caracteres, a.ancho, a.fuente, a.tamano)
    if not a.hojas:
        return _wrap_proyecto(a, fits)
    files = []
    for p in a.hojas:
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
            sheet.write_xlsx(dst, sheets, config.load()["idiomas"])
        else:
            rows = sheet.read_tsv(f)
            c, o = wrap.wrap_rows(rows, fits, _estados(a.estados), a.reflow, a.max_lineas)
            tot_c += c
            tot_o += o
            sheet.write_tsv(dst, rows, config.load()["idiomas"])
    print(f"{tot_c} textos con saltos de línea nuevos en {len(files)} archivo(s)"
          + (f"; {tot_o} con más de {a.max_lineas} líneas (marcados en «nota»)" if a.max_lineas else "")
          + ("" if a.salida or a.sin_copia else "; copia de seguridad: <archivo>.bak"))
    return 0


# ---------------------------------------------------------------- argumentos

def _parser():
    ap = argparse.ArgumentParser(prog="tl-organizer", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="comando")

    p = sub.add_parser("init", help="crea el proyecto en la carpeta de instalación del juego")
    p.add_argument("carpeta", nargs="?", help="carpeta de instalación del juego (por defecto, la actual)")
    p.add_argument("--parche-viejo", metavar="ARCHIVO.zip", help="el parche en español anterior (.zip o carpeta): precarga el texto y trae voces/gráficos sueltos")
    p.add_argument("--idioma", metavar="CÓDIGO", help="idioma de la traducción (es, en, pt…; por defecto es)")
    p.set_defaults(f=cmd_init)

    p = sub.add_parser("estado", help="muestra el proyecto y el avance de la traducción (-v por archivo, -vv por escenario)")
    p.add_argument("-v", "--verbose", action="count", default=0, help="-v: una tabla por archivo; -vv: además, una por escenario")
    p.set_defaults(f=cmd_estado)

    p = sub.add_parser("exportar", help="vuelca todo lo que hay que traducir (imágenes, galería, hojas de texto)")
    p.add_argument("--forzar", action="store_true", help="exportar de nuevo aunque ya haya hojas (se guarda una copia de las anteriores)")
    p.add_argument("--ocr", action="store_true", help="la galería usa OCR (Tesseract) como pista de qué imágenes tienen japonés")
    p.set_defaults(f=cmd_exportar)

    clases = [cls for _n, cls in motores.clases()]
    p = sub.add_parser("build", help="crea en «salida» lo que hay que copiar al juego")
    p.add_argument("--estados", default="traducido,del parche", help="estados que se aplican (por defecto traducido,del parche; agregá «revisar» para probar todo)")
    p.add_argument("--jugable", action="store_true", help="arma una carpeta de prueba con enlaces a los archivos del juego, para ejecutarla sin tocar la instalación")
    p.add_argument("--salida", metavar="CARPETA", help="otra carpeta de salida (no se borra)")
    for cls in clases:
        cls.argumentos_build(p)                # opciones propias de cada motor
    p.set_defaults(f=cmd_build)

    p = sub.add_parser("revisar", help="control de calidad de las traducciones (marcadores, caracteres, puntuación, largo…)")
    p.add_argument("--estados", default="traducido,del parche,revisar", help="estados a revisar")
    p.add_argument("--solo", metavar="CÓDIGOS", help="solo estos problemas (separados por comas: marcadores,restos,…)")
    p.add_argument("--max-caracteres", type=int, metavar="N", help="avisa las líneas de más de N caracteres")
    p.add_argument("--ancho", type=int, metavar="PX", help="avisa las líneas de más de PX píxeles (con --fuente y --tamano)")
    p.add_argument("--fuente", metavar="TTF"); p.add_argument("--tamano", type=int, metavar="PX")
    p.add_argument("--max-lineas", type=int, metavar="M", help="avisa los textos de más de M líneas")
    p.add_argument("-v", "--verbose", action="store_true", help="listar todos los problemas (si no, los primeros 20)")
    p.set_defaults(f=cmd_revisar)

    p = sub.add_parser("instalar", help="copia «salida» sobre el juego (guarda copia de lo que pisa)")
    p.set_defaults(f=cmd_instalar)
    p = sub.add_parser("desinstalar", help="deshace «instalar»: restaura el juego como estaba")
    p.set_defaults(f=cmd_desinstalar)

    p = sub.add_parser("reset", help="borra el proyecto (el JSON; con --todo, también la carpeta de trabajo)")
    p.add_argument("--todo", action="store_true", help="borra también la carpeta de trabajo (hojas, imágenes traducidas, respaldos)")
    p.add_argument("--si", action="store_true", help="no pedir confirmación")
    p.add_argument("--forzar", action="store_true", help="aunque el parche esté instalado")
    p.set_defaults(f=cmd_reset)

    im = sub.add_parser("images", help="(suelto) imágenes de interfaz").add_subparsers(dest="sub", required=True, metavar="subcomando")
    p = im.add_parser("index", help="índice HTML/CSV: original vs traducida y qué falta")
    p.add_argument("originales", nargs="?"); p.add_argument("traducidas", nargs="?"); p.add_argument("salida", nargs="?")
    p.add_argument("--estado", help="TSV de decisiones manuales"); p.add_argument("--ocr", action="store_true")
    p.set_defaults(f=cmd_images_index)
    tx = sub.add_parser("text", help="(suelto) texto de los escenarios").add_subparsers(dest="sub", required=True, metavar="subcomando")
    p = tx.add_parser("wrap", help="inserta saltos de línea manuales en las hojas, cortando en límites de palabra")
    p.add_argument("hojas", nargs="*", help=".xlsx / .tsv o carpetas (por defecto, la traducción del proyecto)")
    p.add_argument("--max-caracteres", type=int, metavar="N", help="largo máximo de línea en caracteres")
    p.add_argument("--ancho", type=int, metavar="PX", help="ancho máximo en píxeles (medido con --fuente y --tamano)")
    p.add_argument("--fuente", metavar="TTF"); p.add_argument("--tamano", type=int, metavar="PX")
    p.add_argument("--max-lineas", type=int, metavar="M", help="solo avisa: anota en «nota» los textos que pasen de M líneas")
    p.add_argument("--estados", default="traducido,del parche,revisar", help="estados a procesar")
    p.add_argument("--reflow", action="store_true", help="primero descarta los saltos manuales existentes y vuelve a cortar")
    p.add_argument("--salida", metavar="CARPETA", help="con archivos: escribir los nuevos acá (por defecto, en el lugar con copia .bak)")
    p.add_argument("--sin-copia", action="store_true"); p.set_defaults(f=cmd_text_wrap)
    p = tx.add_parser("hojas", help="trae lo editado en las hojas y las regenera desde traduccion/")
    p.add_argument("--forzar", action="store_true", help="regenera todas las hojas (descarta lo que tengan sin traer, salvo lo que ya se trajo)")
    p.set_defaults(f=cmd_text_hojas)
    p = tx.add_parser("po-export", help="exporta las hojas a archivos .po (Poedit, OmegaT, Weblate…)")
    p.add_argument("--salida", metavar="CARPETA", help="por defecto, la carpeta «po» del proyecto")
    p.add_argument("--estados", help="solo filas con estos estados (por defecto, todas)")
    p.set_defaults(f=cmd_text_po_export)
    p = tx.add_parser("po-import", help="vuelca a las hojas lo traducido en los .po")
    p.add_argument("archivos", nargs="*", help=".po o carpetas (por defecto, la carpeta «po» del proyecto)")
    p.set_defaults(f=cmd_text_po_import)

    for cls in clases:
        cls.registrar_comandos(sub, {"images": im, "text": tx})     # comandos sueltos de cada motor
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")       # consolas de Windows con otra página de códigos
    ap = _parser()
    a = ap.parse_args(argv)
    try:
        return a.f(a)
    except (project.ProjectError, perfiles.PerfilError, motores.MotorError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    sys.exit(main())

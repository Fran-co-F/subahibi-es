# SPDX-License-Identifier: GPL-3.0-or-later
"""Las órdenes de alto nivel que trabajan sobre un proyecto (proyecto.py): exportar, estado, build, instalar y desinstalar.

No conocen ningún formato: le piden al motor del proyecto (proj.motor) lo que haga falta, según sus capacidades.
"""
import datetime
import glob
import json
import os
import shutil

from ..motores import base
from . import proyecto as proj_mod


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def exportar(proj, forzar=False, ocr=False, log=print):
    """Vuelca todo lo necesario para traducir: PNG de la interfaz, galería de imágenes y hojas de texto.
    Las hojas de texto que ya existen NO se pisan (hay trabajo de traducción adentro) salvo con forzar=True, y entonces
    se guarda una copia en backup/."""
    from .galeria import index as img_index
    game = proj.root
    motor = proj.motor
    rep = {}
    if base.IMAGENES in motor.capacidades:
        if not os.path.exists(proj.estado_tsv):                  # por si se borró para empezar de cero
            os.makedirs(os.path.dirname(proj.estado_tsv), exist_ok=True)
            with open(proj.estado_tsv, "w", encoding="utf-8", newline="\n") as f:
                f.write(proj_mod.ESTADO_PLANTILLA)
        # 1) PNG originales de la interfaz
        orig = proj.dir("originales")
        if forzar or not glob.glob(os.path.join(orig, "*.png")):
            n, skipped = motor.exportar_imagenes(game, orig)
            rep["imagenes_exportadas"] = n
            log(f"imágenes de la interfaz: {n} PNG en {orig}")
        else:
            log("imágenes de la interfaz: ya estaban exportadas")
        # 2) galería editable
        cnt = img_index.build(orig, proj.dir("traducidas"), proj.dir("indice"), proj.estado_tsv, ocr,
                              pantallas=proj.perfil.seccion("galeria").get("pantallas"))
        rep["indice"] = dict(cnt)
        log(f"galería de imágenes: {os.path.join(proj.dir('indice'), 'index.html')}")
    if base.TEXTO in motor.capacidades:
        _exportar_texto(proj, motor, forzar, rep, log)
    return rep


def _exportar_texto(proj, motor, forzar, rep, log):
    from . import texto as txt, vistas
    alm = proj.almacen
    sincronizar(proj, log)                                      # incluye la migración de proyectos con texto/*.xlsx
    if alm.existe() and not forzar:
        log(f"texto: ya está exportado en {alm.carpeta}; NO se pisa (usá --forzar para exportar de nuevo; se guardará una copia)")
        rep["texto"] = "conservado"
    else:
        if alm.existe():
            dest = os.path.join(proj.dir("backup"), "texto-" + _stamp())
            shutil.copytree(alm.carpeta, os.path.join(dest, "traduccion"))
            if os.path.isdir(proj.dir("hojas")):
                shutil.move(proj.dir("hojas"), os.path.join(dest, "hojas"))
            log(f"texto: copia de la traducción y las hojas anteriores en {dest}")
        datos, r = txt.agrupar(motor.textos(proj.root, proj.parche_viejo))
        alm.escribir(datos)
        vistas.generar(alm, proj.dir("hojas"), log=log)
        rep["texto"] = r
        log(f"texto: {r['scripts']} escenarios, {r['filas']} filas ({r['precargadas']} precargadas desde el parche viejo) en {alm.carpeta}")
        log(f"       hojas para editar: {proj.dir('hojas')}")
        if r["sin_texto"]:
            log(f"       ({len(r['sin_texto'])} escenarios sin texto que traducir no tienen hoja: guiones de configuración y finales)")


def build(proj, out, estados=base.ESTADOS_LISTOS, opciones=None, jugable=False, log=print):
    """Arma en 'out' lo que hay que copiar al juego: el motor aplica las hojas de texto y las imágenes traducidas.
    jugable=True agrega enlaces a los archivos del juego (carpeta de prueba que se ejecuta tal cual)."""
    from . import enlaces
    exe = proj.original_exe()
    rep = {"enlaces": 0, "metodos_enlace": {}}
    os.makedirs(out, exist_ok=True)
    if jugable:
        rep["enlaces"], rep["metodos_enlace"] = enlaces.link_game(proj.root, os.path.abspath(out), proj.perfil)
    sincronizar(proj, log)
    filas = proj.almacen.filas_por_escenario() if proj.almacen.existe() else None
    trad = proj.dir("traducidas")
    imagenes = trad if os.path.isdir(trad) and os.listdir(trad) else None
    rep.update(proj.motor.construir(proj.root, out, filas, imagenes, estados, opciones or {}, proj.parche_viejo, exe, log))
    return rep


ESTADOS_TEXTO = ("del parche", "traducido", "revisar", "sin traducir")
LISTOS = ("del parche", "traducido")          # lo que `build` aplica por defecto


def _pct(parte, total):
    return f"{100 * parte / total:5.1f}%" if total else "    -"


def _tabla(titulo, filas, log, ancho):
    """filas: [(nombre, {estado: cantidad})]; imprime una línea por fila y una de totales."""
    cab = f"{titulo:<{ancho}} {'filas':>7} {'listo':>7} {'del parche':>11} {'traducido':>10} {'revisar':>8} {'sin traducir':>13}"
    log(cab)
    log("-" * len(cab))
    tot = {k: 0 for k in ESTADOS_TEXTO}
    for nombre, c in filas:
        n = sum(c.get(k, 0) for k in ESTADOS_TEXTO)
        listo = sum(c.get(k, 0) for k in LISTOS)
        log(f"{nombre:<{ancho}} {n:>7} {_pct(listo, n):>7} {c.get('del parche', 0):>11} {c.get('traducido', 0):>10} "
            f"{c.get('revisar', 0):>8} {c.get('sin traducir', 0):>13}")
        for k in ESTADOS_TEXTO:
            tot[k] += c.get(k, 0)
    n = sum(tot.values())
    log("-" * len(cab))
    log(f"{'TOTAL':<{ancho}} {n:>7} {_pct(sum(tot[k] for k in LISTOS), n):>7} {tot['del parche']:>11} {tot['traducido']:>10} "
        f"{tot['revisar']:>8} {tot['sin traducir']:>13}")


def estado(proj, log=print, nivel=0):
    """Resumen del proyecto y del avance de la traducción.  nivel 1: una tabla por archivo; nivel 2: además, por escenario.
    «listo» = filas «traducido» + «del parche», que es lo que `build` aplica por defecto."""
    sincronizar(proj, log)
    log(f"proyecto:        {proj.root}")
    log(f"juego:           {proj.perfil.nombre} (perfil {proj.perfil.id})")
    log(f"motor:           {proj.perfil.motor}" + (f", versión {proj.version}" if proj.version else ""))
    log(f"parche viejo:    {proj.parche_viejo or '(no configurado)'}")
    if proj.almacen.existe():
        por_archivo = []                              # [(archivo, [(escenario, {estado: n})])]
        cnt = {}
        for grupo, escenarios_ in proj.almacen.leer().items():
            escenarios = []
            for nombre, rows in escenarios_.items():
                c = {}
                for r in rows:
                    c[r["estado"]] = c.get(r["estado"], 0) + 1
                    cnt[r["estado"]] = cnt.get(r["estado"], 0) + 1
                escenarios.append((nombre, c))
            por_archivo.append((grupo, escenarios))
        total = sum(cnt.values())
        log(f"texto:           {total} filas en {len(por_archivo)} archivos   (listo {_pct(sum(cnt.get(k, 0) for k in LISTOS), total).strip()}: traducido + del parche)")
        for k in ESTADOS_TEXTO:
            if k in cnt:
                log(f"                 {k:13} {cnt[k]:6}  ({100 * cnt[k] / total:.1f}%)")
        if nivel >= 1:
            log("")
            filas = [(arch, {k: sum(c.get(k, 0) for _n, c in esc) for k in ESTADOS_TEXTO}) for arch, esc in por_archivo]
            _tabla("archivo", filas, log, max(len("archivo"), max(len(a) for a, _ in filas)))
        if nivel >= 2:
            ancho = max(len("escenario"), max(len(n) for _a, esc in por_archivo for n, _c in esc))
            for arch, esc in por_archivo:
                log("")
                log(f"== {arch} ==")
                _tabla("escenario", esc, log, ancho)
        log("")
    else:
        log("texto:           todavía no exportado (ejecutá «tl-organizer exportar»)")
    trad = [f for f in os.listdir(proj.dir("traducidas"))] if os.path.isdir(proj.dir("traducidas")) else []
    log(f"imágenes:        {len(trad)} traducidas en {proj.dir('traducidas')}")
    salida = proj.dir("salida")
    log(f"build:           {'hecho' if os.path.isdir(salida) and os.listdir(salida) else 'sin hacer'} ({salida})")
    log(f"instalado:       {'sí' if os.path.exists(_manifest(proj)) else 'no'}")


def revisar(proj, estados=None, fits=None, max_lineas=None, opciones=None, log=print):
    """Corre los controles de calidad sobre la traducción del proyecto y escribe el informe en revision.tsv.  -> [Problema]"""
    from . import revisar as rv
    sincronizar(proj, log)
    ctx = rv.Contexto(idiomas=proj.idiomas, motor=proj.motor, fits=fits, max_lineas=max_lineas, opciones=opciones or {})
    problemas = []
    for rows in proj.almacen.filas_por_escenario().values():
        problemas += rv.revisar_filas(rows, ctx, estados or rv.ESTADOS)
    problemas.sort(key=lambda p: p.nivel != rv.ERROR)          # primero los errores de todas las hojas
    rv.escribir_tsv(proj.informe_revision, problemas)
    return problemas


def sincronizar(proj, log=print):
    """Trae a traduccion/ lo editado en las hojas (hojas/*.xlsx) y regenera las hojas que cambiaron.
    La primera vez en un proyecto de antes del almacén (con texto/*.xlsx) migra esas hojas.  Los conflictos se informan
    y esa hoja no se regenera (para no perder lo editado).  -> informe de Almacen.aplicar() (o None si no hay traducción)."""
    from . import vistas
    alm = proj.almacen
    if not alm.existe():
        _migrar(proj, log)
        if not alm.existe():
            return None
    rep = vistas.importar(alm, proj.dir("hojas"))
    if rep["actualizadas"]:
        log(f"hojas: {rep['actualizadas']} filas editadas pasaron a {alm.carpeta}")
    for k, v in rep["errores"][:10]:
        log(f"ERROR hojas: {k} - {v}")
    if rep["conflictos"]:
        log(f"CONFLICTO: {len(rep['conflictos'])} filas cambiaron en la hoja y también en traduccion/ (no se tocaron):")
        for k, v in rep["conflictos"][:10]:
            log(f"  {k}: {v}")
        log("  resolvelos en la hoja (copiá lo que quieras conservar) o borrá la hoja para regenerarla desde traduccion/")
    con_conflicto = {k.rsplit(":", 1)[0] for k, _ in rep["conflictos"]}
    escenarios = {g: set(e) for g, e in alm.escenarios().items()}
    grupos = {g for g in rep["grupos"] | rep["desactualizadas"] if not (escenarios[g] & con_conflicto)}
    faltan = {g for g in escenarios if not os.path.exists(os.path.join(proj.dir("hojas"), g + ".xlsx"))}
    if grupos | faltan:
        vistas.generar(alm, proj.dir("hojas"), grupos | faltan, log)
    return rep


def actualizar_vistas(proj, grupos=None, log=print):
    """Después de cambiar traduccion/ (wrap, po-import…): regenera las hojas de esos grupos."""
    from . import vistas
    vistas.generar(proj.almacen, proj.dir("hojas"), grupos, log)


def _migrar(proj, log):
    """Proyectos de antes del almacén: las hojas de texto/ pasan a traduccion/ (y quedan copiadas en backup/)."""
    from . import hojas
    viejas = sorted(glob.glob(os.path.join(proj.dir("texto"), "*.xlsx")))
    if not viejas:
        return
    datos = {}
    for h in viejas:
        grupo = os.path.splitext(os.path.basename(h))[0]
        for rows in hojas.read_xlsx(h).values():
            if rows:
                datos.setdefault(grupo, {})[rows[0]["clave"].rsplit(":", 1)[0]] = rows
    proj.almacen.escribir(datos)
    dest = os.path.join(proj.dir("backup"), "texto-migrado-" + _stamp())
    shutil.move(proj.dir("texto"), dest)
    actualizar_vistas(proj, log=log)
    log(f"migración: la traducción ahora vive en {proj.almacen.carpeta} (un archivo de texto por escenario, apto para git);")
    log(f"           las hojas para editar están en {proj.dir('hojas')}; las anteriores quedaron en {dest}")


def _manifest(proj):
    return os.path.join(proj.dir("backup"), "instalado.json")


def _files(src):
    for root, _d, fs in os.walk(src):
        for f in fs:
            full = os.path.join(root, f)
            yield os.path.relpath(full, src), full


def instalar(proj, log=print):
    """Copia lo que dejó `build` (carpeta salida) sobre la instalación del juego.  Lo que se pisa se guarda en
    backup/instalado/ para poder volver atrás con desinstalar."""
    src = proj.dir("salida")
    if not os.path.isdir(src) or not os.listdir(src):
        raise proj_mod.ProjectError("no hay nada para instalar: ejecutá primero «tl-organizer build»")
    mpath = _manifest(proj)
    manifest = {}
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            manifest = json.load(f)
    bdir = os.path.join(proj.dir("backup"), "instalado")
    n = 0
    seen = set()
    for rel, full in _files(src):
        key = rel.replace(os.sep, "/")
        seen.add(key)
        dst = os.path.join(proj.root, rel)
        if key not in manifest:
            if os.path.exists(dst):
                os.makedirs(os.path.dirname(os.path.join(bdir, rel)), exist_ok=True)
                shutil.copy2(dst, os.path.join(bdir, rel))
                manifest[key] = "reemplazado"
            else:
                manifest[key] = "nuevo"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(full, dst)
        n += 1
    for key in [k for k in manifest if k not in seen and manifest[k] == "nuevo"]:      # lo que ya no se genera
        p = os.path.join(proj.root, *key.split("/"))
        if os.path.exists(p):
            os.remove(p)
        del manifest[key]
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    log(f"{n} archivos copiados a {proj.root} ({sum(1 for v in manifest.values() if v == 'reemplazado')} originales respaldados)")
    return n


def desinstalar(proj, log=print):
    """Deshace `instalar`: borra lo que se agregó y restaura lo que se pisó."""
    mpath = _manifest(proj)
    if not os.path.exists(mpath):
        raise proj_mod.ProjectError("el parche no está instalado (no hay registro de una instalación)")
    with open(mpath, encoding="utf-8") as f:
        manifest = json.load(f)
    bdir = os.path.join(proj.dir("backup"), "instalado")
    borrados = restaurados = 0
    for key, state in manifest.items():
        rel = os.path.join(*key.split("/"))
        dst = os.path.join(proj.root, rel)
        if state == "nuevo":
            if os.path.exists(dst):
                os.remove(dst)
                borrados += 1
        else:
            shutil.copy2(os.path.join(bdir, rel), dst)
            restaurados += 1
    for d in proj.motor.carpetas_sueltas:                                   # carpetas que quedaron vacías
        for root, dirs, files in os.walk(os.path.join(proj.root, d), topdown=False):
            if not os.listdir(root):
                os.rmdir(root)
    os.remove(mpath)
    log(f"{borrados} archivos borrados, {restaurados} originales restaurados")

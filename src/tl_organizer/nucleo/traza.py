# SPDX-License-Identifier: GPL-3.0-or-later
"""Traza de archivos: ejecuta el juego, anota qué archivos abre, busca y escribe, y lo compara con el parche.

Sirve para saber, sin adivinar, dónde busca el motor los archivos sueltos y si de verdad lee lo que instaló `instalar`.

  Linux / macOS   el juego corre con Wine (WINEDEBUG=+file).  El Wine, el prefijo y el entorno se toman de la
                  configuración de Lutris del juego si existe; si no, del PATH y de la carpeta del juego (se busca
                  hacia arriba un prefijo con drive_c/ y system.reg).  Se pueden indicar con --wine, --prefijo, --env.
  Windows         con Process Monitor de Sysinternals (--procmon RUTA\\Procmon.exe; necesita permisos de
                  administrador).  Se graba un .pml, se convierte a CSV y se lee igual que la traza de Wine.

El resultado es una lista de accesos (ruta, operación, encontrado, escritura) que analizar() resume.
"""
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

# ------------------------------------------------------------------ accesos


@dataclass
class Acceso:
    ruta: str              # ruta nativa del sistema (en Wine, ya traducida a la ruta Unix)
    op: str                # abrir | consultar
    encontrado: bool
    escritura: bool = False


# Wine: máscaras de acceso y disposiciones de NtCreateFile que implican escribir
_ESCRIBE = 0x40000000 | 0x10000000 | 0x2 | 0x4          # GENERIC_WRITE, GENERIC_ALL, FILE_WRITE_DATA, FILE_APPEND_DATA
_CREA = {0, 2, 4, 5}                                      # SUPERSEDE, CREATE, OVERWRITE, OVERWRITE_IF
_RE_CREATE = re.compile(r'trace:file:NtCreateFile handle=\S+ access=([0-9a-fA-F]+) name=L"(.*?)" .*?disp=(\d+) options=([0-9a-fA-F]+)')
_RE_NO_ESTA = re.compile(r'warn:file:(NtCreateFile|NtQueryAttributesFile|NtQueryFullAttributesFile) L"(.*?)" not found')
_RE_CONSULTA = re.compile(r'trace:file:(GetFileAttributesW|NtQueryAttributesFile|NtQueryFullAttributesFile|FindFirstFileExW) '
                          r'\(?L"(.*?)"')
_FILTRO_WINE = re.compile(r"NtCreateFile|NtQuery(Full)?AttributesFile|GetFileAttributesW|FindFirstFileExW")


def _des(s):
    return s.replace("\\\\", "\\")


class RutasWine:
    """Traduce rutas de Windows dentro de Wine (\\??\\C:\\..., Z:\\...) a rutas Unix con dosdevices/ del prefijo."""

    def __init__(self, prefijo):
        self.dos = os.path.join(prefijo, "dosdevices") if prefijo else None

    def unix(self, ruta):
        r = _des(ruta)
        for p in ("\\??\\", "\\\\?\\", "\\\\.\\"):
            if r.startswith(p):
                r = r[len(p):]
        if r.lower().startswith("unix\\"):
            return r[4:].replace("\\", "/")
        m = re.match(r"([A-Za-z]):\\?(.*)", r)
        if not m:
            return None
        letra, resto = m.group(1).lower(), m.group(2)
        base = os.path.join(self.dos, letra + ":") if self.dos else ("/" if letra == "z" else None)
        if base is None or not os.path.exists(base):
            return None
        return os.path.join(os.path.realpath(base), *[x for x in resto.split("\\") if x])


def leer_traza_wine(lineas, rutas):
    """Accesos a partir de las líneas de WINEDEBUG=+file.  Un NtCreateFile sin el «not found» que lo sigue se
    cuenta como encontrado."""
    out, pend = [], {}
    for ln in lineas:
        m = _RE_CREATE.search(ln)
        if m:
            acc, nombre, disp, opc = int(m.group(1), 16), m.group(2), int(m.group(3)), int(m.group(4), 16)
            if opc & 1:                                   # FILE_DIRECTORY_FILE: abre una carpeta
                continue
            u = rutas.unix(nombre)
            if u:
                a = Acceso(u, "abrir", True, bool(acc & _ESCRIBE) or disp in _CREA)
                out.append(a)
                pend[_des(nombre)] = a
            continue
        m = _RE_NO_ESTA.search(ln)
        if m:
            n = _des(m.group(2))
            if m.group(1) == "NtCreateFile" and n in pend:
                pend.pop(n).encontrado = False
            elif m.group(1) != "NtCreateFile":
                u = rutas.unix(m.group(2))
                if u:
                    # la consulta ya se anotó como encontrada al ver su línea de traza: se corrige
                    for a in reversed(out[-8:]):
                        if a.op == "consultar" and a.ruta == u:
                            a.encontrado = False
                            break
                    else:
                        out.append(Acceso(u, "consultar", False))
            continue
        m = _RE_CONSULTA.search(ln)
        if m:
            u = rutas.unix(m.group(2))
            if u:
                out.append(Acceso(u, "consultar", os.path.exists(u)))
    return out


def leer_csv_procmon(ruta, proceso):
    """Accesos a partir del CSV de Process Monitor, solo los del proceso del juego."""
    out = []
    with open(ruta, encoding="utf-8-sig", errors="replace", newline="") as f:
        for fila in csv.DictReader(f):
            if (fila.get("Process Name") or "").lower() != proceso.lower():
                continue
            op, res, det, p = fila.get("Operation", ""), fila.get("Result", ""), fila.get("Detail", ""), fila.get("Path", "")
            if not p or op not in ("CreateFile", "QueryOpen", "WriteFile", "SetEndOfFileInformationFile"):
                continue
            if "Directory" in det and "Non-Directory" not in det:
                continue
            esc = op != "CreateFile" and op != "QueryOpen" or bool(re.search(r"Desired Access:[^,]*(Write|Generic All)", det))
            out.append(Acceso(p, "abrir" if op == "CreateFile" else "consultar" if op == "QueryOpen" else "escribir",
                              res == "SUCCESS", esc))
    return out


# ------------------------------------------------------------------ ejecutar


def config_lutris(exe):
    """Busca en ~/.local/share/lutris/games/*.yml (y ~/.config/lutris/games) la entrada cuyo exe es este.
    Lee lo mínimo (exe, prefix, wine.version, system.env) sin depender de PyYAML."""
    real = os.path.realpath(exe)
    for d in ("~/.local/share/lutris/games", "~/.config/lutris/games"):
        for yml in glob.glob(os.path.join(os.path.expanduser(d), "*.yml")):
            try:
                texto = open(yml, encoding="utf-8").read()
            except OSError:
                continue
            datos, seccion, sub = {"env": {}}, None, None
            for ln in texto.splitlines():
                if not ln.strip() or ln.lstrip().startswith("#"):
                    continue
                ind = len(ln) - len(ln.lstrip())
                clave, _, valor = ln.strip().partition(":")
                valor = valor.strip().strip("'\"")
                if ind == 0:
                    seccion, sub = clave, None
                elif ind == 2:
                    sub = clave
                    if valor:
                        datos[f"{seccion}.{clave}"] = valor
                elif seccion == "system" and sub == "env" and valor:
                    datos["env"][clave] = valor
            e = datos.get("game.exe")
            if e and os.path.realpath(os.path.expanduser(e)) == real:
                return dict(prefijo=datos.get("game.prefix"), version=datos.get("wine.version"), env=datos["env"])
    return None


def buscar_wine(version):
    """El binario de Wine de una versión de Lutris (GE-Proton…, lutris-…) o None."""
    if not version:
        return None
    for patron in ("~/.local/share/lutris/runners/wine/{v}/bin/wine",
                   "~/.local/share/lutris/runners/proton/{v}/files/bin/wine",
                   "~/.local/share/Steam/compatibilitytools.d/{v}/files/bin/wine",
                   "~/.steam/root/compatibilitytools.d/{v}/files/bin/wine"):
        p = os.path.expanduser(patron.format(v=version))
        if os.path.isfile(p):
            return p
    return None


def buscar_prefijo(carpeta):
    d = os.path.abspath(carpeta)
    while True:
        if os.path.isdir(os.path.join(d, "drive_c")) and os.path.isfile(os.path.join(d, "system.reg")):
            return d
        padre = os.path.dirname(d)
        if padre == d:
            return None
        d = padre


def _esperar(proc, segundos, log):
    if segundos:
        log(f"el juego queda abierto {segundos} s (se cierra solo); jugá hasta la parte que quieras revisar")
    else:
        log("jugá hasta la parte que quieras revisar y cerrá el juego")
    try:
        proc.wait(timeout=segundos or None)
        return False
    except subprocess.TimeoutExpired:
        return True


def ejecutar_wine(carpeta, exe, wine=None, prefijo=None, env=None, segundos=0, guardar=None, log=print):
    """Ejecuta exe (relativo a carpeta) con WINEDEBUG=+file.  -> (accesos, descripción de cómo se ejecutó)."""
    lut = config_lutris(os.path.join(carpeta, exe)) or {}
    wine = wine or buscar_wine(lut.get("version")) or shutil.which("wine")
    if not wine:
        raise SystemExit("no encuentro Wine: instalalo o indicá --wine RUTA")
    prefijo = prefijo or (os.path.expanduser(lut["prefijo"]) if lut.get("prefijo") else None) \
        or os.environ.get("WINEPREFIX") or buscar_prefijo(carpeta)
    entorno = dict(os.environ)
    entorno.update(lut.get("env", {}))
    entorno.update(env or {})
    if prefijo:
        entorno["WINEPREFIX"] = prefijo
    entorno["WINEDEBUG"] = "+file"
    log(f"Wine: {wine}\nprefijo: {prefijo or '(el de Wine por defecto)'}"
        + (f"\nentorno: {' '.join(f'{k}={v}' for k, v in {**lut.get('env', {}), **(env or {})}.items())}" if lut.get("env") or env else ""))
    proc = subprocess.Popen([wine, exe], cwd=carpeta, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            start_new_session=True)
    lineas = []
    import threading

    def leer():
        for b in proc.stderr:
            ln = b.decode("utf-8", "replace")
            if _FILTRO_WINE.search(ln):
                lineas.append(ln)
    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    vencido = _esperar(proc, segundos, log)
    if vencido:
        # wineserver -k cierra todos los programas de ese prefijo: el juego y los servicios de Wine
        ws = os.path.join(os.path.dirname(wine), "wineserver")
        subprocess.run([ws if os.path.isfile(ws) else "wineserver", "-k"], env=entorno, check=False)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    hilo.join(timeout=10)
    if guardar:
        with open(guardar, "w", encoding="utf-8") as f:
            f.writelines(lineas)
    return leer_traza_wine(lineas, RutasWine(prefijo)), dict(metodo="wine", wine=wine, prefijo=prefijo)


def ejecutar_procmon(carpeta, exe, procmon, segundos=0, guardar=None, log=print):
    """Windows: graba con Process Monitor mientras corre el juego."""
    tmp = tempfile.mkdtemp(prefix="tl-traza-")
    pml, csv_ = os.path.join(tmp, "traza.pml"), guardar or os.path.join(tmp, "traza.csv")
    subprocess.Popen([procmon, "/AcceptEula", "/Quiet", "/Minimized", "/BackingFile", pml])
    time.sleep(3)
    try:
        proc = subprocess.Popen([os.path.join(carpeta, exe)], cwd=carpeta)
        if _esperar(proc, segundos, log):
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], check=False, capture_output=True)
    finally:
        subprocess.run([procmon, "/Terminate"], check=False)
    subprocess.run([procmon, "/OpenLog", pml, "/SaveAs", csv_], check=False)
    return leer_csv_procmon(csv_, os.path.basename(exe)), dict(metodo="procmon", procmon=procmon)


# ------------------------------------------------------------------ análisis


def _rel(ruta, raiz):
    """Ruta relativa a la carpeta del juego (con «/»), o None si está afuera.  Sin distinguir mayúsculas: Wine y
    Windows no las distinguen."""
    r, raiz = os.path.realpath(ruta), os.path.realpath(raiz)
    if not r.lower().startswith(raiz.lower() + os.sep):
        return None
    return r[len(raiz) + 1:].replace(os.sep, "/")


_DEL_SISTEMA = (".dll", ".drv", ".conf")          # lo que Wine/Windows buscan junto al exe (no es del motor)


def analizar(accesos, juego, entradas=(), salida=None, exe=None):
    """Resume la traza.
    entradas: nombres de los archivos que hay dentro de los contenedores del juego (los .arc de BGI…): si el juego los
    busca sueltos en alguna carpeta, esa es la carpeta donde el motor acepta archivos que tapan a los del contenedor.
    salida: la carpeta «salida» del proyecto (lo que instala `instalar`): se comprueba si el juego leyó cada archivo."""
    ent = {e.lower() for e in entradas}
    leidos, faltan, escritos, afuera = Counter(), defaultdict(Counter), Counter(), Counter()
    vistos = defaultdict(set)                         # nombre (minúsculas) -> carpetas donde se lo buscó
    for a in accesos:
        rel = _rel(a.ruta, juego)
        if rel is None:
            if a.escritura:
                afuera[a.ruta] += 1
            continue
        carpeta, _, nombre = rel.rpartition("/")
        vistos[nombre.lower()].add(carpeta.lower())
        if a.escritura:
            escritos[rel] += 1
        elif a.encontrado:
            leidos[rel] += 1
        elif not nombre.lower().endswith(_DEL_SISTEMA):
            faltan[carpeta][nombre] += 1
    # carpetas donde busca sueltos: búsquedas fallidas o lecturas de nombres que existen dentro de los contenedores
    sueltos = Counter()
    for nombre, carpetas in vistos.items():
        if nombre in ent:
            for c in carpetas:
                sueltos[c] += 1
    rep = dict(
        leidos=dict(leidos.most_common()),
        no_encontrados={c or ".": dict(n.most_common()) for c, n in sorted(faltan.items(), key=lambda kv: -sum(kv[1].values()))},
        escritos=dict(escritos.most_common()),
        escritos_fuera=dict(afuera.most_common()),
        carpetas_de_sueltos={c or ".": n for c, n in sueltos.most_common()},
    )
    if salida and os.path.isdir(salida):
        parche, ya = {}, {k.lower() for k in leidos}
        for root, _d, fs in os.walk(salida):
            for f in fs:
                rel = os.path.relpath(os.path.join(root, f), salida).replace(os.sep, "/")
                if exe and rel.lower() == exe.replace(os.sep, "/").lower():
                    parche[rel] = "leído"                     # el ejecutable lo carga el sistema, no el motor
                elif rel.lower() in ya:
                    parche[rel] = "leído"
                else:
                    otras = sorted(vistos.get(f.lower(), set()) - {rel.rpartition("/")[0].lower()})
                    parche[rel] = ("lo buscó en otra carpeta: " + ", ".join(c or "." for c in otras)) if otras \
                        else "no lo pidió (no llegó a usarlo en esta partida, o lo busca con otro nombre)"
        rep["parche"] = parche
    return rep


def informe(rep, log=print, maximo=12):
    def lista(d, n=maximo):
        items = list(d.items())
        for k, v in items[:n]:
            log(f"    {v:5}  {k}")
        if len(items) > n:
            log(f"    … y {len(items) - n} más")
    log("\nDónde busca archivos sueltos el motor (carpetas donde pidió nombres que están dentro de los contenedores):")
    if rep["carpetas_de_sueltos"]:
        lista(rep["carpetas_de_sueltos"])
    else:
        log("    (ninguna: no pidió sueltos, o el motor no informa qué hay en sus contenedores)")
    if "parche" in rep:
        est = Counter("leído" if v == "leído" else "otra" if v.startswith("lo buscó") else "no" for v in rep["parche"].values())
        log(f"\nArchivos del parche (salida): {est['leído']} leídos, {est['otra']} buscados en otra carpeta, {est['no']} sin pedir")
        for k, v in sorted(rep["parche"].items(), key=lambda kv: (kv[1] == "leído", kv[0]))[:maximo * 2]:
            log(f"    {k}: {v}")
    log("\nArchivos del juego que abrió o consultó (veces):")
    lista(rep["leidos"])
    log("\nBuscados y no encontrados, por carpeta:")
    for c, nombres in list(rep["no_encontrados"].items())[:maximo]:
        log(f"  {c}/  ({sum(nombres.values())} búsquedas): " + ", ".join(list(nombres)[:10]) + (" …" if len(nombres) > 10 else ""))
    log("\nArchivos que escribió dentro de la carpeta del juego:")
    lista(rep["escritos"]) if rep["escritos"] else log("    (ninguno)")
    if rep["escritos_fuera"]:
        log("\nArchivos que escribió fuera de la carpeta del juego:")
        lista(rep["escritos_fuera"])


def guardar(rep, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)


def ejecutar(carpeta, exe, procmon=None, segundos=0, guardar_traza=None, log=print, **wine):
    """Ejecuta el juego con el método de la plataforma.  -> (accesos, cómo)."""
    if sys.platform == "win32":
        if not procmon:
            raise SystemExit("en Windows la traza usa Process Monitor de Sysinternals: descargalo e indicá --procmon RUTA\\Procmon.exe")
        return ejecutar_procmon(carpeta, exe, procmon, segundos, guardar_traza, log)
    return ejecutar_wine(carpeta, exe, segundos=segundos, guardar=guardar_traza, log=log, **wine)


def accesos_json(accesos):
    return [asdict(a) for a in accesos]

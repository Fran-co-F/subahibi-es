# SPDX-License-Identifier: GPL-3.0-or-later
"""API local (HTTP + JSON) para la interfaz gráfica:  tl-organizer servir  /  tl-organizer gui.

Escucha solo en 127.0.0.1 y cada pedido a /api tiene que traer el token de la sesión en la cabecera X-TL-Token (así una
página web abierta en el navegador no puede tocar tus archivos).  Hecha con la biblioteca estándar: no agrega dependencias.

    GET  /api/info                               versión y proyecto abierto (o null)
    POST /api/proyecto/abrir   {carpeta}         abre el proyecto de esa carpeta (o de una de arriba)
    POST /api/proyecto/crear   {carpeta, parche_viejo?, idioma?}
    GET  /api/resumen                            filas por estado, por grupo y por escenario
    GET  /api/filas?escenario=&q=&estado=&tipo=&offset=&limit=
    PUT  /api/filas            {cambios: [{clave, traduccion, estado, nota, base}]}   (fusión a tres bandas)
    POST /api/revisar          {estados?, max_caracteres?, max_lineas?}
    POST /api/tareas           {tipo: exportar|build|jugable|instalar|desinstalar|wrap, opciones?}
    GET  /api/tareas/<id>?desde=N                registro y resultado de una tarea
    GET  /api/galeria                            imágenes de interfaz con su estado
    GET  /api/galeria/(original|traducida)/<nombre>
    PUT  /api/galeria/traducida/<nombre>         cuerpo: la imagen (PNG/BMP, mismo tamaño que el original)
    PUT  /api/galeria/estado   {nombre, estado, nota}
    GET|PUT /api/config        preferencias de la interfaz guardadas en el proyecto (vista previa…)
Lo demás se sirve desde la carpeta de la interfaz compilada (gui/dist), si existe.
"""
import argparse
import io
import json
import mimetypes
import os
import secrets
import shutil
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import motores
from . import flujo, perfiles, proyecto as project

VERSION_API = 1


class ApiError(Exception):
    def __init__(self, status, mensaje):
        super().__init__(mensaje)
        self.status = status


class Tarea:
    def __init__(self, id_, tipo):
        self.id, self.tipo = id_, tipo
        self.estado = "corriendo"                      # corriendo | ok | error
        self.log, self.resultado, self.error = [], None, None
        self.inicio, self.fin = time.time(), None

    def json(self, desde=0):
        return dict(id=self.id, tipo=self.tipo, estado=self.estado, log=self.log[desde:], total_log=len(self.log),
                    resultado=self.resultado, error=self.error, segundos=round((self.fin or time.time()) - self.inicio, 1))


class Servidor:
    def __init__(self, token, carpeta_proyecto=None, estaticos=None):
        self.token = token
        self.estaticos = estaticos
        self.lock = threading.Lock()                   # una sola operación que escribe a la vez (las cortas esperan su turno)
        self.tarea_activa = None                       # una tarea larga en curso: lo que escribe se rechaza enseguida
        self.tareas = {}
        self.proyecto = project.find(carpeta_proyecto) if carpeta_proyecto else None

    # ------------------------------------------------------------ ayudas
    def proj(self):
        if self.proyecto is None:
            raise ApiError(409, "no hay un proyecto abierto")
        return self.proyecto

    def _ocupado(self):
        """Toma el candado para una operación corta que escribe (o 409 si hay una tarea larga en curso)."""
        if not self.lock.acquire(timeout=120):
            raise ApiError(409, "el proyecto está ocupado; probá de nuevo")
        if self.tarea_activa:
            self.lock.release()
            raise ApiError(409, f"hay una tarea en curso ({self.tarea_activa.tipo}); esperá a que termine")

    def _sincronizar(self, proj, log=lambda *a: None):
        """Trae lo editado en las hojas (durante una tarea larga no: se lee lo que hay)."""
        if self.tarea_activa:
            return
        with self.lock:
            if not self.tarea_activa:
                flujo.sincronizar(proj, log)

    def info_proyecto(self):
        p = self.proyecto
        if p is None:
            return None
        return dict(raiz=p.root, trabajo=p.work, perfil=p.perfil.id, juego=p.perfil.nombre, motor=p.perfil.motor,
                    version=p.version, idiomas=list(p.idiomas), parche_viejo=p.parche_viejo,
                    capacidades=sorted(p.motor.capacidades), exportado=p.almacen.existe(),
                    instalado=os.path.exists(os.path.join(p.dir("backup"), "instalado.json")),
                    build=os.path.isdir(p.dir("salida")) and bool(os.listdir(p.dir("salida"))))

    # ------------------------------------------------------------ rutas
    def get_info(self, q):
        return dict(version_api=VERSION_API, proyecto=self.info_proyecto(), motores=list(motores.disponibles()),
                    recientes=_recientes())

    def post_proyecto_abrir(self, q, body):
        carpeta = (body or {}).get("carpeta") or ""
        p = project.find(carpeta) if carpeta and os.path.isdir(carpeta) else None
        if p is None:
            raise ApiError(404, f"no hay un proyecto en {carpeta or '(carpeta vacía)'}: creá uno")
        self.proyecto = p
        _recordar(p.root)
        return self.info_proyecto()

    def post_proyecto_crear(self, q, body):
        body = body or {}
        self._ocupado()
        try:
            p, _creado = project.init(body.get("carpeta") or "", body.get("parche_viejo") or None, destino=body.get("idioma") or None)
        finally:
            self.lock.release()
        self.proyecto = p
        _recordar(p.root)
        return self.info_proyecto()

    def get_resumen(self, q):
        p = self.proj()
        self._sincronizar(p)
        if not p.almacen.existe():
            return dict(exportado=False, estados={}, grupos=[])
        total, grupos = {}, []
        for grupo, escs in p.almacen.leer().items():
            lista = []
            for esc, filas in escs.items():
                c = {}
                for f in filas:
                    c[f["estado"]] = c.get(f["estado"], 0) + 1
                    total[f["estado"]] = total.get(f["estado"], 0) + 1
                lista.append(dict(escenario=esc, filas=len(filas), estados=c))
            grupos.append(dict(grupo=grupo, escenarios=lista))
        trad = p.dir("traducidas")
        return dict(exportado=True, estados=total, grupos=grupos,
                    imagenes_traducidas=len(os.listdir(trad)) if os.path.isdir(trad) else 0)

    def get_filas(self, q):
        from .almacen import huella
        p = self.proj()
        self._sincronizar(p)
        if not p.almacen.existe():
            return dict(total=0, filas=[])
        esc = q.get("escenario")
        if esc:
            try:
                _g, filas = p.almacen.leer_escenario(esc)
            except KeyError:
                raise ApiError(404, f"no existe el escenario {esc}")
        else:
            filas = [f for fs in p.almacen.filas_por_escenario().values() for f in fs]
        texto = (q.get("q") or "").lower()
        estados = set(filter(None, (q.get("estado") or "").split(",")))
        tipo = q.get("tipo")
        if texto or estados or tipo:
            filas = [f for f in filas if (not estados or f["estado"] in estados) and (not tipo or f["tipo"] == tipo)
                     and (not texto or texto in f["original"].lower() or texto in f["traduccion"].lower()
                          or texto in f["clave"].lower() or texto in f["nota"].lower())]
        offset, limit = int(q.get("offset") or 0), int(q.get("limit") or 100000)
        out = [dict(f, base=huella(f)) for f in filas[offset:offset + limit]]
        return dict(total=len(filas), filas=out)

    def put_filas(self, q, body):
        from .almacen import huella
        p = self.proj()
        lista = (body or {}).get("cambios", [])
        for c in lista:
            if not c.get("clave") or any(not isinstance(c.get(k), str) for k in ("traduccion", "estado", "nota")):
                raise ApiError(400, "cada cambio necesita clave, traduccion, estado y nota (y la base de la fila)")
        cambios = {c["clave"]: ({k: c[k] for k in ("traduccion", "estado", "nota")}, c.get("base")) for c in lista}
        if not cambios:
            return dict(actualizadas=0, conflictos=[], errores=[], filas={})
        self._ocupado()
        try:
            flujo.sincronizar(p, lambda *a: None)
            rep = p.almacen.aplicar(cambios)
            actuales = {f["clave"]: dict(f, base=huella(f)) for fs in p.almacen.filas_por_escenario().values()
                        for f in fs if f["clave"] in cambios}
        finally:
            self.lock.release()
        return dict(actualizadas=rep["actualizadas"], conflictos=[dict(clave=k, detalle=d) for k, d in rep["conflictos"]],
                    errores=[dict(clave=k, detalle=d) for k, d in rep["errores"]], filas=actuales)

    def post_revisar(self, q, body):
        from . import wrap
        body = body or {}
        p = self.proj()
        fits = wrap.make_fits(body.get("max_caracteres")) if body.get("max_caracteres") else None
        self._ocupado()
        try:
            probs = flujo.revisar(p, body.get("estados") or None, fits, body.get("max_lineas") or None, log=lambda *a: None)
        finally:
            self.lock.release()
        cuenta = {}
        for pr in probs:
            cuenta.setdefault(pr.codigo, {"nivel": pr.nivel, "filas": 0})["filas"] += 1
        return dict(total=len(probs), por_codigo=cuenta,
                    problemas=[pr.__dict__ for pr in probs[:int(body.get("limite") or 5000)]])

    def post_tareas(self, q, body):
        body = body or {}
        tipo = body.get("tipo")
        if tipo not in TAREAS:
            raise ApiError(400, f"tarea desconocida: {tipo}")
        p = self.proj()
        self._ocupado()
        t = Tarea(secrets.token_hex(4), tipo)
        self.tareas[t.id] = t
        self.tarea_activa = t                          # desde acá, lo que escribe se rechaza hasta que termine
        self.lock.release()

        def correr():
            try:
                t.resultado = _json_seguro(TAREAS[tipo](p, body.get("opciones") or {}, t.log.append))
                t.estado = "ok"
            except SystemExit as e:
                t.estado, t.error = "error", str(e)
            except Exception as e:                     # noqa: BLE001 — se informa en la interfaz
                t.estado, t.error = "error", f"{type(e).__name__}: {e}"
                t.log.append(traceback.format_exc())
            finally:
                t.fin = time.time()
                self.tarea_activa = None
        threading.Thread(target=correr, daemon=True).start()
        return t.json()

    def get_tarea(self, q, id_):
        t = self.tareas.get(id_)
        if t is None:
            raise ApiError(404, "no existe esa tarea")
        return t.json(int(q.get("desde") or 0))

    def get_galeria(self, q):
        from .galeria import index
        p = self.proj()
        filas = index.listar(p.dir("originales"), p.dir("traducidas"), p.estado_tsv,
                             p.perfil.seccion("galeria").get("pantallas"))
        for f in filas:
            f["traducida"] = bool(f["traducida"])
        return dict(imagenes=filas, etiquetas=index.ETIQUETAS, colores=index.COLORES)

    def get_galeria_imagen(self, q, cual, nombre):
        p = self.proj()
        if cual == "original":
            path = os.path.join(p.dir("originales"), _nombre_seguro(nombre) + ".png")
        else:
            tr = p.dir("traducidas")
            cand = [f for f in os.listdir(tr) if os.path.splitext(f)[0] == _nombre_seguro(nombre)] if os.path.isdir(tr) else []
            if not cand:
                raise ApiError(404, "no hay imagen traducida")
            path = os.path.join(tr, cand[0])
        if not os.path.isfile(path):
            raise ApiError(404, "no existe la imagen")
        if path.lower().endswith(".png"):
            with open(path, "rb") as f:
                return Binario(f.read(), "image/png")
        from .imagenes import open_any
        buf = io.BytesIO()
        open_any(path).save(buf, format="PNG")
        return Binario(buf.getvalue(), "image/png")

    def put_galeria_traducida(self, q, nombre, datos):
        from PIL import Image
        from .imagenes import open_any
        p = self.proj()
        nombre = _nombre_seguro(nombre)
        orig = os.path.join(p.dir("originales"), nombre + ".png")
        if not os.path.isfile(orig):
            raise ApiError(404, f"no hay una imagen original llamada {nombre}")
        tmp = os.path.join(p.dir("traducidas"), f".{nombre}.subiendo")
        os.makedirs(p.dir("traducidas"), exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(datos)
        try:
            im = open_any(tmp)
        except Exception:
            os.remove(tmp)
            raise ApiError(400, "no es una imagen PNG o BMP")
        with Image.open(orig) as o:
            if im.size != o.size:
                os.remove(tmp)
                raise ApiError(400, f"tamaño {im.size[0]}x{im.size[1]} distinto del original {o.size[0]}x{o.size[1]}")
        for f in os.listdir(p.dir("traducidas")):
            if os.path.splitext(f)[0] == nombre:
                os.remove(os.path.join(p.dir("traducidas"), f))
        im.save(os.path.join(p.dir("traducidas"), nombre + ".png"))
        os.remove(tmp)
        return dict(ok=True)

    def put_galeria_estado(self, q, body):
        from .galeria import index
        body = body or {}
        p = self.proj()
        nombre, estado, nota = _nombre_seguro(body.get("nombre") or ""), body.get("estado"), (body.get("nota") or "").replace("\t", " ")
        if estado not in index.ETIQUETAS or estado == "traducida":
            raise ApiError(400, f"estado inválido: {estado}")
        lineas = open(p.estado_tsv, encoding="utf-8").read().split("\n") if os.path.exists(p.estado_tsv) else []
        lineas = [l for l in lineas if l.split("\t")[0] != nombre]
        primera = next((i for i, l in enumerate(lineas) if l.strip() and not l.startswith("#")), len(lineas))
        lineas.insert(primera, f"{nombre}\t{estado}\t{nota}".rstrip("\t"))     # la regla exacta va antes que los patrones
        with open(p.estado_tsv, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lineas).rstrip("\n") + "\n")
        return dict(ok=True)

    def get_config(self, q):
        return self.proj().cfg.get("gui", {})

    def put_config(self, q, body):
        p = self.proj()
        p.cfg["gui"] = {**p.cfg.get("gui", {}), **(body or {})}
        with open(p.json_path, "w", encoding="utf-8") as f:
            json.dump(p.cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return p.cfg["gui"]


class Binario:
    def __init__(self, datos, tipo):
        self.datos, self.tipo = datos, tipo


# ---------------------------------------------------------------- tareas largas

def _opciones_build(proj, extra):
    """Las opciones de build del motor con sus valores por defecto (los de la línea de comandos), pisadas por 'extra'."""
    ap = argparse.ArgumentParser()
    cls = type(proj.motor)
    cls.argumentos_build(ap)
    op = cls.opciones_build(ap.parse_args([]))
    op.update({k: v for k, v in extra.items() if k in op})
    return op


def _tarea_exportar(proj, op, log):
    return flujo.exportar(proj, forzar=bool(op.get("forzar")), log=log)


def _tarea_build(proj, op, log, jugable=False):
    proj.original_exe()
    out = proj.dir("jugable" if jugable else "salida")
    if not jugable and os.path.isdir(out):
        shutil.rmtree(out)
    estados = tuple(op.get("estados") or ("traducido", "del parche"))
    r = flujo.build(proj, out, estados, _opciones_build(proj, op), jugable=jugable, log=log)
    t = r.get("texto") or {}
    if t:
        log(f"{t.get('scripts', 0)} escenarios generados, {t.get('cambiadas', 0)} textos traducidos, {len(t.get('errores', []))} errores"
            + (f"; {t['omitidas']} filas no se aplicaron por su estado" if t.get("omitidas") else ""))
        for k, v in t.get("errores", [])[:50]:
            log(f"ERROR: {k} - {v}")
    if "imagenes" in r:
        log(f"{r['imagenes']['colocadas']} imágenes traducidas colocadas")
    log(f"listo: {out}")
    return r


def _tarea_wrap(proj, op, log):
    from . import wrap
    if not op.get("max_caracteres"):
        raise SystemExit("indicá el máximo de caracteres por línea")
    fits = wrap.make_fits(int(op["max_caracteres"]))
    flujo.sincronizar(proj, log)
    copia = os.path.join(proj.dir("backup"), "traduccion-antes-de-wrap")
    if not os.path.exists(copia):
        shutil.copytree(proj.almacen.carpeta, copia)
    tot, grupos = 0, set()
    for grupo, escs in proj.almacen.leer().items():
        for esc, rows in escs.items():
            c, o = wrap.wrap_rows(rows, fits, ("traducido", "del parche", "revisar"), bool(op.get("reflow")), op.get("max_lineas"))
            if c or o:
                proj.almacen.guardar(grupo, esc, rows)
                grupos.add(grupo)
                tot += c
    flujo.actualizar_vistas(proj, grupos, log)
    log(f"{tot} textos con saltos de línea nuevos")
    return dict(cambiados=tot)


TAREAS = {
    "exportar": _tarea_exportar,
    "build": _tarea_build,
    "jugable": lambda p, op, log: _tarea_build(p, op, log, jugable=True),
    "instalar": lambda p, op, log: flujo.instalar(p, log=log),
    "desinstalar": lambda p, op, log: flujo.desinstalar(p, log=log),
    "wrap": _tarea_wrap,
}


def _json_seguro(x):
    """Lo que devuelven las tareas, convertido a algo que se pueda pasar a JSON."""
    return json.loads(json.dumps(x, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))


def _nombre_seguro(n):
    n = os.path.basename(urllib.parse.unquote(n))
    if not n or n.startswith("."):
        raise ApiError(400, "nombre inválido")
    return n


# ---------------------------------------------------------------- proyectos recientes

def _archivo_recientes():
    return os.path.join(os.path.dirname(perfiles.carpeta_de_usuario()), "recientes.json")


def _recientes():
    try:
        with open(_archivo_recientes(), encoding="utf-8") as f:
            return [r for r in json.load(f) if os.path.isdir(r)][:10]
    except (OSError, ValueError):
        return []


def _recordar(raiz):
    lista = [raiz] + [r for r in _recientes() if r != raiz]
    try:
        os.makedirs(os.path.dirname(_archivo_recientes()), exist_ok=True)
        with open(_archivo_recientes(), "w", encoding="utf-8") as f:
            json.dump(lista[:10], f, ensure_ascii=False, indent=1)
    except OSError:
        pass


# ---------------------------------------------------------------- HTTP

RUTAS = [
    ("GET", ("info",), "get_info"),
    ("POST", ("proyecto", "abrir"), "post_proyecto_abrir"),
    ("POST", ("proyecto", "crear"), "post_proyecto_crear"),
    ("GET", ("resumen",), "get_resumen"),
    ("GET", ("filas",), "get_filas"),
    ("PUT", ("filas",), "put_filas"),
    ("POST", ("revisar",), "post_revisar"),
    ("POST", ("tareas",), "post_tareas"),
    ("GET", ("tareas", "*"), "get_tarea"),
    ("GET", ("galeria",), "get_galeria"),
    ("GET", ("galeria", "original|traducida", "*"), "get_galeria_imagen"),
    ("PUT", ("galeria", "traducida", "*"), "put_galeria_traducida"),
    ("PUT", ("galeria", "estado"), "put_galeria_estado"),
    ("GET", ("config",), "get_config"),
    ("PUT", ("config",), "put_config"),
]


def _ruta(metodo, partes):
    for m, patron, nombre in RUTAS:
        if m != metodo or len(patron) != len(partes):
            continue
        args = []
        for p, x in zip(patron, partes):
            if p == "*":
                args.append(x)
            elif "|" in p:
                if x not in p.split("|"):
                    break
                args.append(x)
            elif p != x:
                break
        else:
            return nombre, args
    return None, None


def crear_manejador(srv):
    class Manejador(BaseHTTPRequestHandler):
        server_version = "tl-organizer"

        def log_message(self, fmt, *args):
            pass                                        # silencioso: la interfaz muestra lo que importa

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-TL-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")

        def _responder(self, status, cuerpo, tipo="application/json; charset=utf-8"):
            datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(datos)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            self._atender("GET")

        def do_POST(self):
            self._atender("POST")

        def do_PUT(self):
            self._atender("PUT")

        def _atender(self, metodo):
            url = urllib.parse.urlsplit(self.path)
            if not url.path.startswith("/api/"):
                return self._estatico(url.path) if metodo == "GET" else self._responder(404, {"error": "no existe"})
            q = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
            if not secrets.compare_digest(self.headers.get("X-TL-Token", "") or q.pop("token", ""), srv.token):
                return self._responder(403, {"error": "token inválido"})
            partes = tuple(urllib.parse.unquote(p) for p in url.path[len("/api/"):].strip("/").split("/"))
            nombre, args = _ruta(metodo, partes)
            if nombre is None:
                return self._responder(404, {"error": f"no existe {metodo} {url.path}"})
            try:
                largo = int(self.headers.get("Content-Length") or 0)
                crudo = self.rfile.read(largo) if largo else b""
                if nombre == "put_galeria_traducida":
                    r = getattr(srv, nombre)(q, *args, crudo)
                elif metodo in ("POST", "PUT"):
                    r = getattr(srv, nombre)(q, json.loads(crudo or b"{}"), *args)
                else:
                    r = getattr(srv, nombre)(q, *args)
            except ApiError as e:
                return self._responder(e.status, {"error": str(e)})
            except (project.ProjectError, perfiles.PerfilError, motores.MotorError, SystemExit, ValueError) as e:
                return self._responder(400, {"error": str(e)})
            except Exception as e:                      # noqa: BLE001
                traceback.print_exc()
                return self._responder(500, {"error": f"{type(e).__name__}: {e}"})
            if isinstance(r, Binario):
                return self._responder(200, r.datos, r.tipo)
            return self._responder(200, r)

        def _estatico(self, path):
            if not srv.estaticos:
                return self._responder(404, {"error": "la interfaz no está compilada (cd gui && npm run build)"})
            rel = os.path.normpath(urllib.parse.unquote(path).lstrip("/")) or "index.html"
            full = os.path.join(srv.estaticos, rel)
            if rel.startswith("..") or not os.path.isfile(full):
                full = os.path.join(srv.estaticos, "index.html")
            with open(full, "rb") as f:
                datos = f.read()
            if full.endswith("index.html"):            # la página servida por nosotros recibe el token
                datos = datos.replace(b"<head>", b"<head><script>window.TL_ORGANIZER=" +
                                      json.dumps({"url": "", "token": srv.token}).encode() + b"</script>", 1)
            self._responder(200, datos, TIPOS.get(os.path.splitext(full)[1]) or mimetypes.guess_type(full)[0] or "application/octet-stream")

    return Manejador


TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
         ".json": "application/json", ".png": "image/png", ".woff2": "font/woff2"}


def carpeta_interfaz():
    """La interfaz compilada: dentro del paquete (instalado) o en gui/dist del repositorio (desarrollo)."""
    aqui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for c in (os.path.join(aqui, "interfaz"), os.path.join(os.path.dirname(os.path.dirname(aqui)), "gui", "dist")):
        if os.path.isfile(os.path.join(c, "index.html")):
            return c
    return None


def servir(puerto=0, token=None, carpeta_proyecto=None, abrir_navegador=False, log=print):
    token = token or os.environ.get("TL_ORGANIZER_TOKEN") or secrets.token_urlsafe(24)
    srv = Servidor(token, carpeta_proyecto, carpeta_interfaz())
    httpd = ThreadingHTTPServer(("127.0.0.1", puerto), crear_manejador(srv))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    log(f"LISTO {url}", flush=True) if log is print else log(f"LISTO {url}")
    if abrir_navegador:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

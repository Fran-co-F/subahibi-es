# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas sin archivos del juego. Las que usan el juego real se saltan si no existe GAME_DIR."""
import os
import struct

import pytest
from PIL import Image

from tl_organizer.motores.bgi import exe_patch
from tl_organizer.motores.bgi import image
from tl_organizer.motores.bgi.arc import Arc
from tl_organizer.nucleo.galeria import index


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    """Ni los perfiles del usuario ni un proyecto forzado por variable de entorno afectan a las pruebas."""
    monkeypatch.delenv("TL_ORGANIZER_PERFILES", raising=False)
    monkeypatch.delenv("TL_ORGANIZER_PROJECT", raising=False)
    monkeypatch.delenv("SUBAHIBI_ES_PROJECT", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-usuario"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config-usuario"))


def test_imagen_cruda_ida_y_vuelta():
    im = Image.new("RGBA", (5, 3), (10, 20, 30, 40))
    im.putpixel((1, 1), (200, 100, 50, 255))
    raw = image.from_pil(im)
    assert image.is_raw_image(raw)
    assert image.to_pil(raw).tobytes() == im.tobytes()


def test_exe_desconocido_se_rechaza():
    with pytest.raises(exe_patch.PatchError):
        exe_patch.patch(b"MZ" + b"\0" * 100, {})


def test_arc_sintetico(tmp_path):
    data = b"hola"
    table = b"a.txt".ljust(0x60, b"\0") + struct.pack("<II", 0, len(data)) + b"\0" * 24
    p = tmp_path / "x.arc"
    p.write_bytes(b"BURIKO ARC20" + struct.pack("<I", 1) + table + data)
    arc = Arc(str(p))
    assert arc.names() == ["a.txt"] and arc.read("a.txt") == data


def test_estado_manual_gana(tmp_path):
    f = tmp_path / "s.tsv"
    f.write_text("# c\nAB*\tdecidir\tnota\n", encoding="utf-8")
    assert index.read_status(str(f)) == [("AB*", "decidir", "nota")]


@pytest.mark.skipif(not os.environ.get("GAME_DIR"), reason="GAME_DIR no definido")
def test_juego_real_sysgrp():
    from tl_organizer.motores.bgi.images import export
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "tl_organizer_test")
    n, skipped = export.export_arc(os.path.join(os.environ["GAME_DIR"], "sysgrp.arc"), out)
    assert n == 338 and not skipped


def _escenario_sintetico(textos):
    """Escenario mínimo: cabecera, un push, un 'str' por texto y la tabla de cadenas."""
    import struct
    from tl_organizer.motores.bgi import scn
    head_rest = struct.pack("<I", 0) + struct.pack("<I", 1) + b"main\0" + struct.pack("<I", 0)
    head = scn.MAGIC + struct.pack("<I", 4 + len(head_rest) + 0)
    head += head_rest
    head += b"\0" * ((-len(head)) % 16)
    head = head[:0x1C] + struct.pack("<I", len(head) - 0x1C) + head[0x20:]
    n_words = 2 + 2 * len(textos)
    strs, off = b"", n_words * 4
    code = struct.pack("<II", 0, 1)
    for t in textos:
        b = t.encode("cp932") + b"\0"
        code += struct.pack("<II", 3, off + len(strs))
        strs += b
    return head + code + strs


def test_escenario_ida_y_vuelta():
    from tl_organizer.motores.bgi import scn
    data = _escenario_sintetico(["hola", "mundo"])
    sc = scn.parse(data)
    assert scn.serialize(sc) == data
    assert [sc.string_at(t.args[0]) for t in sc.tokens if t.op == 3] == [b"hola", b"mundo"]


def test_pagina_funciones_puras(tmp_path):
    """Las funciones de index.html (glob, TSV, zip, BMP de 32 bits) se prueban con Node si está instalado."""
    import shutil
    import subprocess
    import zipfile
    node = shutil.which("node")
    if not node:
        pytest.skip("node no instalado")
    from tl_organizer.nucleo.galeria import _page
    rows = [dict(n="SGX000000", g="SGX", w=2, h=1, st="sin_clasificar", note="", tr=False)]
    html = _page.render(rows, {"traducida": "T", "sin_clasificar": "S"}, {"traducida": "#000", "sin_clasificar": "#111"})
    js = html.split("<script>")[1].split("</script>")[0]
    bmp = tmp_path / "a.bmp"
    Image.new("RGBA", (2, 1), (1, 2, 3, 4)).save(bmp, format="BMP")
    prog = (js + """
const fs=require('fs');
const re=globToRegex('SGKeyCnfg2060[0-9]0');
if(!re.test('SGKeyCnfg206050')||re.test('SGKeyCnfg206051'))throw new Error('glob');
const r=parseTsv('# c\\nSG*\\tpendiente\\tn\\nmal\\testado_raro\\n',['pendiente']);
if(r.length!==1||r[0].note!=='n')throw new Error('tsv');
if(buildTsv([{n:'A',st:'decidir',note:'x\\ty'}]).split('\\n')[2]!=='A\\tdecidir\\tx y')throw new Error('buildTsv');
const d=decodeBmp(new Uint8Array(fs.readFileSync(process.argv[2])));
if(d.w!==2||d.h!==1||d.rgba[0]!==1||d.rgba[3]!==4)throw new Error('bmp alfa');
fs.writeFileSync(process.argv[3],makeZip([{name:'a.png',data:new Uint8Array([1,2,3])},{name:'b.bmp',data:new Uint8Array(100)}]));
""")
    f = tmp_path / "t.js"
    f.write_text(prog, encoding="utf-8")
    z = tmp_path / "o.zip"
    r = subprocess.run([node, str(f), str(bmp), str(z)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    zf = zipfile.ZipFile(z)
    assert zf.testzip() is None and zf.read("a.png") == b"\x01\x02\x03" and len(zf.read("b.bmp")) == 100


def test_acentos_ida_y_vuelta():
    from tl_organizer.motores.bgi.text import accents
    s = "¿Qué está pasando, señor Núñez? ¡Ándale! Pingüino, ÉL, ÍNDICE, ÓPERA, ÚLTIMO, ÜBER, Ñandú"
    raw = accents.encode(s)
    assert accents.decode(raw) == s
    assert all(b < 0x80 or 0xA1 <= b <= 0xDF for b in raw)         # solo ASCII o katakana de ancho medio
    assert accents.unencodable("hola €") == ["€"]
    assert accents.decode("日本語".encode("cp932")) == "日本語"


def _escenario_con_textos(textos, cmd=0x140):
    """Escenario sintético: por cada texto, 'str' + un comando (por defecto 0x140 = mensaje)."""
    import struct
    from tl_organizer.motores.bgi import scn
    head_rest = struct.pack("<I", 0) + struct.pack("<I", 1) + b"main\0" + struct.pack("<I", 0)
    head = scn.MAGIC + struct.pack("<I", 4 + len(head_rest)) + head_rest
    head += b"\0" * ((-len(head)) % 16)
    head = head[:0x1C] + struct.pack("<I", len(head) - 0x1C) + head[0x20:]
    # cada texto ocupa 3 palabras (str, operando, comando): la tabla de cadenas empieza tras todo el código
    start = 12 * len(textos)
    code, strs = b"", b""
    for t in textos:
        code += struct.pack("<II", 3, start + len(strs)) + struct.pack("<I", cmd)
        strs += t.encode("cp932") + b"\0"
    return head + code + strs


def test_texto_exportar_e_importar():
    from tl_organizer.motores.bgi import scn
    from tl_organizer.motores.bgi.text import accents, export, extract, import_
    from tl_organizer.nucleo import hojas
    jp = _escenario_con_textos(["こんにちは", "さようなら"])
    rows = export.script_rows("prueba", jp)
    assert [r["tipo"] for r in rows] == ["mensaje", "mensaje"] and rows[0]["original"] == "こんにちは"
    rows[0]["traduccion"], rows[0]["estado"] = "¡Hola, señor!", "traducido"
    rows[1]["traduccion"], rows[1]["estado"] = "Adiós", "sin traducir"       # no se aplica
    out, rep = import_.build_script("prueba", jp, rows)
    assert rep["cambiadas"] == 1 and rep["omitidas"] == 1 and not rep["errores"]
    sj = scn.parse(jp)
    nuevo = extract.rows(scn.parse(out, strings_start=sj.strings_start))
    assert accents.decode(nuevo[0].raw) == "¡Hola, señor!" and nuevo[1].raw == "さようなら".encode("cp932")
    # un hash distinto (juego de otra versión) y un carácter imposible se rechazan
    rows[0]["hash"] = "00000000"
    assert import_.build_script("prueba", jp, rows)[1]["errores"]
    rows[0]["hash"] = hojas.jp_hash("こんにちは".encode("cp932")); rows[0]["traduccion"] = "precio 5 €"
    assert "€" in import_.build_script("prueba", jp, rows)[1]["errores"][0][1]


def test_tsv_escapes(tmp_path):
    from tl_organizer.nucleo import hojas as sheet
    fila = dict(clave="a:00001", tipo="mensaje", original="x\ty\nz\\", traduccion="línea1\nlínea2", estado="traducido",
                nota="", pos=12, hash="abcd1234")
    p = tmp_path / "a.tsv"
    sheet.write_tsv(str(p), [fila])
    leida = sheet.read_tsv(str(p))[0]
    assert leida["original"] == "x\ty\nz\\" and leida["traduccion"] == "línea1\nlínea2" and leida["pos"] == "12"


def test_parche_viejo_zip_y_config(tmp_path, monkeypatch):
    import zipfile
    from tl_organizer.motores.bgi import oldpatch
    jp = _escenario_con_textos(["hola"])
    z = tmp_path / "parche.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Raiz/Script/CVTD/esc1", jp)
        zf.writestr("Raiz/Script/CVTD/boton", b"BM" + b"\0" * 50)
        zf.writestr("Raiz/Voice/CVTD/v1", b"x")
        zf.writestr("Raiz/BGI.exe", b"x")
    op = oldpatch.OldPatch(str(z))
    assert sorted((k, n) for k, n, _ in op.files()) == [("Script", "boton"), ("Script", "esc1"), ("Voice", "v1")]
    assert list(op.scenarios()) == ["esc1"]
    r = op.copy_loose(str(tmp_path / "out"), skip=lambda kind, name, head: name == "boton")
    assert r["copiados"] == 2 and (tmp_path / "out" / "Voice" / "CVTD" / "v1").exists()


def test_modo_utf8_reescribe_todo():
    """En modo UTF-8 también las cadenas japonesas sin traducir pasan de Shift-JIS a UTF-8."""
    from tl_organizer.motores.bgi import scn
    from tl_organizer.motores.bgi.text import export, extract, import_
    jp = _escenario_con_textos(["こんにちは", "さようなら"])
    rows = export.script_rows("prueba", jp)
    rows[0]["traduccion"], rows[0]["estado"] = "¡Hola, señor! ñé", "traducido"
    out, rep = import_.build_script("prueba", jp, rows, utf8=True)
    nuevo = extract.rows(scn.parse(out, strings_start=scn.parse(jp).strings_start))
    assert nuevo[0].raw.decode("utf-8") == "¡Hola, señor! ñé"            # español tal cual
    assert nuevo[1].raw.decode("utf-8") == "さようなら"                      # japonés convertido a UTF-8
    assert rep["cambiadas"] == 1 and not rep["errores"]
    # sin traducciones, el modo UTF-8 igual produce el escenario convertido
    out2, rep2 = import_.build_script("prueba", jp, export.script_rows("prueba", jp), utf8=True)
    assert out2 is not None and extract.rows(scn.parse(out2, strings_start=scn.parse(jp).strings_start))[0].raw.decode("utf-8") == "こんにちは"


def test_exe_utf8_desvia_la_entrada():
    from tl_organizer.motores.bgi import exe_patch
    assert "utf8" in exe_patch.patch.__code__.co_varnames


def test_wrap_corta_en_palabras():
    from tl_organizer.nucleo import wrap
    fits = wrap.make_fits(max_chars=20)
    t = "El veloz murciélago hindú comía feliz cardillo"
    r = wrap.wrap_text(t, fits)
    assert all(len(l) <= 20 for l in r.split("\n")) and r.replace("\n", " ") == t
    assert wrap.wrap_text("corto", fits) == "corto"
    assert wrap.wrap_text("supercalifragilisticoespialidoso corto", fits) == "supercalifragilisticoespialidoso\ncorto"   # palabra larga: no se parte
    # los saltos que ya hay se respetan; con reflow se rehacen
    assert wrap.wrap_text("uno dos\ntres cuatro cinco seis siete", fits) == "uno dos\ntres cuatro cinco\nseis siete"
    assert wrap.wrap_text("uno dos\ntres", fits, reflow=True) == "uno dos tres"
    rows = [dict(tipo="mensaje", traduccion=t, estado="del parche", nota=""), dict(tipo="mensaje", traduccion=t, estado="sin traducir", nota="")]
    assert wrap.wrap_rows(rows, fits, max_lines=2) == (1, 1) and "más de 2 líneas" in rows[0]["nota"] and "\n" not in rows[1]["traduccion"]


def test_nombre_de_fuente_configurable():
    import pytest
    from tl_organizer.motores.bgi import exe_patch
    assert exe_patch.font_slot("Lune") == b"Lune" + b"\0" * 12
    for malo in ("", "NombreDeFuenteDemasiadoLargo", "Fuente ñ"):
        with pytest.raises(exe_patch.PatchError):
            exe_patch.font_slot(malo)


def test_enlaces_con_respaldo(tmp_path, monkeypatch):
    """Sin permiso para enlaces simbólicos (Windows normal) se usa enlace duro y, si tampoco, copia."""
    import os as _os
    import shutil
    from tl_organizer.nucleo import enlaces as build
    src = tmp_path / "datos.arc"
    src.write_bytes(b"x" * 100)
    assert build._link(str(src), str(tmp_path / "a")) in ("enlace simbólico", "enlace duro")
    def sin_permiso(*a, **k):
        raise OSError("sin permiso")
    monkeypatch.setattr(_os, "symlink", sin_permiso)
    assert build._link(str(src), str(tmp_path / "b")) == "enlace duro" and (tmp_path / "b").read_bytes() == b"x" * 100
    monkeypatch.setattr(_os, "link", sin_permiso)
    assert build._link(str(src), str(tmp_path / "c")) == "copia" and (tmp_path / "c").read_bytes() == b"x" * 100
    assert build._link(str(src), str(tmp_path / "c")) == "copia"              # idempotente: no vuelve a copiar
    assert shutil.copy2  # (la copia conserva la fecha, por eso se reconoce)


REQUERIDOS = ("BGI.exe", "sysgrp.arc", "sysprg.arc", "system.arc", "data01101.arc")


def _perfil(tmp_path, monkeypatch, texto, nombre="falso.toml"):
    """Escribe un perfil de juego en una carpeta de $TL_ORGANIZER_PERFILES."""
    d = tmp_path / "perfiles"
    d.mkdir(exist_ok=True)
    (d / nombre).write_text(texto, encoding="utf-8")
    monkeypatch.setenv("TL_ORGANIZER_PERFILES", str(d))
    return d / nombre


def _juego_falso(tmp_path, monkeypatch):
    """Una 'instalación' mínima: un perfil de prueba registra el BGI.exe falso como versión conocida."""
    g = tmp_path / "juego"
    g.mkdir()
    (g / "BGI.exe").write_bytes(b"MZ-falso")
    for f in REQUERIDOS[1:]:
        (g / f).write_bytes(b"x")
    _perfil(tmp_path, monkeypatch, f"""
id = "falso"
nombre = "Juego falso"
motor = "bgi"
[deteccion]
requeridos = {list(REQUERIDOS)!r}
ejecutable = "BGI.exe"
[[bgi.ejecutables]]
sha256 = "{exe_patch.sha256(b"MZ-falso")}"
version = "falso 1.0"
""".replace("'", '"'))
    return g


def test_init_valida_y_crea_el_proyecto(tmp_path, monkeypatch):
    from tl_organizer.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, creado = project.init(str(g))
    assert creado and proj.cfg["perfil"] == "falso" and proj.cfg["motor"] == "bgi" and proj.version == "falso 1.0"
    for name in ("originales", "traduccion", "hojas", "traducidas", "indice", "backup", "salida"):
        assert (g / project.WORK / project.SUBDIRS[name]).is_dir()
    assert (g / project.WORK / "backup" / "BGI.exe").read_bytes() == b"MZ-falso"      # respaldo del exe original
    assert (g / "tl-organizer.json").exists() and (g / project.WORK / "imagenes" / "estado.tsv").exists()
    assert "traduccion" not in (g / project.WORK / ".gitignore").read_text(encoding="utf-8").split("\n")    # se versiona
    sub = g / "Script"
    sub.mkdir()
    assert project.find(str(sub)).root == str(g)                  # se encuentra desde una subcarpeta
    with pytest.raises(project.ProjectError):
        project.init(str(g))                                      # no se puede repetir
    # agregar el parche viejo a un proyecto existente
    z = tmp_path / "p.zip"
    z.write_bytes(b"x")
    assert project.init(str(g), str(z))[1] is False and project.find(str(g)).parche_viejo == str(z)


def test_init_rechaza_lo_que_no_es_el_juego(tmp_path):
    from tl_organizer.nucleo import proyecto as project
    vacia = tmp_path / "otra"
    vacia.mkdir()
    with pytest.raises(project.ProjectError) as e:
        project.init(str(vacia))
    assert "falta" in str(e.value)
    # con todos los archivos de la 15th pero un exe desconocido, el más parecido es ese perfil y dice qué pasa con el exe
    for f in REQUERIDOS:
        (vacia / f).write_bytes(b"cualquier cosa")
    with pytest.raises(project.ProjectError) as e:
        project.init(str(vacia))
    assert "Subarashiki Hibi" in str(e.value) and "BGI.exe no es una versión conocida" in str(e.value)


def test_reset_no_toca_el_juego(tmp_path, monkeypatch):
    from tl_organizer.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    project.reset(proj)                                           # solo el JSON
    assert not (g / "tl-organizer.json").exists() and (g / project.WORK).is_dir() and (g / "BGI.exe").exists()
    proj, _ = project.init(str(g))
    project.reset(proj, todo=True)                                # JSON y carpeta de trabajo; el juego queda
    assert not (g / project.WORK).exists() and (g / "BGI.exe").exists() and (g / "sysgrp.arc").exists()


def test_instalar_y_desinstalar(tmp_path, monkeypatch):
    from tl_organizer.nucleo import flujo as workflow, proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    salida = g / project.WORK / "salida"
    (salida / "Script" / "CVTD").mkdir(parents=True)
    (salida / "Script" / "CVTD" / "esc1").write_bytes(b"nuevo")
    (salida / "BGI.exe").write_bytes(b"MZ-parcheado")                    # pisa el exe original
    workflow.instalar(proj)
    assert (g / "BGI.exe").read_bytes() == b"MZ-parcheado" and (g / "Script" / "CVTD" / "esc1").read_bytes() == b"nuevo"
    assert proj.original_exe().endswith(os.path.join("backup", "BGI.exe"))   # con el parche instalado, el original sale del respaldo
    (salida / "Script" / "CVTD" / "esc1").write_bytes(b"nuevo2")
    workflow.instalar(proj)                                                   # reinstalar actualiza sin perder el respaldo original
    workflow.desinstalar(proj)
    assert (g / "BGI.exe").read_bytes() == b"MZ-falso" and not (g / "Script").exists()
    with pytest.raises(project.ProjectError):
        workflow.desinstalar(proj)


def test_cli_init_estado_reset(tmp_path, monkeypatch, capsys):
    from tl_organizer import cli
    from tl_organizer.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    monkeypatch.chdir(g)
    assert cli.main(["init"]) == 0 and (g / "tl-organizer.json").exists()
    assert "juego detectado" in capsys.readouterr().out
    monkeypatch.chdir(g / "tl-organizer-trabajo")                       # los comandos funcionan desde una subcarpeta
    assert project.find().root == str(g)
    with pytest.raises(SystemExit):
        cli.main(["init"])                                             # ya hay un proyecto
    assert cli.main(["reset", "--todo", "--si"]) == 0
    assert not (g / "tl-organizer.json").exists() and not (g / "tl-organizer-trabajo").exists() and (g / "BGI.exe").exists()
    monkeypatch.chdir(g)
    with pytest.raises(SystemExit) as e:
        cli.main(["build"])                                            # sin proyecto, mensaje claro
    assert "init" in str(e.value)


def test_parche_viejo_se_guarda_relativo(tmp_path, monkeypatch):
    """Si el parche viejo está dentro del proyecto, la ruta se guarda relativa y sobrevive a mover la carpeta."""
    import json
    import shutil
    from tl_organizer.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    (g / "parche.zip").write_bytes(b"x")
    proj, _ = project.init(str(g), str(g / "parche.zip"))
    assert json.load(open(g / "tl-organizer.json", encoding="utf-8"))["parche_viejo"] == "parche.zip"
    assert proj.parche_viejo == str(g / "parche.zip")
    nuevo = tmp_path / "movido"
    shutil.move(str(g), str(nuevo))
    assert project.find(str(nuevo)).parche_viejo == str(nuevo / "parche.zip")
    fuera = tmp_path / "fuera.zip"
    fuera.write_bytes(b"x")
    proj2, _ = project.init(str(nuevo), str(fuera))                          # ya existe: actualiza; fuera del proyecto queda absoluta
    assert project.find(str(nuevo)).parche_viejo == str(fuera)


def test_estado_tsv_arranca_vacio(tmp_path, monkeypatch):
    from tl_organizer.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    assert index.read_status(proj.estado_tsv) == []                          # solo comentarios: ninguna regla propia
    assert "patrón<TAB>estado<TAB>nota" in open(proj.estado_tsv, encoding="utf-8").read()


def test_export_no_crea_hojas_vacias(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from tl_organizer.motores.bgi.text import export
    from tl_organizer.nucleo import texto
    con = _escenario_con_textos(["hola", "mundo"])
    sin = _escenario_con_textos(["cualquier_nombre"], cmd=0x1a1)     # una cadena que no es texto (nombre de archivo, etc.)
    fuente = [(g, n, export.script_rows(n, d)) for g, n, d in [("a", "con_texto", con), ("a", "sin_texto", sin), ("b", "solo_vacio", sin)]]
    r = texto.exportar(fuente, str(tmp_path / "out"))
    assert r["scripts"] == 1 and sorted(r["sin_texto"]) == ["sin_texto", "solo_vacio"]
    assert sorted(f.name for f in (tmp_path / "out").iterdir()) == ["a.xlsx"]     # b.xlsx no existe: no tenía ninguna hoja con filas
    from tl_organizer.nucleo import hojas as sheet
    assert list(sheet.read_xlsx(str(tmp_path / "out" / "a.xlsx"))) == ["con_texto"]


def test_alineacion_dudosa_por_correlacion_de_largos():
    import random
    from tl_organizer.nucleo import alineacion as align
    random.seed(7)
    jp = [random.randint(3, 120) for _ in range(300)]
    es = [int(x * 2.4) + random.randint(-4, 4) for x in jp]               # bien alineado: largos proporcionales
    assert align.doubtful(jp, es) == set()
    roto = es[:150] + es[151:] + [50]                                      # a partir de la fila 150 el español está corrido una fila
    bad = align.doubtful(jp, roto)
    assert bad and min(bad) >= 120 and max(bad) == 299                     # se marca desde la zona del desfase, no antes
    assert align.doubtful(jp[:5], es[:5]) == set()                         # muy pocos pares: no se puede juzgar
    assert align.doubtful(jp[:30], list(reversed(es[:30]))) == set(range(30))     # escenario corto sin relación: todo dudoso


def test_precarga_quita_el_tab_final(tmp_path, monkeypatch):
    from tl_organizer.motores.bgi.text import export
    jp = _escenario_con_textos(["こんにちは"])
    old = _escenario_con_textos(["Hola\t"])                               # el parche viejo agrega un TAB final
    rows = export.script_rows("p", jp, old)
    assert rows[0]["traduccion"] == "Hola" and rows[0]["estado"] == "del parche"


def test_estado_por_archivo_y_por_escenario(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from tl_organizer.nucleo import flujo as workflow, hojas as sheet, proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    (g / project.WORK / "texto").mkdir()                     # un proyecto de antes del almacén: hojas en texto/
    fila = lambda esc, i, st: dict(clave=f"{esc}:{i:05d}", tipo="mensaje", original="j", traduccion="e" if st != "sin traducir" else "",
                                   estado=st, nota="", pos=i, hash="h")
    sheet.write_xlsx(str(g / project.WORK / "texto" / "data01.xlsx"),
                     {"esc_a": [fila("esc_a", 1, "del parche"), fila("esc_a", 2, "del parche"), fila("esc_a", 3, "sin traducir"),
                                fila("esc_a", 4, "revisar")],
                      "esc_b": [fila("esc_b", 1, "traducido")]})
    sheet.write_xlsx(str(g / project.WORK / "texto" / "data02.xlsx"), {"esc_c": [fila("esc_c", i, "sin traducir") for i in range(1, 5)]})
    def salida(nivel):
        out = []
        workflow.estado(proj, log=out.append, nivel=nivel)
        return "\n".join(out)
    v0, v1, v2 = salida(0), salida(1), salida(2)
    assert "9 filas en 2 archivos" in v0 and "listo 33.3%" in v0
    assert proj.almacen.existe() and not (g / project.WORK / "texto").exists()                  # se migró a traduccion/
    assert (g / project.WORK / "hojas" / "data01.xlsx").exists() and list((g / project.WORK / "backup").glob("texto-migrado-*"))                                 # 3 de 9 listas (2 del parche + 1 traducido)
    assert "data01" not in v0 and "archivo" in v1 and "data01" in v1 and "esc_a" not in v1
    linea = [l for l in v1.splitlines() if l.startswith("data01")][0]
    assert linea.split()[:3] == ["data01", "5", "60.0%"]                                       # 3 de 5 listas
    assert [l for l in v1.splitlines() if l.startswith("data02")][0].split()[:3] == ["data02", "4", "0.0%"]
    assert "== data01 ==" in v2 and "esc_a" in v2 and "esc_c" in v2
    assert [l for l in v2.splitlines() if l.startswith("esc_a")][0].split()[:3] == ["esc_a", "4", "50.0%"]


# ---------------------------------------------------------------- perfiles y motores

def test_perfil_incluido_conserva_los_datos_del_exe():
    """El perfil TOML de la 15th reproduce exactamente las direcciones que antes estaban fijas en exe_patch.py."""
    from tl_organizer import motores
    from tl_organizer.nucleo import perfiles
    perfil = perfiles.obtener("subahibi-15th")
    m = motores.crear(perfil)
    b = m.builds["993e9803a4335ff752dd7b4fd7b5036c3200c88c74fbde05d29b5123be5bd29c"]
    assert b["font"] == [(0x17C740, b"MS Gothic\x00", 16), (0x17C750, b"\x82l\x82r \x83S\x83V\x83b\x83N\x00", 16)]
    assert (b["hook"], b["hook_bytes"], b["cave"], b["back"]) == (0x1400DF7FA, "89742428458bc4", 0x1400DF76C, 0x1400DF801)
    assert (b["entry_field"], b["entry_rva"], b["image_base"], b["utf8_cave"], b["set_encoding"]) == \
        (0x150, 0x11D74, 0x140000000, 0x140001DF0, 0x1400F74C0)
    assert m.fuente == "SubaHibi07Inq" and m.data_arcs == ("data0*.arc",) and m.ui_arcs == ("sysgrp.arc",)
    assert perfil.requeridos == list(REQUERIDOS) and perfil.ejecutable == "BGI.exe"


def test_perfil_del_usuario_gana_y_errores_claros(tmp_path, monkeypatch):
    from tl_organizer.nucleo import perfiles
    # un perfil del usuario con el mismo id reemplaza al incluido
    d = tmp_path / "config-usuario" / "tl-organizer" / "juegos"
    d.mkdir(parents=True)
    (d / "mio.toml").write_text('id = "subahibi-15th"\nnombre = "Mi versión"\nmotor = "bgi"\n', encoding="utf-8")
    assert perfiles.obtener("subahibi-15th").nombre == "Mi versión"
    # $TL_ORGANIZER_PERFILES tiene más prioridad que la carpeta del usuario
    _perfil(tmp_path, monkeypatch, 'id = "subahibi-15th"\nnombre = "De la variable"\nmotor = "bgi"\n')
    assert perfiles.obtener("subahibi-15th").nombre == "De la variable"
    with pytest.raises(perfiles.PerfilError, match="no encuentro el perfil"):
        perfiles.obtener("no-existe")
    for malo, msg in [('nombre = "x"\nmotor = "bgi"\n', "falta «id»"), ('id = "x"\nnombre = "x"\nmotor = "bgi"\ntexto = 3\n', "sección"),
                      ("id = = 1", "TOML inválido")]:
        p = tmp_path / "malo.toml"
        p.write_text(malo, encoding="utf-8")
        with pytest.raises(perfiles.PerfilError, match=msg):
            perfiles.leer(str(p))


def test_motor_desconocido_y_seccion_mal_escrita(tmp_path, monkeypatch):
    from tl_organizer import motores
    from tl_organizer.nucleo import perfiles
    with pytest.raises(motores.MotorError, match="motor desconocido «nada»"):
        motores.crear(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "nada"}))
    with pytest.raises(motores.MotorError, match="falta «version»"):
        motores.crear(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "bgi": {"ejecutables": [{"sha256": "ab"}]}}))
    with pytest.raises(motores.MotorError, match="fuente"):
        motores.crear(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "bgi": {"fuente": "Fuente ñ"}}))


def test_init_con_varios_perfiles_muestra_el_mas_parecido(tmp_path, monkeypatch):
    from tl_organizer.nucleo import proyecto as project
    _perfil(tmp_path, monkeypatch, 'id = "otro"\nnombre = "Otro juego"\nmotor = "bgi"\n[deteccion]\nrequeridos = ["otro.dat"]\n')
    g = tmp_path / "carpeta"
    g.mkdir()
    (g / "otro.dat").write_bytes(b"x")
    proj, _ = project.init(str(g))                        # un juego sin ejecutable que reconocer también vale
    assert proj.perfil.id == "otro" and proj.original_exe() is None
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    with pytest.raises(project.ProjectError, match="el más parecido es Otro juego") as e:
        project.init(str(vacia))
    assert "falta otro.dat" in str(e.value)


def test_proyecto_viejo_sin_perfil_se_sigue_abriendo(tmp_path):
    """Los proyectos creados antes de los perfiles guardaban la versión del exe en «motor» y no tenían «perfil»."""
    import json
    from tl_organizer.nucleo import proyecto as project
    (tmp_path / "subahibi-es.json").write_text(json.dumps({"version_del_proyecto": 1,          # el nombre anterior de la herramienta
                                                           "motor": "1.685.3 (15th Anniversary, x86_64)", "parche_viejo": None}),
                                               encoding="utf-8")
    (tmp_path / "subahibi-es-trabajo" / "texto").mkdir(parents=True)
    proj = project.find(str(tmp_path / "subahibi-es-trabajo" / "texto"))
    assert proj.perfil.id == "subahibi-15th" and proj.motor.nombre == "bgi" and proj.version.startswith("1.685.3")
    assert proj.json_path.endswith("subahibi-es.json") and proj.dir("texto") == str(tmp_path / "subahibi-es-trabajo" / "texto")


def test_jugable_nunca_enlaza_el_ejecutable(tmp_path):
    """Si el perfil pidiera enlazar los .exe, el del juego se omite: el exe parcheado se escribiría a través del enlace."""
    from tl_organizer.nucleo import enlaces, perfiles
    g, out = tmp_path / "g", tmp_path / "out"
    g.mkdir(); out.mkdir()
    for f in ("BGI.exe", "BHVC.exe", "a.arc", "nota.txt"):
        (g / f).write_bytes(b"x")
    perfil = perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "deteccion": {"ejecutable": "BGI.exe"},
                              "jugable": {"enlazar_extensiones": [".exe", ".arc"]}})
    n, _m = enlaces.link_game(str(g), str(out), perfil)
    assert n == 2 and sorted(os.listdir(out)) == ["BHVC.exe", "a.arc"]


# Un motor mínimo de prueba, cargado como plugin (entry point): solo sabe texto.
from tl_organizer.motores.base import Motor, TEXTO  # noqa: E402


class MotorDePrueba(Motor):
    nombre = "prueba"
    capacidades = frozenset({TEXTO})
    carpetas_sueltas = ("textos",)

    def textos(self, juego, parche_viejo=None, archivos=None):
        with open(os.path.join(juego, "juego.dat"), encoding="utf-8") as f:
            lineas = f.read().splitlines()
        filas = [dict(clave=f"esc1:{i:05d}", tipo="mensaje", original=t, traduccion="", estado="sin traducir", nota="", pos=i, hash="h")
                 for i, t in enumerate(lineas, 1)]
        yield "juego", "esc1", filas

    def construir(self, juego, salida, filas=None, imagenes=None, estados=(), opciones=None, parche_viejo=None,
                  ejecutable=None, log=print):
        os.makedirs(os.path.join(salida, "textos"), exist_ok=True)
        with open(os.path.join(salida, "textos", "esc1.txt"), "w", encoding="utf-8") as f:
            for r in (filas or {}).get("esc1", []):
                f.write((r["traduccion"] if r["estado"] in estados and r["traduccion"] else r["original"]) + "\n")
        return {"opciones": opciones}


def test_plugin_de_motor_con_su_perfil_hace_todo_el_flujo(tmp_path, monkeypatch):
    """Un motor nuevo = una clase + un entry point + un perfil TOML; el núcleo hace el resto (init, exportar, build, estado)."""
    pytest.importorskip("openpyxl")
    from importlib.metadata import EntryPoint
    from tl_organizer import motores
    from tl_organizer.nucleo import flujo, hojas, proyecto as project
    ep = EntryPoint("prueba", f"{__name__}:MotorDePrueba", motores.GRUPO)
    monkeypatch.setattr(motores, "entry_points", lambda group: [ep] if group == motores.GRUPO else [])
    assert "prueba" in motores.disponibles()
    _perfil(tmp_path, monkeypatch, 'id = "juego-prueba"\nnombre = "Juego de prueba"\nmotor = "prueba"\n'
                                   '[deteccion]\nrequeridos = ["juego.dat"]\n')
    g = tmp_path / "juego"
    g.mkdir()
    (g / "juego.dat").write_text("こんにちは\nさようなら\n", encoding="utf-8")
    proj, _ = project.init(str(g))
    assert proj.perfil.id == "juego-prueba" and isinstance(proj.motor, MotorDePrueba)
    rep = flujo.exportar(proj, log=lambda *a: None)
    assert "imagenes_exportadas" not in rep and rep["texto"]["filas"] == 2           # sin capacidad «imagenes», no se intenta
    assert (g / project.WORK / "traduccion" / "juego" / "esc1.tsv").exists()
    hoja = g / project.WORK / "hojas" / "juego.xlsx"
    sheets = hojas.read_xlsx(str(hoja))
    sheets["esc1"][0].update(traduccion="Hola", estado="traducido")          # lo que haría quien traduce en Excel
    hojas.write_xlsx(str(hoja), sheets, huella=lambda r: r["base"])
    r = flujo.build(proj, proj.dir("salida"), opciones={"x": 1}, log=lambda *a: None)
    assert r["opciones"] == {"x": 1}
    assert (g / project.WORK / "salida" / "textos" / "esc1.txt").read_text(encoding="utf-8") == "Hola\nさようなら\n"
    assert proj.almacen.filas_por_escenario()["esc1"][0]["traduccion"] == "Hola"            # build trajo la hoja a traduccion/
    out = []
    flujo.estado(proj, log=out.append)
    assert any("Juego de prueba" in l for l in out) and any("listo 50.0%" in l for l in out)


# ---------------------------------------------------------------- fase 2: idiomas, revisar, PO

def _fila(i, original, traduccion="", estado="traducido", tipo="mensaje", nota=""):
    return dict(clave=f"esc:{i:05d}", tipo=tipo, original=original, traduccion=traduccion, estado=estado, nota=nota, pos=i, hash="h")


def test_idiomas_del_proyecto_dan_los_encabezados(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from tl_organizer.nucleo import hojas, proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g), destino="en")
    assert proj.idiomas == ("ja", "en") and hojas.encabezado(proj.idiomas)[2:4] == ["japones", "ingles"]
    assert hojas.encabezado(("ja", "xx"))[3] == "xx"                        # código desconocido: tal cual
    # una hoja con otros nombres de idioma se lee igual (las columnas se reconocen por posición)
    p = tmp_path / "h.xlsx"
    hojas.write_xlsx(str(p), {"esc": [_fila(1, "原文", "translation")]}, ("ja", "en"))
    assert hojas.read_xlsx(str(p))["esc"][0]["traduccion"] == "translation"
    t = tmp_path / "h.tsv"
    hojas.write_tsv(str(t), [_fila(1, "原文", "traducción")])
    assert t.read_text(encoding="utf-8").split("\n")[0].split("\t")[2:4] == ["japones", "espanol"]
    t.write_text("clave\ttipo\tjapones\testado\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cabecera inesperada"):
        hojas.read_tsv(str(t))
    # los proyectos sin «idiomas» en el JSON son japonés -> español
    assert project.Project(str(g), {}).idiomas == ("ja", "es")


def test_revisar_controles_generales():
    from tl_organizer.nucleo import revisar as rv
    from tl_organizer.motores.bgi import MotorBGI
    from tl_organizer.nucleo import perfiles, wrap
    m = MotorBGI(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi"}))
    ctx = rv.Contexto(idiomas=("ja", "es"), motor=m, fits=wrap.make_fits(max_chars=20), max_lineas=2)
    filas = [
        _fila(1, "こんにちは", "Hola"),                                          # bien
        _fila(2, "こんにちは", "", estado="traducido"),                          # vacia
        _fila(3, "こんにちは", "こんにちは"),                                    # sin_traducir
        _fila(4, "こんにちは", "Hola さん, saーn"),                              # restos (la ー no cuenta)
        _fila(5, "こんにちは", "Hola\tamigo"),                                   # control
        _fila(6, "こんにちは", "Hola  amigo "),                                  # espacios (dobles y al final)
        _fila(7, "こんにちは\n", "Hola"),                                        # saltos
        _fila(8, "こんにちは", "¿Qué tal. ¡Bien!"),                              # puntuacion
        _fila(9, "こんにちは", "<i>Hola"),                                       # marcadores + etiquetas sin cerrar
        _fila(10, "こんにちは", "Hola\0"),                                       # caracteres (NUL)
        _fila(11, "こんにちは", "una línea demasiado larga para veinte\nb\nc"),  # largo + lineas
        _fila(12, "こんにちは", "<r よみ>Hola</r>", estado="sin traducir"),     # no se revisa por su estado
    ]
    por_clave = {}
    for p in rv.revisar_filas(filas, ctx):
        por_clave.setdefault(int(p.clave.split(":")[1]), set()).add(p.codigo)
    assert por_clave == {2: {"vacia"}, 3: {"sin_traducir"}, 4: {"restos"}, 5: {"control"}, 6: {"espacios"}, 7: {"saltos"},
                         8: {"puntuacion"}, 9: {"marcadores", "etiquetas"}, 10: {"caracteres"}, 11: {"largo", "lineas"}}
    assert rv.revisar_filas(filas, ctx)[0].nivel == rv.ERROR                  # primero los errores
    # etiquetas balanceadas e iguales al original: sin problemas
    assert not rv.revisar_filas([_fila(1, "<r よみ>漢字</r>", "<r lectura>Kanji</r>")], ctx)
    # modo katakana: lo que no entra en Shift-JIS es un error
    ctx.opciones = {"utf8": False}
    assert {p.codigo for p in rv.revisar_filas([_fila(1, "こんにちは", "precio: 5 €")], ctx)} == {"caracteres"}
    # destino que no es español: no hay control de ¿?
    assert not rv.revisar_filas([_fila(1, "こんにちは", "¿What")], rv.Contexto(idiomas=("ja", "en")))


def test_revisar_comando_escribe_el_informe(tmp_path, monkeypatch, capsys):
    pytest.importorskip("openpyxl")
    from tl_organizer import cli
    from tl_organizer.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    project.init(str(g))
    project.find(str(g)).almacen.escribir({"data01": {"esc": [_fila(1, "こんにちは", "<i>Hola"), _fila(2, "さようなら", "Adiós")]}})
    monkeypatch.chdir(g)
    assert cli.main(["revisar"]) == 1                                         # hay un error (etiqueta sin cerrar)
    out = capsys.readouterr().out
    assert "etiquetas" in out and "esc:00001" in out and "esc:00002" not in out
    informe = (g / project.WORK / "revision.tsv").read_text(encoding="utf-8").splitlines()
    assert informe[0].startswith("clave\tnivel") and len(informe) == 3      # etiquetas + marcadores


def test_po_ida_y_vuelta(tmp_path, monkeypatch):
    polib = pytest.importorskip("polib")
    from tl_organizer.nucleo import po
    from tl_organizer.nucleo.almacen import Almacen
    alm = Almacen(str(tmp_path / "traduccion"))
    alm.escribir({"data01": {"esc": [
        _fila(1, "こんにちは\nさん", "Hola\nseñor", estado="del parche"),
        _fila(2, "さようなら", "Chau", estado="revisar", nota="dudoso"),
        _fila(3, "ありがとう", "", estado="sin traducir"),
        _fila(4, "すみません", "Perdón", estado="traducido"),
        _fila(5, "おはよう", "Buen día", estado="del parche")]}})
    r = po.exportar(alm, str(tmp_path / "po"), "Prueba")
    assert r == {"archivos": 1, "entradas": 5, "omitidas": 0}
    pf = polib.pofile(str(tmp_path / "po" / "data01.po"))
    e = {x.msgctxt: x for x in pf}
    assert e["esc:00001"].msgid == "こんにちは\nさん" and e["esc:00001"].msgstr == "Hola\nseñor"
    assert "fuzzy" in e["esc:00002"].flags and e["esc:00002"].tcomment == "dudoso" and pf.metadata["Language"] == "es"
    # sin tocar nada: importar no cambia nada
    assert po.importar([str(tmp_path / "po")], alm)["actualizadas"] == 0
    # quien traduce: confirma la dudosa, traduce la vacía, corrige otra, cambia una nota y toca una entrada de otra versión
    e["esc:00002"].flags.remove("fuzzy")
    e["esc:00003"].msgstr = "Gracias"
    e["esc:00004"].msgstr = "Disculpe"; e["esc:00004"].flags.append("fuzzy")
    e["esc:00005"].tcomment = "ok"
    e["esc:00001"].msgid = "otro texto"; e["esc:00001"].msgstr = "Otra cosa"
    pf.append(polib.POEntry(msgctxt="no:00001", msgid="x", msgstr="y"))
    pf.save()
    # mientras tanto, en traduccion/ (por ejemplo, un git pull) alguien corrigió la 4: conflicto con el .po
    filas = alm.leer()["data01"]["esc"]
    filas[3]["traduccion"] = "Perdón, señor"
    alm.guardar("data01", "esc", filas)
    r = po.importar([str(tmp_path / "po")], alm)
    assert r["actualizadas"] == 3 and r["desconocidas"] == 1 and [k for k, _ in r["errores"]] == ["esc:00001"]
    assert [k for k, _ in r["conflictos"]] == ["esc:00004"] and r["grupos"] == {"data01"}
    f = {x["clave"]: x for x in alm.filas_por_escenario()["esc"]}
    assert (f["esc:00002"]["traduccion"], f["esc:00002"]["estado"]) == ("Chau", "traducido")
    assert (f["esc:00003"]["traduccion"], f["esc:00003"]["estado"]) == ("Gracias", "traducido")
    assert (f["esc:00004"]["traduccion"], f["esc:00004"]["estado"]) == ("Perdón, señor", "traducido")   # conflicto: no se pisa
    assert (f["esc:00005"]["nota"], f["esc:00005"]["estado"]) == ("ok", "del parche")                  # solo la nota
    assert (f["esc:00001"]["traduccion"], f["esc:00001"]["estado"]) == ("Hola\nseñor", "del parche")  # rechazada


def test_hojas_son_vistas_con_fusion_a_tres_bandas(tmp_path, monkeypatch):
    """Lo editado en una hoja vuelve a traduccion/; si la fila también cambió en traduccion/ (git pull), es un conflicto."""
    pytest.importorskip("openpyxl")
    from tl_organizer.nucleo import flujo, hojas, proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    proj.almacen.escribir({"data01": {"esc": [_fila(1, "一", "uno", "del parche"), _fila(2, "二", "dos", "del parche"),
                                              _fila(3, "三", "", "sin traducir")]}})
    log = []
    flujo.sincronizar(proj, log.append)                      # no había hojas: se generan
    hoja = g / project.WORK / "hojas" / "data01.xlsx"
    assert hojas.read_xlsx(str(hoja))["esc"][0]["base"]
    # en la hoja: se corrige la 1 y se traduce la 3; en traduccion/: alguien cambió la 1 y la 2
    sheets = hojas.read_xlsx(str(hoja))
    sheets["esc"][0].update(traduccion="UNO", estado="traducido")
    sheets["esc"][2].update(traduccion="tres", estado="traducido")
    hojas.write_xlsx(str(hoja), sheets, huella=lambda r: r["base"])
    filas = proj.almacen.leer()["data01"]["esc"]
    filas[0]["traduccion"], filas[1]["traduccion"] = "Uno.", "Dos."
    proj.almacen.guardar("data01", "esc", filas)
    rep = flujo.sincronizar(proj, log.append)
    assert rep["actualizadas"] == 1 and [k for k, _ in rep["conflictos"]] == ["esc:00001"]
    f = proj.almacen.filas_por_escenario()["esc"]
    assert [x["traduccion"] for x in f] == ["Uno.", "Dos.", "tres"]        # la 2 (solo cambió en traduccion/) no se revierte
    assert any("CONFLICTO" in l for l in log)
    assert hojas.read_xlsx(str(hoja))["esc"][0]["traduccion"] == "UNO"     # con conflicto, la hoja no se regenera
    # se resuelve en la hoja (se acepta lo de traduccion/) y queda todo al día
    sheets = hojas.read_xlsx(str(hoja))
    sheets["esc"][0].update(traduccion="Uno.", estado="del parche")
    hojas.write_xlsx(str(hoja), sheets, huella=lambda r: r["base"])
    rep = flujo.sincronizar(proj, log.append)
    assert not rep["conflictos"] and hojas.read_xlsx(str(hoja))["esc"][1]["traduccion"] == "Dos."
    # un cambio que llega solo a traduccion/ (git pull) regenera la hoja aunque nadie la haya tocado
    filas = proj.almacen.leer()["data01"]["esc"]
    filas[2]["traduccion"] = "Tres."
    proj.almacen.guardar("data01", "esc", filas)
    flujo.sincronizar(proj, log.append)
    assert hojas.read_xlsx(str(hoja))["esc"][2]["traduccion"] == "Tres."


# ---------------------------------------------------------------- fase 3: kit para escribir motores

def test_kit_codificaciones():
    from tl_organizer.motores.kit import codificaciones as k
    assert k.decodificar("¿Qué?".encode("utf-8")) == ("¿Qué?", "utf-8")
    assert k.decodificar("日本語".encode("cp932")) == ("日本語", "cp932")
    assert k.decodificar("﻿hola".encode("utf-8"))[1] == "utf-8-sig" and k.decodificar("hola".encode("utf-16"))[1] == "utf-16"
    with pytest.raises(k.CodificacionError):
        k.decodificar(b"\xff\xfe\x00"[1:] + b"\x81", ("utf-8",))
    with pytest.raises(k.CodificacionError, match="€"):
        k.codificar("5 €", "cp932")
    s = k.Sustitucion({"ñ": "ﾃ"}, "cp932")
    assert s.decodificar(s.codificar("año")) == "año" and s.no_codificables("año €") == ["€"]


def test_kit_contenedores(tmp_path):
    import zipfile
    from tl_organizer.motores.kit import Carpeta, Zip, escribir_suelto
    from tl_organizer.motores.kit.contenedores import Contenedor
    escribir_suelto(str(tmp_path / "j"), "scn/a.txt", b"A")
    escribir_suelto(str(tmp_path / "j"), "scn/sub/b.TXT", b"B")
    escribir_suelto(str(tmp_path / "j"), "otro.dat", b"C")
    c = Carpeta(str(tmp_path / "j"))
    assert c.nombres() == ["otro.dat", "scn/a.txt", "scn/sub/b.TXT"] and c.buscar("scn/*.txt") == ["scn/a.txt", "scn/sub/b.TXT"]
    assert c.leer("scn/sub/b.TXT") == b"B" and "otro.dat" in c
    with zipfile.ZipFile(tmp_path / "z.zip", "w") as z:
        z.writestr("d/x.txt", "x")
    assert Zip(str(tmp_path / "z.zip")).leer("d/x.txt") == b"x"
    assert issubclass(Arc, Contenedor)


def test_kit_tabla_de_cadenas():
    from tl_organizer.motores.kit import TablaDeCadenas, reapuntar, verificar_operandos
    from tl_organizer.motores.kit.cadenas import CadenasError
    t = TablaDeCadenas(b"uno\0dos\0", inicio=100)
    assert t.cadena_en(104) == b"dos" and t.agregar(b"tres") == 108 and t.agregar(b"tres") == 108 and t.agregar(b"x") == 113
    assert t.bytes() == b"uno\0dos\0tres\0x\0"
    with pytest.raises(CadenasError):
        t.agregar(b"a\0b")
    orig = struct.pack("<III", 1, 100, 7)
    nuevo = reapuntar(orig, {4: 108}) + b"tres\0"
    verificar_operandos(orig, nuevo, [4])
    with pytest.raises(CadenasError, match="0x8"):
        verificar_operandos(orig, reapuntar(orig, {8: 9}), [4])


def _arc(entradas):
    """Un BURIKO ARC20 con las entradas [(nombre, bytes)]."""
    tabla, datos = b"", b""
    for nombre, d in entradas:
        tabla += nombre.encode().ljust(0x60, b"\0") + struct.pack("<II", len(datos), len(d)) + b"\0" * 0x18
        datos += d
    return b"BURIKO ARC20" + struct.pack("<I", len(entradas)) + tabla + datos


@pytest.mark.parametrize("utf8", [True, False])
def test_contrato_motor_bgi(tmp_path, utf8):
    from tl_organizer.motores import contrato
    from tl_organizer.motores.bgi import MotorBGI
    from tl_organizer.nucleo import perfiles
    juego = tmp_path / "juego"
    juego.mkdir()
    (juego / "data01.arc").write_bytes(_arc([("esc1", _escenario_con_textos(["一つ目", "二つ目", "三つ目", "四つ目"])),
                                              ("esc2", _escenario_con_textos(["いち", "に", "さん"]))]))
    m = MotorBGI(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi"}))      # sin ejecutable: no se parchea exe
    assert contrato.verificar(m, str(juego), str(tmp_path / "t"), traduccion=lambda f: "¡Traducción!",
                              opciones={"utf8": utf8}) == []


def test_sueltos_en_la_raiz(tmp_path):
    """[bgi] sueltos = "raiz" (DESIRE remaster): los escenarios van a la carpeta del juego, no a Script/CVTD."""
    from tl_organizer.motores import contrato
    from tl_organizer.motores.base import MotorError
    from tl_organizer.motores.bgi import MotorBGI
    from tl_organizer.nucleo import perfiles
    juego = tmp_path / "juego"
    juego.mkdir()
    (juego / "data01.arc").write_bytes(_arc([("esc1", _escenario_con_textos(["一つ目", "二つ目"]))]))
    m = MotorBGI(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "bgi": {"sueltos": "raiz", "modo": "katakana"}}))
    assert m.sueltos == "raiz"
    assert contrato.verificar(m, str(juego), str(tmp_path / "t"), traduccion=lambda f: "¡Hola!") == []
    filas = {"esc1": [dict(f, traduccion="¡Hola!", estado="traducido") for f in next(m.textos(str(juego)))[2]]}
    m.construir(str(juego), str(tmp_path / "salida"), filas, log=lambda *a: None)
    assert (tmp_path / "salida" / "esc1").exists() and not (tmp_path / "salida" / "Script").exists()
    with pytest.raises(MotorError):
        MotorBGI(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "bgi": {"sueltos": "Script"}}))


class MotorJuguete(__import__("tl_organizer.motores.kit", fromlist=["MotorTextoPlano"]).MotorTextoPlano):
    """Un formato de texto inventado: 【nombre】「diálogo」, narración suelta, @opcion texto, ; comentario."""
    nombre = "juguete"
    archivos = ("scn/*.txt",)
    codificaciones = ("cp932",)
    patrones = {
        "nombre": r"^【(?P<texto>[^】]+)】",
        "mensaje": r"^(?:【[^】]+】)?「(?P<texto>[^」]*)」",
        "narracion": r"^(?P<texto>[^【「@;\s][^\n]*)$",
        "opcion": r"^@opcion (?P<texto>.+)$",
    }
    ignorar = r"^\s*;"
    salto_de_linea = "[r]"
    marcador = r"\[[a-z]+\]"


def _juego_juguete(tmp_path):
    from tl_organizer.motores.kit import escribir_suelto
    j = tmp_path / "juego"
    escribir_suelto(str(j), "scn/uno.txt", "; comentario 「no」\n【太郎】「こんにちは[r]元気？」\n空が青い。\n@opcion はい\n@opcion いいえ\n".encode("cp932"))
    escribir_suelto(str(j), "scn/dos.txt", "「さようなら」\n風が吹く。\n@opcion また\n".encode("cp932"))
    return j


def test_motor_texto_plano_extrae_y_cumple_el_contrato(tmp_path):
    from tl_organizer.motores import contrato
    from tl_organizer.nucleo import perfiles
    m = MotorJuguete(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "juguete"}))
    j = _juego_juguete(tmp_path)
    datos = {esc: filas for _g, esc, filas in m.textos(str(j))}
    assert [(f["tipo"], f["original"]) for f in datos["scn/uno"]] == [
        ("nombre", "太郎"), ("mensaje", "こんにちは\n元気？"), ("narracion", "空が青い。"), ("opcion", "はい"), ("opcion", "いいえ")]
    assert datos["scn/uno"][0]["clave"] == "scn/uno:00001"
    assert contrato.verificar(m, str(j), str(tmp_path / "t"), traduccion=lambda f: "Hola\nque tal") == []
    # un salto de línea se escribe como [r]; un carácter que cp932 no tiene es un error de esa fila
    filas = {esc: [dict(f) for f in fs] for esc, fs in datos.items()}
    filas["scn/uno"][1].update(traduccion="Hola\ntodo bien?", estado="traducido")
    filas["scn/uno"][2].update(traduccion="Precio: 5 €", estado="traducido")
    rep = m.construir(str(j), str(tmp_path / "s"), filas, log=lambda *a: None)["texto"]
    assert rep["cambiadas"] == 1 and [k for k, _ in rep["errores"]] == ["scn/uno:00003"]
    assert "【太郎】「Hola[r]todo bien?」" in (tmp_path / "s" / "scn" / "uno.txt").read_bytes().decode("cp932")
    assert m.caracteres_invalidos("a\nb") == [] and m.marcadores("a[r]b[p]") == ["[r]", "[p]"]


def test_motor_texto_plano_opciones_del_perfil(tmp_path):
    from tl_organizer.nucleo import perfiles
    m = MotorJuguete(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "juguete",
                                      "juguete": {"codificacion_salida": "utf-8", "carpeta_salida": "parche"}}))
    j = _juego_juguete(tmp_path)
    filas = {esc: fs for _g, esc, fs in m.textos(str(j))}
    filas["scn/dos"][0].update(traduccion="Adiós, señor", estado="traducido")
    m.construir(str(j), str(tmp_path / "s"), filas, log=lambda *a: None)
    assert (tmp_path / "s" / "parche" / "scn" / "dos.txt").read_text(encoding="utf-8").startswith("「Adiós, señor」")
    assert m.caracteres_invalidos("5 €") == [] and MotorJuguete(perfiles.Perfil(
        {"id": "x", "nombre": "x", "motor": "juguete", "juguete": {"codificacion_salida": "cp932"}})).caracteres_invalidos("5 €") == ["€"]


HERRAMIENTA = r'''
import json, os, sys
cmd = sys.argv[1]
if cmd == "extraer":
    juego, dest = sys.argv[2:4]
    for f in sorted(os.listdir(juego)):
        if f.endswith(".txt"):
            lineas = open(os.path.join(juego, f), encoding="utf-8").read().splitlines()
            json.dump([{"texto": l} for l in lineas], open(os.path.join(dest, f[:-4] + ".json"), "w", encoding="utf-8"))
elif cmd == "insertar":
    juego, src, salida = sys.argv[2:5]
    for f in sorted(os.listdir(src)):
        d = json.load(open(os.path.join(src, f), encoding="utf-8"))
        open(os.path.join(salida, f[:-5] + ".txt"), "w", encoding="utf-8").write("\n".join(x.get("traduccion") or x["texto"] for x in d) + "\n")
else:
    print("comando desconocido", file=sys.stderr); sys.exit(3)
'''


class MotorHerramienta(__import__("tl_organizer.motores.kit", fromlist=["MotorExterno"]).MotorExterno):
    """Envuelve una «herramienta externa» de prueba (un script de Python) que extrae a JSON e inserta desde JSON."""
    nombre = "herramienta"

    def comando_extraer(self, juego, carpeta):
        return ["extraer", juego, carpeta]

    def leer_extraido(self, carpeta):
        import json
        from tl_organizer.nucleo import hojas
        for f in sorted(os.listdir(carpeta)):
            esc = f[:-5]
            filas = [dict(clave=f"{esc}:{n:05d}", tipo="mensaje", original=x["texto"], traduccion="", estado="sin traducir",
                          nota="", pos=n, hash=hojas.jp_hash(x["texto"].encode()))
                     for n, x in enumerate(json.load(open(os.path.join(carpeta, f), encoding="utf-8")), 1)]
            yield "textos", esc, filas

    def escribir_para_insertar(self, carpeta, filas_del_juego, traducciones):
        import json
        for esc, fs in filas_del_juego.items():
            json.dump([{"texto": f["original"], "traduccion": traducciones.get(f["clave"])} for f in fs],
                      open(os.path.join(carpeta, esc + ".json"), "w", encoding="utf-8"))

    def comando_insertar(self, juego, carpeta, salida):
        return ["insertar", juego, carpeta, salida]

    def releer(self, juego, salida):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for f in os.listdir(juego):
                shutil.copy(os.path.join(salida, f) if os.path.exists(os.path.join(salida, f)) else os.path.join(juego, f), tmp)
            yield from self.textos(tmp)


def test_motor_externo_envuelve_una_herramienta(tmp_path):
    import sys as _sys
    from tl_organizer.motores import MotorError, contrato
    from tl_organizer.nucleo import perfiles
    script = tmp_path / "herramienta.py"
    script.write_text(HERRAMIENTA, encoding="utf-8")
    j = tmp_path / "juego"
    j.mkdir()
    (j / "a.txt").write_text("uno\ndos\ntres\n", encoding="utf-8")
    (j / "b.txt").write_text("cuatro\n", encoding="utf-8")
    perfil = perfiles.Perfil({"id": "x", "nombre": "x", "motor": "herramienta",
                              "herramienta": {"programa": [_sys.executable, str(script)], "lanzador": []}})
    m = MotorHerramienta(perfil)
    assert contrato.verificar(m, str(j), str(tmp_path / "t")) == []
    # sin programa, o con uno que falla: errores claros
    with pytest.raises(MotorError, match="no encuentro"):
        MotorHerramienta(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "herramienta",
                                          "herramienta": {"programa": "no-existe-este-programa"}})).ejecutable()
    with pytest.raises(MotorError, match="terminó con error 3"):
        m.ejecutar(["otra-cosa"])


# ---------------------------------------------------------------- fase 5: API local de la interfaz gráfica

def _api_cliente(srv):
    """Levanta la API en un hilo; devuelve (pedir(metodo, ruta, cuerpo=None, token=...), cerrar)."""
    import json as _json
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer
    from tl_organizer.nucleo import api
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), api.crear_manejador(srv))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/api/"

    def pedir(metodo, ruta, cuerpo=None, token=srv.token):
        datos = _json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(base + ruta, data=datos, method=metodo, headers={"X-TL-Token": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, _json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, _json.loads(e.read())
    return pedir, httpd.shutdown


def test_api_local(tmp_path, monkeypatch):
    import time as _time
    from tl_organizer.nucleo import api, proyecto as project
    monkeypatch.setattr(api, "_archivo_recientes", lambda: str(tmp_path / "recientes.json"))
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    proj.almacen.escribir({"data01": {"esc": [_fila(1, "一", "uno", "del parche"), _fila(2, "二", "", "sin traducir")]}})
    srv = api.Servidor("secreto")
    pedir, cerrar = _api_cliente(srv)
    try:
        assert pedir("GET", "info", token="otro")[0] == 403                              # sin el token no se entra
        st, info = pedir("GET", "info")
        assert st == 200 and info["proyecto"] is None and "bgi" in info["motores"]
        assert pedir("GET", "resumen")[0] == 409                                          # todavía no hay proyecto
        assert pedir("POST", "proyecto/abrir", {"carpeta": str(tmp_path / "nada")})[0] == 404
        st, p = pedir("POST", "proyecto/abrir", {"carpeta": str(g)})
        assert st == 200 and p["perfil"] == "falso" and p["exportado"] and pedir("GET", "info")[1]["recientes"] == [str(g)]
        st, r = pedir("GET", "resumen")
        assert r["estados"] == {"del parche": 1, "sin traducir": 1} and r["grupos"][0]["escenarios"][0]["escenario"] == "esc"
        st, f = pedir("GET", "filas?escenario=esc")
        assert f["total"] == 2 and f["filas"][1]["base"]
        assert pedir("GET", "filas?q=uno")[1]["total"] == 1 and pedir("GET", "filas?estado=sin%20traducir")[1]["total"] == 1
        # editar con la base: se aplica; repetir con la base vieja y otro texto: conflicto
        fila = f["filas"][1]
        cambio = {"clave": fila["clave"], "traduccion": "dos", "estado": "traducido", "nota": "", "base": fila["base"]}
        st, r = pedir("PUT", "filas", {"cambios": [cambio]})
        assert r["actualizadas"] == 1 and r["filas"][fila["clave"]]["traduccion"] == "dos"
        st, r = pedir("PUT", "filas", {"cambios": [dict(cambio, traduccion="DOS")]})
        assert r["actualizadas"] == 0 and r["conflictos"][0]["clave"] == fila["clave"]
        assert pedir("PUT", "filas", {"cambios": [{"clave": "x", "traduccion": "y"}]})[0] == 400        # faltan campos
        assert proj.almacen.filas_por_escenario()["esc"][1]["traduccion"] == "dos"
        # una tarea: corre en segundo plano y deja su registro
        st, t = pedir("POST", "tareas", {"tipo": "wrap", "opciones": {"max_caracteres": 20}})
        for _ in range(100):
            st, t = pedir("GET", f"tareas/{t['id']}")
            if t["estado"] != "corriendo":
                break
            _time.sleep(0.05)
        assert t["estado"] == "ok" and any("saltos de línea" in l for l in t["log"])
        assert pedir("POST", "tareas", {"tipo": "borrar-todo"})[0] == 400
        st, r = pedir("POST", "revisar", {})
        assert st == 200 and "total" in r
        assert pedir("PUT", "config", {"vista_previa": {"tamano": 30}})[1] == {"vista_previa": {"tamano": 30}}
        assert project.find(str(g)).cfg["gui"]["vista_previa"]["tamano"] == 30
        assert pedir("GET", "galeria")[1]["imagenes"] == []
        assert pedir("GET", "no/existe")[0] == 404
    finally:
        cerrar()


# ---------------------------------------------------------------- BGI viejo (DESIRE 1.642.1): proporcional y exe genérico

def _programa(codigo):
    """Un programa de sistema (._bp) sintético: cabecera de 16 bytes y el código."""
    return struct.pack("<II", 16, len(codigo)) + b"\0" * 8 + codigo


def test_proporcional_en_programas_de_sistema():
    from tl_organizer.motores.bgi import sysprg
    pref = bytes.fromhex("0210000000" "0006" "20")                 # dirección de la preferencia: 0x10 + 6
    dibujar = _programa(bytes.fromhex("0007" "0000" "0009" "9188")          # 91:88 con el 2.º argumento = push 0
                        + pref + b"\x08\x00" + bytes.fromhex("0000" "9188"))  # 91:88 que lee la preferencia
    formato = _programa(b"".join(bytes([0, v]) for v in [0, 5, 5, 5, 5, 5, 5, 5, 5]) + b"\x92\x9c"           # 9.º (el 1.º empujado) = push 0
                        + bytes.fromhex("0001" "0c") + bytes([0, 1]) * 8 + b"\x92\x9c")              # algo raro: no se toca
    datos = _programa(pref + bytes.fromhex("0000" "0900"))           # inicializa la preferencia con 0
    nuevos, rep = sysprg.parchear_proporcional({"a._bp": dibujar, "b._bp": formato, "userdata._bp": datos, "c._bp": _programa(b"\x00\x05")})
    assert sorted(nuevos) == ["a._bp", "b._bp", "userdata._bp"] and len(rep["cambios"]) == 4
    assert nuevos["a._bp"][16 + 3] == 1 and nuevos["a._bp"][16 + 5] == 9 and nuevos["userdata._bp"][16 + 9] == 1
    # la lectura de la preferencia (10 bytes) pasa a ser una constante 1 del mismo largo; lo que sigue no se mueve
    leer = nuevos["a._bp"][16 + 8:16 + 18]
    assert leer == sysprg.constante(10) and nuevos["a._bp"][16 + 18:] == bytes.fromhex("0000" "9188")
    ins = sysprg.instrucciones(nuevos["a._bp"])
    assert sysprg.argumentos(ins, len(ins) - 1, 2) is not None
    assert nuevos["b._bp"][16 + 1] == 1 and nuevos["b._bp"][16 + 3] == 5
    assert len(rep["omitidas"]) == 1 and rep["omitidas"][0][0] == "b._bp"
    assert sysprg.parchear_proporcional({**{"a._bp": dibujar, "b._bp": formato, "userdata._bp": datos}, **nuevos})[1]["cambios"] == []


def test_constante_de_largo_fijo():
    from tl_organizer.motores.bgi import sysprg
    assert sysprg.constante(4) is None and sysprg.constante(1) is None       # no hay forma con push8/16/32 y add
    for largo in [2, 3] + list(range(5, 40)):
        c = sysprg.constante(largo)
        assert c is not None and len(c) == largo, largo
        ins = sysprg.instrucciones(struct.pack("<II", 16, len(c)) + b"\0" * 8 + c)
        # efecto en la pila: +1 (un push más que adds) y el único push distinto de cero es el primero
        assert sum(1 if op in sysprg.EMPUJA else -1 for _p, op, _a in ins) == 1
        assert int.from_bytes(ins[0][2], "little") == 1 and all(not any(a) for _p, op, a in ins[1:] if op in sysprg.EMPUJA)


def test_exe_parches_genericos_y_capacidades():
    from tl_organizer.motores.bgi import exe_patch
    exe = bytearray(b"\xcc" * 64)
    exe[0:14] = "ＭＳ ゴシック".encode("cp932") + b"\0"
    exe[32:36] = bytes.fromhex("f0e24e00")
    b = exe_patch.desde_perfil({"sha256": exe_patch.sha256(bytes(exe)), "version": "prueba x86",
                                "font": [{"offset": 0, "original": exe[0:14].hex(), "tamano": 16}],
                                "parches": [{"offset": 32, "original": "f0e24e00", "nuevo": "e0e24e00"}]})
    builds = {b["sha256"]: b}
    assert not exe_patch.tiene_proporcional(b) and not exe_patch.tiene_utf8(b)
    nuevo = exe_patch.patch(bytes(exe), builds, proportional=False, font_name="SubaHibi07Inq")
    assert nuevo[0:16] == b"SubaHibi07Inq\0\0\0" and nuevo[32:36] == bytes.fromhex("e0e24e00") and nuevo[36:] == exe[36:]
    with pytest.raises(exe_patch.PatchError, match="no tiene modo UTF-8"):
        exe_patch.patch(bytes(exe), builds, proportional=False, utf8=True, font_name="X")
    with pytest.raises(exe_patch.PatchError, match="programas"):
        exe_patch.patch(bytes(exe), builds, proportional=True, font_name="X")
    with pytest.raises(exe_patch.PatchError, match="1 a 15"):
        exe_patch.patch(bytes(exe), builds, proportional=False, font_name="NombreMuyLargoDeFuente")


def test_perfil_desire():
    from tl_organizer import motores
    from tl_organizer.nucleo import perfiles
    m = motores.crear(perfiles.obtener("desire-remaster"))
    b = m.builds["3c9ef4e0296e019daad247ae9689eec53676626d74864fac56d2133ebc5d508f"]
    assert m.utf8 is False and m.opciones["proporcional"] == "programas" and m.data_arcs == ("data010*.arc",)
    assert not m.caracteres_invalidos("¡Ñandú!") and m.caracteres_invalidos("5 €") == ["€"]      # katakana: el € no entra
    assert m._utf8({"utf8": True}) is True and b["parches"][0][0] == 0x6eea5


def test_traza_wine_procmon_y_analisis(tmp_path):
    """tl-organizer traza: lectura de la traza de Wine y del CSV de Process Monitor, y el análisis de dónde busca sueltos."""
    import sys
    from tl_organizer.nucleo import traza
    juego = tmp_path / "juego"
    (juego / "UserData").mkdir(parents=True)
    (juego / "a01").write_bytes(b"x")
    if sys.platform != "win32":                                    # Wine: solo en Linux/macOS (z: -> / en dosdevices)
        pref = tmp_path / "pfx"
        (pref / "dosdevices").mkdir(parents=True)
        (pref / "dosdevices" / "z:").symlink_to("/")
        w = "Z:" + str(juego).replace("/", "\\\\")           # como lo escribe Wine en la traza: barras dobles
        lineas = [
            f'0024:trace:file:NtCreateFile handle=0x1 access=80100080 name=L"\\??\\{w}\\a01" objattr=40 root=(nil) sec=(nil) io=0x2 alloc_size=(nil) attr=00000020 sharing=00000001 disp=1 options=00000064 ea=(nil).0x0\n',
            f'0024:trace:file:NtCreateFile handle=0x1 access=80100080 name=L"\\??\\{w}\\a02" objattr=40 root=(nil) sec=(nil) io=0x2 alloc_size=(nil) attr=00000020 sharing=00000001 disp=1 options=00000064 ea=(nil).0x0\n',
            f'0024:warn:file:NtCreateFile L"\\??\\{w}\\a02" not found (c0000034)\n',
            f'0024:trace:file:NtCreateFile handle=0x1 access=c0100080 name=L"\\??\\{w}\\UserData\\s.sud" objattr=40 root=(nil) sec=(nil) io=0x2 alloc_size=(nil) attr=00000020 sharing=00000001 disp=5 options=00000064 ea=(nil).0x0\n',
        ]
        acc = traza.leer_traza_wine(lineas, traza.RutasWine(str(pref)))
        assert [(a.ruta.rsplit("/", 1)[1], a.encontrado, a.escritura) for a in acc] == \
            [("a01", True, False), ("a02", False, False), ("s.sud", True, True)]
    acc = [traza.Acceso(str(juego / "a01"), "abrir", True), traza.Acceso(str(juego / "a02"), "abrir", False),
           traza.Acceso(str(juego / "UserData" / "s.sud"), "abrir", True, True),
           traza.Acceso(str(juego / "hid.dll"), "abrir", False)]
    salida = tmp_path / "salida"
    (salida / "Script" / "CVTD").mkdir(parents=True)
    (salida / "Script" / "CVTD" / "a02").write_bytes(b"y")
    rep = traza.analizar(acc, str(juego), entradas={"a01", "a02"}, salida=str(salida))
    assert rep["carpetas_de_sueltos"] == {".": 2} and rep["escritos"] == {"UserData/s.sud": 1}
    assert rep["no_encontrados"] == {".": {"a02": 1}}                     # la DLL que busca Wine no cuenta
    assert rep["parche"]["Script/CVTD/a02"].startswith("lo buscó en otra carpeta: .")
    csv_ = tmp_path / "pm.csv"
    a01, a02, sud = juego / "a01", juego / "a02", juego / "UserData" / "s.sud"      # rutas nativas, como las de Procmon
    csv_.write_text('"Time of Day","Process Name","PID","Operation","Path","Result","Detail"\n'
                    f'"1","JUEGO.exe","1","CreateFile","{a01}","SUCCESS","Desired Access: Generic Read, Disposition: Open"\n'
                    f'"1","JUEGO.exe","1","CreateFile","{a02}","NAME NOT FOUND","Desired Access: Generic Read"\n'
                    f'"1","otro.exe","2","CreateFile","{a01}","SUCCESS","Desired Access: Generic Read"\n'
                    f'"1","JUEGO.exe","1","WriteFile","{sud}","SUCCESS","Offset: 0"\n', encoding="utf-8")
    acc = traza.leer_csv_procmon(str(csv_), "juego.exe")
    assert [(os.path.basename(a.ruta), a.encontrado, a.escritura) for a in acc] == \
        [("a01", True, False), ("a02", False, False), ("s.sud", True, True)]

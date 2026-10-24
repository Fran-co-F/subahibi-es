# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas sin archivos del juego. Las que usan el juego real se saltan si no existe GAME_DIR."""
import os
import struct

import pytest
from PIL import Image

from subahibi_es.motores.bgi import exe_patch
from subahibi_es.motores.bgi import image
from subahibi_es.motores.bgi.arc import Arc
from subahibi_es.nucleo.galeria import index


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    """Ni los perfiles del usuario ni un proyecto forzado por variable de entorno afectan a las pruebas."""
    monkeypatch.delenv("SUBAHIBI_ES_PERFILES", raising=False)
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
    from subahibi_es.motores.bgi.images import export
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "subahibi_es_test")
    n, skipped = export.export_arc(os.path.join(os.environ["GAME_DIR"], "sysgrp.arc"), out)
    assert n == 338 and not skipped


def _escenario_sintetico(textos):
    """Escenario mínimo: cabecera, un push, un 'str' por texto y la tabla de cadenas."""
    import struct
    from subahibi_es.motores.bgi import scn
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
    from subahibi_es.motores.bgi import scn
    data = _escenario_sintetico(["hola", "mundo"])
    sc = scn.parse(data)
    assert scn.serialize(sc) == data
    assert [sc.string_at(t.args[0]) for t in sc.tokens if t.op == 3] == [b"hola", b"mundo"]


def test_pagina_funciones_puras(tmp_path):
    """Las funciones de index.html (glob, TSV, zip, BMP de 32 bits) se prueban con Node si está instalado."""
    import json
    import shutil
    import subprocess
    import zipfile
    node = shutil.which("node")
    if not node:
        pytest.skip("node no instalado")
    from subahibi_es.nucleo.galeria import _page
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
    from subahibi_es.motores.bgi.text import accents
    s = "¿Qué está pasando, señor Núñez? ¡Ándale! Pingüino, ÉL, ÍNDICE, ÓPERA, ÚLTIMO, ÜBER, Ñandú"
    raw = accents.encode(s)
    assert accents.decode(raw) == s
    assert all(b < 0x80 or 0xA1 <= b <= 0xDF for b in raw)         # solo ASCII o katakana de ancho medio
    assert accents.unencodable("hola €") == ["€"]
    assert accents.decode("日本語".encode("cp932")) == "日本語"


def _escenario_con_textos(textos, cmd=0x140):
    """Escenario sintético: por cada texto, 'str' + un comando (por defecto 0x140 = mensaje)."""
    import struct
    from subahibi_es.motores.bgi import scn
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
    from subahibi_es.motores.bgi import scn
    from subahibi_es.motores.bgi.text import accents, export, extract, import_
    from subahibi_es.nucleo import hojas
    jp = _escenario_con_textos(["こんにちは", "さようなら"])
    rows = export.script_rows("prueba", jp)
    assert [r["tipo"] for r in rows] == ["mensaje", "mensaje"] and rows[0]["japones"] == "こんにちは"
    rows[0]["espanol"], rows[0]["estado"] = "¡Hola, señor!", "traducido"
    rows[1]["espanol"], rows[1]["estado"] = "Adiós", "sin traducir"       # no se aplica
    out, rep = import_.build_script("prueba", jp, rows)
    assert rep["cambiadas"] == 1 and rep["omitidas"] == 1 and not rep["errores"]
    sj = scn.parse(jp)
    nuevo = extract.rows(scn.parse(out, strings_start=sj.strings_start))
    assert accents.decode(nuevo[0].raw) == "¡Hola, señor!" and nuevo[1].raw == "さようなら".encode("cp932")
    # un hash distinto (juego de otra versión) y un carácter imposible se rechazan
    rows[0]["hash"] = "00000000"
    assert import_.build_script("prueba", jp, rows)[1]["errores"]
    rows[0]["hash"] = hojas.jp_hash("こんにちは".encode("cp932")); rows[0]["espanol"] = "precio 5 €"
    assert "€" in import_.build_script("prueba", jp, rows)[1]["errores"][0][1]


def test_tsv_escapes(tmp_path):
    from subahibi_es.nucleo import hojas as sheet
    fila = dict(clave="a:00001", tipo="mensaje", japones="x\ty\nz\\", espanol="línea1\nlínea2", estado="traducido",
                nota="", pos=12, hash="abcd1234")
    p = tmp_path / "a.tsv"
    sheet.write_tsv(str(p), [fila])
    leida = sheet.read_tsv(str(p))[0]
    assert leida["japones"] == "x\ty\nz\\" and leida["espanol"] == "línea1\nlínea2" and leida["pos"] == "12"


def test_parche_viejo_zip_y_config(tmp_path, monkeypatch):
    import zipfile
    from subahibi_es.motores.bgi import oldpatch
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
    from subahibi_es.motores.bgi import scn
    from subahibi_es.motores.bgi.text import export, extract, import_
    jp = _escenario_con_textos(["こんにちは", "さようなら"])
    rows = export.script_rows("prueba", jp)
    rows[0]["espanol"], rows[0]["estado"] = "¡Hola, señor! ñé", "traducido"
    out, rep = import_.build_script("prueba", jp, rows, utf8=True)
    nuevo = extract.rows(scn.parse(out, strings_start=scn.parse(jp).strings_start))
    assert nuevo[0].raw.decode("utf-8") == "¡Hola, señor! ñé"            # español tal cual
    assert nuevo[1].raw.decode("utf-8") == "さようなら"                      # japonés convertido a UTF-8
    assert rep["cambiadas"] == 1 and not rep["errores"]
    # sin traducciones, el modo UTF-8 igual produce el escenario convertido
    out2, rep2 = import_.build_script("prueba", jp, export.script_rows("prueba", jp), utf8=True)
    assert out2 is not None and extract.rows(scn.parse(out2, strings_start=scn.parse(jp).strings_start))[0].raw.decode("utf-8") == "こんにちは"


def test_exe_utf8_desvia_la_entrada():
    from subahibi_es.motores.bgi import exe_patch
    assert "utf8" in exe_patch.patch.__code__.co_varnames


def test_wrap_corta_en_palabras():
    from subahibi_es.nucleo import wrap
    fits = wrap.make_fits(max_chars=20)
    t = "El veloz murciélago hindú comía feliz cardillo"
    r = wrap.wrap_text(t, fits)
    assert all(len(l) <= 20 for l in r.split("\n")) and r.replace("\n", " ") == t
    assert wrap.wrap_text("corto", fits) == "corto"
    assert wrap.wrap_text("supercalifragilisticoespialidoso corto", fits) == "supercalifragilisticoespialidoso\ncorto"   # palabra larga: no se parte
    # los saltos que ya hay se respetan; con reflow se rehacen
    assert wrap.wrap_text("uno dos\ntres cuatro cinco seis siete", fits) == "uno dos\ntres cuatro cinco\nseis siete"
    assert wrap.wrap_text("uno dos\ntres", fits, reflow=True) == "uno dos tres"
    rows = [dict(tipo="mensaje", espanol=t, estado="del parche", nota=""), dict(tipo="mensaje", espanol=t, estado="sin traducir", nota="")]
    assert wrap.wrap_rows(rows, fits, max_lines=2) == (1, 1) and "más de 2 líneas" in rows[0]["nota"] and "\n" not in rows[1]["espanol"]


def test_nombre_de_fuente_configurable():
    import pytest
    from subahibi_es.motores.bgi import exe_patch
    assert exe_patch.font_slot("Lune") == b"Lune" + b"\0" * 12
    for malo in ("", "NombreDeFuenteDemasiadoLargo", "Fuente ñ"):
        with pytest.raises(exe_patch.PatchError):
            exe_patch.font_slot(malo)


def test_enlaces_con_respaldo(tmp_path, monkeypatch):
    """Sin permiso para enlaces simbólicos (Windows normal) se usa enlace duro y, si tampoco, copia."""
    import os as _os
    import shutil
    from subahibi_es.nucleo import enlaces as build
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
    """Escribe un perfil de juego en una carpeta de $SUBAHIBI_ES_PERFILES."""
    d = tmp_path / "perfiles"
    d.mkdir(exist_ok=True)
    (d / nombre).write_text(texto, encoding="utf-8")
    monkeypatch.setenv("SUBAHIBI_ES_PERFILES", str(d))
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
    from subahibi_es.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, creado = project.init(str(g))
    assert creado and proj.cfg["perfil"] == "falso" and proj.cfg["motor"] == "bgi" and proj.version == "falso 1.0"
    for name in ("originales", "texto", "traducidas", "indice", "backup", "salida"):
        assert (g / project.WORK / project.SUBDIRS[name]).is_dir()
    assert (g / project.WORK / "backup" / "BGI.exe").read_bytes() == b"MZ-falso"      # respaldo del exe original
    assert (g / "subahibi-es.json").exists() and (g / project.WORK / "imagenes" / "estado.tsv").exists()
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
    from subahibi_es.nucleo import proyecto as project
    vacia = tmp_path / "otra"
    vacia.mkdir()
    with pytest.raises(project.ProjectError) as e:
        project.init(str(vacia))
    assert "falta BGI.exe" in str(e.value)
    (vacia / "BGI.exe").write_bytes(b"cualquier cosa")
    with pytest.raises(project.ProjectError) as e:
        project.init(str(vacia))
    assert "no es una versión conocida" in str(e.value)


def test_reset_no_toca_el_juego(tmp_path, monkeypatch):
    from subahibi_es.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    project.reset(proj)                                           # solo el JSON
    assert not (g / "subahibi-es.json").exists() and (g / project.WORK).is_dir() and (g / "BGI.exe").exists()
    proj, _ = project.init(str(g))
    project.reset(proj, todo=True)                                # JSON y carpeta de trabajo; el juego queda
    assert not (g / project.WORK).exists() and (g / "BGI.exe").exists() and (g / "sysgrp.arc").exists()


def test_instalar_y_desinstalar(tmp_path, monkeypatch):
    from subahibi_es.nucleo import flujo as workflow, proyecto as project
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
    from subahibi_es import cli
    from subahibi_es.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    monkeypatch.chdir(g)
    assert cli.main(["init"]) == 0 and (g / "subahibi-es.json").exists()
    assert "juego detectado" in capsys.readouterr().out
    monkeypatch.chdir(g / "subahibi-es-trabajo")                       # los comandos funcionan desde una subcarpeta
    assert project.find().root == str(g)
    with pytest.raises(SystemExit):
        cli.main(["init"])                                             # ya hay un proyecto
    assert cli.main(["reset", "--todo", "--si"]) == 0
    assert not (g / "subahibi-es.json").exists() and not (g / "subahibi-es-trabajo").exists() and (g / "BGI.exe").exists()
    monkeypatch.chdir(g)
    with pytest.raises(SystemExit) as e:
        cli.main(["build"])                                            # sin proyecto, mensaje claro
    assert "init" in str(e.value)


def test_parche_viejo_se_guarda_relativo(tmp_path, monkeypatch):
    """Si el parche viejo está dentro del proyecto, la ruta se guarda relativa y sobrevive a mover la carpeta."""
    import json
    import shutil
    from subahibi_es.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    (g / "parche.zip").write_bytes(b"x")
    proj, _ = project.init(str(g), str(g / "parche.zip"))
    assert json.load(open(g / "subahibi-es.json", encoding="utf-8"))["parche_viejo"] == "parche.zip"
    assert proj.parche_viejo == str(g / "parche.zip")
    nuevo = tmp_path / "movido"
    shutil.move(str(g), str(nuevo))
    assert project.find(str(nuevo)).parche_viejo == str(nuevo / "parche.zip")
    fuera = tmp_path / "fuera.zip"
    fuera.write_bytes(b"x")
    proj2, _ = project.init(str(nuevo), str(fuera))                          # ya existe: actualiza; fuera del proyecto queda absoluta
    assert project.find(str(nuevo)).parche_viejo == str(fuera)


def test_estado_tsv_arranca_vacio(tmp_path, monkeypatch):
    from subahibi_es.nucleo import proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    assert index.read_status(proj.estado_tsv) == []                          # solo comentarios: ninguna regla propia
    assert "patrón<TAB>estado<TAB>nota" in open(proj.estado_tsv, encoding="utf-8").read()


def test_export_no_crea_hojas_vacias(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from subahibi_es.motores.bgi.text import export
    from subahibi_es.nucleo import texto
    con = _escenario_con_textos(["hola", "mundo"])
    sin = _escenario_con_textos(["cualquier_nombre"], cmd=0x1a1)     # una cadena que no es texto (nombre de archivo, etc.)
    fuente = [(g, n, export.script_rows(n, d)) for g, n, d in [("a", "con_texto", con), ("a", "sin_texto", sin), ("b", "solo_vacio", sin)]]
    r = texto.exportar(fuente, str(tmp_path / "out"))
    assert r["scripts"] == 1 and sorted(r["sin_texto"]) == ["sin_texto", "solo_vacio"]
    assert sorted(f.name for f in (tmp_path / "out").iterdir()) == ["a.xlsx"]     # b.xlsx no existe: no tenía ninguna hoja con filas
    from subahibi_es.nucleo import hojas as sheet
    assert list(sheet.read_xlsx(str(tmp_path / "out" / "a.xlsx"))) == ["con_texto"]


def test_alineacion_dudosa_por_correlacion_de_largos():
    import random
    from subahibi_es.nucleo import alineacion as align
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
    from subahibi_es.motores.bgi.text import export
    jp = _escenario_con_textos(["こんにちは"])
    old = _escenario_con_textos(["Hola\t"])                               # el parche viejo agrega un TAB final
    rows = export.script_rows("p", jp, old)
    assert rows[0]["espanol"] == "Hola" and rows[0]["estado"] == "del parche"


def test_estado_por_archivo_y_por_escenario(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from subahibi_es.nucleo import flujo as workflow, hojas as sheet, proyecto as project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    fila = lambda i, st: dict(clave=f"x:{i:05d}", tipo="mensaje", japones="j", espanol="e" if st != "sin traducir" else "",
                              estado=st, nota="", pos=i, hash="h")
    sheet.write_xlsx(str(g / project.WORK / "texto" / "data01.xlsx"),
                     {"esc_a": [fila(1, "del parche"), fila(2, "del parche"), fila(3, "sin traducir"), fila(4, "revisar")],
                      "esc_b": [fila(1, "traducido")]})
    sheet.write_xlsx(str(g / project.WORK / "texto" / "data02.xlsx"), {"esc_c": [fila(1, "sin traducir")] * 4})
    def salida(nivel):
        out = []
        workflow.estado(proj, log=out.append, nivel=nivel)
        return "\n".join(out)
    v0, v1, v2 = salida(0), salida(1), salida(2)
    assert "9 filas en 2 hojas" in v0 and "listo 33.3%" in v0                                 # 3 de 9 listas (2 del parche + 1 traducido)
    assert "data01" not in v0 and "archivo" in v1 and "data01" in v1 and "esc_a" not in v1
    linea = [l for l in v1.splitlines() if l.startswith("data01")][0]
    assert linea.split()[:3] == ["data01", "5", "60.0%"]                                       # 3 de 5 listas
    assert [l for l in v1.splitlines() if l.startswith("data02")][0].split()[:3] == ["data02", "4", "0.0%"]
    assert "== data01 ==" in v2 and "esc_a" in v2 and "esc_c" in v2
    assert [l for l in v2.splitlines() if l.startswith("esc_a")][0].split()[:3] == ["esc_a", "4", "50.0%"]


# ---------------------------------------------------------------- perfiles y motores

def test_perfil_incluido_conserva_los_datos_del_exe():
    """El perfil TOML de la 15th reproduce exactamente las direcciones que antes estaban fijas en exe_patch.py."""
    from subahibi_es import motores
    from subahibi_es.nucleo import perfiles
    perfil = perfiles.obtener("subahibi-15th")
    m = motores.crear(perfil)
    b = m.builds["993e9803a4335ff752dd7b4fd7b5036c3200c88c74fbde05d29b5123be5bd29c"]
    assert b["font"] == [(0x17C740, b"MS Gothic\x00"), (0x17C750, b"\x82l\x82r \x83S\x83V\x83b\x83N\x00")]
    assert (b["hook"], b["hook_bytes"], b["cave"], b["back"]) == (0x1400DF7FA, "89742428458bc4", 0x1400DF76C, 0x1400DF801)
    assert (b["entry_field"], b["entry_rva"], b["image_base"], b["utf8_cave"], b["set_encoding"]) == \
        (0x150, 0x11D74, 0x140000000, 0x140001DF0, 0x1400F74C0)
    assert m.fuente == "SubaHibi07Inq" and m.data_arcs == ("data0*.arc",) and m.ui_arcs == ("sysgrp.arc",)
    assert perfil.requeridos == list(REQUERIDOS) and perfil.ejecutable == "BGI.exe"


def test_perfil_del_usuario_gana_y_errores_claros(tmp_path, monkeypatch):
    from subahibi_es.nucleo import perfiles
    # un perfil del usuario con el mismo id reemplaza al incluido
    d = tmp_path / "config-usuario" / "subahibi-es" / "juegos"
    d.mkdir(parents=True)
    (d / "mio.toml").write_text('id = "subahibi-15th"\nnombre = "Mi versión"\nmotor = "bgi"\n', encoding="utf-8")
    assert perfiles.obtener("subahibi-15th").nombre == "Mi versión"
    # $SUBAHIBI_ES_PERFILES tiene más prioridad que la carpeta del usuario
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
    from subahibi_es import motores
    from subahibi_es.nucleo import perfiles
    with pytest.raises(motores.MotorError, match="motor desconocido «nada»"):
        motores.crear(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "nada"}))
    with pytest.raises(motores.MotorError, match="falta «version»"):
        motores.crear(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "bgi": {"ejecutables": [{"sha256": "ab"}]}}))
    with pytest.raises(motores.MotorError, match="fuente"):
        motores.crear(perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "bgi": {"fuente": "Fuente ñ"}}))


def test_init_con_varios_perfiles_muestra_el_mas_parecido(tmp_path, monkeypatch):
    from subahibi_es.nucleo import proyecto as project
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
    from subahibi_es.nucleo import proyecto as project
    (tmp_path / project.NAME).write_text(json.dumps({"version_del_proyecto": 1, "motor": "1.685.3 (15th Anniversary, x86_64)",
                                                     "parche_viejo": None}), encoding="utf-8")
    proj = project.find(str(tmp_path))
    assert proj.perfil.id == "subahibi-15th" and proj.motor.nombre == "bgi" and proj.version.startswith("1.685.3")


def test_jugable_nunca_enlaza_el_ejecutable(tmp_path):
    """Si el perfil pidiera enlazar los .exe, el del juego se omite: el exe parcheado se escribiría a través del enlace."""
    from subahibi_es.nucleo import enlaces, perfiles
    g, out = tmp_path / "g", tmp_path / "out"
    g.mkdir(); out.mkdir()
    for f in ("BGI.exe", "BHVC.exe", "a.arc", "nota.txt"):
        (g / f).write_bytes(b"x")
    perfil = perfiles.Perfil({"id": "x", "nombre": "x", "motor": "bgi", "deteccion": {"ejecutable": "BGI.exe"},
                              "jugable": {"enlazar_extensiones": [".exe", ".arc"]}})
    n, _m = enlaces.link_game(str(g), str(out), perfil)
    assert n == 2 and sorted(os.listdir(out)) == ["BHVC.exe", "a.arc"]


# Un motor mínimo de prueba, cargado como plugin (entry point): solo sabe texto.
from subahibi_es.motores.base import Motor, TEXTO  # noqa: E402


class MotorDePrueba(Motor):
    nombre = "prueba"
    capacidades = frozenset({TEXTO})
    carpetas_sueltas = ("textos",)

    def textos(self, juego, parche_viejo=None, archivos=None):
        with open(os.path.join(juego, "juego.dat"), encoding="utf-8") as f:
            lineas = f.read().splitlines()
        filas = [dict(clave=f"esc1:{i:05d}", tipo="mensaje", japones=t, espanol="", estado="sin traducir", nota="", pos=i, hash="h")
                 for i, t in enumerate(lineas, 1)]
        yield "juego", "esc1", filas

    def construir(self, juego, salida, filas=None, imagenes=None, estados=(), opciones=None, parche_viejo=None,
                  ejecutable=None, log=print):
        os.makedirs(os.path.join(salida, "textos"), exist_ok=True)
        with open(os.path.join(salida, "textos", "esc1.txt"), "w", encoding="utf-8") as f:
            for r in (filas or {}).get("esc1", []):
                f.write((r["espanol"] if r["estado"] in estados and r["espanol"] else r["japones"]) + "\n")
        return {"opciones": opciones}


def test_plugin_de_motor_con_su_perfil_hace_todo_el_flujo(tmp_path, monkeypatch):
    """Un motor nuevo = una clase + un entry point + un perfil TOML; el núcleo hace el resto (init, exportar, build, estado)."""
    pytest.importorskip("openpyxl")
    from importlib.metadata import EntryPoint
    from subahibi_es import motores
    from subahibi_es.nucleo import flujo, hojas, proyecto as project
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
    hoja = g / project.WORK / "texto" / "juego.xlsx"
    sheets = hojas.read_xlsx(str(hoja))
    sheets["esc1"][0].update(espanol="Hola", estado="traducido")
    hojas.write_xlsx(str(hoja), sheets)
    r = flujo.build(proj, proj.dir("salida"), opciones={"x": 1}, log=lambda *a: None)
    assert r["opciones"] == {"x": 1}
    assert (g / project.WORK / "salida" / "textos" / "esc1.txt").read_text(encoding="utf-8") == "Hola\nさようなら\n"
    out = []
    flujo.estado(proj, log=out.append)
    assert any("Juego de prueba" in l for l in out) and any("listo 50.0%" in l for l in out)

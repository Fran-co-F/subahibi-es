# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas sin archivos del juego. Las que usan el juego real se saltan si no existe GAME_DIR."""
import os
import struct

import pytest
from PIL import Image

from subahibi_es import exe_patch
from subahibi_es.bgi import image
from subahibi_es.bgi.arc import Arc
from subahibi_es.images import import_, index


def test_imagen_cruda_ida_y_vuelta():
    im = Image.new("RGBA", (5, 3), (10, 20, 30, 40))
    im.putpixel((1, 1), (200, 100, 50, 255))
    raw = image.from_pil(im)
    assert image.is_raw_image(raw)
    assert image.to_pil(raw).tobytes() == im.tobytes()


def test_exe_desconocido_se_rechaza():
    with pytest.raises(exe_patch.PatchError):
        exe_patch.patch(b"MZ" + b"\0" * 100)


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
    from subahibi_es.images import export
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "subahibi_es_test")
    n, skipped = export.export_arc(os.path.join(os.environ["GAME_DIR"], "sysgrp.arc"), out)
    assert n == 338 and not skipped


def _escenario_sintetico(textos):
    """Escenario mínimo: cabecera, un push, un 'str' por texto y la tabla de cadenas."""
    import struct
    from subahibi_es.bgi import scn
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
    from subahibi_es.bgi import scn
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
    from subahibi_es.images import _page
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
    from subahibi_es.text import accents
    s = "¿Qué está pasando, señor Núñez? ¡Ándale! Pingüino, ÉL, ÍNDICE, ÓPERA, ÚLTIMO, ÜBER, Ñandú"
    raw = accents.encode(s)
    assert accents.decode(raw) == s
    assert all(b < 0x80 or 0xA1 <= b <= 0xDF for b in raw)         # solo ASCII o katakana de ancho medio
    assert accents.unencodable("hola €") == ["€"]
    assert accents.decode("日本語".encode("cp932")) == "日本語"


def _escenario_con_textos(textos, cmd=0x140):
    """Escenario sintético: por cada texto, 'str' + un comando (por defecto 0x140 = mensaje)."""
    import struct
    from subahibi_es.bgi import scn
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
    from subahibi_es.bgi import scn
    from subahibi_es.text import accents, export, extract, import_
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
    rows[0]["hash"] = export.sheet.jp_hash("こんにちは".encode("cp932")); rows[0]["espanol"] = "precio 5 €"
    assert "€" in import_.build_script("prueba", jp, rows)[1]["errores"][0][1]


def test_tsv_escapes(tmp_path):
    from subahibi_es.text import sheet
    fila = dict(clave="a:00001", tipo="mensaje", japones="x\ty\nz\\", espanol="línea1\nlínea2", estado="traducido",
                nota="", pos=12, hash="abcd1234")
    p = tmp_path / "a.tsv"
    sheet.write_tsv(str(p), [fila])
    leida = sheet.read_tsv(str(p))[0]
    assert leida["japones"] == "x\ty\nz\\" and leida["espanol"] == "línea1\nlínea2" and leida["pos"] == "12"


def test_parche_viejo_zip_y_config(tmp_path, monkeypatch):
    import zipfile
    from subahibi_es import config, oldpatch
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
    from subahibi_es.bgi import scn
    from subahibi_es.text import export, extract, import_
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
    from subahibi_es import exe_patch
    assert "utf8" in exe_patch.patch.__code__.co_varnames


def test_wrap_corta_en_palabras():
    from subahibi_es.text import wrap
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
    from subahibi_es import exe_patch
    assert exe_patch.font_slot("Lune") == b"Lune" + b"\0" * 12
    for malo in ("", "NombreDeFuenteDemasiadoLargo", "Fuente ñ"):
        with pytest.raises(exe_patch.PatchError):
            exe_patch.font_slot(malo)


def test_enlaces_con_respaldo(tmp_path, monkeypatch):
    """Sin permiso para enlaces simbólicos (Windows normal) se usa enlace duro y, si tampoco, copia."""
    import os as _os
    import shutil
    from subahibi_es import build
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


def _juego_falso(tmp_path, monkeypatch):
    """Una 'instalación' mínima: el BGI.exe falso se registra como versión conocida."""
    from subahibi_es import exe_patch, project
    g = tmp_path / "juego"
    g.mkdir()
    (g / "BGI.exe").write_bytes(b"MZ-falso")
    for f in project.REQUIRED[1:]:
        (g / f).write_bytes(b"x")
    monkeypatch.setitem(exe_patch.KNOWN_BUILDS, exe_patch.sha256(b"MZ-falso"), {"version": "falso 1.0"})
    return g


def test_init_valida_y_crea_el_proyecto(tmp_path, monkeypatch):
    from subahibi_es import project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, creado = project.init(str(g))
    assert creado and proj.cfg["motor"] == "falso 1.0"
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
    from subahibi_es import project
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
    from subahibi_es import project
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    project.reset(proj)                                           # solo el JSON
    assert not (g / "subahibi-es.json").exists() and (g / project.WORK).is_dir() and (g / "BGI.exe").exists()
    proj, _ = project.init(str(g))
    project.reset(proj, todo=True)                                # JSON y carpeta de trabajo; el juego queda
    assert not (g / project.WORK).exists() and (g / "BGI.exe").exists() and (g / "sysgrp.arc").exists()


def test_instalar_y_desinstalar(tmp_path, monkeypatch):
    from subahibi_es import project, workflow
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
    from subahibi_es import cli, project
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
    from subahibi_es import project
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
    from subahibi_es import project
    from subahibi_es.images import index
    g = _juego_falso(tmp_path, monkeypatch)
    proj, _ = project.init(str(g))
    assert index.read_status(proj.estado_tsv) == []                          # solo comentarios: ninguna regla propia
    assert "patrón<TAB>estado<TAB>nota" in open(proj.estado_tsv, encoding="utf-8").read()


def test_export_no_crea_hojas_vacias(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from subahibi_es.text import export
    con = _escenario_con_textos(["hola", "mundo"])
    sin = _escenario_con_textos(["cualquier_nombre"], cmd=0x1a1)     # una cadena que no es texto (nombre de archivo, etc.)
    monkeypatch.setattr(export, "scenarios", lambda game, arcs=None: iter([("a", "con_texto", con), ("a", "sin_texto", sin), ("b", "solo_vacio", sin)]))
    r = export.export_text(str(tmp_path), str(tmp_path / "out"), None, None)
    assert r["scripts"] == 1 and sorted(r["sin_texto"]) == ["sin_texto", "solo_vacio"]
    assert sorted(f.name for f in (tmp_path / "out").iterdir()) == ["a.xlsx"]     # b.xlsx no existe: no tenía ninguna hoja con filas
    from subahibi_es.text import sheet
    assert list(sheet.read_xlsx(str(tmp_path / "out" / "a.xlsx"))) == ["con_texto"]

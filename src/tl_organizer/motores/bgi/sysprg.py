# SPDX-License-Identifier: GPL-3.0-or-later
"""Programas de sistema de BGI (._bp, en sysprg.arc): texto proporcional sin tocar el exe.

En los motores sin un desvío de exe para el modo proporcional (las versiones viejas, de 32 bits), el modo se elige con un
argumento de dos llamadas de los programas de sistema (método descrito por ArcusMaximus y Operation Bellflower, y el que usa
el parche de Sakura no Uta de Taikutsu Translation):

    graphcall 91:88  (dibujar texto)       el 2.º argumento contando desde abajo
    graphcall 92:9C  (formato de texto)    el 9.º argumento contando desde abajo (el 12.º es el tamaño de letra)

Cuando el argumento es `push 0` se cambia por `push 1`.  Cuando se lee de memoria (base + desplazamiento: la preferencia
de modo proporcional, que en DESIRE usa la ventana de mensajes), la lectura se reemplaza por una expresión que vale 1 y
ocupa los mismos bytes (así no se mueve ningún salto): la preferencia viene de los datos guardados, y si el jugador ya tenía
el juego configurado conservaría el 0.  Además se cambia a 1 el valor inicial (dónde se guarda un `push 0` en esa misma
dirección).  Los programas modificados van sin comprimir a Script/CVTD (el motor los prefiere a los de sysprg.arc).

Formato (observado): cabecera de 16 bytes (u32 tamaño de la cabecera, u32 tamaño del código) y el código: un byte de opcode
y sus operandos.  Para separar argumentos solo hace falta el efecto en la pila de unas pocas instrucciones; si en los
argumentos de una llamada aparece otra cosa, esa llamada no se toca (y se informa).
"""
import collections

# bytes de operando de cada opcode (los usados al armar argumentos y los que hacen falta para recorrer el código)
OPERANDOS = {0x00: 1, 0x01: 2, 0x02: 4, 0x04: 2, 0x05: 2, 0x06: 2, 0x08: 1, 0x09: 1, 0x0A: 1}
OPERANDOS.update({op: 1 for op in range(0x80, 0xA0)})      # llamadas al sistema: un byte de función
EMPUJA = {0x00, 0x01, 0x02, 0x04, 0x05, 0x06}              # ponen un valor en la pila
BINARIAS = set(range(0x20, 0x30))                          # sacan dos y ponen uno (add, sub…)
LOAD, MOVE = 0x08, 0x09

# (opcode, función) -> (posición del argumento «proporcional» contando desde abajo, cantidad de argumentos a separar)
LLAMADAS = {(0x91, 0x88): (2, 2), (0x92, 0x9C): (9, 9)}


def instrucciones(datos):
    """[(posición, opcode, operandos)] recorriendo el código de punta a punta."""
    ini = int.from_bytes(datos[0:4], "little")
    fin = min(len(datos), ini + int.from_bytes(datos[4:8], "little"))
    out, i = [], ini
    while i < fin:
        op = datos[i]
        k = OPERANDOS.get(op, 0)
        out.append((i, op, datos[i + 1:i + 1 + k]))
        i += 1 + k
    return out


def argumentos(ins, idx, cuantos):
    """Los argumentos de la llamada ins[idx] (el 1.º es el último empujado), cada uno como lista de instrucciones,
    o None si aparece una instrucción cuyo efecto en la pila no se conoce."""
    out, actual, falta = [], [], 1
    j = idx - 1
    while j >= 0 and len(out) < cuantos:
        i, op, a = ins[j]
        if op in EMPUJA:
            efecto = 1
        elif op in BINARIAS:
            efecto = -1
        elif op == LOAD:
            efecto = 0
        else:
            return None
        actual.insert(0, ins[j])
        falta -= efecto
        if falta == 0:
            out.append(actual)
            actual, falta = [], 1
        j -= 1
    return out if len(out) == cuantos else None


def _es_push0(arg):
    return len(arg) == 1 and arg[0][1] == 0x00 and arg[0][2] == b"\x00"


def _direccion(arg):
    """La expresión de dirección (bytes) de un argumento leído de memoria («… load»), o None."""
    if len(arg) >= 2 and arg[-1][1] == LOAD and all(op in EMPUJA | BINARIAS for _i, op, _a in arg[:-1]):
        return b"".join(bytes([op]) + a for _i, op, a in arg[:-1]), arg[-1][2]
    return None


def constante(largo, valor=1):
    """Bytes de código que dejan 'valor' en la pila y ocupan exactamente 'largo' bytes: un push y pares «push 0, add»
    (push8 = 2 bytes, push16 = 3, push32 = 5, add = 1).  None si no se puede con ese largo."""
    pushes = {2: b"\x00" + bytes([valor]), 3: b"\x01" + valor.to_bytes(2, "little"), 5: b"\x02" + valor.to_bytes(4, "little")}
    ceros = {3: b"\x00\x00\x20", 4: b"\x01\x00\x00\x20", 6: b"\x02\x00\x00\x00\x00\x20"}
    for t, primero in pushes.items():
        resto, out = largo - t, primero
        if resto < 0:
            continue
        for n in (6, 4, 3):                      # relleno goloso; con 3, 4 y 6 se cubre todo resto >= 3
            while resto - n >= 0 and (resto - n == 0 or resto - n >= 3):
                out += ceros[n]
                resto -= n
        if resto == 0:
            return out
    return None


def parchear_proporcional(programas):
    """programas: {nombre: bytes}.  -> ({nombre: bytes modificados}, informe).
    informe = {"cambios": [(programa, posición, qué)], "omitidas": [(programa, posición, motivo)]}"""
    nuevos = {n: bytearray(d) for n, d in programas.items()}
    rep = {"cambios": [], "omitidas": []}
    direcciones = set()
    tablas = {n: instrucciones(d) for n, d in programas.items()}
    for n, ins in tablas.items():
        for k, (pos, op, a) in enumerate(ins):
            clave = (op, a[0]) if a else None
            if clave not in LLAMADAS:
                continue
            cual, cuantos = LLAMADAS[clave]
            args = argumentos(ins, k, cuantos)
            nombre = f"{op:02x}:{a[0]:02x}"
            if args is None:
                rep["omitidas"].append((n, pos, f"{nombre}: no se pudieron separar los argumentos"))
                continue
            arg = args[cual - 1]
            if _es_push0(arg):
                nuevos[n][arg[0][0] + 1] = 1
                rep["cambios"].append((n, arg[0][0], f"{nombre}: argumento {cual} push 0 -> push 1"))
            elif _direccion(arg):
                direcciones.add(_direccion(arg))
                ini = arg[0][0]
                fin = arg[-1][0] + 1 + len(arg[-1][2])
                nuevo = constante(fin - ini)
                if nuevo is None:
                    rep["omitidas"].append((n, pos, f"{nombre}: la lectura de la preferencia no se puede reemplazar"))
                else:
                    nuevos[n][ini:fin] = nuevo
                    rep["cambios"].append((n, ini, f"{nombre}: argumento {cual} leído de la preferencia -> 1 fijo"))
    # preferencias: «<dirección> push8 0 move(tamaño)» -> push8 1
    for n, ins in tablas.items():
        for k in range(len(ins) - 1):
            for expr, tam in direcciones:
                largo = len(expr)
                pos = ins[k][0]
                if bytes(programas[n][pos:pos + largo]) != expr:
                    continue
                # tras la dirección: push8 0 y move del mismo tamaño
                j = next((m for m in range(k, len(ins)) if ins[m][0] == pos + largo), None)
                if j is None or j + 1 >= len(ins):
                    continue
                (p1, o1, a1), (o2, a2) = ins[j], ins[j + 1][1:]
                if o1 == 0x00 and a1 == b"\x00" and o2 == MOVE and a2 == tam:
                    nuevos[n][p1 + 1] = 1
                    rep["cambios"].append((n, p1, "valor inicial de la preferencia de modo proporcional: 0 -> 1"))
    cambiados = {n for n, _p, _q in rep["cambios"]}
    return {n: bytes(nuevos[n]) for n in cambiados}, rep


def resumen(rep):
    c = collections.Counter(n for n, _p, _q in rep["cambios"])
    return ", ".join(f"{n} ({k})" for n, k in sorted(c.items()))

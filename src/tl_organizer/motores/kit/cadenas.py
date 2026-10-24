# SPDX-License-Identifier: GPL-3.0-or-later
"""Tabla de cadenas: la estrategia para traducir un binario sin reubicar nada.

Muchos formatos compilados guardan las cadenas en una tabla y el código las referencia por desplazamiento.  En vez de
reescribir el archivo (y tener que corregir saltos, exportaciones y demás), se dejan las cadenas originales donde están,
las nuevas se AGREGAN AL FINAL de la tabla y solo se cambia el operando que apunta a cada texto traducido.

    tabla = TablaDeCadenas(cola_original, inicio=desplazamiento_de_la_tabla)
    nuevo_operando = tabla.agregar(texto_codificado)      # repetidos: se guardan una sola vez
    ... escribir los operandos nuevos (reapuntar) y, al final, tabla.bytes() ...
    verificar_operandos(original, nuevo, posiciones)      # comprueba que no cambió nada más

(Ver motores/bgi/text/import_.py: los escenarios de BGI se traducen así.)
"""
import struct


class CadenasError(Exception):
    pass


class TablaDeCadenas:
    def __init__(self, cola, inicio=0, terminador=b"\0"):
        """cola: los bytes de la tabla original; inicio: el desplazamiento (en el sistema de los operandos) de su primer byte."""
        self.cola = bytearray(cola)
        self.inicio = inicio
        self.terminador = terminador
        self._nuevas = {}

    def cadena_en(self, desplazamiento):
        """La cadena (sin terminador) que empieza en ese desplazamiento."""
        i = desplazamiento - self.inicio
        fin = self.cola.index(self.terminador, i)
        return bytes(self.cola[i:fin])

    def agregar(self, datos):
        """Agrega una cadena al final y devuelve su desplazamiento.  La misma cadena se agrega una sola vez."""
        if self.terminador in datos:
            raise CadenasError("la cadena contiene el terminador")
        if datos not in self._nuevas:
            self._nuevas[datos] = self.inicio + len(self.cola)
            self.cola.extend(datos + self.terminador)
        return self._nuevas[datos]

    def bytes(self):
        return bytes(self.cola)


def reapuntar(datos, operandos, formato="<I"):
    """Copia de 'datos' con cada operando en su posición cambiado: operandos = {posición_en_bytes: valor_nuevo}."""
    out = bytearray(datos)
    for pos, valor in operandos.items():
        struct.pack_into(formato, out, pos, valor)
    return bytes(out)


def verificar_operandos(original, nuevo, posiciones, ancho=4):
    """Comprueba que 'nuevo' empieza igual que 'original' salvo en los operandos de 'posiciones' (cada uno de 'ancho' bytes).
    Lo que 'nuevo' tenga después del largo de 'original' (las cadenas agregadas) no se compara.  Lanza CadenasError."""
    if len(nuevo) < len(original):
        raise CadenasError("el archivo nuevo es más corto que el original")
    permitidos = set()
    for p in posiciones:
        permitidos.update(range(p, p + ancho))
    for i, (a, b) in enumerate(zip(original, nuevo)):
        if a != b and i not in permitidos:
            raise CadenasError(f"cambió el byte 0x{i:x}, que no es un operando de texto")

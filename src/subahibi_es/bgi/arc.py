# SPDX-License-Identifier: GPL-3.0-or-later
"""Lector de archivos BURIKO ARC20 (*.arc) de Ethornell/BGI."""
import struct
from dataclasses import dataclass

MAGIC = b"BURIKO ARC20"


@dataclass
class Entry:
    name: str
    offset: int          # relativo al inicio de los datos
    size: int


class Arc:
    """Un contenedor .arc: tabla de entradas de 0x80 bytes y datos a continuación."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            head = f.read(16)
            if head[:12] != MAGIC:
                raise ValueError(f"{path}: no es un BURIKO ARC20")
            count = struct.unpack_from("<I", head, 12)[0]
            table = f.read(count * 0x80)
        self._base = 16 + count * 0x80
        self.entries = []
        for i in range(count):
            e = table[i * 0x80:(i + 1) * 0x80]
            name = e[:0x60].split(b"\0")[0].decode("cp932", "replace")
            off, size = struct.unpack_from("<II", e, 0x60)
            self.entries.append(Entry(name, off, size))
        self._by_name = {e.name: e for e in self.entries}

    def __len__(self):
        return len(self.entries)

    def __contains__(self, name):
        return name in self._by_name

    def names(self):
        return [e.name for e in self.entries]

    def read(self, name):
        """Bytes tal como están guardados (sin descomprimir)."""
        e = self._by_name[name]
        with open(self.path, "rb") as f:
            f.seek(self._base + e.offset)
            return f.read(e.size)

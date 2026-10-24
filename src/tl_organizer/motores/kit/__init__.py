# SPDX-License-Identifier: GPL-3.0-or-later
"""Kit para escribir motores en Python (ver docs/MOTORES.md).

    codificaciones   decodificar(), codificar(), Sustitucion (letras que la codificación no tiene)
    contenedores     Contenedor, Carpeta, Zip, escribir_suelto()
    cadenas          TablaDeCadenas, reapuntar(), verificar_operandos()  (traducir binarios sin reubicar)
    texto_plano      MotorTextoPlano  (scripts de texto: patrones y listo)
    externo          MotorExterno     (envolver una herramienta de línea de comandos)
"""
from .cadenas import TablaDeCadenas, reapuntar, verificar_operandos
from .codificaciones import Sustitucion, codificar, decodificar, no_codificables
from .contenedores import Carpeta, Contenedor, Zip, escribir_suelto
from .externo import MotorExterno
from .texto_plano import MotorTextoPlano

__all__ = ["TablaDeCadenas", "reapuntar", "verificar_operandos", "Sustitucion", "codificar", "decodificar", "no_codificables",
           "Carpeta", "Contenedor", "Zip", "escribir_suelto", "MotorExterno", "MotorTextoPlano"]

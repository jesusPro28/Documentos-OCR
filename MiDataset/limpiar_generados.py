# -*- coding: utf-8 -*-
"""
limpiar_generados.py — Script para limpiar archivos generados por el pipeline.
Versión robusta para evitar errores de bloqueo de carpetas en Windows.
"""

import os
from pathlib import Path

def limpiar():
    print("\n=======================================================")
    print("  LIMPIEZA DEL ESPACIO DE TRABAJO (ROBUSTA)")
    print("=======================================================\n")

    # 1. Borrar manifiesto.csv
    manifiesto = Path("manifiesto.csv")
    if manifiesto.exists():
        try:
            manifiesto.unlink()
            print("  [x] Eliminado: manifiesto.csv")
        except Exception as e:
            print(f"  [ERROR] No se pudo eliminar manifiesto.csv: {e}")

    # 2. Carpetas a limpiar (borrar todos los archivos de su interior)
    carpetas_a_limpiar = [
        "02_imagenes_convertidas",
        "03_imagenes_aumentadas",
        "05_reportes",
        "registros"
    ]

    for carpeta_nombre in carpetas_a_limpiar:
        base_dir = Path(carpeta_nombre)
        if base_dir.exists():
            # Buscamos de forma recursiva todos los archivos en esta carpeta
            archivos_borrados = 0
            for archivo in list(base_dir.rglob("*")):
                if archivo.is_file() and archivo.name != ".gitkeep":
                    try:
                        archivo.unlink()
                        archivos_borrados += 1
                    except Exception as e:
                        print(f"  [AVISO] No se pudo borrar {archivo.relative_to(base_dir)}: {e}")
            
            if archivos_borrados > 0:
                print(f"  [x] Limpiado en {carpeta_nombre}/: {archivos_borrados} archivo(s)")
            else:
                print(f"  [ ] {carpeta_nombre}/ ya estaba limpia.")

    print("\n[LISTO] El espacio de trabajo está limpio y listo para ejecutarse de nuevo.\n")

if __name__ == "__main__":
    limpiar()

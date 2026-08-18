# -*- coding: utf-8 -*-
# ============================================================
# PASO A — Preparar la estructura del dataset
# ============================================================
#
# ¿CÓMO FUNCIONA ESTE PASO?
# ─────────────────────────────────────────────────────────────
# Este es el primer paso. Crea las carpetas y el manifiesto.
#
# Lo que hace:
#   1. Lee configuracion.yaml (archivo de configuración)
#   2. Crea las carpetas del proyecto en disco
#   3. Crea manifiesto.csv vacío (registro de todas las imágenes)
#   4. Muestra un resumen de configuración en la consola
#
# ESTRUCTURA DE CARPETAS EN DISCO:
#   01_datos_originales/{clase}/       ← PDFs del usuario
#   02_imagenes_convertidas/{clase}/   ← PNGs generados por Paso B
#   03_imagenes_aumentadas/{clase}/    ← Copias artificiales (Paso C)
#   04_informacion_documentos/         ← Metadatos de procesamiento
#   05_reportes/                       ← Reportes de calidad
#   registros/                         ← Logs de control
# ============================================================

# Importamos la librería 'csv' para poder crear y escribir archivos CSV
import csv
# Importamos 'sys' para poder interactuar con el sistema (como cerrar el programa en caso de error)
import sys
# Importamos 'yaml' para leer y procesar el archivo 'configuracion.yaml'
import yaml
# Importamos 'Path' de la librería 'pathlib' que facilita la creación y manejo de rutas de archivos
from pathlib import Path


def cargar_configuracion():
    """
    ¿QUÉ HACE?
      Lee el archivo 'configuracion.yaml' para obtener los parámetros globales del proyecto.
    ¿CÓMO SE HACE?
      1. Define la ruta hacia el archivo YAML.
      2. Verifica si el archivo existe físicamente en el disco.
      3. Si existe, lo abre en modo lectura y lo parsea como un diccionario de Python.
    """
    # 1. Definimos el nombre del archivo de configuración como un objeto Path
    ruta = Path("configuracion.yaml")
    
    # 2. Comprobamos si el archivo no existe para evitar que el programa falle con un error feo
    if not ruta.exists():
        print("[ERROR] No encontre 'configuracion.yaml'")
        print("        Asegurate de estar ejecutando el script desde la carpeta raiz: MiDataset/")
        # sys.exit(1) finaliza la ejecución de Python inmediatamente con código de error (1)
        sys.exit(1)

    # 3. Abrimos el archivo usando un bloque 'with' (que asegura que el archivo se cierre al terminar)
    # Especificamos encoding='utf-8' para soportar acentos y caracteres especiales en español
    with open(ruta, "r", encoding="utf-8") as archivo:
        # yaml.safe_load convierte el texto del archivo YAML en un diccionario legible por Python
        config = yaml.safe_load(archivo)

    # 4. Imprimimos un mensaje de éxito mostrando el nombre del dataset configurado
    print(f"[OK] Configuracion cargada: {config['dataset']['nombre']}")
    return config


def crear_carpetas(config):
    """
    ¿QUÉ HACE?
      Crea toda la estructura de carpetas del proyecto.
    ¿CÓMO SE HACE?
      1. Lee las rutas del archivo de configuración.
      2. Crea carpetas generales (informacion, reportes, registros).
      3. Crea carpetas específicas para cada clase de documento (actas_nacimiento, curp).
      4. Deja un archivo de texto de aviso en la carpeta de originales.
    """
    print("\n--- Verificando carpetas del proyecto ---")

    # Extraemos la sección de rutas de carpetas de la configuración
    carpetas = config["carpetas"]
    # Extraemos solo los nombres de las clases (ej: ['actas_nacimiento', 'curp']) usando una lista por comprensión
    clases   = [c["nombre"] for c in config["clases"]]

    # Definimos la lista de carpetas simples (que no se dividen por clase de documento)
    carpetas_simples = [
        carpetas["informacion"], # Ruta para guardar metadatos JSON
        carpetas["reportes"],    # Ruta para los reportes finales de calidad
        carpetas["registros"],   # Ruta para guardar bitácoras e historial
    ]

    # Definimos la lista de carpetas base que SÍ se dividen en subcarpetas para cada clase de documento
    carpetas_por_clase = [
        carpetas["originales"],  # 01_datos_originales
        carpetas["convertidas"], # 02_imagenes_convertidas
        carpetas["aumentadas"],  # 03_imagenes_aumentadas
    ]

    # 1. Bucle para crear las carpetas generales
    for carpeta in carpetas_simples:
        # Path(carpeta).mkdir crea el directorio.
        # parents=True crea carpetas padre si faltan. exist_ok=True evita fallar si la carpeta ya existe.
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        print(f"  [v] {carpeta}/")

    # 2. Bucle anidado para crear las carpetas por clase (ej: 01_datos_originales/curp)
    for base in carpetas_por_clase:
        for clase in clases:
            # Combinamos la carpeta base con el nombre de la clase (ej: "01_datos_originales" + "curp")
            Path(base, clase).mkdir(parents=True, exist_ok=True)
        print(f"  [v] {base}/  (subcarpetas creadas: {', '.join(clases)})")

    print("\n[OK] Todas las carpetas estan listas y preparadas en el disco.")


def crear_manifiesto(config):
    """
    ¿QUÉ HACE?
      Crea el archivo 'manifiesto.csv' que sirve como índice central del dataset.
    ¿CÓMO SE HACE?
      1. Define el nombre del archivo.
      2. Si ya existe, aborta (para no sobreescribir datos anteriores).
      3. Si no existe, define las 12 columnas y escribe el encabezado.
    """
    # 1. Definimos la ruta del archivo manifiesto
    ruta = Path("manifiesto.csv")

    # 2. Si el manifiesto ya existe, mostramos aviso y salimos de la función sin tocarlo
    if ruta.exists():
        print(f"\n[INFO] El manifiesto ya existe. No se sobreescribio para proteger tus datos.")
        return

    # 3. Definimos las 12 columnas que tendrá nuestra tabla de control
    columnas = [
        "nombre_archivo_original", # Nombre original del PDF tal como estaba en disco (ej: acta_wendy.pdf)
        "id_documento",       # Prefijo único del documento (ej: ACT_0001)
        "id_pagina",          # Nombre único de la página (ej: ACT_0001_pagina_001)
        "clase",              # Clase del documento (actas_nacimiento / curp)
        "ruta_imagen",        # Ruta exacta del archivo PNG en el disco
        "ruta_pdf_original",  # Ruta al PDF original de donde se extrajo la página
        "ancho_pixeles",      # Resolución horizontal en píxeles
        "alto_pixeles",       # Resolución vertical en píxeles
        "puntuacion_calidad", # Puntuación de calidad calculada (0.0 a 1.0)
        "necesita_revision",  # Booleano (True/False): si la calidad es baja y requiere revisión
        "es_aumentada",       # Booleano (True/False): si la imagen es real o es copia aumentada
        "fecha_procesado",    # Fecha y hora en la que se procesó el archivo
        "notas",              # Campo de texto libre para observaciones
    ]

    # 4. Abrimos el archivo en modo escritura ('w') con codificación UTF-8
    # newline="" es necesario para evitar filas vacías adicionales en sistemas Windows al escribir CSVs
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        # DictWriter es un ayudante de Python que escribe filas en el CSV mapeando diccionarios
        escritor = csv.DictWriter(f, fieldnames=columnas)
        # writeheader escribe la primera línea del CSV con los nombres de las columnas
        escritor.writeheader()

    print(f"\n[OK] Manifiesto creado: {ruta}  ({len(columnas)} columnas de control)")


def mostrar_resumen(config):
    """
    ¿QUÉ HACE?
      Imprime en la consola un cuadro con el resumen de la configuración del proyecto.
    """
    clases = config["clases"]
    conv   = config["conversion"]
    aum    = config["aumento"]

    print("\n" + "="*55)
    print("  RESUMEN DEL DATASET")
    print("="*55)
    print(f"  Nombre      : {config['dataset']['nombre']}")
    print(f"\n  CLASES      : {len(clases)} tipos de documento configurados")
    for c in clases:
        # c['id'] es el número interno, c['codigo'] es el prefijo (ACT/CUR), c['nombre'] es la carpeta
        print(f"    ID {c['id']} [{c['codigo']}]  {c['nombre']}")
    print(f"\n  CONVERSION  : {conv['dpi']} DPI  |  formato {conv['formato'].upper()}")
    print(f"  AUMENTACION : {aum['copias_por_imagen']} copias artificiales por original")
    print(f"  CORRECCION  : NO (el modelo de IA decidira si esta bien o mal)")
    print("="*55)


# ---------------------------------------------------------------
# PUNTO DE ENTRADA: Solo se ejecuta si corres este archivo directamente
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  PASO A — Preparar estructura del dataset")
    print("="*55 + "\n")

    # Ejecutamos las funciones en orden secuencial
    config = cargar_configuracion()  # 1. Leer archivo de configuración
    crear_carpetas(config)          # 2. Crear las carpetas en disco
    crear_manifiesto(config)        # 3. Crear manifiesto.csv vacío
    mostrar_resumen(config)         # 4. Imprimir resumen en consola

    print("\n[LISTO] Paso A completado.")
    print("  Siguiente → coloca tus archivos PDFs en: 01_datos_originales/")
    print("  Luego     → ejecuta el Paso B con: python construir_dataset.py\n")

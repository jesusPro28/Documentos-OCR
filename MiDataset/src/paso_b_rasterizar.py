# -*- coding: utf-8 -*-
# ============================================================
# PASO B — Convertir PDFs a imágenes PNG de 300 DPI
# ============================================================
#
# ¿CÓMO FUNCIONA ESTE PASO?
# ─────────────────────────────────────────────────────────────
# Un PDF escaneado es como un álbum de fotos digital (contenedor).
# Las redes neuronales de visión artificial necesitan archivos de
# imágenes individuales (como PNG) para poder procesarlas.
#
# PROCESO POR CADA PDF:
#   1. Abre el PDF usando la librería PyMuPDF (fitz).
#   2. Por cada página:
#        a) Calcula el zoom necesario para alcanzar 300 DPI (calidad profesional).
#        b) Renderiza la página a una imagen en la memoria RAM (pixmap).
#        c) Convierte la imagen a un formato que entienda OpenCV (NumPy array).
#        d) Calcula su calidad de forma matemática (nitidez y contraste).
#        e) Guarda la imagen en formato PNG en la carpeta correspondiente.
#   3. Añade los registros de cada página al archivo manifiesto.csv.
# ============================================================

# Importamos 'csv' para poder escribir registros en manifiesto.csv
import csv
# Importamos 'sys' para detener el script si algo sale mal
import sys
# Importamos 'yaml' para leer los parámetros en configuracion.yaml
import yaml
# Importamos 'fitz' (que pertenece a PyMuPDF) para abrir y renderizar PDFs
import fitz           
# Importamos 'numpy' como 'np' para transformar los datos de píxeles en memoria
import numpy as np    
# Importamos 'cv2' (OpenCV) para guardar imágenes PNG y calcular calidad visual
import cv2            
# Importamos 'Path' para interactuar de forma segura con rutas en el disco
from pathlib import Path
# Importamos 'datetime' para registrar la fecha y hora exacta del procesamiento
from datetime import datetime


def cargar_configuracion():
    """
    ¿QUÉ HACE?
      Lee y carga el archivo 'configuracion.yaml'.
    ¿CÓMO SE HACE?
      Comprueba si existe el archivo yaml y lo carga usando safe_load.
    """
    ruta = Path("configuracion.yaml")
    if not ruta.exists():
        print("[ERROR] No encontre 'configuracion.yaml'")
        print("        Ejecuta primero: python src/paso_a_preparar.py")
        sys.exit(1)
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def calcular_puntuacion_calidad(imagen_bgr):
    """
    ¿QUÉ HACE?
      Calcula una puntuación numérica de calidad entre 0.0 y 1.0 para una imagen.
    ¿CÓMO SE HACE?
      1. Convierte la imagen a escala de grises.
      2. Mide la NITIDEZ usando el operador Laplaciano (mide variaciones en bordes de texto).
         Un valor de varianza alto significa bordes definidos (nítido).
      3. Mide el CONTRASTE usando la desviación estándar (std) de píxeles.
         Alta dispersión de colores significa letras negras legibles sobre fondo blanco.
      4. Normaliza y pondera ambos valores: 60% Nitidez + 40% Contraste.
    """
    # 1. Convertimos la imagen de color (BGR) a escala de grises (GRAY) para facilitar el análisis
    gris = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)

    # 2. Calculamos el operador Laplaciano de la imagen en formato de precisión de punto flotante de 64 bits (.var() obtiene la varianza)
    # Un Laplaciano calcula la segunda derivada geométrica. En bordes definidos, la varianza es alta.
    nitidez   = cv2.Laplacian(gris, cv2.CV_64F).var()
    # 3. Calculamos la desviación estándar de la escala de grises (mide la dispersión/contraste de píxeles)
    contraste = float(gris.std())

    # 4. Normalizamos los valores dividiéndolos por un valor de referencia óptimo.
    # 600.0 es la varianza típica para texto nítido a 300 DPI. Limitamos a un máximo de 1.0 usando min()
    p_nitidez   = min(nitidez   / 600.0, 1.0)
    # 80.0 es la desviación estándar típica de buen contraste (negro absoluto vs blanco absoluto). Max 1.0
    p_contraste = min(contraste / 80.0,  1.0)

    # 5. Retornamos la suma ponderada redondeada a 4 decimales: (60% peso nitidez + 40% peso contraste)
    return round(0.60 * p_nitidez + 0.40 * p_contraste, 4)


def convertir_pdf(ruta_pdf, carpeta_salida, id_documento, dpi=300):
    """
    ¿QUÉ HACE?
      Abre un PDF y convierte todas sus páginas a archivos de imagen PNG.
    ¿CÓMO SE HACE?
      1. Calcula el factor de zoom (fitz.Matrix) basado en los DPI configurados (300 DPI).
      2. Abre el PDF en memoria con PyMuPDF.
      3. Itera por cada página y extrae su representación visual en memoria (pixmap).
      4. Transforma los datos en bruto a un array de NumPy y los convierte al orden de color BGR de OpenCV.
      5. Calcula el score de calidad de la página.
      6. Guarda la imagen en disco como PNG (usando cv2.imwrite).
      7. Guarda un diccionario con los datos listos para el manifiesto.
    """
    # 1. Calculamos el factor de escala: el PDF nativo trabaja a 72 DPI base.
    # Si queremos 300 DPI, el zoom debe ser 300 / 72 = 4.166 veces más píxeles.
    zoom   = dpi / 72.0
    # fitz.Matrix define la escala geométrica (zoom en X y zoom en Y)
    matriz = fitz.Matrix(zoom, zoom)

    paginas = []

    try:
        # 2. Abrimos el PDF pasándole la ruta como cadena de texto
        pdf = fitz.open(str(ruta_pdf))
        print(f"    {ruta_pdf.name}  ({len(pdf)} pag.)")

        # 3. Iteramos por el índice de cada página (desde 0 hasta el total de páginas - 1)
        for num in range(len(pdf)):
            pagina = pdf[num]

            # Renderizamos la página en un mapa de píxeles (pixmap) con la matriz de zoom
            # alpha=False desactiva la transparencia (fondo blanco en vez de transparente si no hay color)
            pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)

            # 4. Convertimos los datos del pixmap (formato RGB crudo en bytes) en una matriz de NumPy unidimensional
            datos = np.frombuffer(pixmap.samples, dtype=np.uint8)
            # Reorganizamos los bytes en una matriz 3D con forma (alto_imagen, ancho_imagen, 3 canales RGB)
            imagen_rgb = datos.reshape(pixmap.height, pixmap.width, 3)

            # OpenCV trabaja en formato BGR. Convertimos el orden de canales de color: RGB -> BGR
            imagen_bgr = cv2.cvtColor(imagen_rgb, cv2.COLOR_RGB2BGR)

            # 5. Calculamos la calidad de la matriz BGR
            puntuacion       = calcular_puntuacion_calidad(imagen_bgr)
            # Si el puntaje es menor a 0.65, marcamos el booleano 'necesita_revision' como True
            necesita_revision = puntuacion < 0.65

            # 6. Definimos el nombre único del archivo (ej: ACT_0001_pagina_001.png)
            # :03d le da formato de 3 dígitos con ceros a la izquierda (ej: 001)
            nombre_pagina  = f"{id_documento}_pagina_{num + 1:03d}"
            nombre_archivo = f"{nombre_pagina}.png"
            ruta_salida    = carpeta_salida / nombre_archivo

            # Nos aseguramos de que la carpeta de destino exista antes de guardar
            carpeta_salida.mkdir(parents=True, exist_ok=True)
            # cv2.imwrite escribe físicamente la matriz BGR como archivo de imagen PNG en el disco
            cv2.imwrite(str(ruta_salida), imagen_bgr)

            estado = "REVISAR" if necesita_revision else "OK"
            print(f"      {nombre_archivo}  calidad={puntuacion:.2f} [{estado}]")

            # 7. Añadimos un diccionario con los datos a la lista de páginas
            paginas.append({
                "nombre_archivo_original": ruta_pdf.name,
                "id_documento":       id_documento,
                "id_pagina":          nombre_pagina,
                "ruta_imagen":        str(ruta_salida),
                "ruta_pdf_original":  str(ruta_pdf),
                "ancho_pixeles":      pixmap.width,
                "alto_pixeles":       pixmap.height,
                "puntuacion_calidad": puntuacion,
                "necesita_revision":  necesita_revision,
            })

        # Cerramos el objeto PDF para liberar la memoria RAM
        pdf.close()

    except Exception as err:
        # Si ocurre algún error en la conversión, lo capturamos para evitar que todo el pipeline se caiga
        print(f"    [ERROR] {ruta_pdf.name}: {err}")

    return paginas


def registrar_en_manifiesto(registros, clase):
    """
    ¿QUÉ HACE?
      Añade las páginas procesadas al final del archivo manifiesto.csv (Append).
    ¿CÓMO SE HACE?
      1. Abre manifiesto.csv en modo append ('a').
      2. Usa DictWriter para escribir cada registro mapeado con las columnas oficiales.
    """
    ruta = Path("manifiesto.csv")
    if not ruta.exists():
        print("[ERROR] No existe manifiesto.csv. Ejecuta primero el Paso A.")
        return

    # Columnas esperadas en el manifiesto
    columnas = [
        "nombre_archivo_original", "id_documento", "id_pagina", "clase", "ruta_imagen",
        "ruta_pdf_original", "ancho_pixeles", "alto_pixeles",
        "puntuacion_calidad", "necesita_revision", "es_aumentada",
        "fecha_procesado", "notas",
    ]

    # Abrimos en modo 'a' (append/añadir al final) sin sobreescribir lo que ya estaba
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        for reg in registros:
            # Escribimos la fila complementando con los datos fijos de esta clase
            escritor.writerow({
                **reg,
                "clase":           clase,
                "es_aumentada":    False, # Estas son imágenes reales, no aumentadas
                "fecha_procesado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "notas":           "",
            })


# ---------------------------------------------------------------
# PUNTO DE ENTRADA PRINCIPAL
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  PASO B — Convertir PDFs a imagenes PNG (300 DPI)")
    print("="*55 + "\n")

    # Cargamos configuraciones
    config   = cargar_configuracion()
    carpetas = config["carpetas"]
    dpi      = config["conversion"]["dpi"]

    total_docs   = 0
    total_paginas = 0

    # Iteramos por cada clase configurada (ej: actas_nacimiento, curp)
    for clase_info in config["clases"]:
        nombre = clase_info["nombre"]
        codigo = clase_info["codigo"]

        # Definimos las carpetas de entrada y salida para esta clase
        carpeta_origen  = Path(carpetas["originales"])  / nombre
        carpeta_destino = Path(carpetas["convertidas"]) / nombre

        print(f"\n--- Clase: {nombre} ---")

        # Buscamos todos los archivos PDF en la carpeta de origen (.pdf y .PDF)
        # Usamos un conjunto (set) para evitar duplicados en sistemas case-insensitive como Windows
        pdfs_encontrados = set(carpeta_origen.glob("*.pdf")) | set(carpeta_origen.glob("*.PDF"))
        pdfs = sorted(list(pdfs_encontrados))

        if not pdfs:
            print(f"  [AVISO] Sin PDFs en {carpeta_origen}/")
            print(f"          Coloca tus archivos .pdf ahi y vuelve a ejecutar.")
            continue

        print(f"  {len(pdfs)} PDF(s) encontrado(s)")

        # Calculamos el siguiente número consecutivo analizando las imágenes que ya están en la carpeta de destino
        # Esto nos permite ejecutar el script múltiples veces sin sobreescribir documentos anteriores
        existentes    = {img.stem.rsplit("_pagina_", 1)[0]
                         for img in carpeta_destino.glob("*.png")}
        siguiente_num = len(existentes) + 1

        todos_registros = []

        # Convertimos cada PDF de la lista
        for pdf in pdfs:
            # Generamos el ID único (ej: ACT_0001) con formato de 4 dígitos
            id_doc   = f"{codigo}_{siguiente_num:04d}"
            registros = convertir_pdf(pdf, carpeta_destino, id_doc, dpi)
            todos_registros.extend(registros)
            siguiente_num += 1
            total_docs    += 1
            total_paginas += len(registros)

        # Si convertimos páginas con éxito, las registramos en el manifiesto
        if todos_registros:
            registrar_en_manifiesto(todos_registros, nombre)

    # Imprimimos resumen final del Paso B
    print(f"\n{'='*55}")
    print(f"  RESUMEN PASO B")
    print(f"  Documentos procesados : {total_docs}")
    print(f"  Imagenes generadas    : {total_paginas}")
    print(f"  Resolucion            : {dpi} DPI")
    print(f"{'='*55}")
    print("\n[LISTO] Paso B completado.")
    print("  Siguiente → ejecuta el Paso C con: python construir_dataset.py (o corre src/paso_c_aumentar.py)\n")

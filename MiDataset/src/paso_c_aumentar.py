# -*- coding: utf-8 -*-
# ============================================================
# PASO C — Aumentar el dataset (Data Augmentation)
# ============================================================
#
# ¿CÓMO FUNCIONA ESTE PASO?
# ─────────────────────────────────────────────────────────────
# PROBLEMA: Para entrenar un modelo de Inteligencia Artificial
#   se requieren cientos o miles de ejemplos. Con pocos documentos
#   originales, la IA sufrirá de sobreajuste (overfitting).
#
# SOLUCIÓN:
#   Generamos copias artificiales (aumentadas) aplicando alteraciones
#   realistas basadas en los errores típicos de captura de los usuarios:
#     1. Rotación leve (±10 grados) -> Simula hojas mal alineadas.
#     2. Cambio de brillo/contraste (±30%) -> Simula sombras o luz solar directa.
#     3. Ruido gaussiano -> Simula grano del sensor de la cámara del celular.
#     4. Zoom / Recorte aleatorio -> Simula mal encuadre de la foto.
#     5. Desenfoque leve -> Simula mala pulsación de la cámara (cámara movida).
# ============================================================

# Importamos 'sys' para control del sistema (detener en caso de error)
import sys
# Importamos 'csv' para registrar las nuevas variantes en el manifiesto
import csv
# Importamos 'yaml' para leer los parámetros globales en configuracion.yaml
import yaml
# Importamos 'cv2' (OpenCV) para aplicar transformaciones a las matrices de píxeles
import cv2
# Importamos 'numpy' para manipulación y cálculo numérico sobre los arrays de imágenes
import numpy as np
# Importamos 'Path' de pathlib para manejar las rutas de archivos en disco de forma multiplataforma
from pathlib import Path
# Importamos 'datetime' para fechar el momento exacto en el que creamos las aumentadas
from datetime import datetime

# Intentamos cargar la librería profesional de aumentación para Deep Learning 'albumentations'
# Si no está instalada, el bloque 'try-except' lo detecta y activa un fallback usando OpenCV básico
try:
    import albumentations as A
    USA_ALBUMENTATIONS = True
except ImportError:
    USA_ALBUMENTATIONS = False
    print("[AVISO] La libreria 'albumentations' no esta instalada en tu Python.")
    print("        Usaremos metodos nativos de OpenCV basico en su lugar.")
    print("        Para un mejor rendimiento, puedes instalarla con: pip install albumentations\n")


def cargar_configuracion():
    """
    ¿QUÉ HACE?
      Lee y carga el archivo central configuracion.yaml.
    """
    ruta = Path("configuracion.yaml")
    if not ruta.exists():
        print("[ERROR] No encontre 'configuracion.yaml'")
        sys.exit(1)
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def crear_transformaciones_albumentations():
    """
    ¿QUÉ HACE?
      Define las 5 pipelines (cadenas de transformación) usando albumentations.
    ¿CÓMO SE HACE?
      Cada transformación es un objeto Compose que siempre se ejecutará (p=1.0).
    """
    return [
        # Variante 1: Rotación leve de ±10 grados. BORDER_REPLICATE estira los píxeles de los bordes para no dejar esquinas negras.
        A.Compose([A.Rotate(limit=10, p=1.0, border_mode=cv2.BORDER_REPLICATE)]),

        # Variante 2: Cambios aleatorios de brillo y contraste de hasta ±30%
        A.Compose([A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=1.0)]),

        # Variante 3: Inyección de grano digital fino (ruido gaussiano estándar)
        A.Compose([A.GaussNoise(std_range=(0.02, 0.05), p=1.0)]),

        # Variante 4: Recorte aleatorio del layout (entre 85% y 95% del tamaño original) y redimensión
        A.Compose([A.RandomResizedCrop(size=(800, 600), scale=(0.85, 0.95), ratio=(0.95, 1.05), p=1.0)]),

        # Variante 5: Desenfoque de lente simulado usando un filtro Gaussiano leve de 3x3 a 5x5
        A.Compose([A.GaussianBlur(blur_limit=(3, 5), p=1.0)]),
    ]


def aumentar_con_opencv(imagen, variante):
    """
    ¿QUÉ HACE?
      Método alternativo para generar variantes si albumentations no está instalado.
    ¿CÓMO SE HACE?
      Aplica transformaciones nativas de OpenCV:
      - Variante 1: Rotación de 7 grados en el sentido de las agujas del reloj.
      - Variante 2: Rotación de -7 grados en sentido contrario.
      - Variante 3: Aumento de brillo multiplicando píxeles (alpha) e inyectando un offset constante (beta).
      - Variante 4: Disminución de brillo reduciendo valores y restando offset.
      - Variante 5: Desenfoque gaussiano suave (3x3).
    """
    # Obtenemos dimensiones de la imagen (alto, ancho)
    alto, ancho = imagen.shape[:2]
    # Calculamos la coordenada del píxel central de la imagen
    centro = (ancho // 2, alto // 2)

    if variante == 1:
        # getRotationMatrix2D obtiene la matriz matemática de rotación de 2D (centro, ángulo, escala)
        M = cv2.getRotationMatrix2D(centro, 7, 1.0)
        # warpAffine aplica físicamente la rotación sobre los píxeles
        return cv2.warpAffine(imagen, M, (ancho, alto), borderMode=cv2.BORDER_REPLICATE)
        
    elif variante == 2:
        # Rotación a -7 grados
        M = cv2.getRotationMatrix2D(centro, -7, 1.0)
        return cv2.warpAffine(imagen, M, (ancho, alto), borderMode=cv2.BORDER_REPLICATE)
        
    elif variante == 3:
        # Aumentamos brillo: alpha=1.3 (multiplica los píxeles para aumentar contraste) y beta=25 (suma brillo)
        # convertScaleAbs se asegura de que no nos pasemos de 255 (límite de color de 8 bits)
        return cv2.convertScaleAbs(imagen, alpha=1.3, beta=25)
        
    elif variante == 4:
        # Disminuimos brillo: multiplicamos por 0.7 y restamos 25 unidades de color
        return cv2.convertScaleAbs(imagen, alpha=0.7, beta=-25)
        
    else:
        # Filtro de desenfoque gaussiano de tamaño 3x3
        return cv2.GaussianBlur(imagen, (3, 3), 0)


def generar_variantes(ruta_imagen, carpeta_salida, num_copias, transformaciones):
    """
    ¿QUÉ HACE?
      Carga una imagen original, crea N variantes alteradas y las guarda en la carpeta de aumentadas.
    ¿CÓMO SE HACE?
      1. Carga la imagen BGR original de la ruta.
      2. Crea un bucle según el número de copias configuradas.
      3. Si usa Albumentations, convierte la imagen a RGB, aplica el transformador asignado y vuelve a BGR.
      4. Si el tamaño de la imagen resultante difiere del original (por ejemplo, debido a recortes), la redimensiona.
      5. Si Albumentations falla o no está disponible, utiliza el método nativo de OpenCV.
      6. Guarda la variante en disco con cv2.imwrite y añade la ruta a una lista de salida.
    """
    # 1. Cargamos la imagen original desde el disco
    imagen_bgr = cv2.imread(str(ruta_imagen))
    if imagen_bgr is None:
        return []

    alto, ancho = imagen_bgr.shape[:2]
    nombre_base = ruta_imagen.stem
    generadas   = []

    # 2. Bucle para generar cada variante numerada
    for i in range(1, num_copias + 1):
        # El nombre del archivo tendrá la extensión _aug01.png, _aug02.png, etc.
        nombre  = f"{nombre_base}_aug{i:02d}.png"
        destino = carpeta_salida / nombre

        # Si la imagen ya fue generada anteriormente, evitamos volver a gastar CPU y la agregamos directamente
        if destino.exists():
            generadas.append(str(destino))
            continue

        # 3. Aplicamos la transformación
        if USA_ALBUMENTATIONS and transformaciones:
            # Albumentations requiere las imágenes en formato RGB, mientras que OpenCV trabaja en BGR.
            # Convertimos el orden de canales: BGR -> RGB
            imagen_rgb = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2RGB)
            
            # Seleccionamos la transformación correspondiente usando operador módulo (%) para alternar entre las 5
            idx  = (i - 1) % len(transformaciones)
            try:
                # Ejecutamos la transformación pasando la imagen RGB
                resultado  = transformaciones[idx](image=imagen_rgb)
                # Volvemos a convertir el resultado a BGR para OpenCV
                imagen_aug = cv2.cvtColor(resultado["image"], cv2.COLOR_RGB2BGR)
                
                # 4. Si la variante cambió de tamaño, la redimensionamos al ancho y alto original
                if imagen_aug.shape[:2] != (alto, ancho):
                    imagen_aug = cv2.resize(imagen_aug, (ancho, alto))
            except Exception:
                # Si ocurre un fallo en albumentations, usamos OpenCV básico como plan de emergencia
                imagen_aug = aumentar_con_opencv(imagen_bgr, i)
        else:
            # 5. Si no está instalado Albumentations, usamos OpenCV directamente
            imagen_aug = aumentar_con_opencv(imagen_bgr, i)

        # 6. Guardamos físicamente el PNG de la variante aumentada en el disco
        cv2.imwrite(str(destino), imagen_aug)
        generadas.append(str(destino))

    return generadas


def registrar_aumentadas(registros_nuevos):
    """
    ¿QUÉ HACE?
      Registra las variantes aumentadas en el archivo manifiesto.csv (modo append).
    ¿CÓMO SE HACE?
      Abre manifiesto.csv en modo append ('a') y escribe el diccionario de cada fila.
    """
    ruta = Path("manifiesto.csv")
    if not ruta.exists():
        return

    # Definimos el orden estricto de las 13 columnas del manifiesto
    columnas = [
        "nombre_archivo_original", "id_documento", "id_pagina", "clase", "ruta_imagen",
        "ruta_pdf_original", "ancho_pixeles", "alto_pixeles",
        "puntuacion_calidad", "necesita_revision", "es_aumentada",
        "fecha_procesado", "notas",
    ]

    with open(ruta, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        for reg in registros_nuevos:
            escritor.writerow(reg)


# ---------------------------------------------------------------
# PUNTO DE ENTRADA PRINCIPAL
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  PASO C — Aumentar el dataset (Data Augmentation)")
    print("="*55 + "\n")

    # Cargamos archivos de configuración
    config     = cargar_configuracion()
    carpetas   = config["carpetas"]
    num_copias = config["aumento"]["copias_por_imagen"]

    # Inicializamos transformaciones de albumentations
    transformaciones = crear_transformaciones_albumentations() if USA_ALBUMENTATIONS else None

    print(f"  Copias por imagen  : {num_copias}")
    print(f"  Albumentations     : {'Si' if USA_ALBUMENTATIONS else 'No (OpenCV basico)'}\n")

    total_generadas = 0

    # Iteramos por las clases del proyecto
    for clase_info in config["clases"]:
        nombre = clase_info["nombre"]

        # Carpetas de entrada y salida
        carpeta_entrada = Path(carpetas["convertidas"]) / nombre
        carpeta_salida  = Path(carpetas["aumentadas"]) / nombre
        carpeta_salida.mkdir(parents=True, exist_ok=True)

        print(f"--- Clase: {nombre} ---")

        # Buscamos SOLO las imágenes originales en la carpeta de convertidas (excluimos las que tengan '_aug')
        originales = sorted([
            img for img in carpeta_entrada.glob("*.png")
            if "_aug" not in img.stem
        ])

        if not originales:
            print(f"  [AVISO] Sin imagenes en {carpeta_entrada}/")
            continue

        print(f"  {len(originales)} original(es) × {num_copias} = "
              f"{len(originales) * num_copias} imagenes a generar")

        nuevos_registros = []

        # Generamos variantes para cada original
        for img in originales:
            rutas = generar_variantes(img, carpeta_salida, num_copias, transformaciones)

            # Estructuramos la metadata de cada variante para el manifiesto
            for ruta_aug in rutas:
                p = Path(ruta_aug)
                # Extraemos el ID del documento original analizando el nombre (ej: ACT_0001)
                partes  = p.stem.split("_pagina_")
                id_doc  = partes[0] if len(partes) > 1 else p.stem.split("_aug")[0]

                # Añadimos al buffer de nuevos registros
                # Nota: Dejamos vacíos ancho, alto y calidad, ya que serán calculados en el Paso D
                nuevos_registros.append({
                    "id_documento":       id_doc,
                    "id_pagina":          p.stem,
                    "clase":              nombre,
                    "ruta_imagen":        ruta_aug,
                    "ruta_pdf_original":  "",
                    "ancho_pixeles":      "",
                    "alto_pixeles":       "",
                    "puntuacion_calidad": "",
                    "necesita_revision":  False,
                    "es_aumentada":       True, # Indicamos que esta es una imagen artificial
                    "fecha_procesado":    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "notas":              f"Aumentada de {img.name}",
                })
                total_generadas += 1

        # Registramos las variantes generadas en el manifiesto
        if nuevos_registros:
            registrar_aumentadas(nuevos_registros)
            print(f"  [OK] {len(nuevos_registros)} imagenes registradas en manifiesto")

    # Resumen final de aumentación
    print(f"\n{'='*55}")
    print(f"  RESUMEN PASO C")
    print(f"  Imagenes generadas : {total_generadas}")
    print(f"{'='*55}")
    print("\n[LISTO] Paso C completado.")
    print("  Siguiente → ejecuta el Paso D con: python construir_dataset.py (o corre src/paso_d_calidad.py)\n")

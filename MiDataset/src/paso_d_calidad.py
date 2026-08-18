# -*- coding: utf-8 -*-
# ============================================================
# PASO D — Control de calidad del dataset
# ============================================================
#
# ¿CÓMO FUNCIONA ESTE PASO?
# ─────────────────────────────────────────────────────────────
# Antes de entrenar la IA, necesitamos saber qué tan legibles son
# las imágenes en nuestro dataset. Si le damos a la IA imágenes
# borrosas o de muy mala calidad, se confundirá y aprenderá mal.
#
# PROCESO:
#   1. Lee el manifiesto.csv completo usando la librería 'pandas'.
#   2. Detecta qué imágenes no tienen puntuación de calidad aún
#      (como las imágenes aumentadas generadas en el Paso C).
#   3. Por cada imagen sin puntuación:
#        a) Calcula su score matemático de calidad (0.0 a 1.0)
#           basado en su nitidez y contraste.
#        b) Compara con el umbral mínimo de calidad (0.65).
#        c) Si está por debajo, marca la columna 'necesita_revision' como True.
#   4. Genera reportes en la carpeta configurada:
#        - reporte_calidad.json (estadísticas agregadas del dataset)
#        - imagenes_a_revisar.csv (lista de imágenes que fallaron el control)
#   5. Muestra un resumen visual en la consola.
# ============================================================

# Importamos 'sys' para detener la ejecución en caso de error
import sys
# Importamos 'json' para poder escribir el reporte final en formato JSON estructurado
import json
# Importamos 'yaml' para leer los parámetros en configuracion.yaml
import yaml
# Importamos 'cv2' (OpenCV) para abrir imágenes y calcular su nitidez/contraste
import cv2
# Importamos 'pandas' como 'pd' para manejar el archivo csv como una tabla dinámica (DataFrame)
import pandas as pd
# Importamos 'Path' para interactuar con rutas en disco de forma multiplataforma
from pathlib import Path
# Importamos 'datetime' para registrar el momento del reporte
from datetime import datetime


def cargar_configuracion():
    """
    ¿QUÉ HACE?
      Lee y carga configuracion.yaml.
    """
    ruta = Path("configuracion.yaml")
    if not ruta.exists():
        print("[ERROR] No encontre 'configuracion.yaml'")
        sys.exit(1)
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def calcular_puntuacion(ruta_imagen):
    """
    ¿QUÉ HACE?
      Calcula una puntuación de legibilidad (calidad) de una imagen en escala [0.0, 1.0].
    ¿CÓMO SE HACE?
      1. Carga la imagen de la ruta en formato BGR.
      2. La convierte a escala de grises.
      3. Nitidez (60%): Evalúa la varianza del operador Laplaciano (mide bordes de texto nítidos).
      4. Contraste (40%): Mide la desviación estándar de la escala de grises (blanco vs negro).
      5. Pondera y redondea a 4 decimales.
    """
    # 1. Cargamos la imagen desde la ruta de archivo
    img = cv2.imread(str(ruta_imagen))
    if img is None:
        return 0.0

    # 2. Convertimos el orden de canales: BGR -> Escala de grises (GRAY)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Calculamos la nitidez usando la varianza matemática del operador Laplaciano
    nitidez   = cv2.Laplacian(gris, cv2.CV_64F).var()
    # 4. Calculamos el contraste usando la desviación estándar de la intensidad de los píxeles
    contraste = float(gris.std())

    # 5. Normalizamos y ponderamos. 
    # Umbral de nitidez óptima: 600.0. Umbral de contraste óptimo: 80.0
    p_nitidez   = min(nitidez   / 600.0, 1.0)
    p_contraste = min(contraste / 80.0,  1.0)

    # Sumamos aplicando los pesos: 60% nitidez y 40% contraste
    return round(0.60 * p_nitidez + 0.40 * p_contraste, 4)


def analizar_y_actualizar(config):
    """
    ¿QUÉ HACE?
      Carga el manifiesto.csv, encuentra filas sin calidad, calcula sus scores y sobreescribe el CSV.
    ¿CÓMO SE HACE?
      1. Abre manifiesto.csv usando pandas (pd.read_csv).
      2. Filtra las filas donde 'puntuacion_calidad' es NaN o vacía.
      3. Ejecuta un bucle por cada índice filtrado y calcula su score.
      4. Actualiza las columnas 'puntuacion_calidad' y 'necesita_revision'.
      5. Guarda de nuevo el archivo CSV sobreescribiéndolo (to_csv).
    """
    ruta_manifiesto = Path("manifiesto.csv")
    umbral          = config["calidad"]["puntuacion_minima"]

    # 1. Si no existe el manifiesto, detenemos la ejecución
    if not ruta_manifiesto.exists():
        print("[ERROR] manifiesto.csv no existe. Ejecuta los pasos A-C primero.")
        return None

    # 2. Cargamos el manifiesto.csv completo como un DataFrame de Pandas (tabla)
    df = pd.read_csv(ruta_manifiesto, encoding="utf-8")

    if df.empty:
        print("[AVISO] El manifiesto esta vacio. Ejecuta los pasos B y C primero.")
        return None

    print(f"  Total filas en manifiesto: {len(df)}")

    # CORRECCIÓN: Si la columna no existe aún, la creamos vacía para evitar KeyError
    if "puntuacion_calidad" not in df.columns:
        df["puntuacion_calidad"] = ""
    if "necesita_revision" not in df.columns:
        df["necesita_revision"] = False

    # 3. Buscamos filas vacías en la columna de calidad
    # isna() detecta campos nulos (NaN) y el operador '|' (OR) incluye campos que sean cadenas vacías ("")
    sin_puntuacion = df[
        df["puntuacion_calidad"].isna() | (df["puntuacion_calidad"] == "")
    ]

    # 4. Si hay imágenes pendientes por evaluar:
    if not sin_puntuacion.empty:
        print(f"\n  Calculando calidad de {len(sin_puntuacion)} imagenes...")
        # Iteramos por el índice (número de fila) de cada elemento pendiente
        for idx in sin_puntuacion.index:
            ruta = df.at[idx, "ruta_imagen"]
            # Comprobamos que la ruta no sea nula y que el archivo exista en disco
            if pd.notna(ruta) and Path(ruta).exists():
                # Calculamos el score de la imagen
                puntuacion = calcular_puntuacion(ruta)
                # Escribimos los resultados directamente en las celdas de la tabla
                df.at[idx, "puntuacion_calidad"]  = puntuacion
                # Si el score es menor al umbral (0.65), 'necesita_revision' será True, si no, False
                df.at[idx, "necesita_revision"]   = puntuacion < umbral

        # 5. Guardamos la tabla actualizada sobreescribiendo el manifiesto.csv
        # index=False evita escribir una columna adicional con los números de fila
        df.to_csv(ruta_manifiesto, index=False, encoding="utf-8")
        print("  [OK] Manifiesto actualizado con los nuevos scores de calidad.")

    return df


def generar_reportes(df, config):
    """
    ¿QUÉ HACE?
      Genera reportes estadísticos agregados a partir de la tabla del manifiesto.
    ¿CÓMO SE HACE?
      1. Obtiene las rutas y umbrales desde configuracion.yaml.
      2. Mapea la columna de calidad a formato numérico puro.
      3. Bucle para calcular estadísticas agrupadas por clase (número de imágenes, promedio, aprobadas, reprobadas).
      4. Guarda las estadísticas en 'reporte_calidad.json'.
      5. Filtra las imágenes reprobadas (necesita_revision == True) y las escribe en 'imagenes_a_revisar.csv'.
    """
    # 1. Definimos y creamos la carpeta de reportes (05_reportes)
    carpeta = Path(config["carpetas"]["reportes"])
    carpeta.mkdir(parents=True, exist_ok=True)

    umbral_minimo = config["calidad"]["puntuacion_minima"]
    umbral_buena  = config["calidad"]["puntuacion_buena"]

    # 2. Forzamos que la columna 'puntuacion_calidad' sea numérica, convirtiendo cualquier error a nulo (NaN)
    df["puntuacion_calidad"] = pd.to_numeric(df["puntuacion_calidad"], errors="coerce")

    # 3. Calculamos estadísticas agregadas por clase de documento
    stats_clases = {}
    # dropna().unique() obtiene la lista de clases únicas (ej: ['actas_nacimiento', 'curp']) sin valores nulos
    for clase in df["clase"].dropna().unique():
        # Filtramos la tabla obteniendo solo las filas de esta clase
        sub    = df[df["clase"] == clase]
        scores = sub["puntuacion_calidad"].dropna()
        
        # Guardamos estadísticas resumidas
        stats_clases[clase] = {
            "total":              int(len(sub)),
            "originales":         int((sub["es_aumentada"] == False).sum()),
            "aumentadas":         int((sub["es_aumentada"] == True).sum()),
            "calidad_promedio":   round(float(scores.mean()), 4) if len(scores) else None,
            "excelentes (>=0.80)": int((scores >= umbral_buena).sum()),
            "buenas (>=0.65)":    int(((scores >= umbral_minimo) & (scores < umbral_buena)).sum()),
            "necesitan_revision": int((scores < umbral_minimo).sum()),
        }

    # Calculamos estadísticas a nivel de todo el dataset completo
    scores_totales = df["puntuacion_calidad"].dropna()
    reporte = {
        "fecha":                  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_imagenes":         int(len(df)),
        "calidad_promedio_total": round(float(scores_totales.mean()), 4) if len(scores_totales) else None,
        "necesitan_revision":     int((scores_totales < umbral_minimo).sum()),
        "por_clase":              stats_clases,
    }

    # 4. Guardamos el reporte general en formato JSON legible e identado en disco
    ruta_json = carpeta / "reporte_calidad.json"
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"\n  [OK] Reporte guardado: {ruta_json}")

    # 5. Guardamos la lista de imágenes defectuosas en un CSV separado para fácil revisión manual
    a_revisar = df[df["necesita_revision"] == True]
    if not a_revisar.empty:
        ruta_csv = carpeta / "imagenes_a_revisar.csv"
        # Filtramos solo las columnas clave y escribimos el CSV
        a_revisar[["nombre_archivo_original", "id_pagina", "clase", "es_aumentada", "puntuacion_calidad", "ruta_imagen"]].to_csv(
            ruta_csv, index=False, encoding="utf-8"
        )
        print(f"  [OK] Lista de imagenes a revisar: {ruta_csv}  ({len(a_revisar)} filas)")

    return reporte


def mostrar_resumen(reporte):
    """
    ¿QUÉ HACE?
      Imprime una bonita tabla de resumen de calidad en la pantalla de la consola.
    """
    print(f"\n{'='*55}")
    print(f"  RESUMEN DE CALIDAD")
    print(f"{'='*55}")
    print(f"  Total imagenes        : {reporte['total_imagenes']}")
    print(f"  Calidad promedio      : {reporte.get('calidad_promedio_total', 'N/A')}")
    print(f"  Necesitan revision    : {reporte['necesitan_revision']}")
    print(f"\n  Por clase:")
    print(f"  {'Clase':<28} {'Total':>6} {'Promedio':>9} {'Revision':>9}")
    print(f"  {'-'*55}")
    for clase, s in reporte["por_clase"].items():
        prom = s["calidad_promedio"] if s["calidad_promedio"] else "N/A"
        # Ajustamos el espaciado para alinear las columnas
        print(f"  {clase:<28} {s['total']:>6} {str(prom):>9} {s['necesitan_revision']:>9}")
    print(f"{'='*55}")


# ---------------------------------------------------------------
# PUNTO DE ENTRADA PRINCIPAL
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  PASO D — Control de calidad del dataset")
    print("="*55 + "\n")

    # Cargamos archivos de configuración
    config = cargar_configuracion()

    # Ejecutamos el análisis de calidad
    df = analizar_y_actualizar(config)
    if df is None:
        sys.exit(1)

    # Generamos los reportes estructurados
    reporte = generar_reportes(df, config)
    # Mostramos el resumen en consola
    mostrar_resumen(reporte)

    n = reporte["necesitan_revision"]
    if n > 0:
        print(f"\n  [ATENCION] Se encontraron {n} imagenes con baja calidad.")
        print(f"             Revisa el archivo en: 05_reportes/imagenes_a_revisar.csv")

    print("\n[LISTO] Paso D completado.")
    print("  Tu dataset esta listo en manifiesto.csv y las carpetas correspondientes.\n")

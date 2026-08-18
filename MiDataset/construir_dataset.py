# -*- coding: utf-8 -*-
# ============================================================
# construir_dataset.py — Script principal del pipeline
# ============================================================
#
# ¿CÓMO FUNCIONA ESTE ARCHIVO?
# ─────────────────────────────────────────────────────────────
# Es el orquestador principal del proyecto. Ejecuta de forma secuencial
# los 4 pasos para construir, aumentar y evaluar la calidad de tu dataset:
#
#   Paso A → Crear carpetas vacías y manifiesto inicial.
#   Paso B → Convertir PDFs originales a imágenes PNG de 300 DPI.
#   Paso C → Generar 5 variantes aumentadas por cada imagen original.
#   Paso D → Calcular calidad (nitidez y contraste) de todas las imágenes.
#
# CÓMO SE USA:
# ─────────────────────────────────────────────────────────────
#   1. Coloca tus PDFs originales en '01_datos_originales/actas_nacimiento/'
#      y '01_datos_originales/curp/'
#   2. Ejecuta: python construir_dataset.py
#
# RESULTADO FINAL:
#   * Carpeta 02_imagenes_convertidas/ -> PNGs a 300 DPI sin corregir.
#   * Carpeta 03_imagenes_aumentadas/  -> Copias con alteraciones (ruido, rotación).
#   * Carpeta 05_reportes/             -> Estadísticas generales y lista de revisión.
#   * Archivo manifiesto.csv           -> Catálogo con el registro completo.
# ============================================================

# Importamos 'sys' para poder manipular el PATH de Python e importar los scripts de la carpeta src/
import sys
# Importamos 'time' para cronometrar cuánto tarda en ejecutarse cada paso
import time
# Importamos 'yaml' para leer configuracion.yaml
import yaml
# Importamos 'pandas' para poder validar la estructura del manifiesto en disco
import pandas as pd
# Importamos 'Path' para manejo seguro de rutas
from pathlib import Path
# Importamos 'datetime' para registrar marcas temporales
from datetime import datetime

# Configurar la salida estándar para forzar codificación UTF-8 en consolas Windows (evita UnicodeEncodeError al imprimir '█')
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Añadimos la subcarpeta 'src/' al inicio de la lista de rutas de Python (sys.path)
# Esto le dice a Python que busque los módulos allí dentro al usar 'import'
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Importamos los 4 scripts individuales que se encuentran dentro de src/
import paso_a_preparar
import paso_b_rasterizar
import paso_c_aumentar
import paso_d_calidad


def banner(titulo):
    """
    ¿QUÉ HACE?
      Imprime un banner gráfico de bloques gruesos en la consola para separar visualmente los pasos.
    """
    print(f"\n{'█'*55}")
    print(f"█  {titulo}")
    print(f"{'█'*55}")


def tiempo(inicio):
    """
    ¿QUÉ HACE?
      Calcula los segundos transcurridos desde un tiempo de inicio y lo formatea a texto.
    """
    s = time.time() - inicio
    # Si tarda menos de un minuto, muestra segundos con 1 decimal. Si no, muestra minutos y segundos enteros.
    return f"{s:.1f}s" if s < 60 else f"{int(s//60)}m {int(s%60)}s"


def main():
    """
    ¿QUÉ HACE?
      Ejecuta los 4 pasos del pipeline de forma controlada con cronometraje y control de excepciones.
    """
    t0 = time.time() # Guardamos el tiempo de inicio global del pipeline

    # Imprimimos la carátula inicial del proceso
    print("\n" + "█"*55)
    print("█")
    print("█   CONSTRUCCION DEL DATASET")
    print("█   Actas de Nacimiento + CURP + Otros")
    print(f"█   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("█")
    print("█"*55)

    # 1. Cargamos el archivo de configuración centralizado
    with open("configuracion.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    clases   = config["clases"]
    carpetas = config["carpetas"]
    dpi      = config["conversion"]["dpi"]

    # ══════════════════════════════════════════════════════════
    # PASO A — Preparar estructura y carpetas
    # ══════════════════════════════════════════════════════════
    banner("PASO A — Preparar carpetas y manifiesto")
    t = time.time() # Cronómetro para el Paso A
    try:
        paso_a_preparar.crear_carpetas(config)
        paso_a_preparar.crear_manifiesto(config)
        paso_a_preparar.mostrar_resumen(config)
        print(f"\n  Tiempo transcurrido en Paso A: {tiempo(t)}")
    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN PASO A]: {e}")
        # Detiene la ejecución completa ya que sin carpetas no podemos continuar
        sys.exit(1)

    # ══════════════════════════════════════════════════════════
    # PASO B — Convertir PDFs a PNG (300 DPI)
    # ══════════════════════════════════════════════════════════
    banner("PASO B — Convertir PDFs a PNG (300 DPI)")
    t = time.time() # Cronómetro para el Paso B
    try:
        total_docs = total_imgs = 0
        
        # Procesamos cada clase documental configurada
        for cl in clases:
            nombre = cl["nombre"]
            codigo = cl["codigo"]
            
            # Definimos rutas origen y destino en base a la clase
            origen  = Path(carpetas["originales"])  / nombre
            destino = Path(carpetas["convertidas"]) / nombre

            # Buscamos PDFs en la carpeta de origen (.pdf y .PDF)
            # Usamos un conjunto (set) para evitar duplicados en sistemas case-insensitive como Windows
            pdfs_encontrados = set(origen.glob("*.pdf")) | set(origen.glob("*.PDF"))
            pdfs = sorted(list(pdfs_encontrados))
            if not pdfs:
                print(f"\n  [AVISO] Sin PDFs en {origen}/")
                continue

            print(f"\n  Clase {nombre}: {len(pdfs)} PDF(s) detectado(s)")
            
            # Contamos cuántos documentos ya existen convertidos en disco para continuar la numeración consecutiva
            existentes = {img.stem.rsplit("_pagina_", 1)[0]
                          for img in destino.glob("*.png")}
            siguiente  = len(existentes) + 1
            registros  = []

            # Convertimos cada PDF
            for pdf in pdfs:
                # Generamos ID único (ej: ACT_0001)
                id_doc = f"{codigo}_{siguiente:04d}"
                regs   = paso_b_rasterizar.convertir_pdf(pdf, destino, id_doc, dpi)
                registros.extend(regs)
                siguiente  += 1
                total_docs += 1
                total_imgs += len(regs)

            # Si convertimos páginas, las registramos al final del manifiesto
            if registros:
                paso_b_rasterizar.registrar_en_manifiesto(registros, nombre)

        print(f"\n  Documentos procesados: {total_docs}  |  Imagenes PNG creadas: {total_imgs}")
        print(f"  Tiempo transcurrido en Paso B: {tiempo(t)}")
    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN PASO B]: {e}")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════
    # PASO B.5 — Registrar imagenes JPG/PNG de clase 'otros'
    # (Paso B solo convierte PDFs; 'otros' tiene imagenes JPG)
    # ══════════════════════════════════════════════════════════
    banner("PASO B.5 — Registrar imagenes de clase 'otros'")
    t = time.time()
    try:
        import csv, shutil
        from PIL import Image as PILImage

        otros_orig  = Path(carpetas["originales"])  / "otros"
        otros_dest  = Path(carpetas["convertidas"]) / "otros"
        otros_dest.mkdir(parents=True, exist_ok=True)

        extensiones = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
        imagenes_otros = sorted([
            f for f in otros_orig.iterdir()
            if f.suffix.lower() in extensiones
        ]) if otros_orig.exists() else []

        if not imagenes_otros:
            print(f"  [INFO] Sin imagenes en {otros_orig}/ — clase 'otros' omitida.")
        else:
            print(f"  {len(imagenes_otros)} imagen(es) encontradas en otros/")
            col = [
                "nombre_archivo_original","id_documento","id_pagina","clase",
                "ruta_imagen","ruta_pdf_original","ancho_pixeles","alto_pixeles",
                "puntuacion_calidad","necesita_revision","es_aumentada",
                "fecha_procesado","notas",
            ]
            registros_otros = []
            for idx, img_path in enumerate(imagenes_otros, start=1):
                id_doc    = f"OTR_{idx:04d}"
                id_pagina = f"{id_doc}_pagina_001"
                dest_png  = otros_dest / f"{id_pagina}.png"
                try:
                    img = PILImage.open(img_path).convert("RGB")
                    w, h = img.size
                    img.save(dest_png, "PNG")
                except Exception:
                    shutil.copy2(img_path, dest_png)
                    w, h = 800, 1100
                print(f"    {id_pagina}.png  ({w}x{h})")
                registros_otros.append({
                    "nombre_archivo_original": img_path.name,
                    "id_documento":       id_doc,
                    "id_pagina":          id_pagina,
                    "clase":              "otros",
                    "ruta_imagen":        str(dest_png),
                    "ruta_pdf_original":  str(img_path),
                    "ancho_pixeles":      w,
                    "alto_pixeles":       h,
                    "puntuacion_calidad": 0.85,
                    "necesita_revision":  False,
                    "es_aumentada":       False,
                    "fecha_procesado":    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "notas":              "imagen no-PDF registrada manualmente",
                })
            with open("manifiesto.csv", "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=col)
                for reg in registros_otros:
                    writer.writerow(reg)
            print(f"\n  {len(registros_otros)} registros agregados al manifiesto.")
        print(f"  Tiempo transcurrido en Paso B.5: {tiempo(t)}")
    except Exception as e:
        print(f"\n[AVISO PASO B.5]: {e} — continuando sin 'otros'...")

    # ══════════════════════════════════════════════════════════
    # PASO C — Aumentar (lee de 02_imagenes_convertidas)
    # ══════════════════════════════════════════════════════════
    banner("PASO C — Aumentar dataset")

    t = time.time() # Cronómetro para el Paso C
    try:
        num_copias = config["aumento"]["copias_por_imagen"]
        # Inicializa Albumentaciones si está instalado
        transf = paso_c_aumentar.crear_transformaciones_albumentations() \
                 if paso_c_aumentar.USA_ALBUMENTATIONS else None
        total_c = 0

        # Procesamos cada clase para aumentación
        for cl in clases:
            nombre  = cl["nombre"]
            entrada = Path(carpetas["convertidas"]) / nombre
            salida  = Path(carpetas["aumentadas"])  / nombre
            salida.mkdir(parents=True, exist_ok=True)

            # Buscamos solo imágenes originales reales (sin '_aug') en convertidas
            originales = [i for i in sorted(entrada.glob("*.png"))
                          if "_aug" not in i.stem]
            print(f"\n  Clase {nombre}: {len(originales)} original(es) × {num_copias} copias")

            registros = []
            # Generamos las N variantes
            for img in originales:
                rutas = paso_c_aumentar.generar_variantes(
                    img, salida, num_copias, transf)
                
                # Preparamos el registro en manifiesto para cada variante aumentada
                for ruta in rutas:
                    p      = Path(ruta)
                    partes = p.stem.split("_pagina_")
                    id_doc = partes[0] if len(partes) > 1 else p.stem.split("_aug")[0]
                    
                    registros.append({
                        "nombre_archivo_original": img.stem.split("_pagina_")[0] if "_pagina_" in img.stem else img.stem,
                        "id_documento": id_doc, "id_pagina": p.stem,
                        "clase": nombre, "ruta_imagen": ruta,
                        "ruta_pdf_original": "", "ancho_pixeles": "",
                        "alto_pixeles": "", "puntuacion_calidad": "",
                        "necesita_revision": False, "es_aumentada": True, # Aumentada = True
                        "fecha_procesado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "notas": f"Aumentada de {img.name}",
                    })
                    total_c += 1
            
            # Registramos las variantes en el manifiesto
            if registros:
                paso_c_aumentar.registrar_aumentadas(registros)

        print(f"\n  Imagenes generadas por aumentacion: {total_c}")
        print(f"  Tiempo transcurrido en Paso C: {tiempo(t)}")
    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN PASO C]: {e}")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════
    # PASO D — Control de Calidad
    # ══════════════════════════════════════════════════════════
    banner("PASO D — Control de calidad")
    t = time.time() # Cronómetro para el Paso D
    try:
        # Analiza la calidad de las imágenes que tengan este campo vacío
        df = paso_d_calidad.analizar_y_actualizar(config)
        if df is not None:
            # Genera los archivos JSON y CSV de reportes
            reporte = paso_d_calidad.generar_reportes(df, config)
            # Imprime la tabla en la consola
            paso_d_calidad.mostrar_resumen(reporte)
        print(f"\n  Tiempo transcurrido en Paso D: {tiempo(t)}")
    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN PASO D]: {e}")
        sys.exit(1)

    # Imprimimos bloque de finalización con éxito
    print("\n" + "█"*55)
    print("█")
    print("█   DATASET COMPLETADO CON EXITO")
    print(f"█   Tiempo total de procesamiento: {tiempo(t0)}")
    print("█")
    print("█   Carpetas principales:")
    print(f"█     {carpetas['originales']}/       <- PDFs originales")
    print(f"█     {carpetas['convertidas']}/   <- PNG 300 DPI (sin corregir)")
    print(f"█     {carpetas['aumentadas']}/    <- Copias artificiales (x5)")
    print(f"█     {carpetas['reportes']}/              <- Reporte de calidad")
    print("█     manifiesto.csv            <- Registro completo de control")
    print("█")
    print("█   Tu modelo puede leer manifiesto.csv o importar cargar_datos:")
    print("█     from cargar_dataset import cargar_datos")
    print("█")
    print("█"*55 + "\n")


# ---------------------------------------------------------------
# PUNTO DE ENTRADA AL PIPELINE
# ---------------------------------------------------------------
if __name__ == "__main__":
    main()

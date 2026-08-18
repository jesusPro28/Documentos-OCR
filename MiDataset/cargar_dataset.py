# -*- coding: utf-8 -*-
# ============================================================
# cargar_dataset.py — Conectar el dataset con el modelo
# ============================================================
#
# ¿CÓMO FUNCIONA ESTE ARCHIVO?
# ─────────────────────────────────────────────────────────────
# Este script es el puente de comunicación entre las imágenes de
# tu disco y la red neuronal de Inteligencia Artificial.
#
# Proceso:
#   1. Lee el manifiesto.csv (que contiene el mapa de archivos).
#   2. Si 'detectar_mal_escaneados' es False (Modo Normal):
#        - Filtra y descarta las imágenes con baja calidad.
#        - Mapea: actas_nacimiento -> 0, curp -> 1.
#   3. Si 'detectar_mal_escaneados' es True (Modo 3 Clases):
#        - Incluye todas las imágenes (incluso las inclinadas/ruidosas).
#        - Mapea: actas_nacimiento -> 0, curp -> 1, mal_escaneado -> 2.
#   4. Separa en conjunto de Entrenamiento (80%) y Prueba (20%).
#   5. Devuelve cuatro listas optimizadas y listas para la IA.
# ============================================================

# Importamos 'sys' para cerrar la ejecución en caso de error crítico
import sys
# Importamos 'pandas' para leer manifiesto.csv de forma cómoda como una tabla (DataFrame)
import pandas as pd
# Importamos 'Path' para manejar las rutas del disco
from pathlib import Path
# Importamos 'train_test_split' de scikit-learn que automatiza la partición de datos aleatoria
from sklearn.model_selection import train_test_split

# Configuramos la salida estándar para soportar codificación UTF-8 en consolas Windows (evita errores con '→')
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------
# MAPA DE CLASES OFICIALES (TEXTO -> NÚMERO)
# ---------------------------------------------------------------
CLASES = {
    "actas_nacimiento": 0,
    "curp":             1,
}


def cargar_datos(
    ruta_manifiesto="manifiesto.csv",
    incluir_aumentadas=True,
    solo_originales_en_prueba=True,
    tamaño_prueba=0.20,
    semilla=42,
    puntuacion_minima=0.65,
    detectar_mal_escaneados=False,
):
    """
    ¿QUÉ HACE?
      Carga las rutas de imágenes y etiquetas del manifiesto y las divide en train/test.
    ¿CÓMO SE HACE?
      1. Lee manifiesto.csv con pandas.
      2. Aplica filtros según la calidad de imagen física.
      3. Convierte las etiquetas textuales a valores enteros (0, 1 o 2).
      4. Divide los datos en grupos usando train_test_split.
      5. Devuelve X_train, X_test, y_train, y_test.
    """

    # ── 1. LEER EL MANIFIESTO ──────────────────────────────────
    ruta = Path(ruta_manifiesto)
    if not ruta.exists():
        print(f"[ERROR] No encontre el archivo: {ruta_manifiesto}")
        print("        Ejecuta primero: python construir_dataset.py")
        sys.exit(1)

    df = pd.read_csv(ruta, encoding="utf-8")

    if df.empty:
        print("[ERROR] El manifiesto esta vacio.")
        print("        Ejecuta el pipeline completo primero.")
        sys.exit(1)

    print(f"  Total filas en manifiesto: {len(df)}")

    # ── 2. FILTRAR IMÁGENES VÁLIDAS ────────────────────────────
    # Nos aseguramos de que el score de calidad sea numérico de punto flotante
    df["puntuacion_calidad"] = pd.to_numeric(df["puntuacion_calidad"], errors="coerce")
    # Forzamos que la columna booleana sea texto en minúsculas para compararla
    df["necesita_revision"] = df["necesita_revision"].astype(str).str.lower()

    # Comprobamos que el archivo físico exista en el disco duro (devuelve lista de True/False)
    mascara_existentes = df["ruta_imagen"].apply(
        lambda r: Path(r).exists() if pd.notna(r) else False
    )

    # Aplicamos la bifurcación lógica según el modo de entrenamiento seleccionado
    if detectar_mal_escaneados:
        # MODO B: Incluimos todas las existentes. Las de mala calidad no se descartan, se etiquetan como Clase 2
        df_validas = df[mascara_existentes].copy()
        descartadas = len(df) - len(df_validas)
        print(f"  Imagenes validas    : {len(df_validas)} (incluyendo baja calidad para deteccion)")
        print(f"  Descartadas (no exist.): {descartadas}")
    else:
        # MODO A (Estándar): Descartamos las imágenes que tengan baja calidad o que requieran revisión
        mascara_validas = (
            mascara_existentes
            & (df["puntuacion_calidad"] >= puntuacion_minima)
            & (df["necesita_revision"] != "true")
        )
        df_validas = df[mascara_validas].copy()
        descartadas = len(df) - len(df_validas)
        print(f"  Imagenes validas    : {len(df_validas)}")
        print(f"  Descartadas         : {descartadas}  (baja calidad o archivo no encontrado)")

    if df_validas.empty:
        print("\n[ERROR] No hay imagenes validas para cargar.")
        print("        Verifica que el pipeline se ejecuto correctamente.")
        sys.exit(1)

    # ── 3. ASIGNAR ETIQUETAS NUMÉRICAS (texto -> int) ─────────
    if detectar_mal_escaneados:
        # Si la fila necesita revisión (es borrosa/inclinada), le asignamos la etiqueta 2
        # De lo contrario, buscamos su etiqueta en el diccionario CLASES (0 o 1)
        df_validas["etiqueta"] = df_validas.apply(
            lambda r: 2 if r["necesita_revision"] == "true" else CLASES.get(r["clase"]),
            axis=1
        )
    else:
        # Modo normal: mapeamos directamente la columna clase usando el diccionario CLASES
        df_validas["etiqueta"] = df_validas["clase"].map(CLASES)

    # Ignoramos filas con clases desconocidas por seguridad
    desconocidas = df_validas["etiqueta"].isna().sum()
    if desconocidas > 0:
        clases_desconocidas = df_validas[df_validas["etiqueta"].isna()]["clase"].unique()
        print(f"[AVISO] Clases desconocidas ignoradas: {clases_desconocidas}")
        df_validas = df_validas.dropna(subset=["etiqueta"])

    # ── 4. SEPARAR REALES DE ARTIFICIALES ────────────────────
    df_validas["es_aumentada"] = df_validas["es_aumentada"].astype(str).str.lower()

    # Filtramos la tabla en originales (es_aumentada != True) y aumentadas (es_aumentada == True)
    df_originales = df_validas[df_validas["es_aumentada"] != "true"].copy()
    df_aumentadas = df_validas[df_validas["es_aumentada"] == "true"].copy()

    print(f"\n  Originales          : {len(df_originales)}")
    print(f"  Aumentadas          : {len(df_aumentadas)}")

    # ── 5. SEPARACIÓN EN ENTRENAMIENTO (TRAIN) Y PRUEBA (TEST) ─
    # Si solo_originales_en_prueba = True (Altamente Recomendado):
    #   Evaluamos el modelo final únicamente con imágenes reales (no aumentadas).
    #   Por ende, el 100% de las aumentadas van directo a Entrenamiento.
    #   El 20% de las originales van a Prueba, y el 80% restante de las originales a Entrenamiento.
    num_clases     = df_validas["etiqueta"].nunique()
    min_por_clase  = df_originales.groupby("etiqueta").size().min() if not df_originales.empty else 0

    if solo_originales_en_prueba and not df_originales.empty:
        n_test_deseado = max(1, int(len(df_originales) * tamaño_prueba))

        # Estrategia de división según la cantidad de datos disponibles
        if min_por_clase >= 3:
            # Caso ideal: suficientes datos para dividir de forma estratificada (mismo ratio de clases)
            orig_train, orig_test = train_test_split(
                df_originales,
                test_size=tamaño_prueba,
                random_state=semilla,
                stratify=df_originales["etiqueta"],
                shuffle=True,
            )
        elif len(df_originales) >= num_clases * 2:
            # Caso intermedio: pocos datos, dividimos de forma aleatoria simple
            print("  [AVISO] Pocos datos. Split sin estratificar.")
            orig_train, orig_test = train_test_split(
                df_originales,
                test_size=tamaño_prueba,
                random_state=semilla,
                shuffle=True,
            )
        else:
            # Caso extremo (ej: solo 2 originales por clase): tomamos manualmente 1 por clase para prueba
            print("  [AVISO] Dataset muy pequeño. Tomando 1 por clase para prueba.")
            test_indices = []
            for etiqueta in df_originales["etiqueta"].unique():
                sub = df_originales[df_originales["etiqueta"] == etiqueta]
                sampled = sub.sample(1, random_state=semilla)
                test_indices.extend(sampled.index.tolist())
            orig_test = df_originales.loc[test_indices].copy()
            orig_train = df_originales.drop(test_indices).copy()
            orig_test = orig_test.reset_index(drop=True)

        # Concatenamos las imágenes aumentadas al conjunto de entrenamiento
        if incluir_aumentadas and not df_aumentadas.empty:
            df_train = pd.concat([orig_train, df_aumentadas])
        else:
            df_train = orig_train

        df_test = orig_test

    else:
        # Si es False, mezclamos todas las imágenes y dividimos de forma simple
        df_todos = df_validas if incluir_aumentadas else df_originales

        if min_por_clase >= 3:
            df_train, df_test = train_test_split(
                df_todos,
                test_size=tamaño_prueba,
                random_state=semilla,
                stratify=df_todos["etiqueta"],
                shuffle=True,
            )
        else:
            print("  [AVISO] Pocos datos. Split sin estratificar.")
            df_train, df_test = train_test_split(
                df_todos,
                test_size=tamaño_prueba,
                random_state=semilla,
                shuffle=True,
            )

    # ── 6. EXTRAER LISTAS FINALES DE SALIDA ────────────────────
    # Extraemos las rutas de imagen y las etiquetas y las convertimos en listas de Python
    X_train = df_train["ruta_imagen"].tolist()
    y_train = df_train["etiqueta"].astype(int).tolist()
    X_test  = df_test["ruta_imagen"].tolist()
    y_test  = df_test["etiqueta"].astype(int).tolist()

    return X_train, X_test, y_train, y_test


def mostrar_distribucion(X_train, X_test, y_train, y_test):
    """
    ¿QUÉ HACE?
      Imprime en pantalla la tabla con la cantidad de imágenes asignadas a cada clase.
    """
    nombres_clases = {v: k for k, v in CLASES.items()}  # Invertimos el mapa para imprimir texto en vez de números
    nombres_clases[2] = "mal_escaneado"

    print(f"\n{'='*70}")
    print(f"  DISTRIBUCIÓN DEL DATASET")
    print(f"{'='*70}")
    print(f"  {'':20} {'Total':>7}  {'Clase 0 (ACT)':>14}  {'Clase 1 (CUR)':>14}  {'Clase 2 (MAL)':>14}")
    print(f"  {'-'*70}")

    # Contamos las frecuencias en y_train e y_test
    for nombre, X, y in [("Entrenamiento", X_train, y_train),
                          ("Prueba",        X_test,  y_test)]:
        total = len(y)
        c0    = y.count(0)
        c1    = y.count(1)
        c2    = y.count(2)
        print(f"  {nombre:<20} {total:>7}  {c0:>14}  {c1:>14}  {c2:>14}")

    print(f"{'='*70}")
    print(f"\n  Mapa de clases asignadas:")
    for num, nombre in sorted(nombres_clases.items()):
        print(f"    {num} → {nombre}")
    print()


# ---------------------------------------------------------------
# SI EJECUTAS ESTE SCRIPT DIRECTAMENTE, SE CORRE ESTA PRUEBA DE CARGA
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "="*70)
    print("  PRUEBA 1: CARGA DEL DATASET ESTÁNDAR (DESCARTANDO MALAS)")
    print("="*70 + "\n")

    # Prueba de carga estándar
    X_train, X_test, y_train, y_test = cargar_datos(
        ruta_manifiesto="manifiesto.csv",
        incluir_aumentadas=True,
        solo_originales_en_prueba=True,
        tamaño_prueba=0.20,
        semilla=42,
        puntuacion_minima=0.65,
        detectar_mal_escaneados=False,
    )
    mostrar_distribucion(X_train, X_test, y_train, y_test)

    print("\n" + "="*70)
    print("  PRUEBA 2: CARGA PARA DETECCIÓN DE MAL ESCANEADOS (3 CLASES)")
    print("="*70 + "\n")

    # Prueba de carga para detección de calidad
    X_train2, X_test2, y_train2, y_test2 = cargar_datos(
        ruta_manifiesto="manifiesto.csv",
        incluir_aumentadas=True,
        solo_originales_en_prueba=True,
        tamaño_prueba=0.20,
        semilla=42,
        puntuacion_minima=0.65,
        detectar_mal_escaneados=True,
    )
    mostrar_distribucion(X_train2, X_test2, y_train2, y_test2)

    # Imprimimos ejemplos de las rutas y etiquetas resultantes en la consola
    print("  Ejemplos de rutas en X_train (Prueba 2):")
    for r in X_train2[:3]:
        print(f"    {r}")
    print("  ...")
    print(f"\n  Ejemplos de etiquetas correspondientes en y_train: {y_train2[:10]}  ...")

    print("\n[LISTO] Ambas pruebas de dataset completadas correctamente.")
    print("  Usa el parametro detectar_mal_escaneados=True si deseas que la IA")
    print("  aprenda a identificar documentos mal escaneados o inclinados.\n")

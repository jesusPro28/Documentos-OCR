

# 1. IMPORTACIONES Y CONFIGURACIÓN DEL ENTORNO DE EJECUCIÓN
import os

# Restricción explícita de hilos de cómputo en librerías numéricas de C/C++ subyacentes.
# Esto previene la sobrecarga por contención de hilos CPU (thread contention)
# y garantiza un tiempo de respuesta determinista en servidores multitarea de producción.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import io
import re
import time
import json as json_lib
import shutil
import tempfile
import urllib.request
import fitz  # PyMuPDF: Conversión ultarrápida de documentos PDF a buffers de imagen
import cv2
import torch

# Restringe a PyTorch a emplear un único hilo de CPU en operaciones internas de tensor.
torch.set_num_threads(1)

import easyocr
import numpy as np
import pandas as pd
import unicodedata
from pathlib import Path
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from torchvision import models, transforms

# 2. CONFIGURACIÓN Y ESTABLECIMIENTO DE RUTAS DE ALMACENAMIENTO
API_DIR  = Path(__file__).resolve().parent
BASE_DIR = API_DIR.parent.parent

# URL base del servidor PHP local
PHP_API_BASE = "http://localhost/pagina_web"

# Algoritmo de resolución inteligente de rutas para la localización del archivo de pesos `.pth`.
# Previene fallos de ejecución si la carpeta de la API es movida dentro o fuera del paquete principal.
POSIBLES_RUTAS_MODELO = [
    API_DIR / 'modelo_barrera1.pth',                   # Dentro de la carpeta de la API (ubicación actual)
    BASE_DIR / 'modelo_barrera1.pth',                  # Si 'modelo' está dentro de MiDataset/
    BASE_DIR / 'MiDataset' / 'modelo_barrera1.pth',    # Si está en la raíz de 'como contruir mi data set/'
]

MODEL_PATH = None
for ruta in POSIBLES_RUTAS_MODELO:
    if ruta.exists():
        MODEL_PATH = ruta
        break

# Si el archivo no es encontrado en ninguna de las rutas de búsqueda, se establece la ruta por defecto.
if MODEL_PATH is None:
    MODEL_PATH = API_DIR / 'modelo_barrera1.pth'

# 3. INICIALIZACIÓN DE COMPONENTES DE INTELIGENCIA ARTIFICIAL
# Selección dinámica del acelerador de hardware: prioriza GPU mediante CUDA si está disponible,
# de lo contrario conmuta automáticamente a procesamiento por CPU.
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Inicialización de la arquitectura MobileNetV3-Small (Barrera 1).
# Se prescinde de los pesos preentrenados genéricos (weights=None) para cargar los pesos específicos del dominio.
model_b1 = models.mobilenet_v3_small(weights=None)

# ADVERTENCIA CRÍTICA DE ARQUITECTURA:
# La capa oculta del clasificador está configurada explícitamente con 256 neuronas.
# BAJO NINGUNA CIRCUNSTANCIA SE DEBE MODIFICAR ESTA ESTRUCTURA (Linear(576, 256)).
# Debe coincidir exactamente con la arquitectura utilizada durante la etapa de entrenamiento.
# Alterar este valor provocará un fallo catastrófico por desajuste de tensores
# (RuntimeError: shape mismatch) al ejecutar `load_state_dict`.
model_b1.classifier = torch.nn.Sequential(
    torch.nn.Linear(576, 256),
    torch.nn.Hardswish(),
    torch.nn.Dropout(p=0.2),
    torch.nn.Linear(256, 2)
)

if MODEL_PATH.exists():
    # `map_location=device`: Carga los tensores mapeándolos dinámicamente al hardware destino
    # (CPU o GPU), evitando errores de compatibilidad si el modelo fue guardado en un dispositivo distinto.
    model_b1.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model_b1 = model_b1.to(device)
    
    # `model_b1.eval()`: Desactiva el cálculo de Dropout y ajusta las capas de Normalización de Lotes (BatchNorm)
    # al modo de inferencia pura, garantizando respuestas deterministas.
    model_b1.eval()
else:
    # Registramos advertencia pero no detenemos la API para permitir pruebas locales
    print(f"ADVERTENCIA: No se encontró el archivo de pesos del modelo en {MODEL_PATH}")

# ADVERTENCIA DE TRANSFORMACIÓN DE IMAGEN:
# Pipeline de preprocesamiento de tensores de entrada para la red neuronal B1.
# Mantiene la resolución de 224x224 y la normalización estandarizada de ImageNet
# (mean y std), requeridas obligatoriamente por la arquitectura MobileNetV3.
transform_b1 = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# Inicialización en memoria del motor EasyOCR configurado para los idiomas Español ('es') e Inglés ('en').
# Se desactiva la GPU interna de EasyOCR (gpu=False) para evitar conflicto de asignación VRAM con PyTorch.
reader_ocr = easyocr.Reader(['es', 'en'], gpu=False)

# 4. LÓGICA DE NEGOCIO Y PIPELINE DE BARRERAS (B1, B2, B3)

# Clases inversas de clasificación documental
CLASSES_MAP = {0: 'actas_nacimiento', 1: 'curp'}

# ADVERTENCIA CRÍTICA: UMBRALES OPERATIVOS DEL SISTEMA
# Modificar estos valores altera la sensibilidad global de aceptación o rechazo.
# UMBRAL_B1 = 0.70: Exige un nivel de certeza mínimo del 70% a la CNN en la clasificación de tipo
# documental para evitar falsos positivos y propagación de errores hacia las barreras B2 y B3.
UMBRAL_B1 = 0.70        # Confianza mínima de clasificación

# BLUR_THRESHOLD = 80.0: Varianza mínima del filtro Laplaciano para evaluar nitidez física.
BLUR_THRESHOLD = 80.0    # Varianza Laplaciana mínima (Nitidez)

# NOISE_THRESHOLD = 10.0: Varianza matricial global mínima para evaluar contraste de la imagen.
NOISE_THRESHOLD = 10.0   # Varianza global mínima (Ruido/Contraste)

# SKEW_THRESHOLD = 15.0: Ángulo máximo de inclinación permitido (grados sexagesimales) mediante Hough.
SKEW_THRESHOLD = 15.0    # Ángulo máximo de inclinación tolerado (Hough)

# Regex ESTRICTO: valida una CURP ya normalizada (solo dígitos reales en posiciones numéricas)
PATTERN_CURP = re.compile(
    r'[A-Z]{4}[0-9]{6}[HM][A-Z]{2}[BCDFGHJKLMNPQRSTVWXYZ]{3}[A-Z0-9][0-9]'
)

# Regex FLEXIBLE: detecta CURPs con confusiones OCR típicas en las posiciones de dígitos.
# EasyOCR confunde frecuentemente: 0→O, 5→S, 1→I/L, 8→B en documentos con marcas de agua.
# Solo aplica tolerancia en los 6 dígitos de fecha (pos 5-10) y el dígito final (pos 18).
PATTERN_CURP_FLEXIBLE = re.compile(
    r'[A-Z]{4}[0-9OSILBosib]{6}[HM][A-Z]{2}[BCDFGHJKLMNPQRSTVWXYZ]{3}[A-Z0-9][0-9Oo]'
)

def normalizar_curp_ocr(curp_raw: str) -> str:
    """Convierte una CURP con confusiones OCR a su forma canónica.
    Reemplaza letras visualmente similares por dígitos SOLO en las posiciones
    donde el formato RENAPO exige números (fecha y dígito verificador)."""
    chars = list(curp_raw)
    ocr_a_digito = {'O': '0', 'o': '0', 'S': '5', 's': '5', 'I': '1', 'i': '1', 'L': '1', 'B': '8', 'b': '8'}
    # Posiciones de índice 0: índices 4-9 = fecha de nacimiento, índice 17 = dígito verificador
    for pos in [4, 5, 6, 7, 8, 9, 17]:
        if pos < len(chars) and chars[pos] in ocr_a_digito:
            chars[pos] = ocr_a_digito[chars[pos]]
    return ''.join(chars)

# Campos obligatorios para Actas de Nacimiento y variaciones comunes del OCR
MANDATORY_ACTA_FIELDS = {
    'ACTA': ['ACTA', 'ACTA.', 'ACT4'],
    'NACIMIENTO': ['NACIMIENTO', 'NACI MIENTO', 'NACIM1ENTO'],
    'NOMBRE': ['NOMBRE', 'N0MBRE', 'NOMBR'],
    'MUNICIPIO': ['MUNICIPIO', 'MUNICI PIO', 'MPIO']
}

def normalizar_texto_hispano(texto: str) -> str:
    
    texto = texto.upper().replace('Ñ', '||ENYE||')
    texto_nfd = unicodedata.normalize('NFD', texto)
    texto_limpio = ''.join([c for c in texto_nfd if unicodedata.category(c) != 'Mn'])
    return texto_limpio.replace('||ENYE||', 'Ñ')

def corregir_confusion_ocr(texto: str) -> list:
    
    variantes = [texto]
    v1 = texto.replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B')
    v2 = texto.replace('O', '0').replace('I', '1').replace('S', '5')
    variantes.append(v1)
    variantes.append(v2)
    return variantes

def ejecutar_barrera_1(img_pil: Image.Image) -> tuple:
    
    if not MODEL_PATH.exists():
        return True, "actas_nacimiento", 1.0, "Modo prueba local: Pesos de B1 ausentes."

    tensor = transform_b1(img_pil.convert('RGB')).unsqueeze(0).to(device)
    with torch.no_grad():
        outputs = model_b1(tensor)
        probs = torch.softmax(outputs, dim=1)[0]
    
    idx = int(probs.argmax())
    conf = float(probs.max())
    clase = CLASSES_MAP[idx]
    ok = conf >= UMBRAL_B1
    
    msg = f"Clase: {clase} (confianza={conf*100:.1f}%)" if ok else f"Confianza B1 insuficiente ({conf*100:.1f}%)"
    return ok, clase, conf, msg

def ejecutar_barrera_2(img_gray: np.ndarray) -> tuple:
    
    # 1. Evaluación de desenfoque (Blur) mediante varianza del Laplaciano
    blur_score = cv2.Laplacian(img_gray, cv2.CV_64F).var()
    if blur_score < BLUR_THRESHOLD:
        return False, f"Rechazado en B2: Imagen borrosa (nitidez={blur_score:.1f} < {BLUR_THRESHOLD})"

    # 2. Evaluación de contraste global mediante varianza de la matriz
    noise_score = np.var(img_gray)
    if noise_score < NOISE_THRESHOLD:
        return False, f"Rechazado en B2: Contraste insuficiente (var={noise_score:.1f})"

    # 3. Evaluación de rotación (Skew) mediante transformada de Hough
    bordes = cv2.Canny(img_gray, 50, 150, apertureSize=3)
    lineas = cv2.HoughLinesP(bordes, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
    if lineas is not None:
        angulos = []
        for linea in lineas:
            x1, y1, x2, y2 = linea[0]
            if x2 != x1:
                angulo = np.degrees(np.arctan2(y2-y1, x2-x1))
                angulos.append(angulo)
        if angulos:
            skew = abs(np.median(angulos))
            if skew > SKEW_THRESHOLD:
                return False, f"Rechazado en B2: Inclinación excesiva (rotación={skew:.1f}° > {SKEW_THRESHOLD}°)"

    return True, f"Calidad física aceptable (nitidez={blur_score:.1f})"

def ejecutar_barrera_3(img_gray: np.ndarray, clase_doc: str, img_color: np.ndarray = None) -> tuple:
    """
    Barrera 3: Extracción y validación de texto (OCR).
    Acepta opcionalmente img_color (RGB numpy) para preprocesamiento mejorado
    con documentos de fondos de colores (actas rojas, CURP con bandera, etc).
    """
    # Preprocesamiento adaptativo según disponibilidad de imagen a color
    if img_color is not None:
        # Convertir al espacio LAB: el canal L (luminosidad) separa el texto oscuro
        # del fondo de cualquier color (rojo, verde, rosa, etc.) de forma robusta.
        # Esto resuelve el problema con actas de fondo rojo/rosa y CURPs con bandera.
        lab = cv2.cvtColor(img_color, cv2.COLOR_RGB2LAB)
        canal_l = lab[:, :, 0]   # Solo la luminosidad, descarta los canales de color

        # Umbral adaptativo gaussiano: maneja fondos no uniformes (bordes ornamentales,
        # marcas de agua, agujas, sellos) mejor que el umbral global de Otsu.
        img_adaptativa = cv2.adaptiveThreshold(
            canal_l, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,   # Vecindad grande para ignorar ornamentos y bordes decorativos
            C=12            # Constante de ajuste fino
        )

        # También generar versión CLAHE+Otsu como respaldo
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_mejorado = clahe.apply(canal_l)
        suavizado = cv2.GaussianBlur(l_mejorado, (3, 3), 0)
        _, img_otsu = cv2.threshold(suavizado, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Combinar ambas versiones: retiene solo lo que ambas coinciden como texto
        img_binaria = cv2.bitwise_and(img_adaptativa, img_otsu)
    else:
        # Fallback clásico para imágenes ya en escala de grises
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gris_mejorada = clahe.apply(img_gray)
        suavizado = cv2.GaussianBlur(gris_mejorada, (3, 3), 0)
        _, img_binaria = cv2.threshold(suavizado, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Inferencia con EasyOCR con parámetros de contraste robustos
    resultados = reader_ocr.readtext(img_binaria, detail=1, paragraph=False, contrast_ths=0.1, adjust_contrast=0.5)
    if not resultados:
        return False, 0.0, "Rechazado en B3: No se pudo extraer texto del documento."

    # Filtrado por confianza de caracteres (umbral mínimo del 30%)
    textos_validos = [det[1] for det in resultados if det[2] >= 0.30]
    if not textos_validos:
        return False, 0.0, "Rechazado en B3: Confianza de lectura OCR insuficiente."

    confianza_promedio = sum(det[2] for det in resultados if det[2] >= 0.30) / len(textos_validos)
    texto_completo = normalizar_texto_hispano(" ".join(textos_validos))

    # Validación semántica según tipo documental
    if clase_doc == 'curp':
        curp_detectado = None
        texto_sin_espacios = normalizar_texto_hispano("".join(textos_validos))

        for fuente_texto in [texto_completo, texto_sin_espacios]:
            # Intento 1: regex estricto con correcciones globales de confusión OCR
            for variante in corregir_confusion_ocr(fuente_texto):
                match = PATTERN_CURP.search(variante)
                if match:
                    curp_detectado = match.group(0)
                    break
            if curp_detectado:
                break

            # Intento 2: regex flexible que tolera confusión OCR en posiciones de dígitos,
            # seguido de normalización posicional para recuperar la CURP canónica.
            # Resuelve casos como: 0→O, 5→S en la fecha sin corromper el código de estado.
            match_flex = PATTERN_CURP_FLEXIBLE.search(fuente_texto)
            if match_flex:
                curp_normalizada = normalizar_curp_ocr(match_flex.group(0))
                if PATTERN_CURP.match(curp_normalizada):
                    curp_detectado = curp_normalizada
                    break

        if curp_detectado:
            return True, confianza_promedio, f"CURP Validado: {curp_detectado}"

        # Intento 3: Búsqueda por contexto — nueva generación de CURPs RENAPO (formato 'Soy México')
        # En el nuevo formato la CURP aparece precedida por la etiqueta "Clave:" o "CLAVE"
        # El OCR puede leer esa etiqueta con distintas grafias: CLVE, CLAV, CL4VE, etc.
        patron_contexto = re.compile(
            r'(?:CLAVE|Clave|CLVE|CLAV|CL4VE|CLAVE|KEY)[:\s.]*([A-Z0-9]{15,20})',
            re.IGNORECASE
        )
        for fuente_texto2 in [texto_completo, texto_sin_espacios]:
            match_ctx = patron_contexto.search(fuente_texto2)
            if match_ctx:
                candidato = match_ctx.group(1).upper()
                candidato_norm = normalizar_curp_ocr(candidato[:18])
                if PATTERN_CURP.match(candidato_norm):
                    curp_detectado = candidato_norm
                    break
            if curp_detectado:
                break

        if curp_detectado:
            return True, confianza_promedio, f"CURP Validado: {curp_detectado}"

        # Sin resultado — imprimir debug para diagnosticar en terminal
        print(f"[B3 DEBUG CURP] Texto sin espacios (primeros 300 chars): {texto_sin_espacios[:300]}")
        print(f"[B3 DEBUG CURP] Texto completo (primeros 300 chars): {texto_completo[:300]}")
        return False, confianza_promedio, "Rechazado en B3: Estructura CURP no detectada o inválida."

    elif clase_doc == 'actas_nacimiento':
        hallados = []
        faltantes = []
        for campo, variantes_campo in MANDATORY_ACTA_FIELDS.items():
            if any(v in texto_completo for v in variantes_campo):
                hallados.append(campo)
            else:
                faltantes.append(campo)
        
        # Regla de negocio: Si faltan 2 o más campos indispensables, se rechaza
        if len(faltantes) >= 2:
            return False, confianza_promedio, f"Rechazado en B3: Faltan metadatos esenciales {faltantes}"
        return True, confianza_promedio, f"Acta validada. Metadatos encontrados: {hallados}"

    return False, 0.0, "Rechazado en B3: Tipo documental no soportado."

# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES PARA PROCESAMIENTO EN SEGUNDO PLANO
# ---------------------------------------------------------------------------

def abrir_imagen_desde_disco(file_path: Path) -> Image.Image:
    """Abre un archivo guardado en disco y lo convierte a imagen PIL."""
    nombre = file_path.name.lower()
    if nombre.endswith(".pdf"):
        doc = fitz.open(str(file_path))
        if len(doc) == 0:
            raise ValueError("PDF vacío")
        pagina = doc[0]
        pix = pagina.get_pixmap(dpi=300)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    else:
        return Image.open(file_path).convert('RGB')


def analizar_archivo_desde_disco(file_path: Path, tipo_esperado: str) -> dict:
    """Ejecuta el pipeline B1-B2-B3 sobre un archivo guardado en disco.
    Retorna un dict con 'estado', 'confianza' y 'obs'."""
    try:
        img_pil = abrir_imagen_desde_disco(file_path)
    except Exception as e:
        return {"estado": "RECHAZADO", "confianza": None,
                "obs": f"B1: Error al leer archivo: {str(e)}"}

    img_cv   = np.array(img_pil)
    img_gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)

    b1_ok, clase_pred, b1_conf, b1_msg = ejecutar_barrera_1(img_pil)

    if not b1_ok:
        return {"estado": "RECHAZADO", "confianza": None,
                "obs": f"[B1_CONF:{round(b1_conf*100,1)}] B1: {b1_msg}"}

    # Validación cruzada de tipo documental
    if clase_pred != tipo_esperado:
        tipo_det = "CURP" if clase_pred == "curp" else "Acta de Nacimiento"
        tipo_req = "CURP" if tipo_esperado == "curp" else "Acta de Nacimiento"
        return {"estado": "RECHAZADO", "confianza": None,
                "obs": (f"[B1_CONF:{round(b1_conf*100,1)}] B1: OK | B2: OK | "
                        f"B3: Documento incorrecto. Se detectó {tipo_det} pero se requiere {tipo_req}.")}

    b2_ok, b2_msg = ejecutar_barrera_2(img_gray)
    if not b2_ok:
        return {"estado": "RECHAZADO", "confianza": None,
                "obs": f"[B1_CONF:{round(b1_conf*100,1)}] B1: OK | B2: {b2_msg}"}

    b3_ok, b3_conf, b3_msg = ejecutar_barrera_3(img_gray, clase_pred, img_cv)
    return {
        "estado":    "ACEPTADO" if b3_ok else "RECHAZADO",
        "confianza": round(b3_conf * 100, 1),
        "obs":       f"[B1_CONF:{round(b1_conf*100,1)}] B1: OK | B2: OK | B3: {b3_msg}"
    }


def tarea_analisis_background(alumno_id: int, curp_path: Path, acta_path: Path):
    """Tarea de fondo: analiza ambos documentos con B1-B2-B3 y actualiza la BD via PHP."""
    try:
        res_curp = analizar_archivo_desde_disco(curp_path, "curp")
        res_acta = analizar_archivo_desde_disco(acta_path, "actas_nacimiento")

        payload = json_lib.dumps({
            "id":   alumno_id,
            "curp": res_curp,
            "acta": res_acta
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{PHP_API_BASE}/actualizar_resultado.php",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"[OK] Análisis background completado para alumno_id={alumno_id}")
    except Exception as e:
        print(f"[ERROR] Tarea background alumno_id={alumno_id}: {e}")
    finally:
        # Eliminar archivos temporales — los originales ya están en MySQL como BLOB
        try:
            if curp_path.exists(): curp_path.unlink()
            if acta_path.exists(): acta_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 5. DEFINICIÓN DE SERVICIOS API REST (FASTAPI)
# ---------------------------------------------------------------------------
app = FastAPI(
    title="API de Validación Documental Multitarea",
    description="API para clasificación, control de calidad y extracción de metadatos de documentos académicos.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/subir_y_analizar")
async def subir_y_analizar(
    background_tasks: BackgroundTasks,
    nombre:    str        = Form(...),
    edad:      int        = Form(...),
    carrera:   str        = Form(...),
    curp_file: UploadFile = File(...),
    acta_file: UploadFile = File(...)
):
    """
    Endpoint de carga documental asíncrona.
    Acepta los archivos y datos del alumno, responde INMEDIATAMENTE
    al navegador y delega el análisis de IA a un hilo de segundo plano.
    El alumno recibe confirmación instantánea; los resultados aparecen
    en el panel del administrador cuando el procesamiento concluye.
    """
    ts = int(time.time())
    curp_suffix = Path(curp_file.filename).suffix or ".pdf"
    acta_suffix = Path(acta_file.filename).suffix or ".pdf"
    curp_filename = f"{ts}_curp_{curp_file.filename}"
    acta_filename = f"{ts}_acta_{acta_file.filename}"

    # Leer contenido completo de los archivos en memoria
    curp_bytes = await curp_file.read()
    acta_bytes = await acta_file.read()

    # Guardar en archivos temporales del sistema (se borran después del análisis)
    curp_fd, curp_tmp = tempfile.mkstemp(suffix=curp_suffix, prefix="curp_")
    acta_fd, acta_tmp = tempfile.mkstemp(suffix=acta_suffix, prefix="acta_")
    with os.fdopen(curp_fd, "wb") as f:
        f.write(curp_bytes)
    with os.fdopen(acta_fd, "wb") as f:
        f.write(acta_bytes)
    curp_path = Path(curp_tmp)
    acta_path = Path(acta_tmp)

    # Codificar en base64 para enviar a PHP (almacenamiento BLOB en MySQL)
    import base64
    curp_b64  = base64.b64encode(curp_bytes).decode("utf-8")
    acta_b64  = base64.b64encode(acta_bytes).decode("utf-8")
    curp_mime = curp_file.content_type or "application/pdf"
    acta_mime = acta_file.content_type or "application/pdf"

    # Crear registro 'Analizando' en la BD via PHP (incluye archivos como BLOB)
    try:
        payload = json_lib.dumps({
            "nombre":     nombre,
            "edad":       edad,
            "carrera":    carrera,
            "curp_nombre": curp_filename,
            "curp_b64":    curp_b64,
            "curp_mime":   curp_mime,
            "acta_nombre": acta_filename,
            "acta_b64":    acta_b64,
            "acta_mime":   acta_mime,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{PHP_API_BASE}/guardar_pendiente.php",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        res_data = json_lib.loads(urllib.request.urlopen(req, timeout=30).read())
        alumno_id = res_data.get("id")

        if not alumno_id:
            raise ValueError("La BD no retornó un ID válido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar en BD: {str(e)}")

    # Programar el análisis de IA en segundo plano
    background_tasks.add_task(tarea_analisis_background, alumno_id, curp_path, acta_path)

    return {
        "status":   "recibido",
        "id":        alumno_id,
        "mensaje": "Documentos recibidos. El análisis comenzará en breve."
    }


@app.post("/predict")
async def predict_document(file: UploadFile = File(...)):
    
    filename = file.filename
    content_type = file.content_type
    file_bytes = await file.read()
    
    # 1. Conversión e ingesta de PDF / Imagen
    img_pil = None
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            # Abrimos el archivo PDF desde memoria usando PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if len(doc) == 0:
                raise HTTPException(status_code=400, detail="El archivo PDF está vacío.")
            
            # Renderizamos la primera página a alta resolución (300 DPI) para el OCR
            pagina = doc[0]
            pix = pagina.get_pixmap(dpi=300)
            img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al procesar el archivo PDF: {str(e)}")
    else:
        # Si es una imagen común, la cargamos directamente en memoria
        try:
            img_pil = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        except Exception as e:
            raise HTTPException(status_code=400, detail="Formato de imagen no legible.")

    # Convertimos la imagen de PIL a array de OpenCV (escala de grises) para B2 y B3
    img_cv = np.array(img_pil)
    img_gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)

    # EJECUCIÓN DEL PIPELINE EN CASCADA
    
    # BARRERA 1: Clasificación de tipo de documento
    b1_ok, clase_pred, b1_conf, b1_msg = ejecutar_barrera_1(img_pil)
    
    # Si falla la clasificación, retornamos inmediatamente el rechazo (Corte temprano)
    if not b1_ok:
        return {
            "archivo": filename,
            "estado_final": "RECHAZADO",
            "b1_ok": False,
            "b2_ok": "N/A",
            "b3_ok": "N/A",
            "clase_pred": clase_pred,
            "confianza_b1_%": round(b1_conf * 100, 1),
            "confianza_ocr_%": "N/D",
            "observaciones": f"B1: {b1_msg}"
        }

    # BARRERA 2: Control de calidad física de la imagen
    b2_ok, b2_msg = ejecutar_barrera_2(img_gray)
    
    # Si falla el control de calidad, detenemos el proceso
    if not b2_ok:
        return {
            "archivo": filename,
            "estado_final": "RECHAZADO",
            "b1_ok": True,
            "b2_ok": False,
            "b3_ok": "N/A",
            "clase_pred": clase_pred,
            "confianza_b1_%": round(b1_conf * 100, 1),
            "confianza_ocr_%": "N/D",
            "observaciones": f"B1: OK | B2: {b2_msg}"
        }

    # BARRERA 3: Extracción y validación textual (OCR / KIE)
    b3_ok, b3_conf, b3_msg = ejecutar_barrera_3(img_gray, clase_pred)
    
    estado_final = "ACEPTADO" if b3_ok else "RECHAZADO"

    return {
        "archivo": filename,
        "estado_final": estado_final,
        "b1_ok": True,
        "b2_ok": True,
        "b3_ok": b3_ok,
        "clase_pred": clase_pred,
        "confianza_b1_%": round(b1_conf * 100, 1),
        "confianza_ocr_%": round(b3_conf * 100, 1),
        "observaciones": f"B1: OK | B2: OK | B3: {b3_msg}"
    }

@app.get("/health")
def health_check():
    """
    Endpoint de verificación de salud de la API (Liveness Probe).

    :return: Diccionario indicando el estado del servicio ("healthy") y el dispositivo de cómputo activo ("cpu" o "cuda").
    :rtype: dict
    """
    return {"status": "healthy", "device": device.type}

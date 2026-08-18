# Usamos Python 3.10 en Linux (imagen oficial ligera)
FROM python:3.10-slim

# Instalamos dependencias del sistema operativo que EasyOCR necesita
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero solo el requirements para aprovechar la caché de Docker
COPY requirements.txt .

# Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código (app.py y el modelo .pth)
COPY . .

# Hugging Face Spaces expone el puerto 7860
EXPOSE 7860

# Arrancamos la API en el puerto 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]

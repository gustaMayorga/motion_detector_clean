FROM python:3.10-slim

WORKDIR /app

# Instalar todas las dependencias del sistema necesarias de una vez
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias en orden específico para optimizar
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir psycopg2-binary && \
    pip install --no-cache-dir numpy opencv-python && \
    pip install --no-cache-dir torch>=1.7.0 torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p data/recordings data/snapshots data/hls logs models data/configs

# Configurar variables de entorno
ENV PYTHONPATH=/app

# Puerto para la API
EXPOSE 8000

# Comando por defecto
CMD ["python", "-m", "src.main"]
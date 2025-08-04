# Dockerfile para AWS AI Practitioner Quiz
FROM python:3.11-slim

# Metadata del proyecto
LABEL description="AWS AI Practitioner Quiz - Flask Application"
LABEL version="1.0"

# Configurar variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Crear directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema si son necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt primero para aprovechar el cache de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Crear usuario no privilegiado para seguridad
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Exponer el puerto
EXPOSE 5000

# Verificar que los archivos críticos existen
RUN test -f app.py && test -f questions.json

# Comando por defecto
CMD ["python", "app.py"]
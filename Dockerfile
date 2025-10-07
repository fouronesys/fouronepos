# Dockerfile para aplicación Flask POS
# Enfoque simplificado que preserva los archivos estáticos existentes

FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para psycopg2 y otras bibliotecas
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .
COPY pyproject.toml .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente completo (incluye static/, templates/, etc.)
COPY . .

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Exponer el puerto
EXPOSE 5000

# Variables de entorno predeterminadas
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# Comando de inicio usando gunicorn con configuración optimizada
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "sync", "--timeout", "120", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-", "main:app"]
# 1. Wybieramy oficjalny, lekki obraz Pythona 🐍
FROM python:3.12-slim

# 2. Ustawiamy zmienne środowiskowe dla Pythona
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 3. Tworzymy i ustawiamy katalog roboczy w kontenerze
WORKDIR /app

# 4. Instalujemy zależności systemowe potrzebne do kompilacji pakietów (np. psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Kopiujemy plik wymagań i instalujemy biblioteki Pythona
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Kopiujemy cały kod źródłowy aplikacji
COPY . .

# Domyślna komenda (może być nadpisana w docker-compose.yml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
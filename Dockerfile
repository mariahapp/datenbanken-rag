# Basis-Image
FROM python:3.11-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# Systemabhängigkeiten für PyMuPDF (fitz)
RUN apt-get update && apt-get install -y \
    build-essential \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Skripte in den Container kopieren
COPY lib.py ./

# Default-Befehl, kann beim Start überschrieben werden
CMD ["python", "lib.py", "data"]

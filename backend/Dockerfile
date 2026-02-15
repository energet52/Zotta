FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc for Python packages, libreoffice for DOCX→PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libreoffice-writer && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

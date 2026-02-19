FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc for Python packages, libreoffice for DOCX->PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libreoffice-writer && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium OS-level deps for headless browser (AV Knowles bureau)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-unifont fonts-liberation fonts-noto-color-emoji \
    libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
    libatspi2.0-0t64 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2t64 libxshmfence1 \
    libdrm2 libxkbcommon0 libx11-xcb1 && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Install Playwright browsers as appuser so they land in the right cache dir
USER appuser
RUN playwright install chromium
USER root

COPY . .

# Ensure upload directory is writable by appuser
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

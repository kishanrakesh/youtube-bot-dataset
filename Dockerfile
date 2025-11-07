# ---------- Base ----------
FROM python:3.10-slim

# ---------- Working directory ----------
WORKDIR /app

# ---------- Environment variables ----------
ENV PYTHONUNBUFFERED=1 \
    GCP_PROJECT_ID=youtube-bot-dataset \
    GCP_API_KEY=AIzaSyADvDBHXJNthXmEcWPJA2HtrpsEX3dQnNQ \
    GCS_BUCKET_DATA=yt-bot-data \
    REGION=us-south1

# ---------- System dependencies ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    make git curl wget ca-certificates \
    libnss3 libx11-6 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libxkbcommon0 libatk1.0-0 libgtk-3-0 \
    libasound2 libpangocairo-1.0-0 fonts-liberation \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python deps ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir playwright

# ---------- Install Chromium + deps ----------
RUN playwright install --with-deps chromium

# ---------- Copy project ----------
COPY . .

# ---------- Default command ----------
CMD ["bash"]

# Render Free Tier Dockerfile — backend only (frontend served by Vercel)
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY knowledge_base ./knowledge_base

# Create the data directory so SQLite can write to it
RUN mkdir -p /var/data/sift

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

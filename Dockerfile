# Stage 1: Build React + Vite Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY underfind/frontend/package*.json ./
RUN npm install

COPY underfind/frontend/ ./
RUN npm run build

# Stage 2: Python Runtime Environment
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# curl for healthcheck, ffmpeg for download merging, audio extraction and rendering
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

# Install Python dependencies
COPY pyproject.toml ./
RUN poetry install --no-interaction --no-ansi --no-root

# Copy project source and entrypoint
COPY app.py ./
COPY underfind/ ./underfind/

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./underfind/frontend/dist

# Create persistent data volume directory
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "app.py"]

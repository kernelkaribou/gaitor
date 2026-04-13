# Stage 1: Build frontend
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production image
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gosu curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY VERSION ./VERSION
COPY backend/ ./backend/
COPY --from=frontend-build /build/dist ./frontend/dist/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

LABEL org.opencontainers.image.title="Model gAItor" \
      org.opencontainers.image.description="AI model library manager and sync tool" \
      org.opencontainers.image.vendor="kernelkaribou" \
      org.opencontainers.image.source="https://github.com/kernelkaribou/model-gAItor"

ENV PYTHONUNBUFFERED=1
ENV TZ=Etc/UTC
ENV PORT=8487
ENV LOG_LEVEL=INFO
ENV PUID=1000
ENV PGID=1000

EXPOSE ${PORT}

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8487"]

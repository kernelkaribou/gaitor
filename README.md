# Model gAItor 🐊

AI model library manager and sync tool. A self-hosted, Docker-based web UI for managing AI model files across a **library** (NAS/source of truth) and one or more **destinations** (inferencing machines).

Think of it as a smart FTP specifically designed for AI models - browse, sync, retrieve from Hugging Face / CivitAI, rename with history tracking, and manage models across your local AI infrastructure.

## Features

- **Library Management** - Centralized model library with metadata, categories (ComfyUI-style), search, and tagging
- **Destination Sync** - Copy models to inferencing machines with real-time progress tracking
- **External Retrieval** - Download models from Hugging Face and CivitAI directly into your library
- **Rename Tracking** - Rename models in the library with full history; destinations track rename lineage
- **Web Upload & Scan** - Upload models through the browser or scan for files added directly to storage
- **File Integrity** - SHA-256 hashing for verifying large model file transfers
- **Docker Native** - Single container, volume mounts for library and destinations, PUID/PGID support for NAS

## Quick Start

```yaml
# docker-compose.yml
services:
  modelgaitor:
    image: ghcr.io/kernelkaribou/model-gaitor:latest
    container_name: model-gaitor
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Chicago
      # - HUGGINGFACE_TOKEN=hf_xxxxx
      # - CIVITAI_API_KEY=xxxxx
    ports:
      - "8487:8487"
    volumes:
      - /path/to/nas/models:/library
      - /path/to/local/models:/dest/local-gpu
    restart: unless-stopped
```

```bash
docker compose up -d
# Open http://localhost:8487
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `0` | User ID for file operations |
| `PGID` | `0` | Group ID for file operations |
| `TZ` | `Etc/UTC` | Timezone |
| `PORT` | `8487` | Web UI port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `HUGGINGFACE_TOKEN` | - | Hugging Face API token (for gated models) |
| `CIVITAI_API_KEY` | - | CivitAI API key |

## Development

### Prerequisites
- Python 3.12+
- Node.js 22+
- Docker (for container builds)

### Setup
```bash
# Backend
make setup-backend

# Frontend
make setup-frontend
```

### Run locally
```bash
# Backend (with hot reload)
make dev-backend

# Frontend (with hot reload, separate terminal)
make dev-frontend
```

### Docker development
```bash
make docker-dev
```

### Run tests
```bash
make test
```

## Architecture

- **Backend**: Python 3.12 + FastAPI
- **Frontend**: Svelte 5 + Vite + Tailwind CSS
- **Metadata**: JSON files (no database - network share friendly)
- **Transfers**: Server-side file copy between Docker volume mounts (browser only receives progress updates)

## License

MIT - see [LICENSE](LICENSE)

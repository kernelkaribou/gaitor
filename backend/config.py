"""
Configuration management for gAItor.
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent  # /app
LIBRARY_PATH = Path(os.getenv("LIBRARY_PATH", "/library"))
HOSTS_ROOT = Path(os.getenv("HOSTS_ROOT", "/hosts"))

# Metadata directory name within the library
METADATA_DIR_NAME = ".gaitor"

# Server settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8487))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Timezone
TIMEZONE = os.getenv("TZ", "UTC")

# External service auth
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", "")
CIVITAI_API_KEY = os.getenv("CIVITAI_API_KEY", "")

# GitHub repo for version checking
GITHUB_REPO = "kernelkaribou/gaitor"

# File transfer settings
COPY_BUFFER_SIZE = 8 * 1024 * 1024  # 8MB chunks for file copy progress

# Upload settings
MAX_UPLOAD_SIZE = 100 * 1024 * 1024 * 1024  # 100GB max upload

# Known model file extensions
MODEL_EXTENSIONS = {
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin",
    ".gguf", ".ggml", ".onnx",
}

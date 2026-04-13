"""
Pydantic schemas for library configuration.
"""
from pydantic import BaseModel, Field


class CategoryDefinition(BaseModel):
    """A model category (e.g., checkpoints, LoRAs)."""
    id: str
    label: str
    extensions: list[str] = Field(default_factory=list)
    description: str = ""


class LibraryConfig(BaseModel):
    """Library-level configuration stored in .modelgaitor/config.json."""
    name: str = "Model Library"
    version: str = "1"
    categories_template: str = "default"


DEFAULT_CATEGORIES = [
    CategoryDefinition(
        id="checkpoints", label="Checkpoints",
        extensions=[".safetensors", ".ckpt"],
        description="Base diffusion models",
    ),
    CategoryDefinition(
        id="loras", label="LoRAs",
        extensions=[".safetensors"],
        description="LoRA adapters",
    ),
    CategoryDefinition(
        id="vae", label="VAE",
        extensions=[".safetensors", ".pt"],
        description="VAE models",
    ),
    CategoryDefinition(
        id="clip", label="CLIP",
        extensions=[".safetensors", ".bin"],
        description="CLIP text encoders",
    ),
    CategoryDefinition(
        id="controlnet", label="ControlNet",
        extensions=[".safetensors", ".pth"],
        description="ControlNet models",
    ),
    CategoryDefinition(
        id="upscalers", label="Upscalers",
        extensions=[".pth", ".pt"],
        description="Upscale models",
    ),
    CategoryDefinition(
        id="embeddings", label="Embeddings",
        extensions=[".safetensors", ".pt", ".bin"],
        description="Textual inversion embeddings",
    ),
    CategoryDefinition(
        id="llm", label="LLM",
        extensions=[".gguf", ".bin", ".safetensors"],
        description="Large language models",
    ),
    CategoryDefinition(
        id="other", label="Other",
        extensions=["*"],
        description="Uncategorized models",
    ),
]

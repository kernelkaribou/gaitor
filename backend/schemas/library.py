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
    """Library-level configuration stored in .gaitor/config.json."""
    name: str = "Model Library"
    version: str = "1"
    categories_template: str = "default"


DEFAULT_CATEGORIES = [
    # Primary categories (always visible)
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
        id="llm", label="LLM",
        extensions=[".gguf", ".ggml", ".bin", ".safetensors"],
        description="Large language models",
    ),
    CategoryDefinition(
        id="vae", label="VAE",
        extensions=[".safetensors", ".pt"],
        description="VAE models",
    ),
    CategoryDefinition(
        id="controlnet", label="ControlNet",
        extensions=[".safetensors", ".pth"],
        description="ControlNet models",
    ),
    CategoryDefinition(
        id="embeddings", label="Embeddings",
        extensions=[".safetensors", ".pt", ".bin"],
        description="Textual inversion embeddings",
    ),
    CategoryDefinition(
        id="upscale_models", label="Upscalers",
        extensions=[".pth", ".pt"],
        description="Upscale models",
    ),
    CategoryDefinition(
        id="clip", label="CLIP",
        extensions=[".safetensors", ".bin"],
        description="CLIP text encoders",
    ),
    CategoryDefinition(
        id="clip_vision", label="CLIP Vision",
        extensions=[".safetensors", ".bin"],
        description="CLIP vision encoders",
    ),
    CategoryDefinition(
        id="diffusion_models", label="Diffusion Models",
        extensions=[".safetensors", ".pt"],
        description="Standalone diffusion models",
    ),
    CategoryDefinition(
        id="text_encoders", label="Text Encoders",
        extensions=[".safetensors", ".bin"],
        description="Text encoder models",
    ),
    CategoryDefinition(
        id="unet", label="UNet",
        extensions=[".safetensors", ".pt"],
        description="UNet models",
    ),
    # Extended categories (less common, collapsible in UI)
    CategoryDefinition(
        id="animatediff_models", label="AnimateDiff Models",
        extensions=[".safetensors", ".ckpt"],
        description="AnimateDiff motion models",
    ),
    CategoryDefinition(
        id="animatediff_motion_lora", label="AnimateDiff Motion LoRA",
        extensions=[".safetensors"],
        description="AnimateDiff motion LoRA adapters",
    ),
    CategoryDefinition(
        id="audio_encoders", label="Audio Encoders",
        extensions=[".safetensors", ".pt", ".bin"],
        description="Audio encoder models",
    ),
    CategoryDefinition(
        id="configs", label="Configs",
        extensions=[".yaml", ".json"],
        description="Model configuration files",
    ),
    CategoryDefinition(
        id="diffusers", label="Diffusers",
        extensions=[".safetensors", ".bin"],
        description="Diffusers pipeline models",
    ),
    CategoryDefinition(
        id="gligen", label="GLIGEN",
        extensions=[".safetensors", ".pt"],
        description="GLIGEN grounded models",
    ),
    CategoryDefinition(
        id="hypernetworks", label="Hypernetworks",
        extensions=[".pt"],
        description="Hypernetwork models",
    ),
    CategoryDefinition(
        id="kgen", label="KGen",
        extensions=[".safetensors", ".pt"],
        description="KGen prompt models",
    ),
    CategoryDefinition(
        id="latent_upscale_models", label="Latent Upscalers",
        extensions=[".safetensors", ".pt"],
        description="Latent space upscale models",
    ),
    CategoryDefinition(
        id="model_patches", label="Model Patches",
        extensions=[".safetensors", ".pt"],
        description="Model patch files",
    ),
    CategoryDefinition(
        id="photomaker", label="PhotoMaker",
        extensions=[".safetensors", ".bin"],
        description="PhotoMaker models",
    ),
    CategoryDefinition(
        id="style_models", label="Style Models",
        extensions=[".safetensors"],
        description="Style transfer models",
    ),
    CategoryDefinition(
        id="vae_approx", label="VAE Approx",
        extensions=[".pt"],
        description="Approximate VAE decoders",
    ),
    CategoryDefinition(
        id="other", label="Other",
        extensions=["*"],
        description="Uncategorized models",
    ),
]

# Categories shown by default before the expandable section
PRIMARY_CATEGORY_IDS = {
    "checkpoints", "loras", "llm", "vae", "controlnet", "embeddings",
    "upscale_models", "clip", "clip_vision", "diffusion_models",
    "text_encoders", "unet",
}

"""LLM provider abstraction for card image analysis.

To add a new provider (e.g., Ollama, llama.cpp, a local vision model):
1. Subclass LLMProvider
2. Implement analyze_image() and analyze_text()
3. Add it to get_provider() below

The interface is deliberately simple — one image per call — so that local
models with limited multi-image support can be used as drop-in replacements.
"""

import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image


# Max dimension before we resize (keeps API costs down and speeds up local models)
MAX_IMAGE_DIMENSION = 1568

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}


def load_and_prepare_image(image_path: str) -> tuple[str, str]:
    """Load an image, validate format, resize if needed, return (base64_data, media_type).

    Resizes images where either dimension exceeds MAX_IMAGE_DIMENSION, preserving
    aspect ratio. Converts unusual formats to PNG.
    """
    path = Path(image_path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError(f"Unsupported image format: {suffix}")

    img = Image.open(path)

    # Resize if too large
    w, h = img.size
    if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION:
        ratio = min(MAX_IMAGE_DIMENSION / w, MAX_IMAGE_DIMENSION / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # Determine output format
    if suffix in {".jpg", ".jpeg"}:
        fmt, media_type = "JPEG", "image/jpeg"
    elif suffix == ".png":
        fmt, media_type = "PNG", "image/png"
    elif suffix == ".gif":
        fmt, media_type = "GIF", "image/gif"
    elif suffix == ".webp":
        fmt, media_type = "WEBP", "image/webp"
    else:
        # Convert anything else to PNG
        fmt, media_type = "PNG", "image/png"
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

    import io
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return b64, media_type


class LLMProvider(ABC):
    """Abstract base for vision-capable LLM providers.

    Interface is one-image-per-call for maximum compatibility with local models.
    To add a new provider:
      - Subclass this
      - Implement analyze_image() for vision tasks
      - Implement analyze_text() for text-only synthesis/schema proposals
    """

    @abstractmethod
    def analyze_image(self, image_path: str, prompt: str) -> str:
        """Send a single image + text prompt to the LLM, return text response."""
        ...

    @abstractmethod
    def analyze_text(self, prompt: str) -> str:
        """Send a text-only prompt to the LLM, return text response.

        Used for synthesis steps (e.g., combining individual card descriptions
        into a unified schema proposal).
        """
        ...


class ClaudeProvider(LLMProvider):
    """Vision LLM provider using the Anthropic Claude API.

    Requires ANTHROPIC_API_KEY environment variable.
    Uses claude-sonnet-4-20250514 by default (good balance of vision quality and cost).
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514", max_tokens: int = 4096):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your key at https://console.anthropic.com/"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def analyze_image(self, image_path: str, prompt: str) -> str:
        b64_data, media_type = load_and_prepare_image(image_path)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.content[0].text

    def analyze_text(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


# ---------------------------------------------------------------------------
# Future provider stubs — subclass LLMProvider and implement the two methods.
# ---------------------------------------------------------------------------

# class OllamaProvider(LLMProvider):
#     """Use a local Ollama model (e.g., llava, bakllava) for card analysis.
#
#     def __init__(self, model="llava", base_url="http://localhost:11434"):
#         self.model = model
#         self.base_url = base_url
#
#     def analyze_image(self, image_path, prompt):
#         # POST to /api/generate with base64 image in 'images' field
#         ...
#
#     def analyze_text(self, prompt):
#         # POST to /api/generate (text-only)
#         ...

# class LlamaCppProvider(LLMProvider):
#     """Use llama.cpp server with a multimodal model (e.g., LLaVA GGUF).
#
#     def __init__(self, base_url="http://localhost:8080"):
#         self.base_url = base_url
#
#     def analyze_image(self, image_path, prompt):
#         # POST to /completion with image_data field
#         ...
#
#     def analyze_text(self, prompt):
#         # POST to /completion (text-only)
#         ...

# class OpenAICompatibleProvider(LLMProvider):
#     """Use any OpenAI-compatible API (vLLM, Together AI, etc.).
#
#     def __init__(self, base_url, api_key, model):
#         ...
#
#     def analyze_image(self, image_path, prompt):
#         # Standard OpenAI vision API format
#         ...
#
#     def analyze_text(self, prompt):
#         ...


def get_provider(provider_name: str = "claude", **kwargs) -> LLMProvider:
    """Factory function to get an LLM provider by name.

    Args:
        provider_name: One of "claude" (more to come).
        **kwargs: Passed to the provider constructor (e.g., model, base_url).
    """
    providers = {
        "claude": ClaudeProvider,
        # "ollama": OllamaProvider,
        # "llamacpp": LlamaCppProvider,
        # "openai": OpenAICompatibleProvider,
    }

    if provider_name not in providers:
        available = ", ".join(providers.keys())
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")

    return providers[provider_name](**kwargs)

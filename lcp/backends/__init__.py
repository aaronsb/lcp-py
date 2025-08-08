"""Model backends for LCP."""

from .base import Backend
from .huggingface import HuggingFaceBackend

__all__ = ["Backend", "HuggingFaceBackend"]
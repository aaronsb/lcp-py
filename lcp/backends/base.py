"""Base backend interface."""

from abc import ABC, abstractmethod
from typing import List, Optional, AsyncGenerator, Callable
from pathlib import Path

from ..models import ModelInfo


class Backend(ABC):
    """Abstract base class for model backends."""
    
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
    
    @abstractmethod
    async def search_models(
        self, 
        query: str, 
        limit: int = 10
    ) -> List[ModelInfo]:
        """Search for models matching the query."""
        pass
    
    @abstractmethod
    async def get_model_info(
        self, 
        model_identifier: str
    ) -> Optional[ModelInfo]:
        """Get detailed information about a specific model."""
        pass
    
    @abstractmethod
    async def download_model(
        self, 
        model_info: ModelInfo, 
        target_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """Download a model to the target path."""
        pass
    
    @abstractmethod
    def get_download_url(self, model_info: ModelInfo) -> str:
        """Get the direct download URL for a model."""
        pass
    
    def supports_model(self, model_identifier: str) -> bool:
        """Check if this backend can handle the given model identifier."""
        return True  # Default: accept all identifiers
    
    def parse_model_identifier(self, identifier: str) -> tuple[str, str]:
        """
        Parse model identifier into (repo, filename) parts.
        
        Examples:
        - "phi-3.5-mini" -> ("bartowski/Phi-3.5-mini-instruct-GGUF", "Phi-3.5-mini-instruct-Q4_K_M.gguf")
        - "microsoft/Phi-3-mini" -> ("microsoft/Phi-3-mini", "Phi-3-mini-4k-instruct-q4.gguf")
        """
        if "/" in identifier:
            # Explicit repo/model format
            parts = identifier.split("/")
            repo = "/".join(parts[:2])  # user/repo
            filename = "/".join(parts[2:]) if len(parts) > 2 else ""
            return repo, filename
        else:
            # Simple model name - backend should resolve
            return identifier, ""
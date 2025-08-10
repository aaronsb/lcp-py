"""Data models for LCP."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re


class ModelType(str, Enum):
    """Model type classification."""
    INSTRUCT = "instruct"
    CHAT = "chat"
    CODE = "code"
    BASE = "base"
    FUNCTION = "function"


class QuantizationType(str, Enum):
    """GGUF quantization types."""
    Q2_K = "Q2_K"
    Q3_K_S = "Q3_K_S"
    Q3_K_M = "Q3_K_M"
    Q3_K_L = "Q3_K_L"
    Q4_0 = "Q4_0"
    Q4_1 = "Q4_1"
    Q4_K_S = "Q4_K_S"
    Q4_K_M = "Q4_K_M"
    Q5_0 = "Q5_0"
    Q5_1 = "Q5_1"
    Q5_K_S = "Q5_K_S"
    Q5_K_M = "Q5_K_M"
    Q6_K = "Q6_K"
    Q8_0 = "Q8_0"
    F16 = "F16"
    F32 = "F32"


@dataclass
class ModelInfo:
    """Information about a model."""
    
    name: str
    repo_id: str
    filename: str
    backend: str
    size_bytes: Optional[int] = None
    quantization: Optional[QuantizationType] = None
    model_type: Optional[ModelType] = None
    parameter_count: Optional[str] = None  # e.g., "7B", "70B"
    architecture: Optional[str] = None  # e.g., "llama", "phi3"
    download_url: Optional[str] = None
    local_path: Optional[Path] = None
    metadata: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Auto-extract info from filename if not provided
        if self.quantization is None:
            self.quantization = self._extract_quantization()
        
        if self.parameter_count is None:
            self.parameter_count = self._extract_parameter_count()
        
        if self.model_type is None:
            self.model_type = self._extract_model_type()
    
    def _extract_quantization(self) -> Optional[QuantizationType]:
        """Extract quantization from filename."""
        filename_upper = self.filename.upper()
        
        for quant in QuantizationType:
            if quant.value in filename_upper:
                return quant
        
        return None
    
    def _extract_parameter_count(self) -> Optional[str]:
        """Extract parameter count from name or filename."""
        text = f"{self.name} {self.filename}".upper()
        
        # Look for patterns like "7B", "70B", "1.5B", etc.
        patterns = [
            r'(\d+\.?\d*[BM])',  # 7B, 1.5B, 70B
            r'(\d+\.?\d*)\s*[BM]ILLION',  # 7 billion, 1.5 billion
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_model_type(self) -> ModelType:
        """Extract model type from name."""
        name_lower = self.name.lower()
        
        if any(word in name_lower for word in ["instruct", "chat", "assistant"]):
            return ModelType.INSTRUCT
        elif any(word in name_lower for word in ["code", "coder", "coding"]):
            return ModelType.CODE
        elif any(word in name_lower for word in ["function", "tool", "agent"]):
            return ModelType.FUNCTION
        else:
            return ModelType.BASE
    
    @property
    def size_gb(self) -> Optional[float]:
        """Get size in GB."""
        if self.size_bytes is None:
            return None
        return self.size_bytes / (1024 ** 3)
    
    @property
    def display_name(self) -> str:
        """Get a nice display name."""
        parts = []
        
        # Base name
        name = self.name.replace("-", " ").replace("_", " ")
        parts.append(name)
        
        # Parameter count
        if self.parameter_count:
            parts.append(f"({self.parameter_count})")
        
        # Quantization
        if self.quantization:
            parts.append(f"[{self.quantization.value}]")
        
        return " ".join(parts)
    
    @property
    def model_id(self) -> str:
        """Get a copyable model identifier (uses underscores instead of spaces)."""
        # Use the full path as the identifier
        return f"{self.repo_id}/{self.filename}"
    
    @property
    def is_local(self) -> bool:
        """Check if model is downloaded locally."""
        return self.local_path is not None and self.local_path.exists()
    
    def matches_query(self, query: str) -> bool:
        """Check if model matches a search query."""
        query_lower = query.lower()
        
        # Check various fields
        search_text = " ".join([
            self.name.lower(),
            self.repo_id.lower(),
            self.filename.lower(),
            self.parameter_count or "",
            self.architecture or "",
            str(self.model_type.value) if self.model_type else "",
        ])
        
        return query_lower in search_text


@dataclass
class LocalModel:
    """Information about a locally stored model."""
    
    path: Path
    name: str
    size_bytes: int
    modified_at: datetime
    is_active: bool = False
    model_info: Optional[ModelInfo] = None
    
    @property
    def size_gb(self) -> float:
        """Get size in GB."""
        return self.size_bytes / (1024 ** 3)
    
    @classmethod
    def from_path(cls, path: Path, active_model_path: Optional[Path] = None) -> "LocalModel":
        """Create LocalModel from file path."""
        stat = path.stat()
        
        return cls(
            path=path,
            name=path.stem,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_active=active_model_path is not None and path.samefile(active_model_path),
        )


@dataclass
class ChatMessage:
    """A chat message."""
    
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    token_count: Optional[int] = None
    
    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content, timestamp=datetime.now())
    
    @classmethod
    def assistant(cls, content: str, token_count: Optional[int] = None) -> "ChatMessage":
        return cls(
            role="assistant", 
            content=content, 
            timestamp=datetime.now(),
            token_count=token_count
        )
    
    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content, timestamp=datetime.now())


@dataclass
class ChatSession:
    """A chat session with message history."""
    
    messages: List[ChatMessage]
    model_name: str
    started_at: datetime
    total_tokens: int = 0
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        if message.token_count:
            self.total_tokens += message.token_count
    
    def clear_history(self) -> None:
        """Clear message history."""
        self.messages.clear()
        self.total_tokens = 0
    
    def get_context_messages(self, max_messages: int = 20) -> List[Dict[str, str]]:
        """Get recent messages formatted for API."""
        recent_messages = self.messages[-max_messages:] if max_messages > 0 else self.messages
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
        ]
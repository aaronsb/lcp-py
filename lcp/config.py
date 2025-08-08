"""Configuration management with XDG spec compliance."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import toml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import platformdirs


class ModelPreferences(BaseModel):
    """Model selection preferences."""
    
    preferred_quantization: str = "Q4_K_M"
    max_model_size_gb: Optional[float] = None  # Auto-detect based on GPU memory
    prefer_instruct_models: bool = True
    prefer_recent_models: bool = True


class BackendConfig(BaseModel):
    """Backend configuration."""
    
    name: str
    enabled: bool = True
    priority: int = 1  # Lower number = higher priority
    config: Dict[str, Any] = Field(default_factory=dict)


class APIConfig(BaseModel):
    """API server configuration."""
    
    base_url: str = "http://localhost:11434"
    timeout: int = 30
    streaming: bool = True
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9


class UIConfig(BaseModel):
    """UI preferences."""
    
    use_colors: bool = True
    show_progress: bool = True
    chat_history_length: int = 100
    show_token_count: bool = True
    show_timing: bool = True


class LCPConfig(BaseSettings):
    """Main LCP configuration with XDG compliance."""
    
    # Model management
    models_dir: Path = Field(default_factory=lambda: Path("./models"))
    model_preferences: ModelPreferences = Field(default_factory=ModelPreferences)
    
    # Backends
    backends: List[BackendConfig] = Field(default_factory=lambda: [
        BackendConfig(
            name="huggingface",
            enabled=True,
            priority=1,
            config={
                "popular_repos": [
                    "bartowski/*-GGUF",
                    "microsoft/*-gguf",
                    "mradermacher/*-GGUF",
                ],
                "default_quantizations": ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"],
            }
        ),
        BackendConfig(
            name="ollama_registry",
            enabled=False,
            priority=2,
            config={"registry_url": "https://registry.ollama.ai"}
        ),
    ])
    
    # API configuration
    api: APIConfig = Field(default_factory=APIConfig)
    
    # UI preferences
    ui: UIConfig = Field(default_factory=UIConfig)
    
    class Config:
        env_prefix = "LCP_"
        case_sensitive = False


class ConfigManager:
    """Manages configuration with XDG Base Directory compliance."""
    
    def __init__(self):
        self.app_name = "lcp"
        self.config_dir = Path(platformdirs.user_config_dir(self.app_name))
        self.data_dir = Path(platformdirs.user_data_dir(self.app_name))
        self.cache_dir = Path(platformdirs.user_cache_dir(self.app_name))
        
        # Main config file
        self.config_file = self.config_dir / "config.toml"
        
        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._config: Optional[LCPConfig] = None
    
    def load_config(self) -> LCPConfig:
        """Load configuration from file or create default."""
        if self._config is not None:
            return self._config
        
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config_data = toml.load(f)
                self._config = LCPConfig(**config_data)
            except Exception as e:
                print(f"Warning: Failed to load config ({e}), using defaults")
                self._config = LCPConfig()
        else:
            self._config = LCPConfig()
            self.save_config()
        
        # Update models_dir to use XDG data dir if it's still default
        if str(self._config.models_dir) == "./models":
            self._config.models_dir = self.data_dir / "models"
            self._config.models_dir.mkdir(parents=True, exist_ok=True)
        
        return self._config
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        if self._config is None:
            return
        
        # Convert to dict and save as TOML
        config_dict = self._config.model_dump()
        
        with open(self.config_file, "w") as f:
            toml.dump(config_dict, f)
    
    def get_models_dir(self) -> Path:
        """Get the models directory path."""
        config = self.load_config()
        return Path(config.models_dir)
    
    def get_cache_dir(self) -> Path:
        """Get the cache directory path."""
        return self.cache_dir
    
    def update_config(self, **kwargs) -> None:
        """Update configuration with new values."""
        config = self.load_config()
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self.save_config()


# Global config manager instance
config_manager = ConfigManager()
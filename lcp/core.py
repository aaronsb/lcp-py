"""Core LCP functionality - model management and operations."""

import asyncio
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from .models import ModelInfo, LocalModel
from .backends import Backend, HuggingFaceBackend
from .config import config_manager
from .ui.chat import StreamingChatInterface


class LCPCore:
    """Core LCP functionality."""
    
    def __init__(self):
        self.config = config_manager.load_config()
        self.console = Console()
        self.backends: Dict[str, Backend] = {}
        
        # Initialize backends
        self._init_backends()
    
    def _init_backends(self) -> None:
        """Initialize configured backends."""
        for backend_config in self.config.backends:
            if not backend_config.enabled:
                continue
            
            if backend_config.name == "huggingface":
                backend = HuggingFaceBackend(backend_config.name, backend_config.config)
                self.backends[backend_config.name] = backend
            # Add other backends here as they're implemented
    
    async def search_models(self, query: str, limit: int = 10) -> List[ModelInfo]:
        """Search for models across all backends."""
        all_models = []
        
        # Search in parallel across backends
        tasks = []
        for backend in self.backends.values():
            task = backend.search_models(query, limit)
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_models.extend(result)
        
        # Sort by relevance and deduplicate
        seen = set()
        unique_models = []
        
        for model in all_models:
            key = (model.repo_id, model.filename)
            if key not in seen:
                seen.add(key)
                unique_models.append(model)
        
        return unique_models[:limit]
    
    async def get_model(self, model_identifier: str) -> Optional[ModelInfo]:
        """Get a specific model, trying all backends."""
        for backend in self.backends.values():
            if backend.supports_model(model_identifier):
                model_info = await backend.get_model_info(model_identifier)
                if model_info:
                    return model_info
        
        return None
    
    async def download_model(self, model_info: ModelInfo) -> Path:
        """Download a model with progress display."""
        models_dir = config_manager.get_models_dir()
        models_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = models_dir / model_info.filename
        
        if target_path.exists():
            self.console.print(f"[yellow]Model already exists: {model_info.filename}[/yellow]")
            return target_path
        
        backend = self.backends.get(model_info.backend)
        if not backend:
            raise ValueError(f"Backend not available: {model_info.backend}")
        
        # Download with rich progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=50),
            TaskProgressColumn(),
            TextColumn("[blue]{task.fields[speed]}"),
            console=self.console,
            transient=False,
        ) as progress:
            
            task_id = progress.add_task(
                f"Downloading {model_info.filename}",
                total=None,
                speed="0 MB/s"
            )
            
            start_time = datetime.now()
            
            def update_progress(downloaded: int, total: int):
                if total > 0:
                    progress.update(task_id, completed=downloaded, total=total)
                
                # Calculate speed
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > 0:
                    speed_mb = (downloaded / (1024 * 1024)) / elapsed
                    progress.update(task_id, speed=f"{speed_mb:.1f} MB/s")
            
            downloaded_path = await backend.download_model(
                model_info, 
                target_path, 
                update_progress
            )
        
        self.console.print(f"[green]✅ Downloaded: {model_info.filename}[/green]")
        return downloaded_path
    
    def list_local_models(self) -> List[LocalModel]:
        """List locally downloaded models."""
        models_dir = config_manager.get_models_dir()
        
        if not models_dir.exists():
            return []
        
        # Check for active model symlink
        active_model_path = None
        model_symlink = models_dir / "model.gguf"
        if model_symlink.is_symlink() and model_symlink.exists():
            active_model_path = model_symlink.resolve()
        
        models = []
        for model_file in models_dir.glob("*.gguf"):
            if model_file.is_file() and not model_file.is_symlink():
                local_model = LocalModel.from_path(model_file, active_model_path)
                models.append(local_model)
        
        # Sort by modification time, newest first
        models.sort(key=lambda m: m.modified_at, reverse=True)
        
        return models
    
    def set_active_model(self, model_path: Path) -> bool:
        """Set a model as the active model."""
        models_dir = config_manager.get_models_dir()
        model_symlink = models_dir / "model.gguf"
        
        if model_symlink.exists():
            model_symlink.unlink()
        
        try:
            # Create relative symlink
            relative_path = model_path.relative_to(models_dir)
            model_symlink.symlink_to(relative_path)
            return True
        except Exception:
            return False
    
    def remove_model(self, model_path: Path) -> bool:
        """Remove a local model."""
        try:
            # Check if it's the active model
            models_dir = config_manager.get_models_dir()
            model_symlink = models_dir / "model.gguf"
            
            is_active = (
                model_symlink.exists() and 
                model_symlink.is_symlink() and 
                model_symlink.resolve() == model_path.resolve()
            )
            
            # Remove the file
            model_path.unlink()
            
            # Remove symlink if this was the active model
            if is_active and model_symlink.exists():
                model_symlink.unlink()
            
            return True
        except Exception:
            return False
    
    async def check_api_status(self) -> Dict[str, Any]:
        """Check the status of the llama.cpp API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check health endpoint
                health_response = await client.get(f"{self.config.api.base_url}/health")
                
                if health_response.status_code == 200:
                    return {
                        "status": "healthy",
                        "api_available": True,
                        "base_url": self.config.api.base_url,
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "api_available": False,
                        "error": f"HTTP {health_response.status_code}",
                    }
        
        except Exception as e:
            return {
                "status": "unavailable", 
                "api_available": False,
                "error": str(e),
            }
    
    def show_status(self) -> None:
        """Display system status."""
        self.console.print()
        self.console.print(Panel.fit("📊 LCP Status", border_style="cyan"))
        
        # API Status
        async def check_api():
            status = await self.check_api_status()
            
            if status["api_available"]:
                self.console.print("✅ [green]API: Available[/green]")
                self.console.print(f"   [dim]{status['base_url']}[/dim]")
            else:
                self.console.print("❌ [red]API: Unavailable[/red]")
                self.console.print(f"   [red]{status.get('error', 'Unknown error')}[/red]")
        
        asyncio.run(check_api())
        
        # Models
        local_models = self.list_local_models()
        self.console.print(f"📁 [blue]Local Models: {len(local_models)}[/blue]")
        
        active_count = sum(1 for m in local_models if m.is_active)
        if active_count > 0:
            active_model = next(m for m in local_models if m.is_active)
            self.console.print(f"🎯 [green]Active Model: {active_model.name}[/green]")
        else:
            self.console.print("⚠️  [yellow]No active model set[/yellow]")
        
        # Configuration
        models_dir = config_manager.get_models_dir()
        self.console.print(f"📂 [dim]Models Directory: {models_dir}[/dim]")
        
        # Backends
        enabled_backends = [b for b in self.config.backends if b.enabled]
        backend_names = [b.name for b in enabled_backends]
        self.console.print(f"🔧 [dim]Backends: {', '.join(backend_names)}[/dim]")
        
        self.console.print()
    
    def show_models_table(self, models: List[LocalModel]) -> None:
        """Display local models in a table."""
        if not models:
            self.console.print("[yellow]No local models found[/yellow]")
            return
        
        table = Table(title="📋 Local Models", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", style="blue")
        table.add_column("Status", justify="center")
        
        for model in models:
            status = "🎯 Active" if model.is_active else ""
            size_str = f"{model.size_gb:.1f} GB"
            modified_str = model.modified_at.strftime("%Y-%m-%d %H:%M")
            
            table.add_row(
                model.name,
                size_str,
                modified_str,
                status
            )
        
        self.console.print()
        self.console.print(table)
        self.console.print()
    
    async def chat_with_model(self, model_name: Optional[str] = None) -> None:
        """Start a chat session with a model."""
        # If no model specified, try to use active model
        if not model_name:
            local_models = self.list_local_models()
            active_models = [m for m in local_models if m.is_active]
            
            if not active_models:
                self.console.print("[red]No active model set. Please specify a model name.[/red]")
                return
            
            model_name = active_models[0].name
        
        # Check if model exists locally, if not try to download
        local_models = self.list_local_models()
        local_model_names = [m.name for m in local_models]
        
        if model_name not in local_model_names:
            self.console.print(f"[yellow]Model '{model_name}' not found locally. Searching...[/yellow]")
            
            # Search for the model
            models = await self.search_models(model_name, limit=5)
            
            if not models:
                self.console.print(f"[red]No models found matching '{model_name}'[/red]")
                return
            
            # Use the first match
            model_info = models[0]
            self.console.print(f"[blue]Found: {model_info.display_name}[/blue]")
            
            # Download the model
            downloaded_path = await self.download_model(model_info)
            
            # Set as active model
            if self.set_active_model(downloaded_path):
                self.console.print(f"[green]Set as active model: {model_info.filename}[/green]")
                model_name = Path(model_info.filename).stem
            
            # Restart container message
            self.console.print("[yellow]⚠️  Restart your llamacpp container to load the new model[/yellow]")
            self.console.print("[dim]Run: docker compose restart llamacpp[/dim]")
            self.console.print()
            
            # Wait for user confirmation
            input("Press Enter when the container has restarted...")
        
        # Start chat interface
        async with StreamingChatInterface() as chat:
            chat.start_session(model_name)
            await chat.chat_loop()


# Global core instance
core = LCPCore()
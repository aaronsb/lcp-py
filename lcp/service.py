"""Service management for the llamacpp Docker container."""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Any
import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from .model_analyzer import calculate_gpu_layers

console = Console()


class ServiceManager:
    """Manages the llamacpp Docker service."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.config = config_manager.get_config()
        self.service_name = self.config.docker.service_name
        
        # Find the docker-compose.yml file
        if self.config.docker.compose_dir:
            # Use configured directory
            self.compose_dir = Path(self.config.docker.compose_dir)
        else:
            # Auto-detect based on models directory
            models_dir = self.config.models_dir
            if models_dir.parent.name == "llamacpp":
                self.compose_dir = models_dir.parent
            else:
                # Try common locations
                potential_dirs = [
                    Path.cwd().parent,
                    Path.cwd().parent / "llamacpp",
                    models_dir.parent,
                ]
                
                for dir_path in potential_dirs:
                    if (dir_path / "docker-compose.yml").exists():
                        self.compose_dir = dir_path
                        break
                else:
                    # Default to parent of models dir
                    self.compose_dir = models_dir.parent
        
        self.compose_file = self.compose_dir / "docker-compose.yml"
    
    def _run_docker_compose(self, *args, capture_output=True) -> subprocess.CompletedProcess:
        """Run docker-compose command."""
        if not self.compose_file.exists():
            console.print("[red]Error: docker-compose.yml not found[/red]")
            console.print(f"Expected at: {self.compose_file}")
            sys.exit(1)
        
        cmd = ["docker-compose", "-f", str(self.compose_file)] + list(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                cwd=str(self.compose_file.parent)
            )
            return result
        except FileNotFoundError:
            console.print("[red]Error: docker-compose not found[/red]")
            console.print("Please install Docker and docker-compose")
            sys.exit(1)
    
    def _run_docker(self, *args, capture_output=True) -> subprocess.CompletedProcess:
        """Run docker command."""
        cmd = ["docker"] + list(args)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True
            )
            return result
        except FileNotFoundError:
            console.print("[red]Error: docker not found[/red]")
            console.print("Please install Docker")
            sys.exit(1)
    
    def status(self) -> Dict[str, Any]:
        """Get service status."""
        status_info = {
            "container_exists": False,
            "is_running": False,
            "health": "unknown",
            "ports": [],
            "uptime": None,
            "memory_usage": None,
            "compose_file": str(self.compose_file),
        }
        
        # Check if container exists
        result = self._run_docker("ps", "-a", "--filter", f"name={self.service_name}", "--format", "json")
        
        if result.returncode == 0 and result.stdout.strip():
            import json
            try:
                container_info = json.loads(result.stdout.strip())
                status_info["container_exists"] = True
                
                # Parse status
                if "Up" in container_info.get("Status", ""):
                    status_info["is_running"] = True
                    status_info["uptime"] = container_info.get("Status", "")
                
                # Parse ports
                ports_str = container_info.get("Ports", "")
                if ports_str:
                    status_info["ports"] = ports_str
                
                # Get health status
                health_result = self._run_docker("inspect", self.service_name, "--format", "{{.State.Health.Status}}")
                if health_result.returncode == 0:
                    status_info["health"] = health_result.stdout.strip() or "none"
                
                # Get memory usage if running
                if status_info["is_running"]:
                    stats_result = self._run_docker("stats", self.service_name, "--no-stream", "--format", "{{.MemUsage}}")
                    if stats_result.returncode == 0:
                        status_info["memory_usage"] = stats_result.stdout.strip()
                        
            except (json.JSONDecodeError, KeyError):
                pass
        
        return status_info
    
    def start(self) -> bool:
        """Start the service."""
        console.print(f"🚀 Starting {self.service_name} service...")
        result = self._run_docker_compose("up", "-d", self.service_name, capture_output=False)
        return result.returncode == 0
    
    def stop(self) -> bool:
        """Stop the service."""
        console.print(f"🛑 Stopping {self.service_name} service...")
        result = self._run_docker_compose("stop", self.service_name, capture_output=False)
        return result.returncode == 0
    
    def restart(self, optimize_for_model: bool = True) -> bool:
        """Restart the service with optional GPU optimization."""
        console.print(f"🔄 Restarting {self.service_name} service...")
        
        if optimize_for_model:
            # Update docker-compose with optimized GPU layers
            if self._update_compose_for_model():
                console.print("[🎯] Applied GPU optimization for current model")
                # Need to recreate container for command changes to take effect
                self._run_docker_compose("down", self.service_name)
                result = self._run_docker_compose("up", "-d", self.service_name, capture_output=False)
                return result.returncode == 0
        
        # Regular restart if no optimization or optimization failed
        result = self._run_docker_compose("restart", self.service_name, capture_output=False)
        return result.returncode == 0
    
    def _update_compose_for_model(self) -> bool:
        """Update docker-compose.yml with optimized GPU layer count."""
        try:
            # Get active model path
            models_dir = Path(self.config.models_dir)
            model_symlink = models_dir / "model.gguf"
            
            if not model_symlink.exists():
                return False
            
            # Calculate optimal GPU layers
            hardware = self.config_manager.get_hardware_profile()
            n_gpu_layers = calculate_gpu_layers(
                model_symlink,
                strategy=self.config.docker.gpu_strategy,
                vram_percentage=self.config.docker.gpu_vram_percentage,
                available_vram_mb=hardware.total_vram_gb * 1024  # Convert GB to MB
            )
            
            # Read current docker-compose
            with open(self.compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)
            
            # Update command with new GPU layers
            service = compose_data['services'][self.service_name]
            command_str = service.get('command', '')
            
            # Parse and update command
            import re
            # Replace existing -ngl parameter or add it
            if '-ngl' in command_str:
                command_str = re.sub(r'-ngl\s+\d+', f'-ngl {n_gpu_layers}', command_str)
            else:
                # Add before --host
                command_str = command_str.replace('--host', f'-ngl {n_gpu_layers} --host')
            
            service['command'] = command_str
            
            # Write updated docker-compose
            with open(self.compose_file, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
            
            # Show optimization info
            vram_mb = hardware.total_vram_gb * 1024
            strategy_info = {
                "gpu-only": "🚀 GPU only (all layers)",
                "cpu-only": "📏 CPU only (no GPU)",
                "auto-maximize": f"🎯 Auto-maximize ({n_gpu_layers} layers on GPU)",
                "auto-percentage": f"📊 Using {self.config.docker.gpu_vram_percentage}% of {vram_mb:.0f}MB VRAM ({n_gpu_layers} layers)"
            }
            
            console.print(f"[green]GPU Strategy: {strategy_info.get(self.config.docker.gpu_strategy, 'Unknown')}[/green]")
            
            return True
            
        except Exception as e:
            console.print(f"[yellow]⚠️ Could not optimize GPU layers: {e}[/yellow]")
            return False
    
    def enable(self) -> bool:
        """Enable auto-start (set restart policy)."""
        console.print(f"✅ Enabling auto-start for {self.service_name}...")
        result = self._run_docker("update", "--restart", "unless-stopped", self.service_name)
        if result.returncode == 0:
            console.print("[green]Auto-start enabled (restart: unless-stopped)[/green]")
            return True
        return False
    
    def disable(self) -> bool:
        """Disable auto-start (remove restart policy)."""
        console.print(f"❌ Disabling auto-start for {self.service_name}...")
        result = self._run_docker("update", "--restart", "no", self.service_name)
        if result.returncode == 0:
            console.print("[yellow]Auto-start disabled (restart: no)[/yellow]")
            return True
        return False
    
    def logs(self, lines: int = 50, follow: bool = False) -> None:
        """Show service logs."""
        args = ["logs", self.service_name]
        if not follow:
            args.extend(["--tail", str(lines)])
        if follow:
            args.append("-f")
        
        self._run_docker_compose(*args, capture_output=False)
    
    def show_status_table(self, status_info: Dict[str, Any]) -> None:
        """Display status in a nice table."""
        # Create status panel
        if status_info["is_running"]:
            status_icon = "🟢"
            status_text = "[green]Running[/green]"
        elif status_info["container_exists"]:
            status_icon = "🔴"
            status_text = "[red]Stopped[/red]"
        else:
            status_icon = "⚫"
            status_text = "[dim]Not Created[/dim]"
        
        console.print()
        console.print(Panel.fit(f"{status_icon} LlamaCPP Service Status", border_style="cyan"))
        
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        
        table.add_row("Status", status_text)
        
        if status_info["health"] != "unknown":
            health_color = {
                "healthy": "green",
                "unhealthy": "red",
                "starting": "yellow",
                "none": "dim"
            }.get(status_info["health"], "white")
            table.add_row("Health", f"[{health_color}]{status_info['health']}[/{health_color}]")
        
        if status_info["uptime"]:
            table.add_row("Uptime", status_info["uptime"])
        
        if status_info["memory_usage"]:
            table.add_row("Memory", status_info["memory_usage"])
        
        if status_info["ports"]:
            table.add_row("Ports", status_info["ports"])
        
        table.add_row("Config", f"[dim]{status_info['compose_file']}[/dim]")
        
        console.print(table)
        console.print()



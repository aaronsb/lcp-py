"""Docker Compose service management for llamacpp."""

import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

from .config import config_manager

console = Console()


class DockerManager:
    """Manages Docker Compose services for llamacpp."""
    
    def __init__(self):
        self.config = config_manager.load_config()
    
    def _run_compose_command(self, command: list[str], capture_output: bool = True) -> subprocess.CompletedProcess:
        """Run a docker-compose command in the configured directory."""
        if not self.config.docker.compose_dir:
            raise ValueError("Docker compose directory not configured")
        
        compose_dir = Path(self.config.docker.compose_dir)
        if not compose_dir.exists():
            raise FileNotFoundError(f"Docker compose directory not found: {compose_dir}")
        
        compose_file = compose_dir / "docker-compose.yml"
        if not compose_file.exists():
            raise FileNotFoundError(f"docker-compose.yml not found in {compose_dir}")
        
        # Build full command
        full_command = ["docker-compose", "-f", str(compose_file)] + command
        
        try:
            result = subprocess.run(
                full_command,
                cwd=compose_dir,
                capture_output=capture_output,
                text=True,
                check=False
            )
            return result
        except FileNotFoundError:
            raise RuntimeError("docker-compose not found. Please install Docker Compose.")
    
    def get_service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """Get status of llamacpp service."""
        service_name = service_name or self.config.docker.service_name
        
        try:
            result = self._run_compose_command(["ps", "--format", "json"])
            
            if result.returncode != 0:
                return {
                    "running": False,
                    "error": f"Failed to get service status: {result.stderr}",
                    "service_name": service_name
                }
            
            # Parse the output to find our service
            import json
            services = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        services.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            
            # Find our service
            for service in services:
                if service.get("Service") == service_name:
                    return {
                        "running": service.get("State") == "running",
                        "status": service.get("Status", "unknown"),
                        "service_name": service_name,
                        "container_name": service.get("Name"),
                        "ports": service.get("Ports", "")
                    }
            
            return {
                "running": False,
                "error": f"Service '{service_name}' not found in compose file",
                "service_name": service_name
            }
            
        except Exception as e:
            return {
                "running": False,
                "error": str(e),
                "service_name": service_name
            }
    
    def start_service(self, service_name: Optional[str] = None) -> bool:
        """Start the llamacpp service."""
        service_name = service_name or self.config.docker.service_name
        
        try:
            console.print(f"🚀 Starting {service_name} service...")
            result = self._run_compose_command(["up", "-d", service_name])
            
            if result.returncode == 0:
                console.print(f"✅ {service_name} service started successfully")
                return True
            else:
                console.print(f"❌ Failed to start {service_name}: {result.stderr}")
                return False
                
        except Exception as e:
            console.print(f"❌ Error starting {service_name}: {e}")
            return False
    
    def stop_service(self, service_name: Optional[str] = None) -> bool:
        """Stop the llamacpp service."""
        service_name = service_name or self.config.docker.service_name
        
        try:
            console.print(f"🛑 Stopping {service_name} service...")
            result = self._run_compose_command(["stop", service_name])
            
            if result.returncode == 0:
                console.print(f"✅ {service_name} service stopped successfully")
                return True
            else:
                console.print(f"❌ Failed to stop {service_name}: {result.stderr}")
                return False
                
        except Exception as e:
            console.print(f"❌ Error stopping {service_name}: {e}")
            return False
    
    def restart_service(self, service_name: Optional[str] = None) -> bool:
        """Restart the llamacpp service."""
        service_name = service_name or self.config.docker.service_name
        
        try:
            console.print(f"🔄 Restarting {service_name} service...")
            result = self._run_compose_command(["restart", service_name])
            
            if result.returncode == 0:
                console.print(f"✅ {service_name} service restarted successfully")
                return True
            else:
                console.print(f"❌ Failed to restart {service_name}: {result.stderr}")
                return False
                
        except Exception as e:
            console.print(f"❌ Error restarting {service_name}: {e}")
            return False
    
    def get_service_logs(self, service_name: Optional[str] = None, lines: int = 20) -> str:
        """Get recent logs from the llamacpp service."""
        service_name = service_name or self.config.docker.service_name
        
        try:
            result = self._run_compose_command(["logs", "--tail", str(lines), service_name])
            return result.stdout if result.returncode == 0 else result.stderr
            
        except Exception as e:
            return f"Error getting logs: {e}"
    
    def is_configured(self) -> bool:
        """Check if Docker Compose is properly configured."""
        return (
            self.config.docker.compose_dir is not None and
            Path(self.config.docker.compose_dir).exists() and
            (Path(self.config.docker.compose_dir) / "docker-compose.yml").exists()
        )


# Global instance
docker_manager = DockerManager()
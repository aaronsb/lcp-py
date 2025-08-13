"""Command-line interface for LCP."""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console

from . import __version__
from .core import core
from .config import config_manager
from .service import ServiceManager


console = Console()


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version and exit')
@click.pass_context
def cli(ctx, version):
    """🦙 LCP - LlamaCP Model Management and Chat Interface
    
    Advanced model management for llama.cpp with automatic downloads,
    smart model discovery, and streaming chat interface.
    """
    if version:
        console.print(f"LCP version {__version__}")
        sys.exit(0)
    
    if ctx.invoked_subcommand is None:
        console.print("🦙 [bold cyan]LCP - LlamaCP Model Manager[/bold cyan]")
        console.print()
        console.print("Use [bold]lcp --help[/bold] to see available commands")
        console.print("Quick start: [bold]lcp chat phi-3.5-mini[/bold]")


@cli.command()
def status():
    """Show LCP status and configuration."""
    core.show_status()


@cli.group()
def service():
    """Manage the llamacpp Docker service."""
    pass


@service.command(name="status")
def service_status():
    """Show Docker service status."""
    manager = ServiceManager(config_manager)
    status_info = manager.status()
    manager.show_status_table(status_info)


@service.command(name="start")
def service_start():
    """Start the Docker service."""
    manager = ServiceManager(config_manager)
    if manager.start():
        console.print("[green]✅ Service started successfully[/green]")
    else:
        console.print("[red]❌ Failed to start service[/red]")


@service.command(name="stop")
def service_stop():
    """Stop the Docker service."""
    manager = ServiceManager(config_manager)
    if manager.stop():
        console.print("[green]✅ Service stopped successfully[/green]")
    else:
        console.print("[red]❌ Failed to stop service[/red]")


@service.command(name="restart")
def service_restart():
    """Restart the Docker service."""
    manager = ServiceManager(config_manager)
    if manager.restart():
        console.print("[green]✅ Service restarted successfully[/green]")
        console.print("[yellow]⚠️  Model will be reloaded[/yellow]")
    else:
        console.print("[red]❌ Failed to restart service[/red]")


@service.command(name="enable")
def service_enable():
    """Enable auto-start for the service."""
    manager = ServiceManager(config_manager)
    manager.enable()


@service.command(name="disable")
def service_disable():
    """Disable auto-start for the service."""
    manager = ServiceManager(config_manager)
    manager.disable()


@service.command(name="logs")
@click.option('--lines', '-n', default=50, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def service_logs(lines: int, follow: bool):
    """Show service logs."""
    manager = ServiceManager(config_manager)
    manager.logs(lines=lines, follow=follow)


@cli.command()
@click.option('--limit', '-l', default=30, help='Maximum number of results')
@click.option('--no-download', '-n', is_flag=True, help='Just show results without download prompt')
@click.argument('query')
def search(query: str, limit: int, no_download: bool):
    """Search for models across all backends.
    
    By default, allows selecting a model to download.
    Use --no-download to just view results.
    """
    async def run_search():
        with console.status(f"🔍 Searching for '{query}'...", spinner="dots"):
            models = await core.search_models(query, limit)
        
        if not models:
            console.print(f"[yellow]No models found matching '{query}'[/yellow]")
            return
        
        console.print(f"\n[bold]Found {len(models)} model(s) for '{query}':[/bold]\n")
        
        # Get hardware profile for memory breakdown
        hardware = config_manager.get_hardware_profile()
        
        # Display models with numbers
        for i, model in enumerate(models, 1):
            console.print(f"{i:2d}. [cyan]{model.display_name}[/cyan]")
            console.print(f"    [bold white]{model.model_id}[/bold white]")
            
            if model.size_gb:
                from .hardware import create_memory_usage_bar
                memory_bar = create_memory_usage_bar(model.size_gb, hardware, width=30, enable_storage=False)
                console.print(f"    {memory_bar} {model.size_gb:.1f} GB")
            console.print()
        
        # By default, prompt for download selection (unless --no-download is set)
        if not no_download:
            console.print()
            try:
                choice = click.prompt("Select model number to download (or 0 to cancel)", type=int, default=0)
                
                if choice > 0 and choice <= len(models):
                    selected_model = models[choice - 1]
                    
                    console.print(f"\n[cyan]Downloading: {selected_model.display_name}[/cyan]")
                    console.print(f"[dim]{selected_model.model_id}[/dim]\n")
                    
                    try:
                        downloaded_path = await core.download_model(selected_model)
                        
                        # Ask if user wants to set as active
                        if click.confirm("Set as active model?", default=True):
                            if core.set_active_model(downloaded_path):
                                console.print(f"[green]✅ Set as active model[/green]")
                                console.print("[yellow]Run 'lcp service restart' to load the model[/yellow]")
                            else:
                                console.print(f"[yellow]⚠️  Failed to set as active model[/yellow]")
                    
                    except Exception as e:
                        console.print(f"[red]Download failed: {e}[/red]")
                
            except click.Abort:
                console.print("Cancelled")
    
    asyncio.run(run_search())


@cli.command()
@click.argument('model_name')
def download(model_name: str):
    """Download a specific model.
    
    Examples:
        lcp download phi-3.5-mini
        lcp download bartowski/phi-4-GGUF/phi-4-IQ2_M.gguf
    """
    async def run_download():
        with console.status(f"🔍 Finding model '{model_name}'...", spinner="dots"):
            model_info = await core.get_model(model_name)
        
        if not model_info:
            console.print(f"[red]Model not found: {model_name}[/red]")
            console.print()
            
            # Try to search for similar models
            console.print("[yellow]Searching for similar models...[/yellow]")
            search_results = await core.search_models(model_name, limit=5)
            
            if search_results:
                console.print("\n[bold]Did you mean one of these?[/bold]\n")
                for i, model in enumerate(search_results, 1):
                    console.print(f"{i}. {model.display_name}")
                    console.print(f"   [bold white]{model.model_id}[/bold white]")
                console.print()
                console.print("[bold]To download, copy and paste the model ID:[/bold]")
                console.print(f"  lcp download {search_results[0].model_id}")
            else:
                console.print("Try: [bold]lcp search <query>[/bold] to find available models")
            return
        
        console.print(f"[blue]Found: {model_info.display_name}[/blue]")
        
        try:
            downloaded_path = await core.download_model(model_info)
            
            # Ask if user wants to set as active
            if click.confirm("Set as active model?", default=True):
                if core.set_active_model(downloaded_path):
                    console.print(f"[green]✅ Set as active model[/green]")
                else:
                    console.print(f"[yellow]⚠️  Failed to set as active model[/yellow]")
        
        except Exception as e:
            console.print(f"[red]Download failed: {e}[/red]")
    
    asyncio.run(run_download())


@cli.command()
def list():
    """List downloaded models."""
    models = core.list_local_models()
    core.show_models_table(models)


@cli.command()
@click.argument('model_name', required=False)
def chat(model_name: Optional[str]):
    """Start chat with a model (downloads if needed).
    
    Examples:
        lcp chat                    # Chat with active model
        lcp chat phi-3.5-mini      # Download and chat with Phi-3.5
        lcp chat microsoft/Phi-3   # Use specific repo
    """
    asyncio.run(core.chat_with_model(model_name))


@cli.command()
def active():
    """Show or set the active model."""
    models = core.list_local_models()
    
    if not models:
        console.print("[yellow]No local models found[/yellow]")
        return
    
    # Show current active model
    active_models = [m for m in models if m.is_active]
    
    if active_models:
        console.print(f"[green]Current active model: {active_models[0].name}[/green]")
    else:
        console.print("[yellow]No active model set[/yellow]")
    
    console.print("\n[bold]Available models:[/bold]")
    
    for i, model in enumerate(models, 1):
        status = " (active)" if model.is_active else ""
        console.print(f"{i:2d}. {model.name}{status}")
    
    console.print()
    
    try:
        choice = click.prompt("Select model number (or press Enter to cancel)", type=int, default=0)
        
        if choice > 0 and choice <= len(models):
            selected_model = models[choice - 1]
            
            if core.set_active_model(selected_model.path):
                console.print(f"[green]✅ Set active model: {selected_model.name}[/green]")
                console.print("[yellow]⚠️  Restart your llamacpp container to load the model[/yellow]")
            else:
                console.print("[red]❌ Failed to set active model[/red]")
    
    except click.Abort:
        console.print("Cancelled")


@cli.command()
def remove():
    """Remove a downloaded model."""
    models = core.list_local_models()
    
    if not models:
        console.print("[yellow]No local models found[/yellow]")
        return
    
    console.print("[bold]Local models:[/bold]\n")
    
    for i, model in enumerate(models, 1):
        status = " (active)" if model.is_active else ""
        size_str = f"{model.size_gb:.1f} GB"
        console.print(f"{i:2d}. [cyan]{model.name}[/cyan]{status} - [green]{size_str}[/green]")
    
    console.print()
    
    try:
        choice = click.prompt("Select model number to remove (or 0 to cancel)", type=int, default=0)
        
        if choice > 0 and choice <= len(models):
            selected_model = models[choice - 1]
            
            if click.confirm(f"Delete '{selected_model.name}'?", default=False):
                if core.remove_model(selected_model.path):
                    console.print(f"[green]✅ Removed: {selected_model.name}[/green]")
                else:
                    console.print(f"[red]❌ Failed to remove model[/red]")
    
    except click.Abort:
        console.print("Cancelled")


@cli.group()
def config():
    """Configuration management."""
    pass


@config.command('show')
def config_show():
    """Show current configuration."""
    config_data = config_manager.load_config()
    
    console.print("[bold]Current Configuration:[/bold]\n")
    console.print(f"Models Directory: [cyan]{config_data.models_dir}[/cyan]")
    console.print(f"API Base URL: [cyan]{config_data.api.base_url}[/cyan]")
    console.print(f"Streaming: [green]{'enabled' if config_data.api.streaming else 'disabled'}[/green]")
    console.print(f"GPU Strategy: [cyan]{config_data.docker.gpu_strategy}[/cyan]")
    if config_data.docker.gpu_strategy == "auto-percentage":
        console.print(f"VRAM Usage: [cyan]{config_data.docker.gpu_vram_percentage}%[/cyan]")


@config.command('gpu')
@click.argument('strategy', type=click.Choice(['gpu-only', 'cpu-only', 'auto-maximize', 'auto-percentage']))
@click.option('--percentage', '-p', type=int, default=80, help='For auto-percentage: % of VRAM to use (0-100)')
def config_gpu(strategy: str, percentage: int):
    """Configure GPU memory allocation strategy.
    
    Strategies:
    - gpu-only: Force all layers to GPU (may fail if model too large)
    - cpu-only: Force all layers to CPU (minimal GPU usage)
    - auto-maximize: Fit as many layers as possible in VRAM (default)
    - auto-percentage: Use specified percentage of total VRAM
    
    Examples:
        lcp config gpu auto-maximize         # Use as much VRAM as possible
        lcp config gpu auto-percentage -p 50  # Use 50% of VRAM
        lcp config gpu cpu-only               # CPU inference only
    """
    config_data = config_manager.load_config()
    
    # Update configuration
    config_data.docker.gpu_strategy = strategy
    if strategy == "auto-percentage":
        config_data.docker.gpu_vram_percentage = max(0, min(100, percentage))
    
    # Save configuration
    config_manager.save_config()
    
    # Get hardware info for display
    hardware = config_manager.get_hardware_profile()
    vram_mb = hardware.total_vram_gb * 1024
    
    # Show updated strategy
    console.print(f"[green]✅ GPU strategy set to: {strategy}[/green]")
    
    if strategy == "gpu-only":
        console.print("🚀 Will force all layers to GPU (may fail if model doesn't fit)")
    elif strategy == "cpu-only":
        console.print("📏 Will use CPU only (no GPU acceleration)")
    elif strategy == "auto-maximize":
        console.print(f"🎯 Will fit as many layers as possible in {vram_mb:.0f}MB VRAM")
    elif strategy == "auto-percentage":
        target_mb = vram_mb * (percentage / 100)
        console.print(f"📊 Will use {percentage}% of VRAM ({target_mb:.0f}MB of {vram_mb:.0f}MB)")
    
    console.print("\n[yellow]Run 'lcp service restart' to apply changes[/yellow]")
    console.print()
    
    console.print("[bold]Backends:[/bold]")
    for backend in config_data.backends:
        status = "[green]enabled[/green]" if backend.enabled else "[red]disabled[/red]"
        console.print(f"  {backend.name}: {status}")
    
    console.print()
    console.print(f"[dim]Config file: {config_manager.config_file}[/dim]")


@config.command('edit')
def config_edit():
    """Edit configuration file."""
    import subprocess


@config.group()
def hwprofile():
    """Hardware profiling for intelligent model selection."""
    pass


@hwprofile.command('show')
def hwprofile_show():
    """Show current hardware profile."""
    from rich.table import Table
    from rich.panel import Panel
    
    profile = config_manager.get_hardware_profile()
    
    console.print()
    console.print(Panel.fit("🖥️  Hardware Profile", border_style="cyan"))
    console.print()
    
    # System Information
    console.print("[bold]System Information:[/bold]")
    console.print(f"  Platform: [cyan]{profile.platform}[/cyan]")
    console.print(f"  CPU: [cyan]{profile.cpu_model}[/cyan]")
    console.print(f"  Cores: [cyan]{profile.cpu_cores}[/cyan] physical, [cyan]{profile.cpu_threads}[/cyan] threads")
    console.print()
    
    # Memory Information
    console.print("[bold]Memory:[/bold]")
    console.print(f"  System RAM: [cyan]{profile.system_ram_gb:.1f} GB[/cyan] total, [green]{profile.available_ram_gb:.1f} GB[/green] available")
    if profile.gpu_count > 0:
        console.print(f"  GPU VRAM: [cyan]{profile.total_vram_gb:.1f} GB[/cyan] total, [green]{profile.available_vram_gb:.1f} GB[/green] available")
        for i, gpu_model in enumerate(profile.gpu_models):
            console.print(f"    GPU {i+1}: [cyan]{gpu_model}[/cyan]")
    else:
        console.print("  No GPUs detected")
    console.print()
    
    # Storage Information  
    console.print("[bold]Storage:[/bold]")
    console.print(f"  Available: [cyan]{profile.available_storage_gb:.1f} GB[/cyan]")
    console.print(f"  Type: [cyan]{profile.storage_type}[/cyan]")
    console.print()
    
    # Recommendations
    console.print("[bold]Recommendations:[/bold]")
    console.print(f"  Max Model Size: [green]{profile.recommended_max_model_size_gb:.1f} GB[/green]")
    console.print(f"  GPU Offloading: [green]{'Yes' if profile.can_offload_to_gpu else 'No'}[/green]")
    console.print(f"  Optimal Quantization: [cyan]{profile.optimal_quantization}[/cyan]")
    console.print()
    
    if profile.profile_date:
        from datetime import datetime
        try:
            profile_date = datetime.fromisoformat(profile.profile_date)
            formatted_date = profile_date.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"[dim]Profile created: {formatted_date}[/dim]")
        except:
            console.print(f"[dim]Profile created: {profile.profile_date}[/dim]")


@hwprofile.command('update')
@click.option('--stop-service/--keep-service', default=False, 
              help='Stop llamacpp service during profiling for accurate GPU memory detection')
def hwprofile_update(stop_service: bool):
    """Update hardware profile with current system information."""
    from .docker_manager import docker_manager
    
    service_was_running = False
    
    if stop_service and docker_manager.is_configured():
        # Check if service is running
        status = docker_manager.get_service_status()
        service_was_running = status.get('running', False)
        
        if service_was_running:
            console.print("🛑 Stopping llamacpp service for accurate GPU profiling...")
            docker_manager.stop_service()
            console.print("   Waiting for GPU memory to be released...")
            import time
            time.sleep(3)  # Give time for GPU memory to be released
    
    try:
        with console.status("🔧 Profiling hardware...", spinner="dots"):
            profile = config_manager.update_hardware_profile()
        
        console.print("[green]✅ Hardware profile updated![/green]")
        console.print()
        
        # Show key changes
        console.print(f"Max recommended model size: [green]{profile.recommended_max_model_size_gb:.1f} GB[/green]")
        console.print(f"GPU offloading: [green]{'Available' if profile.can_offload_to_gpu else 'Not available'}[/green]")
        console.print(f"Optimal quantization: [cyan]{profile.optimal_quantization}[/cyan]")
        
        if profile.can_offload_to_gpu:
            console.print(f"Available VRAM: [green]{profile.available_vram_gb:.1f} GB[/green] of {profile.total_vram_gb:.1f} GB total")
    
    finally:
        # Restart service if it was running before
        if stop_service and service_was_running and docker_manager.is_configured():
            console.print()
            console.print("🚀 Restarting llamacpp service...")
            docker_manager.start_service()


@config.command('edit')
def config_edit():
    """Edit configuration file."""
    import subprocess
    import os
    
    config_file = config_manager.config_file
    
    # Create default config if it doesn't exist
    if not config_file.exists():
        config_manager.save_config()
    
    # Try to open with user's preferred editor
    editor = os.environ.get('EDITOR', 'nano')
    
    try:
        subprocess.run([editor, str(config_file)], check=True)
        console.print(f"[green]✅ Configuration updated[/green]")
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(f"[yellow]Could not open editor. Edit manually: {config_file}[/yellow]")


@config.group()
def docker():
    """Docker Compose service management."""
    pass


@docker.command('setup')
@click.argument('compose_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--service-name', '-s', default='llamacpp', help='Service name in docker-compose.yml')
@click.option('--auto-manage/--no-auto-manage', default=False, help='Automatically manage service')
def docker_setup(compose_dir: str, service_name: str, auto_manage: bool):
    """Setup Docker Compose integration."""
    from pathlib import Path
    
    compose_path = Path(compose_dir).resolve()
    compose_file = compose_path / "docker-compose.yml"
    
    if not compose_file.exists():
        console.print(f"[red]docker-compose.yml not found in {compose_path}[/red]")
        return
    
    # Update config
    config = config_manager.load_config()
    config.docker.compose_dir = str(compose_path)
    config.docker.service_name = service_name
    config.docker.auto_manage = auto_manage
    
    config_manager._config = config
    config_manager.save_config()
    
    console.print(f"✅ Docker Compose integration configured")
    console.print(f"   Directory: [cyan]{compose_path}[/cyan]")
    console.print(f"   Service: [cyan]{service_name}[/cyan]")
    console.print(f"   Auto-manage: [cyan]{'enabled' if auto_manage else 'disabled'}[/cyan]")


@docker.command('status')
def docker_status():
    """Show Docker service status."""
    from .docker_manager import docker_manager
    
    if not docker_manager.is_configured():
        console.print("[red]Docker Compose not configured. Run: lcp config docker setup <path>[/red]")
        return
    
    status = docker_manager.get_service_status()
    service_name = status.get('service_name', 'llamacpp')
    
    console.print(f"\n🐳 [bold]Docker Service Status:[/bold]")
    console.print(f"   Service: [cyan]{service_name}[/cyan]")
    
    if status.get('error'):
        console.print(f"   Status: [red]Error - {status['error']}[/red]")
    elif status.get('running'):
        console.print(f"   Status: [green]Running[/green]")
        console.print(f"   Container: [cyan]{status.get('container_name', 'unknown')}[/cyan]")
        if status.get('ports'):
            console.print(f"   Ports: [cyan]{status.get('ports')}[/cyan]")
    else:
        console.print(f"   Status: [yellow]Stopped[/yellow]")


@docker.command('start')
def docker_start():
    """Start the llamacpp service."""
    from .docker_manager import docker_manager
    
    if not docker_manager.is_configured():
        console.print("[red]Docker Compose not configured. Run: lcp config docker setup <path>[/red]")
        return
    
    docker_manager.start_service()


@docker.command('stop') 
def docker_stop():
    """Stop the llamacpp service."""
    from .docker_manager import docker_manager
    
    if not docker_manager.is_configured():
        console.print("[red]Docker Compose not configured. Run: lcp config docker setup <path>[/red]")
        return
    
    docker_manager.stop_service()


@docker.command('restart')
def docker_restart():
    """Restart the llamacpp service."""
    from .docker_manager import docker_manager
    
    if not docker_manager.is_configured():
        console.print("[red]Docker Compose not configured. Run: lcp config docker setup <path>[/red]")
        return
    
    docker_manager.restart_service()


@docker.command('logs')
@click.option('--lines', '-n', default=20, help='Number of log lines to show')
def docker_logs(lines: int):
    """Show service logs."""
    from .docker_manager import docker_manager
    
    if not docker_manager.is_configured():
        console.print("[red]Docker Compose not configured. Run: lcp config docker setup <path>[/red]")
        return
    
    console.print(f"\n📋 [bold]Service Logs (last {lines} lines):[/bold]")
    logs = docker_manager.get_service_logs(lines=lines)
    console.print(logs)


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
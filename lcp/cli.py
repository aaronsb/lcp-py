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
    """Show system status and configuration."""
    core.show_status()


@cli.command()
@click.option('--limit', '-l', default=10, help='Maximum number of results')
@click.argument('query')
def search(query: str, limit: int):
    """Search for models across all backends."""
    async def run_search():
        with console.status(f"🔍 Searching for '{query}'...", spinner="dots"):
            models = await core.search_models(query, limit)
        
        if not models:
            console.print(f"[yellow]No models found matching '{query}'[/yellow]")
            return
        
        console.print(f"\n[bold]Found {len(models)} model(s) for '{query}':[/bold]\n")
        
        for i, model in enumerate(models, 1):
            console.print(f"{i:2d}. [cyan]{model.display_name}[/cyan]")
            console.print(f"    [dim]{model.repo_id}/{model.filename}[/dim]")
            if model.size_gb:
                console.print(f"    [green]{model.size_gb:.1f} GB[/green]")
            console.print()
    
    asyncio.run(run_search())


@cli.command()
@click.argument('model_name')
def download(model_name: str):
    """Download a specific model."""
    async def run_download():
        with console.status(f"🔍 Finding model '{model_name}'...", spinner="dots"):
            model_info = await core.get_model(model_name)
        
        if not model_info:
            console.print(f"[red]Model not found: {model_name}[/red]")
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
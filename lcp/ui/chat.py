"""Streaming chat interface with rich terminal UI."""

import asyncio
import json
from typing import Optional, AsyncGenerator, Dict, Any
import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from datetime import datetime

from ..models import ChatMessage, ChatSession
from ..config import config_manager


class StreamingChatInterface:
    """Rich terminal interface for streaming chat."""
    
    def __init__(self):
        self.console = Console()
        self.config = config_manager.load_config()
        self.session: Optional[ChatSession] = None
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    def start_session(self, model_name: str) -> None:
        """Start a new chat session."""
        self.session = ChatSession(
            messages=[],
            model_name=model_name,
            started_at=datetime.now()
        )
        
        self.console.print()
        self.console.print(Panel.fit(
            f"💬 Chat Session Started\n"
            f"Model: [bold cyan]{model_name}[/bold cyan]\n"
            f"Time: [dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            title="LCP Chat",
            border_style="blue"
        ))
        self.console.print()
        
        self.console.print("[dim]Type 'quit', 'exit', or press Ctrl+C to exit[/dim]")
        self.console.print("[dim]Type '/clear' to clear conversation history[/dim]")
        self.console.print("[dim]Type '/help' for more commands[/dim]")
        self.console.print()
    
    async def chat_loop(self) -> None:
        """Main chat loop with streaming responses."""
        if not self.session:
            raise ValueError("No active chat session")
        
        try:
            while True:
                # Get user input
                user_input = await self._get_user_input()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.startswith('/'):
                    if await self._handle_command(user_input):
                        continue
                    else:
                        break
                
                # Handle quit commands
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                # Add user message
                user_msg = ChatMessage.user(user_input)
                self.session.add_message(user_msg)
                
                # Get streaming response
                await self._get_streaming_response()
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Chat interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
    
    async def _get_user_input(self) -> str:
        """Get user input asynchronously."""
        # Note: In a real implementation, you'd want true async input
        # For now, using sync input which blocks
        try:
            prompt = Text("You: ", style="bold green")
            self.console.print(prompt, end="")
            return input()
        except EOFError:
            return "quit"
    
    async def _handle_command(self, command: str) -> bool:
        """Handle special chat commands. Returns True to continue, False to exit."""
        command = command.lower().strip()
        
        if command == '/clear':
            self.session.clear_history()
            self.console.clear()
            self.console.print("[green]✅ Conversation history cleared[/green]")
            return True
        
        elif command == '/help':
            self._show_help()
            return True
        
        elif command == '/stats':
            self._show_stats()
            return True
        
        elif command in ['/quit', '/exit']:
            return False
        
        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
            self.console.print("[dim]Type '/help' for available commands[/dim]")
            return True
    
    def _show_help(self) -> None:
        """Show help for chat commands."""
        help_text = """
[bold]Available Commands:[/bold]
  /clear    Clear conversation history
  /stats    Show session statistics  
  /help     Show this help message
  /quit     Exit chat session
  
[bold]Other ways to exit:[/bold]
  quit, exit, bye, or Ctrl+C
        """
        self.console.print(Panel(help_text.strip(), title="Help", border_style="blue"))
    
    def _show_stats(self) -> None:
        """Show session statistics."""
        if not self.session:
            return
        
        duration = datetime.now() - self.session.started_at
        stats_text = f"""
[bold]Session Statistics:[/bold]
  Model: [cyan]{self.session.model_name}[/cyan]
  Duration: [yellow]{str(duration).split('.')[0]}[/yellow]
  Messages: [green]{len(self.session.messages)}[/green]
  Total Tokens: [blue]{self.session.total_tokens}[/blue]
        """
        self.console.print(Panel(stats_text.strip(), title="Stats", border_style="green"))
    
    async def _get_streaming_response(self) -> None:
        """Get streaming response from the API."""
        if not self.client or not self.session:
            return
        
        # Prepare API request
        messages = self.session.get_context_messages()
        
        request_data = {
            "model": self.session.model_name,
            "messages": messages,
            "stream": True,
            "max_tokens": self.config.api.max_tokens,
            "temperature": self.config.api.temperature,
            "top_p": self.config.api.top_p,
        }
        
        # Show "Assistant is typing..." indicator
        with self.console.status("[dim]Assistant is thinking...[/dim]", spinner="dots"):
            await asyncio.sleep(0.5)  # Brief pause for UX
        
        self.console.print("Assistant: ", style="bold blue", end="")
        
        # Stream the response
        response_text = ""
        token_count = 0
        start_time = datetime.now()
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.config.api.base_url}/v1/chat/completions",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    self.console.print(f"[red]API Error: {response.status_code}[/red]")
                    self.console.print(f"[red]{error_text.decode()}[/red]")
                    return
                
                # Process streaming chunks
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk_data = line[6:]  # Remove "data: " prefix
                        
                        if chunk_data.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(chunk_data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            
                            if content:
                                response_text += content
                                token_count += 1
                                
                                # Print content as it arrives
                                self.console.print(content, end="", highlight=False)
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            self.console.print(f"[red]\nStreaming error: {e}[/red]")
            return
        
        # Finish the response
        self.console.print()  # New line after response
        
        # Calculate timing
        duration = datetime.now() - start_time
        tokens_per_second = token_count / duration.total_seconds() if duration.total_seconds() > 0 else 0
        
        # Show timing info if enabled
        if self.config.ui.show_timing and token_count > 0:
            timing_text = f"[dim]({token_count} tokens, {tokens_per_second:.1f} tok/s, {duration.total_seconds():.1f}s)[/dim]"
            self.console.print(timing_text)
        
        # Add assistant message to session
        if response_text:
            assistant_msg = ChatMessage.assistant(response_text, token_count)
            self.session.add_message(assistant_msg)
        
        self.console.print()  # Extra space before next input
    
    def show_error(self, message: str) -> None:
        """Show an error message."""
        self.console.print(f"[red]❌ {message}[/red]")
    
    def show_success(self, message: str) -> None:
        """Show a success message."""
        self.console.print(f"[green]✅ {message}[/green]")
    
    def show_info(self, message: str) -> None:
        """Show an info message."""
        self.console.print(f"[blue]ℹ️  {message}[/blue]")
"""Rich Live Streaming Markdown Renderer

Uses Rich's canonical Live display pattern for streaming markdown,
based on the proven Pydantic AI implementation.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text


class RichLiveStreamingRenderer:
    """Uses Rich's Live display for streaming markdown - the canonical approach.
    
    Based on Pydantic AI's proven pattern: accumulate content in buffer
    and update Live display with complete markdown on each token.
    """
    
    def __init__(self, console: Console, ui_config=None):
        self.console = console
        self.buffer = ""
        self.live_display = None
        
        # Use provided config or load default
        if ui_config is None:
            from ..config import config_manager
            ui_config = config_manager.load_config().ui
        
        self.code_theme = ui_config.markdown_code_theme
        self.inline_code_theme = ui_config.markdown_inline_code_theme
        self.enable_hyperlinks = ui_config.enable_hyperlinks
        self.enable_tables = ui_config.enable_markdown_tables
    
    def start_live_display(self):
        """Start Live display for streaming markdown updates."""
        self.live_display = Live(
            Text("", style="dim"),
            console=self.console,
            refresh_per_second=4,  # Reasonable refresh rate
            vertical_overflow="visible"
        )
        self.live_display.start()
    
    def add_content(self, content: str) -> None:
        """Add content and update Live display - Pydantic AI pattern."""
        self.buffer += content
        
        if self.live_display and self.buffer.strip():
            try:
                # Render complete buffer as markdown - let Rich handle everything
                markdown = Markdown(
                    self.buffer,
                    code_theme=self.code_theme,
                    hyperlinks=self.enable_hyperlinks,
                    inline_code_theme=self.inline_code_theme
                )
                # This is the key pattern from Pydantic AI: live.update(Markdown(message))
                self.live_display.update(markdown)
                
            except Exception:
                # Fallback to plain text if markdown parsing fails
                plain_text = Text(self.buffer, style="default")
                self.live_display.update(plain_text)
    
    def finalize(self) -> None:
        """Stop Live display and ensure final content is in scrollback."""
        if self.live_display:
            # Stop the live display
            self.live_display.stop()
            
            # Print final content to permanent scrollback
            if self.buffer.strip():
                try:
                    markdown = Markdown(
                        self.buffer,
                        code_theme=self.code_theme,
                        hyperlinks=self.enable_hyperlinks,
                        inline_code_theme=self.inline_code_theme
                    )
                    self.console.print(markdown)
                    
                except Exception:
                    plain_text = Text(self.buffer, style="default")
                    self.console.print(plain_text)
            
            self.console.print()  # Final newline


class StreamingMarkdownRenderer:
    """Wrapper to maintain API compatibility."""
    
    def __init__(self, console: Console, ui_config=None):
        self.renderer = RichLiveStreamingRenderer(console, ui_config)
    
    def start_live_display(self):
        return self.renderer.start_live_display()
    
    def add_content(self, content: str) -> None:
        return self.renderer.add_content(content)
    
    def finalize(self) -> None:
        return self.renderer.finalize()
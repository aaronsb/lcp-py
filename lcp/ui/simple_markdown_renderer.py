"""Unified Markdown and ANSI Streaming Renderer

Combines Rich's canonical Live display pattern for markdown with
ANSI escape sequence processing for a complete rendering solution.
"""

import re
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text


class UnifiedStreamingRenderer:
    """Unified renderer that handles both markdown and ANSI content seamlessly.
    
    Intelligently detects content type and applies appropriate rendering:
    - Markdown content uses Rich's Markdown class
    - ANSI content uses Text.from_ansi() conversion
    - Mixed content is handled gracefully
    """
    
    def __init__(self, console: Console, ui_config=None):
        self.console = console
        self.buffer = ""
        self.live_display = None
        self.content_type = None  # 'markdown', 'ansi', or 'mixed'
        
        # ANSI detection pattern
        self.ansi_pattern = re.compile(r'\x1b\[[0-9;]*[mGKHF]')
        
        # Use provided config or load default
        if ui_config is None:
            from ..config import config_manager
            ui_config = config_manager.load_config().ui
        
        self.code_theme = ui_config.markdown_code_theme
        self.inline_code_theme = ui_config.markdown_inline_code_theme
        self.enable_hyperlinks = ui_config.enable_hyperlinks
        self.enable_tables = ui_config.enable_markdown_tables
    
    def _detect_content_type(self) -> str:
        """Detect whether buffer contains markdown, ANSI, or mixed content."""
        has_ansi = bool(self.ansi_pattern.search(self.buffer))
        
        # Check for markdown indicators
        markdown_indicators = [
            r'^#{1,6}\s',  # Headers
            r'^\*{1,2}[^\*\n]+\*{1,2}',  # Bold/italic
            r'^```',  # Code blocks
            r'^\|.*\|',  # Tables
            r'^[-*+]\s',  # Lists
            r'^\d+\.\s',  # Numbered lists
            r'\[([^\]]+)\]\(([^)]+)\)',  # Links
        ]
        
        has_markdown = any(
            re.search(pattern, self.buffer, re.MULTILINE) 
            for pattern in markdown_indicators
        )
        
        if has_ansi and has_markdown:
            return 'mixed'
        elif has_ansi:
            return 'ansi'
        elif has_markdown:
            return 'markdown'
        else:
            return 'plain'
    
    def start_live_display(self):
        """Start Live display for streaming updates."""
        self.live_display = Live(
            Text("", style="dim"),
            console=self.console,
            refresh_per_second=4,  # Reasonable refresh rate
            vertical_overflow="visible"
        )
        self.live_display.start()
    
    def add_content(self, content: str) -> None:
        """Add content and update Live display with intelligent rendering."""
        self.buffer += content
        
        if self.live_display and self.buffer.strip():
            # Detect content type
            content_type = self._detect_content_type()
            
            try:
                if content_type == 'ansi':
                    # Pure ANSI content - use Text.from_ansi()
                    rich_text = Text.from_ansi(self.buffer)
                    self.live_display.update(rich_text)
                    
                elif content_type == 'markdown':
                    # Pure markdown - use Rich's Markdown class
                    markdown = Markdown(
                        self.buffer,
                        code_theme=self.code_theme,
                        hyperlinks=self.enable_hyperlinks,
                        inline_code_theme=self.inline_code_theme
                    )
                    self.live_display.update(markdown)
                    
                elif content_type == 'mixed':
                    # Mixed content - try to handle intelligently
                    # For now, prioritize ANSI as it's more fragile
                    rich_text = Text.from_ansi(self.buffer)
                    self.live_display.update(rich_text)
                    
                else:
                    # Plain text
                    plain_text = Text(self.buffer, style="default")
                    self.live_display.update(plain_text)
                    
            except Exception:
                # Fallback to plain text if any processing fails
                plain_text = Text(self.buffer, style="default")
                self.live_display.update(plain_text)
    
    def finalize(self) -> None:
        """Stop Live display and ensure final content is in scrollback."""
        if self.live_display:
            # Stop the live display
            self.live_display.stop()
            
            # Print final content to permanent scrollback
            if self.buffer.strip():
                content_type = self._detect_content_type()
                
                try:
                    if content_type == 'ansi':
                        rich_text = Text.from_ansi(self.buffer)
                        self.console.print(rich_text)
                        
                    elif content_type == 'markdown':
                        markdown = Markdown(
                            self.buffer,
                            code_theme=self.code_theme,
                            hyperlinks=self.enable_hyperlinks,
                            inline_code_theme=self.inline_code_theme
                        )
                        self.console.print(markdown)
                        
                    elif content_type == 'mixed':
                        # For mixed content, use ANSI processing
                        rich_text = Text.from_ansi(self.buffer)
                        self.console.print(rich_text)
                        
                    else:
                        self.console.print(Text(self.buffer))
                        
                except Exception:
                    # Fallback to plain text
                    self.console.print(Text(self.buffer))
            
            self.console.print()  # Final newline


# Backward compatibility - keep the old class name as alias
RichLiveStreamingRenderer = UnifiedStreamingRenderer


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
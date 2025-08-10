"""ANSI Processing Module for Rich Integration

Handles ANSI escape sequences from external sources (commands, tools, etc.)
and converts them to Rich-compatible format for proper display.
"""

from typing import Optional, Union
from rich.console import Console
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
import re


class ANSIProcessor:
    """Process ANSI escape sequences and convert to Rich format."""
    
    def __init__(self, console: Console):
        self.console = console
        
        # Common ANSI patterns
        self.ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        self.color_256_pattern = re.compile(r'\x1b\[38;5;(\d+)m')
        self.rgb_pattern = re.compile(r'\x1b\[38;2;(\d+);(\d+);(\d+)m')
        
    def process_ansi_text(self, text: str) -> Text:
        """Convert ANSI-formatted text to Rich Text object.
        
        Args:
            text: String containing ANSI escape sequences
            
        Returns:
            Rich Text object with preserved formatting
        """
        try:
            # Use Rich's built-in ANSI to Text conversion
            return Text.from_ansi(text)
        except Exception as e:
            # Fallback to plain text if conversion fails
            clean_text = self.strip_ansi(text)
            return Text(clean_text)
    
    def strip_ansi(self, text: str) -> str:
        """Remove all ANSI escape sequences from text.
        
        Args:
            text: String potentially containing ANSI codes
            
        Returns:
            Clean string without ANSI codes
        """
        # Remove all ANSI escape sequences
        clean = self.ansi_pattern.sub('', text)
        clean = self.color_256_pattern.sub('', clean)
        clean = self.rgb_pattern.sub('', clean)
        
        # Remove other common escape sequences
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', clean)
        clean = re.sub(r'\x1b\].*?\x07', '', clean)  # OSC sequences
        clean = re.sub(r'\x1b[PX^_].*?\x1b\\', '', clean)  # Other escape sequences
        
        return clean
    
    def detect_content_type(self, text: str) -> str:
        """Detect if text contains ANSI codes, markdown, or plain text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Content type: 'ansi', 'markdown', or 'plain'
        """
        # Check for ANSI codes
        if self.ansi_pattern.search(text):
            return 'ansi'
        
        # Check for markdown indicators
        markdown_indicators = [
            r'^#{1,6}\s',  # Headers
            r'^\*{1,2}[^\*]+\*{1,2}',  # Bold/italic
            r'^```',  # Code blocks
            r'^\|.*\|',  # Tables
            r'^[-*+]\s',  # Lists
            r'^\d+\.\s',  # Numbered lists
        ]
        
        for pattern in markdown_indicators:
            if re.search(pattern, text, re.MULTILINE):
                return 'markdown'
        
        return 'plain'
    
    def render_mixed_content(self, text: str) -> None:
        """Intelligently render content based on detected type.
        
        Args:
            text: Content to render (may contain ANSI, markdown, or plain text)
        """
        content_type = self.detect_content_type(text)
        
        if content_type == 'ansi':
            # Convert ANSI to Rich Text and render
            rich_text = self.process_ansi_text(text)
            self.console.print(rich_text)
            
        elif content_type == 'markdown':
            # Render as markdown
            try:
                md = Markdown(text)
                self.console.print(md)
            except Exception:
                # Fallback to plain text
                self.console.print(text)
                
        else:
            # Plain text
            self.console.print(text)


class CommandOutputProcessor:
    """Process output from shell commands and external tools."""
    
    def __init__(self, console: Console):
        self.console = console
        self.ansi_processor = ANSIProcessor(console)
        
        # Patterns for common command outputs
        self.error_patterns = [
            re.compile(r'error:', re.IGNORECASE),
            re.compile(r'failed:', re.IGNORECASE),
            re.compile(r'fatal:', re.IGNORECASE),
        ]
        
        self.warning_patterns = [
            re.compile(r'warning:', re.IGNORECASE),
            re.compile(r'warn:', re.IGNORECASE),
        ]
        
        self.success_patterns = [
            re.compile(r'success:', re.IGNORECASE),
            re.compile(r'completed:', re.IGNORECASE),
            re.compile(r'✓|✔|√', re.IGNORECASE),
        ]
    
    def process_command_output(self, output: str, command: Optional[str] = None) -> None:
        """Process and display command output with proper formatting.
        
        Args:
            output: Command output string (may contain ANSI codes)
            command: Optional command that was executed
        """
        # Check if output contains ANSI codes
        if self.ansi_processor.detect_content_type(output) == 'ansi':
            # Process ANSI codes
            rich_text = self.ansi_processor.process_ansi_text(output)
            
            # Apply semantic highlighting based on content
            self._apply_semantic_styles(rich_text)
            
            # Display in a panel if command is provided
            if command:
                panel = Panel(
                    rich_text,
                    title=f"[bold cyan]$ {command}[/bold cyan]",
                    border_style="blue"
                )
                self.console.print(panel)
            else:
                self.console.print(rich_text)
        else:
            # Plain text output
            if command:
                self.console.print(f"[bold cyan]$ {command}[/bold cyan]")
            self.console.print(output)
    
    def _apply_semantic_styles(self, text: Text) -> None:
        """Apply semantic highlighting to text based on content patterns.
        
        Args:
            text: Rich Text object to modify in-place
        """
        plain_text = text.plain
        
        # Check for error patterns
        for pattern in self.error_patterns:
            for match in pattern.finditer(plain_text):
                text.stylize("bold red", match.start(), match.end())
        
        # Check for warning patterns
        for pattern in self.warning_patterns:
            for match in pattern.finditer(plain_text):
                text.stylize("bold yellow", match.start(), match.end())
        
        # Check for success patterns
        for pattern in self.success_patterns:
            for match in pattern.finditer(plain_text):
                text.stylize("bold green", match.start(), match.end())
    
    def format_code_output(self, code: str, language: str = "python") -> Syntax:
        """Format code output with syntax highlighting.
        
        Args:
            code: Code string (may contain ANSI codes)
            language: Programming language for syntax highlighting
            
        Returns:
            Syntax object for rendering
        """
        # Strip ANSI codes from code
        clean_code = self.ansi_processor.strip_ansi(code)
        
        return Syntax(
            clean_code,
            language,
            theme="monokai",
            line_numbers=True
        )


class ANSIStreamingRenderer:
    """Streaming renderer that handles mixed ANSI/markdown content."""
    
    def __init__(self, console: Console, ui_config=None):
        self.console = console
        self.ansi_processor = ANSIProcessor(console)
        self.buffer = ""
        self.is_ansi_mode = False
        
        # Rich Live display for streaming
        from rich.live import Live
        self.live_display = None
        
        # Load config
        if ui_config is None:
            from ..config import config_manager
            ui_config = config_manager.load_config().ui
        
        self.ui_config = ui_config
    
    def start_live_display(self):
        """Start Live display for streaming updates."""
        from rich.live import Live
        
        self.live_display = Live(
            Text("", style="dim"),
            console=self.console,
            refresh_per_second=4,
            vertical_overflow="visible"
        )
        self.live_display.start()
    
    def add_content(self, content: str) -> None:
        """Add content and update display, handling ANSI codes intelligently."""
        self.buffer += content
        
        # Detect if we're in ANSI mode
        if not self.is_ansi_mode and '\x1b[' in content:
            self.is_ansi_mode = True
        
        if self.live_display and self.buffer.strip():
            try:
                if self.is_ansi_mode:
                    # Process as ANSI text
                    rich_text = self.ansi_processor.process_ansi_text(self.buffer)
                    self.live_display.update(rich_text)
                else:
                    # Process as markdown
                    markdown = Markdown(
                        self.buffer,
                        code_theme=self.ui_config.markdown_code_theme,
                        hyperlinks=self.ui_config.enable_hyperlinks
                    )
                    self.live_display.update(markdown)
                    
            except Exception:
                # Fallback to plain text
                plain_text = Text(self.buffer, style="default")
                self.live_display.update(plain_text)
    
    def finalize(self) -> None:
        """Stop live display and render final content."""
        if self.live_display:
            self.live_display.stop()
            
            # Render final content
            if self.buffer.strip():
                if self.is_ansi_mode:
                    rich_text = self.ansi_processor.process_ansi_text(self.buffer)
                    self.console.print(rich_text)
                else:
                    try:
                        markdown = Markdown(
                            self.buffer,
                            code_theme=self.ui_config.markdown_code_theme,
                            hyperlinks=self.ui_config.enable_hyperlinks
                        )
                        self.console.print(markdown)
                    except Exception:
                        self.console.print(Text(self.buffer))
            
            self.console.print()  # Final newline


# Convenience functions
def print_ansi(console: Console, text: str) -> None:
    """Print text containing ANSI escape sequences.
    
    Args:
        console: Rich Console instance
        text: Text with ANSI codes
    """
    processor = ANSIProcessor(console)
    rich_text = processor.process_ansi_text(text)
    console.print(rich_text)


def render_command_output(console: Console, output: str, command: str) -> None:
    """Render command output with proper formatting.
    
    Args:
        console: Rich Console instance
        output: Command output
        command: Command that was executed
    """
    processor = CommandOutputProcessor(console)
    processor.process_command_output(output, command)
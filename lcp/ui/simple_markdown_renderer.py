"""Simple Progressive Markdown Renderer

Instead of trying to recreate Rich's markdown parsing, this approach uses
simple heuristics to detect "logical blocks" and lets Rich handle all 
the complex markdown parsing.
"""

import re
from rich.console import Console
from rich.markdown import Markdown


class SimpleProgressiveRenderer:
    """Simple approach: accumulate content and render complete logical sections.
    
    Uses basic heuristics to detect when we have "enough" content to render
    a meaningful section, then lets Rich handle all the markdown complexity.
    """
    
    def __init__(self, console: Console, ui_config=None):
        self.console = console
        self.buffer = ""
        self.last_rendered_pos = 0
        
        # Use provided config or load default
        if ui_config is None:
            from ..config import config_manager
            ui_config = config_manager.load_config().ui
        
        self.code_theme = ui_config.markdown_code_theme
        self.inline_code_theme = ui_config.markdown_inline_code_theme
        self.enable_hyperlinks = ui_config.enable_hyperlinks
        self.enable_tables = ui_config.enable_markdown_tables
    
    def start_live_display(self):
        """Initialize - no setup needed."""
        pass
    
    def add_content(self, content: str) -> None:
        """Add content and render when we detect logical completion points."""
        self.buffer += content
        
        # Check for logical completion points
        if self._should_render_section():
            self._render_new_section()
    
    def _should_render_section(self) -> bool:
        """Simple heuristics to detect when we have a complete section."""
        new_content = self.buffer[self.last_rendered_pos:]
        
        # Render on paragraph breaks (double newline)
        if '\n\n' in new_content:
            return True
        
        # Render when we have a substantial amount of content
        if len(new_content.strip()) > 200:
            return True
        
        # Render on certain markdown boundaries
        lines = new_content.split('\n')
        for line in lines:
            # Headers, code fences, horizontal rules
            if (line.startswith('#') or 
                line.startswith('```') or 
                line.startswith('---') or
                re.match(r'^\|.*\|', line)):  # Table rows
                return True
        
        return False
    
    def _render_new_section(self) -> None:
        """Render new content since last render point."""
        new_content = self.buffer[self.last_rendered_pos:]
        
        # Find a good breaking point (paragraph boundary, etc.)
        break_point = self._find_break_point(new_content)
        
        if break_point > 0:
            content_to_render = new_content[:break_point]
            
            # Let Rich handle all the markdown parsing
            try:
                markdown = Markdown(
                    content_to_render,
                    code_theme=self.code_theme,
                    hyperlinks=self.enable_hyperlinks,
                    inline_code_theme=self.inline_code_theme
                )
                self.console.print(markdown)
                
            except Exception:
                # Fallback to plain text
                from rich.text import Text
                plain_text = Text(content_to_render, style="default")
                self.console.print(plain_text)
            
            self.last_rendered_pos += break_point
    
    def _find_break_point(self, content: str) -> int:
        """Find a good place to break content for rendering."""
        # Look for paragraph breaks first
        double_newline = content.find('\n\n')
        if double_newline != -1:
            return double_newline + 2
        
        # Look for single logical breaks
        lines = content.split('\n')
        pos = 0
        
        for i, line in enumerate(lines):
            line_end = pos + len(line) + 1  # +1 for newline
            
            # Break after headers
            if line.startswith('#'):
                return line_end
            
            # Break after horizontal rules
            if line.startswith('---') or line.startswith('***'):
                return line_end
            
            # Break after code fence closures
            if line.startswith('```') and i > 0:
                return line_end
            
            pos = line_end
        
        # If no logical break found, return all content
        return len(content)
    
    def finalize(self) -> None:
        """Render any remaining content."""
        if self.last_rendered_pos < len(self.buffer):
            remaining = self.buffer[self.last_rendered_pos:]
            
            try:
                markdown = Markdown(
                    remaining,
                    code_theme=self.code_theme,
                    hyperlinks=self.enable_hyperlinks,
                    inline_code_theme=self.inline_code_theme
                )
                self.console.print(markdown)
                
            except Exception:
                from rich.text import Text
                plain_text = Text(remaining, style="default")
                self.console.print(plain_text)
        
        self.console.print()  # Final newline


class StreamingMarkdownRenderer:
    """Wrapper to maintain API compatibility."""
    
    def __init__(self, console: Console, ui_config=None):
        self.renderer = SimpleProgressiveRenderer(console, ui_config)
    
    def start_live_display(self):
        return self.renderer.start_live_display()
    
    def add_content(self, content: str) -> None:
        return self.renderer.add_content(content)
    
    def finalize(self) -> None:
        return self.renderer.finalize()
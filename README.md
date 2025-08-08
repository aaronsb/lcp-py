# LCP - LlamaCP Model Management & Chat Interface

🦙 **Advanced model management for llama.cpp** with automatic downloads, smart model discovery, and streaming chat interface.

## ✨ Features

- 🔍 **Smart Model Discovery** - Find models with fuzzy search and aliases
- 📥 **Automatic Downloads** - Download models from HuggingFace with progress bars
- 💬 **Streaming Chat** - Real-time token streaming with rich terminal UI  
- ⚙️ **XDG Configuration** - Follows Linux standards for config and data
- 🎯 **Model Management** - Easy switching, removal, and organization
- 🔌 **Multiple Backends** - HuggingFace (more coming)
- 🚀 **Standalone Binary** - No Python required after installation

## 🚀 Quick Start

### Option 1: Standalone Binary (Recommended)
```bash
# Clone and install
git clone <repo-url>
cd lcp-py
./install.sh

# Use immediately
lcp chat phi-3.5-mini
```

### Option 2: Development Setup
```bash
# For development/testing
./dev-install.sh
source venv/bin/activate
lcp chat phi-3.5-mini
```

## 💡 Usage Examples

```bash
# System status
lcp status

# Search for models
lcp search "phi 3.5"
lcp search "qwen 7b"

# Download and chat (one command!)
lcp chat phi-3.5-mini          # Downloads if needed
lcp chat qwen2.5               # Smart alias matching
lcp chat microsoft/Phi-3-mini  # Specific repo

# Model management
lcp list                       # List local models
lcp active                     # Set active model
lcp remove                     # Remove models

# Configuration
lcp config show               # Show settings
lcp config edit              # Edit config file
```

## 🎯 Smart Features

### Automatic Model Resolution
```bash
lcp chat phi3        # → bartowski/Phi-3.5-mini-instruct-GGUF
lcp chat qwen        # → bartowski/Qwen2.5-7B-Instruct-GGUF  
lcp chat llama3.1    # → bartowski/Llama-3.1-8B-Instruct-GGUF
```

### Preferred Quantizations
- Automatically selects **Q4_K_M** (best balance of quality/size)
- Falls back to **Q5_K_M**, **Q6_K**, **Q8_0** if needed
- Prefers **instruct/chat** models over base models

### Streaming Chat Interface
- **Real-time token streaming** - see responses as they're generated
- **Rich formatting** - markdown, syntax highlighting, panels
- **Performance metrics** - tokens/second, timing info
- **Chat commands** - `/clear`, `/stats`, `/help`
- **Conversation memory** - maintains context across turns

## 📁 File Organization (XDG Compliant)

```
~/.config/lcp/
├── config.toml              # Main configuration

~/.local/share/lcp/
├── models/                  # Downloaded models
│   ├── model.gguf          # Symlink to active model
│   ├── phi-3.5-mini.gguf   # Downloaded models
│   └── qwen2.5-7b.gguf

~/.cache/lcp/                # Cache directory
```

## ⚙️ Configuration

### Example `~/.config/lcp/config.toml`:
```toml
models_dir = "~/.local/share/lcp/models"

[model_preferences]
preferred_quantization = "Q4_K_M"
max_model_size_gb = 16.0
prefer_instruct_models = true

[api]
base_url = "http://localhost:11434"
streaming = true
max_tokens = 2048
temperature = 0.7

[ui]
use_colors = true
show_progress = true
show_timing = true

[[backends]]
name = "huggingface"
enabled = true
priority = 1
```

## 🔌 Backend System

### HuggingFace Backend
- Searches popular **GGUF repositories** (bartowski, microsoft, mradermacher)
- **Smart aliases** for common models
- **Fuzzy matching** - finds models even with partial names
- **Concurrent searches** across multiple repos

### Planned Backends
- **Ollama Registry** - Access Ollama's model library
- **Direct URLs** - Download from any URL
- **Local Conversion** - Convert PyTorch models to GGUF

## 🏗️ Integration with LlamaCP Docker

LCP works seamlessly with your existing llama.cpp Docker setup:

1. **Download models** with LCP
2. **Set active model** (creates symlink)  
3. **Restart container** to load new model
4. **Chat with streaming** through LCP

```bash
# Typical workflow
lcp chat qwen2.5               # Downloads and sets active
# LCP prompts: "Restart container? Press Enter when ready..."
docker compose restart llamacpp
# Chat interface starts automatically
```

## 🔧 Development

### Project Structure
```
lcp-py/
├── lcp/
│   ├── backends/           # Model backends
│   ├── ui/                # Terminal interface
│   ├── cli.py             # Command-line interface
│   ├── core.py            # Core functionality
│   ├── config.py          # Configuration management
│   └── models.py          # Data models
├── install.sh             # Production installer
├── dev-install.sh         # Development setup
└── pyproject.toml         # Project metadata
```

### Build System
- **PyInstaller** - Creates standalone binary
- **Development mode** - `pip install -e .` for testing  
- **XDG compliance** - Uses platformdirs for cross-platform paths

## 🆚 Comparison with Bash Version

| Feature | Bash Script | Python LCP |
|---------|-------------|------------|
| **Model Discovery** | Manual URLs | Smart search + aliases |
| **Download Progress** | Basic | Rich progress bars |  
| **Chat Interface** | Simple | Streaming + formatting |
| **Configuration** | Hardcoded | XDG-compliant TOML |
| **Error Handling** | Basic | Comprehensive |
| **Extensibility** | Limited | Plugin architecture |
| **Distribution** | Script file | Standalone binary |

## 🚀 Performance  

- **Concurrent downloads** - Multiple backends searched in parallel
- **Streaming responses** - No waiting for complete responses
- **Lazy loading** - Backends initialized only when needed
- **Async throughout** - Non-blocking I/O operations

## 📋 Requirements

- **Python 3.9+** (for development)
- **llamacpp Docker container** running
- **Internet connection** for model downloads

## 🤝 Contributing

1. Fork the repository
2. Run `./dev-install.sh` for development setup
3. Make changes and test with `lcp --help`
4. Build binary with `./install.sh` for testing
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

---

**🎯 LCP bridges the gap between Ollama's convenience and llama.cpp's performance!**
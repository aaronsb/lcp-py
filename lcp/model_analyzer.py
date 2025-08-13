"""Model analyzer for optimal GPU/CPU layer distribution."""

import struct
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class ModelMetadata:
    """GGUF model metadata."""
    
    n_layers: int = 0
    n_params: int = 0
    n_embd: int = 0
    n_head: int = 0
    n_vocab: int = 0
    model_type: str = ""
    quantization: str = ""
    file_size_gb: float = 0.0
    
    # Estimated memory requirements
    context_mem_mb: int = 0  # Memory for context
    model_mem_mb: int = 0    # Memory for model weights
    overhead_mem_mb: int = 512  # Buffer for activations and overhead
    
    @property
    def total_mem_mb(self) -> int:
        """Total memory requirement in MB."""
        return self.model_mem_mb + self.context_mem_mb + self.overhead_mem_mb
    
    @property
    def mem_per_layer_mb(self) -> float:
        """Average memory per layer in MB."""
        if self.n_layers > 0:
            return self.model_mem_mb / self.n_layers
        return 0


def read_gguf_header(model_path: Path) -> Optional[ModelMetadata]:
    """
    Read GGUF model header to extract metadata.
    
    GGUF format has metadata at the beginning that tells us about the model.
    """
    metadata = ModelMetadata()
    
    # Get file size
    metadata.file_size_gb = model_path.stat().st_size / (1024**3)
    
    try:
        with open(model_path, 'rb') as f:
            # Read GGUF magic number
            magic = f.read(4)
            if magic != b'GGUF':
                return None
            
            # Read version
            version = struct.unpack('<I', f.read(4))[0]
            
            # Read tensor count and metadata KV count
            tensor_count = struct.unpack('<Q', f.read(8))[0]
            metadata_kv_count = struct.unpack('<Q', f.read(8))[0]
            
            # Parse metadata key-value pairs
            # This is simplified - real GGUF parsing is more complex
            # For now, we'll use heuristics based on file size
            
    except Exception:
        pass
    
    # Use heuristics based on file size and common patterns
    # These are rough estimates based on typical GGUF models
    
    if metadata.file_size_gb < 2:
        # Small model (1-3B params)
        metadata.n_layers = 22
        metadata.n_params = 1_300_000_000
        metadata.n_embd = 2048
    elif metadata.file_size_gb < 3:
        # 3B model
        metadata.n_layers = 32
        metadata.n_params = 3_000_000_000
        metadata.n_embd = 3072
    elif metadata.file_size_gb < 5:
        # 7B model  
        metadata.n_layers = 32
        metadata.n_params = 7_000_000_000
        metadata.n_embd = 4096
    elif metadata.file_size_gb < 8:
        # 13B model
        metadata.n_layers = 40
        metadata.n_params = 13_000_000_000
        metadata.n_embd = 5120
    elif metadata.file_size_gb < 15:
        # 14B model (like Phi-4)
        metadata.n_layers = 40
        metadata.n_params = 14_000_000_000
        metadata.n_embd = 5120
    elif metadata.file_size_gb < 25:
        # 30B model
        metadata.n_layers = 60
        metadata.n_params = 30_000_000_000
        metadata.n_embd = 6656
    else:
        # 70B+ model
        metadata.n_layers = 80
        metadata.n_params = 70_000_000_000
        metadata.n_embd = 8192
    
    # Estimate memory requirements
    # Model weights memory is roughly the file size plus some overhead
    metadata.model_mem_mb = int(metadata.file_size_gb * 1024 * 1.1)
    
    # Context memory (assuming 8K context)
    context_size = 8192
    metadata.context_mem_mb = int((context_size * metadata.n_embd * 4) / (1024 * 1024))
    
    return metadata


def calculate_gpu_layers(
    model_path: Path,
    strategy: str = "auto-maximize",
    vram_percentage: int = 80,
    available_vram_mb: float = 16380,
    total_layers: Optional[int] = None
) -> int:
    """
    Calculate number of GPU layers based on strategy.
    
    Args:
        model_path: Path to the GGUF model
        strategy: GPU allocation strategy
            - "gpu-only": Force all layers to GPU (may fail if too large)
            - "cpu-only": Force all layers to CPU (minimal GPU usage)
            - "auto-maximize": Fit as many layers as possible in VRAM
            - "auto-percentage": Use specified percentage of total VRAM
        vram_percentage: For "auto-percentage", percentage of VRAM to use (0-100)
        available_vram_mb: Total GPU VRAM in MB
        total_layers: Override for total layer count
    
    Returns:
        Number of layers to load on GPU
    """
    
    # Get model metadata to determine total layers
    if total_layers is None:
        metadata = read_gguf_header(model_path)
        if metadata:
            total_layers = metadata.n_layers
        else:
            # Estimate based on file size
            file_size_gb = model_path.stat().st_size / (1024**3)
            if file_size_gb < 3:
                total_layers = 32  # Small models
            elif file_size_gb < 8:
                total_layers = 40  # Medium models  
            else:
                total_layers = 80  # Large models
    
    # Apply strategy
    if strategy == "gpu-only":
        # Force all layers on GPU (may fail if model too large)
        return 999  # llama.cpp convention for "all layers"
    
    elif strategy == "cpu-only":
        # Force all layers on CPU (minimal GPU usage)
        return 0
    
    elif strategy == "auto-percentage":
        # Use specified percentage of total VRAM
        vram_percentage = max(0, min(100, vram_percentage))  # Clamp to 0-100
        target_vram_mb = available_vram_mb * (vram_percentage / 100)
        
        # Estimate how many layers fit in target VRAM
        # Reserve 512MB for context and overhead
        usable_vram_mb = target_vram_mb - 512
        
        # Get model size to estimate layer size
        file_size_mb = model_path.stat().st_size / (1024**2)
        
        # Estimate memory per layer (rough approximation)
        mem_per_layer = file_size_mb / total_layers
        
        # Calculate layers that fit
        n_gpu_layers = int(usable_vram_mb / mem_per_layer)
        n_gpu_layers = min(n_gpu_layers, total_layers)  # Don't exceed total
        n_gpu_layers = max(0, n_gpu_layers)  # Ensure non-negative
        
        return n_gpu_layers
    
    elif strategy == "auto-maximize":
        # Fit as many layers as possible in available VRAM
        # This is like auto-percentage with 90% to leave headroom
        return calculate_gpu_layers(
            model_path, 
            "auto-percentage", 
            90,  # Use 90% of VRAM
            available_vram_mb,
            total_layers
        )
    
    else:
        # Default to auto-maximize
        return calculate_gpu_layers(model_path, "auto-maximize", vram_percentage, available_vram_mb, total_layers)


def get_optimized_docker_params(
    model_path: Path,
    hardware_profile: any
) -> Dict[str, any]:
    """
    Get optimized Docker container parameters for a model.
    
    Returns parameters suitable for docker-compose command field.
    """
    
    # Calculate optimal GPU layers
    result = calculate_optimal_gpu_layers(
        model_path,
        available_vram_gb=hardware_profile.total_vram_gb,
        total_ram_gb=hardware_profile.system_ram_gb,
        reserve_vram_gb=1.5,  # Reserve for system and overhead
        reserve_ram_gb=4.0    # Reserve for OS and other processes
    )
    
    # Build command parameters
    params = {
        "model_path": "/models/model.gguf",
        "n_gpu_layers": result["n_gpu_layers"],
        "n_batch": result["recommended_batch"],
        "n_threads": result["recommended_threads"],
        "n_threads_batch": result["recommended_threads"],
        "context_size": 8192,
        "host": "0.0.0.0",
        "port": 8080,
    }
    
    # Add optimization notes
    params["optimization_notes"] = []
    
    if result["fits_fully_in_vram"]:
        params["optimization_notes"].append("✅ Model fits entirely in VRAM")
    else:
        params["optimization_notes"].append(
            f"⚡ Splitting model: {result['n_gpu_layers']}/{result['n_layers_total']} layers on GPU"
        )
        params["optimization_notes"].append(
            f"📊 GPU: {result['gpu_mem_used_gb']:.1f}GB, CPU: {result['cpu_mem_used_gb']:.1f}GB"
        )
    
    return params, result
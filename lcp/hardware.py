"""Hardware profiling for intelligent model selection."""

import platform
import psutil
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    import GPUtil
except ImportError:
    GPUtil = None

from .config import HardwareProfile


def detect_gpu_info() -> tuple[int, List[str], float, float]:
    """Detect GPU information using multiple methods."""
    gpu_count = 0
    gpu_models = []
    total_vram_gb = 0.0
    available_vram_gb = 0.0
    
    # Try GPUtil first (NVIDIA GPUs)
    if GPUtil:
        try:
            gpus = GPUtil.getGPUs()
            gpu_count = len(gpus)
            for gpu in gpus:
                gpu_models.append(gpu.name)
                total_vram_gb += gpu.memoryTotal / 1024  # Convert MB to GB
                available_vram_gb += gpu.memoryFree / 1024
        except Exception:
            pass
    
    # Fallback: Try nvidia-ml-py if GPUtil failed
    if gpu_count == 0:
        try:
            import pynvml
            pynvml.nvmlInit()
            gpu_count = pynvml.nvmlDeviceGetCount()
            
            for i in range(gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle).decode()
                gpu_models.append(name)
                
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_vram_gb += memory_info.total / (1024**3)  # Convert bytes to GB
                available_vram_gb += memory_info.free / (1024**3)
                
        except Exception:
            pass
    
    return gpu_count, gpu_models, total_vram_gb, available_vram_gb


def detect_storage_info(path: Path) -> tuple[float, str]:
    """Detect storage information for a given path."""
    try:
        # Get available space
        total, used, free = shutil.disk_usage(path)
        available_gb = free / (1024**3)
        
        # Try to detect storage type (basic detection)
        storage_type = "unknown"
        
        # Check if it's likely SSD vs HDD (very basic heuristic)
        try:
            # This is a very basic check - in practice, you'd want more sophisticated detection
            if platform.system() == "Linux":
                # Try to read from /proc/mounts or /sys/block for more accurate detection
                storage_type = "SSD"  # Default assumption for modern systems
            else:
                storage_type = "unknown"
        except Exception:
            storage_type = "unknown"
        
        return available_gb, storage_type
    except Exception:
        return 0.0, "unknown"


def get_cpu_info() -> tuple[int, int, str]:
    """Get CPU information."""
    try:
        cpu_cores = psutil.cpu_count(logical=False) or 0
        cpu_threads = psutil.cpu_count(logical=True) or 0
        
        # Get CPU model name
        cpu_model = platform.processor()
        if not cpu_model or cpu_model == "":
            # Fallback for Linux systems
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_model = line.split(":", 1)[1].strip()
                            break
            except Exception:
                cpu_model = "Unknown CPU"
        
        return cpu_cores, cpu_threads, cpu_model
    except Exception:
        return 0, 0, "Unknown CPU"


def get_memory_info() -> tuple[float, float]:
    """Get system memory information."""
    try:
        memory = psutil.virtual_memory()
        system_ram_gb = memory.total / (1024**3)
        available_ram_gb = memory.available / (1024**3)
        return system_ram_gb, available_ram_gb
    except Exception:
        return 0.0, 0.0


def calculate_recommendations(profile: HardwareProfile) -> HardwareProfile:
    """Calculate hardware-based recommendations."""
    # Determine if GPU offloading is viable
    profile.can_offload_to_gpu = profile.total_vram_gb >= 8.0  # Minimum 8GB for reasonable offloading
    
    # Calculate recommended max model size
    if profile.can_offload_to_gpu:
        # Primary constraint is VRAM for GPU-offloaded models
        profile.recommended_max_model_size_gb = profile.available_vram_gb * 0.8  # 80% of available VRAM
    else:
        # Primary constraint is system RAM for CPU-only models  
        profile.recommended_max_model_size_gb = profile.available_ram_gb * 0.5  # 50% of available RAM
    
    # Choose optimal quantization based on available resources
    if profile.recommended_max_model_size_gb >= 20:
        profile.optimal_quantization = "Q5_K_M"  # Higher quality for high-memory systems
    elif profile.recommended_max_model_size_gb >= 15:
        profile.optimal_quantization = "Q4_K_M"  # Balanced quality/size
    elif profile.recommended_max_model_size_gb >= 10:
        profile.optimal_quantization = "Q4_K_S"  # Smaller but decent quality
    else:
        profile.optimal_quantization = "Q3_K_M"  # Smaller models for limited systems
    
    return profile


def create_hardware_profile(models_dir: Optional[Path] = None) -> HardwareProfile:
    """Create a comprehensive hardware profile."""
    # Get CPU information
    cpu_cores, cpu_threads, cpu_model = get_cpu_info()
    
    # Get memory information
    system_ram_gb, available_ram_gb = get_memory_info()
    
    # Get GPU information
    gpu_count, gpu_models, total_vram_gb, available_vram_gb = detect_gpu_info()
    
    # Get storage information (use models directory or home directory)
    storage_path = models_dir or Path.home()
    available_storage_gb, storage_type = detect_storage_info(storage_path)
    
    # Create the profile
    profile = HardwareProfile(
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        cpu_model=cpu_model,
        system_ram_gb=system_ram_gb,
        available_ram_gb=available_ram_gb,
        gpu_count=gpu_count,
        gpu_models=gpu_models,
        total_vram_gb=total_vram_gb,
        available_vram_gb=available_vram_gb,
        available_storage_gb=available_storage_gb,
        storage_type=storage_type,
        profile_date=datetime.now().isoformat(),
        platform=platform.system()
    )
    
    # Calculate recommendations
    profile = calculate_recommendations(profile)
    
    return profile


def get_model_memory_breakdown(model_size_gb: float, hardware: HardwareProfile) -> Dict[str, Any]:
    """Calculate how model memory would be distributed across hardware."""
    breakdown = {
        "vram_gb": 0.0,
        "system_ram_gb": 0.0,
        "storage_gb": 0.0,
        "vram_color": "red",
        "ram_color": "red", 
        "storage_color": "green",
        "feasible": False
    }
    
    remaining_size = model_size_gb
    
    # GPU VRAM (highest priority)
    if hardware.can_offload_to_gpu and hardware.available_vram_gb > 0:
        vram_usage = min(remaining_size, hardware.available_vram_gb * 0.8)  # 80% safety margin
        breakdown["vram_gb"] = vram_usage
        remaining_size -= vram_usage
        
        # Color based on VRAM usage
        vram_percentage = vram_usage / (hardware.available_vram_gb * 0.8) if hardware.available_vram_gb > 0 else 1.0
        if vram_percentage <= 0.7:
            breakdown["vram_color"] = "green"
        elif vram_percentage <= 0.9:
            breakdown["vram_color"] = "yellow"
        else:
            breakdown["vram_color"] = "red"
    
    # System RAM (second priority)
    if remaining_size > 0 and hardware.available_ram_gb > 0:
        ram_usage = min(remaining_size, hardware.available_ram_gb * 0.6)  # 60% safety margin
        breakdown["system_ram_gb"] = ram_usage
        remaining_size -= ram_usage
        
        # Color based on RAM usage
        ram_percentage = ram_usage / (hardware.available_ram_gb * 0.6) if hardware.available_ram_gb > 0 else 1.0
        if ram_percentage <= 0.7:
            breakdown["ram_color"] = "green"
        elif ram_percentage <= 0.9:
            breakdown["ram_color"] = "yellow" 
        else:
            breakdown["ram_color"] = "red"
    
    # Storage/Swap (last resort)
    if remaining_size > 0:
        breakdown["storage_gb"] = remaining_size
        # Storage is always red (bad for performance)
        breakdown["storage_color"] = "red"
    
    # Model is feasible if no storage/swap needed
    breakdown["feasible"] = breakdown["storage_gb"] == 0.0
    
    return breakdown


def create_memory_usage_bar(model_size_gb: float, hardware: HardwareProfile, width: int = 30, enable_storage: bool = False) -> str:
    """Create a visual memory usage bar graph using Rich markup.
    
    The bar represents the total available memory pool. Each character represents 
    an equal portion of the total memory (VRAM + CPU RAM + optionally SSD RAM).
    """
    
    # Calculate available memory pools
    vram_available = hardware.available_vram_gb * 0.8 if hardware.can_offload_to_gpu else 0.0
    ram_available = hardware.available_ram_gb * 0.6
    storage_available = 50.0 if enable_storage else 0.0  # Configurable storage allocation
    
    # Total available memory pool
    total_available = vram_available + ram_available + (storage_available if enable_storage else 0)
    
    if total_available <= 0:
        return "[red]No memory available[/red]".ljust(width)
    
    # Get memory breakdown for this model
    breakdown = get_model_memory_breakdown(model_size_gb, hardware)
    
    # Check if model fits in available memory
    total_needed = breakdown["vram_gb"] + breakdown["system_ram_gb"] + breakdown["storage_gb"]
    if total_needed > total_available:
        return "[red]Insufficient RAM[/red]".ljust(width)
    
    # Calculate characters per memory type (proportional to available memory)
    gb_per_char = total_available / width
    
    vram_total_chars = int(vram_available / gb_per_char) if vram_available > 0 else 0
    ram_total_chars = int(ram_available / gb_per_char) if ram_available > 0 else 0
    storage_total_chars = int(storage_available / gb_per_char) if enable_storage and storage_available > 0 else 0
    
    # Calculate used characters for each memory type
    vram_used_chars = int(breakdown["vram_gb"] / gb_per_char) if breakdown["vram_gb"] > 0 else 0
    ram_used_chars = int(breakdown["system_ram_gb"] / gb_per_char) if breakdown["system_ram_gb"] > 0 else 0
    storage_used_chars = int(breakdown["storage_gb"] / gb_per_char) if breakdown["storage_gb"] > 0 else 0
    
    # Ensure we don't exceed available characters for each type
    vram_used_chars = min(vram_used_chars, vram_total_chars)
    ram_used_chars = min(ram_used_chars, ram_total_chars) 
    storage_used_chars = min(storage_used_chars, storage_total_chars)
    
    # Build the bar character by character
    bar = []
    
    # VRAM section (green)
    for i in range(vram_total_chars):
        if i < vram_used_chars:
            bar.append("[on green] [/on green]")  # Used VRAM: green background
        else:
            bar.append("[green]░[/green]")  # Available VRAM: green outline
    
    # CPU RAM section (yellow/orange)
    for i in range(ram_total_chars):
        if i < ram_used_chars:
            bar.append("[on yellow] [/on yellow]")  # Used RAM: yellow background
        else:
            bar.append("[yellow]░[/yellow]")  # Available RAM: yellow outline
    
    # Storage section (red) - only if enabled
    if enable_storage:
        for i in range(storage_total_chars):
            if i < storage_used_chars:
                bar.append("[on red] [/on red]")  # Used storage: red background
            else:
                bar.append("[red]░[/red]")  # Available storage: red outline
    
    # Ensure exactly 30 characters
    current_length = len(bar)
    if current_length < width:
        # Fill remaining with dim dots
        bar.extend(["[dim]·[/dim]"] * (width - current_length))
    elif current_length > width:
        # Truncate if somehow too long
        bar = bar[:width]
    
    return "".join(bar)
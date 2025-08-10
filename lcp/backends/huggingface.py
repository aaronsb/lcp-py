"""HuggingFace backend for model discovery and download."""

import asyncio
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
import httpx
from fuzzywuzzy import fuzz, process

from .base import Backend
from ..models import ModelInfo, QuantizationType


class HuggingFaceBackend(Backend):
    """HuggingFace backend for GGUF models."""
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.base_url = "https://huggingface.co"
        self.api_url = "https://huggingface.co/api"
        
        # Popular GGUF repositories
        self.popular_repos = config.get("popular_repos", [
            "bartowski/*-GGUF",
            "microsoft/*-gguf",
            "mradermacher/*-GGUF",
            "TheBloke/*-GGUF",
        ])
        
        # Model aliases for common names
        self.model_aliases = {
            "phi3": "bartowski/Phi-3.5-mini-instruct-GGUF",
            "phi-3": "bartowski/Phi-3.5-mini-instruct-GGUF", 
            "phi3.5": "bartowski/Phi-3.5-mini-instruct-GGUF",
            "qwen2.5": "bartowski/Qwen2.5-7B-Instruct-GGUF",
            "qwen": "bartowski/Qwen2.5-7B-Instruct-GGUF",
            "llama3": "bartowski/Llama-3.1-8B-Instruct-GGUF",
            "llama-3": "bartowski/Llama-3.1-8B-Instruct-GGUF",
            "llama3.1": "bartowski/Llama-3.1-8B-Instruct-GGUF",
            "codestral": "bartowski/Codestral-22B-v0.1-GGUF",
            "mistral": "bartowski/Mistral-7B-Instruct-v0.3-GGUF",
        }
        
        self.preferred_quantizations = config.get("default_quantizations", [
            "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"
        ])
    
    async def search_models(self, query: str, limit: int = 10) -> List[ModelInfo]:
        """Search for models using HuggingFace API and fuzzy matching."""
        models = []
        
        # First, check for direct alias match
        if query.lower() in self.model_aliases:
            repo_id = self.model_aliases[query.lower()]
            model_info = await self.get_model_info(repo_id)
            if model_info:
                models.append(model_info)
                if len(models) >= limit:
                    return models
        
        # Search across popular repositories
        async with httpx.AsyncClient() as client:
            search_tasks = []
            
            for repo_pattern in self.popular_repos:
                # Convert pattern to search query
                if "*" in repo_pattern:
                    # Search for repos matching pattern
                    search_query = repo_pattern.replace("*", query)
                else:
                    search_query = repo_pattern
                
                task = self._search_in_repo(client, search_query, query)
                search_tasks.append(task)
            
            # Execute searches concurrently
            repo_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            for result in repo_results:
                if isinstance(result, list):
                    models.extend(result)
        
        # Remove duplicates and sort by relevance
        seen = set()
        unique_models = []
        
        for model in models:
            key = (model.repo_id, model.filename)
            if key not in seen:
                seen.add(key)
                unique_models.append(model)
        
        # Sort by fuzzy match score
        scored_models = []
        for model in unique_models:
            score = fuzz.partial_ratio(query.lower(), model.name.lower())
            scored_models.append((score, model))
        
        scored_models.sort(key=lambda x: x[0], reverse=True)
        
        return [model for _, model in scored_models[:limit]]
    
    async def _search_in_repo(
        self, 
        client: httpx.AsyncClient, 
        repo_pattern: str, 
        query: str
    ) -> List[ModelInfo]:
        """Search for models in a specific repository pattern."""
        models = []
        
        try:
            # First, try to get repo info directly
            if "/" in repo_pattern and "*" not in repo_pattern:
                repo_models = await self._get_repo_models(client, repo_pattern, query)
                models.extend(repo_models)
            else:
                # Search for repositories matching the pattern
                search_url = f"{self.api_url}/models"
                params = {
                    "search": query,
                    "filter": "gguf",
                    "limit": 20,
                }
                
                response = await client.get(search_url, params=params)
                if response.status_code == 200:
                    repos_data = response.json()
                    
                    for repo_data in repos_data:
                        repo_id = repo_data.get("id", "")
                        if self._matches_pattern(repo_id, repo_pattern):
                            repo_models = await self._get_repo_models(client, repo_id, query)
                            models.extend(repo_models)
        
        except Exception:
            # Silently ignore errors for individual repos
            pass
        
        return models
    
    def _matches_pattern(self, repo_id: str, pattern: str) -> bool:
        """Check if a repo ID matches a pattern with wildcards."""
        if "*" not in pattern:
            return repo_id == pattern
        
        # Convert pattern to regex
        regex_pattern = pattern.replace("*", ".*")
        return bool(re.match(regex_pattern, repo_id, re.IGNORECASE))
    
    async def _get_repo_models(
        self, 
        client: httpx.AsyncClient, 
        repo_id: str, 
        query: str
    ) -> List[ModelInfo]:
        """Get GGUF models from a specific repository."""
        models = []
        
        try:
            # Get repository file list
            files_url = f"{self.api_url}/models/{repo_id}/tree/main"
            response = await client.get(files_url)
            
            if response.status_code == 200:
                files_data = response.json()
                
                for file_info in files_data:
                    if file_info.get("type") == "file":
                        filename = file_info.get("path", "")
                        
                        # Only process .gguf files
                        if not filename.lower().endswith(".gguf"):
                            continue
                        
                        # Check if filename matches query or contains preferred quantization
                        if (query.lower() in filename.lower() or 
                            any(q in filename for q in self.preferred_quantizations)):
                            
                            model_info = ModelInfo(
                                name=self._extract_model_name(filename),
                                repo_id=repo_id,
                                filename=filename,
                                backend=self.name,
                                size_bytes=file_info.get("size"),
                                download_url=f"{self.base_url}/{repo_id}/resolve/main/{filename}",
                            )
                            
                            models.append(model_info)
        
        except Exception:
            # Silently ignore errors for individual repos
            pass
        
        return models
    
    def _extract_model_name(self, filename: str) -> str:
        """Extract a clean model name from filename."""
        name = filename.replace(".gguf", "")
        
        # Remove common suffixes
        suffixes_to_remove = [
            r"-Q\d+_K_[MS]",
            r"-q\d+_k_[ms]", 
            r"-F\d+",
            r"-f\d+",
        ]
        
        for suffix_pattern in suffixes_to_remove:
            name = re.sub(suffix_pattern, "", name, flags=re.IGNORECASE)
        
        return name
    
    async def get_model_info(self, model_identifier: str) -> Optional[ModelInfo]:
        """Get detailed information about a specific model."""
        repo_id, filename = self.parse_model_identifier(model_identifier)
        
        if not filename:
            # Try to find the best GGUF file in the repo
            async with httpx.AsyncClient() as client:
                models = await self._get_repo_models(client, repo_id, "")
                if models:
                    # Prefer Q4_K_M quantization
                    preferred = next(
                        (m for m in models if "Q4_K_M" in m.filename),
                        models[0]
                    )
                    return preferred
        else:
            # Specific file requested
            return ModelInfo(
                name=self._extract_model_name(filename),
                repo_id=repo_id,
                filename=filename,
                backend=self.name,
                download_url=f"{self.base_url}/{repo_id}/resolve/main/{filename}",
            )
        
        return None
    
    async def download_model(
        self, 
        model_info: ModelInfo, 
        target_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """Download a model to the target path."""
        if not model_info.download_url:
            raise ValueError("No download URL available for model")
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", model_info.download_url) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get("content-length", 0))
                downloaded_size = 0
                
                with open(target_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded_size, total_size)
        
        return target_path
    
    def get_download_url(self, model_info: ModelInfo) -> str:
        """Get the direct download URL for a model."""
        if model_info.download_url:
            return model_info.download_url
        
        return f"{self.base_url}/{model_info.repo_id}/resolve/main/{model_info.filename}"
    
    def supports_model(self, model_identifier: str) -> bool:
        """Check if this backend can handle the given model identifier."""
        # Support HuggingFace repo format or known aliases
        if "/" in model_identifier:
            return True
        
        return model_identifier.lower() in self.model_aliases
    
    def parse_model_identifier(self, identifier: str) -> tuple[str, str]:
        """Parse model identifier with HuggingFace-specific logic."""
        # Check aliases first
        if identifier.lower() in self.model_aliases:
            repo_id = self.model_aliases[identifier.lower()]
            return repo_id, ""
        
        # Use base implementation for repo/file format
        return super().parse_model_identifier(identifier)
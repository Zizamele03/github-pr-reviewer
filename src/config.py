"""
Configuration management for the GitHub PR Reviewer.
Handles environment variables and validation.
"""
import os
import re
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Model name validation pattern: allows both owner/model and single-token models
# Examples: gpt2, distilgpt2, owner/model, my-org/gpt2-small
MODEL_NAME_REGEX = r'^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$'

logger = logging.getLogger(__name__)

class Config:
    """
    Configuration class for the application.
    
    Manages all environment variables and validates them on initialization.
    Required variables must be set or initialization will raise ValueError.
    """
    
    def __init__(self):
        """Initialize and validate configuration from environment variables."""
        # Required environment variables
        self.huggingface_api_key = self._get_required('HF_API_KEY')
        self.github_token = self._get_required('GITHUB_TOKEN')
        self.github_repository = self._parse_repository(self._get_required('GITHUB_REPOSITORY'))
        
        # Optional settings with defaults
        self.huggingface_model = os.getenv('HUGGINGFACE_MODEL', 'mistralai/Mistral-7B-Instruct-v0.2')
        self.max_diff_length = int(os.getenv('MAX_DIFF_LENGTH', '4000'))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '5'))
        
        # Validate configuration values
        self._validate_config()
    
    def _get_required(self, key: str) -> str:
        """
        Get required environment variable or raise error.
        
        Args:
            key: Environment variable name
            
        Returns:
            Environment variable value
            
        Raises:
            ValueError: If environment variable is missing or empty
        """
        value = os.getenv(key)
        if not value or not value.strip():
            raise ValueError(f"Missing required environment variable: {key}")
        return value.strip()
    
    def _parse_repository(self, repo_input: str) -> str:
        """
        Parse repository input to owner/repo format.
        
        Supports multiple input formats:
        - owner/repo (direct format)
        - https://github.com/owner/repo.git (full URL with .git)
        - https://github.com/owner/repo (full URL without .git)
        
        Args:
            repo_input: Repository identifier in various formats
            
        Returns:
            Normalized repository string in owner/repo format
            
        Raises:
            ValueError: If repository format cannot be parsed
        """
        if not repo_input or not repo_input.strip():
            raise ValueError("Repository input cannot be empty")
        
        repo_input = repo_input.strip()
        
        # If it's already in owner/repo format (contains / but not http)
        if '/' in repo_input and not repo_input.startswith('http'):
            return repo_input
        
        # Extract from URL format
        if repo_input.startswith('http'):
            # Remove .git suffix if present
            repo_input = repo_input.rstrip('.git')
            # Extract owner/repo from GitHub URL
            match = re.search(r'github\.com[/:]([^/]+)/([^/]+)/?$', repo_input)
            if match:
                return f"{match.group(1)}/{match.group(2)}"
        
        raise ValueError(
            f"Invalid repository format: {repo_input}. "
            f"Use 'owner/repo' or GitHub URL (e.g., https://github.com/owner/repo)"
        )
    
    def _validate_config(self) -> None:
        """
        Validate configuration values and log warnings for suspicious values.
        
        Raises:
            ValueError: If critical validation fails (e.g., invalid model name)
        """
        # Warn if API key format looks suspicious (but don't fail)
        if not self.huggingface_api_key.startswith('hf_'):
            logger.warning(
                "HF_API_KEY doesn't start with 'hf_'. This might be invalid. "
                "HuggingFace API keys typically start with 'hf_'."
            )
        
        # Warn if GitHub token seems too short (but don't fail - could be a valid short token)
        if len(self.github_token) < 10:
            logger.warning(
                "GITHUB_TOKEN seems unusually short. Please verify it's correct. "
                "GitHub tokens are typically longer than 10 characters."
            )
        
        # Validate model name format: allows both owner/model and single-token models
        # Examples: gpt2, distilgpt2, owner/model, my-org/gpt2-small
        if not re.match(MODEL_NAME_REGEX, self.huggingface_model):
            raise ValueError(
                f"Invalid model format: {self.huggingface_model}. "
                f"Model name must match pattern: {MODEL_NAME_REGEX}. "
                f"Examples: 'gpt2', 'distilgpt2', 'owner/model', 'my-org/gpt2-small'"
            )
        
        # Validate numeric settings
        if self.max_diff_length <= 0:
            raise ValueError(f"MAX_DIFF_LENGTH must be positive, got: {self.max_diff_length}")
        
        if self.request_timeout <= 0:
            raise ValueError(f"REQUEST_TIMEOUT must be positive, got: {self.request_timeout}")
        
        if self.max_retries < 0:
            raise ValueError(f"MAX_RETRIES must be non-negative, got: {self.max_retries}")

# Global config instance - initialized on module import
config = Config()
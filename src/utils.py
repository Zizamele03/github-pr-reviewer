"""
Utility functions for the GitHub PR Reviewer.
"""
import re
from typing import Optional

def safe_int(value: str, default: int = 0) -> int:
    """
    Safely convert string to integer with default fallback.
    
    Args:
        value: String value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with sensible boundary.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    # Try to break at word boundary
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.7:
        return truncated[:last_space] + suffix
    
    return truncated + suffix

def extract_pr_number_from_url(url: str) -> Optional[int]:
    """
    Extract PR number from GitHub URL.
    
    Args:
        url: GitHub PR URL
        
    Returns:
        PR number or None if not found
    """
    match = re.search(r'/pull/(\d+)', url)
    if match:
        return safe_int(match.group(1))
    return None
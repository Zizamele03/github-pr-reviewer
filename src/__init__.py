"""
GitHub PR Reviewer - Automated code reviews using HuggingFace LLMs.

This package provides automated code review functionality by:
1. Fetching pull requests from GitHub
2. Analyzing code changes using HuggingFace LLMs
3. Generating comprehensive review reports
"""

__version__ = "2.0.0"
__author__ = "Zizamele Nyawo"

# Package-level exports
from src.config import config
from src.github_client import GitHubClient
from src.llm_reviewer import LLMReviewer
from src.main import PRReviewer

__all__ = ['config', 'GitHubClient', 'LLMReviewer', 'PRReviewer']
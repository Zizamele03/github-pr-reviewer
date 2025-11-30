"""
GitHub API client for fetching PR data and diffs.
Handles authentication, rate limiting, and errors.
"""
import requests
import time
import json
import random
import logging
from typing import List, Dict, Optional
from src.config import config

logger = logging.getLogger(__name__)

class GitHubClient:
    """
    GitHub API client with robust error handling and rate limit management.
    
    Features:
    - Exponential backoff for rate limits and transient errors
    - JSON parsing error handling
    - Safe field access for API responses
    - HTTP session reuse for connection pooling
    """
    
    def __init__(self):
        """
        Initialize GitHub client with authentication and HTTP session.
        
        Creates a persistent requests.Session for connection reuse and
        sets up authentication headers.
        """
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {config.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-PR-Reviewer"
        }
        self.rate_limit_remaining = 10
        self.last_request_time = 0
        
        # Create persistent session for connection reuse
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _handle_rate_limit(self, response: requests.Response) -> Optional[int]:
        """
        Handle rate limit response and calculate sleep time.
        
        This method is used by _make_request and can be tested independently.
        It extracts rate limit information from response headers and calculates
        the appropriate wait time.
        
        Args:
            response: HTTP response with rate limit headers
            
        Returns:
            Sleep time in seconds, or None if rate limit not applicable
        """
        # Check for rate limit status codes
        if response.status_code not in (403, 429):
            return None
        
        # Get rate limit remaining from headers
        rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', '0'))
        
        # Only handle if we're actually rate limited
        if rate_limit_remaining > 0 and response.status_code != 429:
            return None
        
        # Try to get reset time from headers
        reset_time_str = response.headers.get('X-RateLimit-Reset')
        if reset_time_str:
            try:
                reset_time = int(reset_time_str)
                current_time = time.time()
                sleep_time = max(reset_time - current_time, 0)
                
                # If reset time is in the past or very close, use minimum backoff
                if sleep_time < 1:
                    logger.warning(
                        f"Rate limit reset time is in the past or too close. "
                        f"Using exponential backoff instead."
                    )
                    return None  # Signal to use exponential backoff
                
                return int(sleep_time)
            except (ValueError, TypeError):
                logger.warning("Invalid X-RateLimit-Reset header, using exponential backoff")
                return None
        
        return None  # No valid reset time, use exponential backoff
    
    def _make_request(
        self, 
        url: str, 
        is_diff: bool = False,
        max_retries: Optional[int] = None
    ) -> Optional[requests.Response]:
        """
        Make HTTP request to GitHub API with robust error handling.
        
        Features:
        - Exponential backoff for rate limits and transient errors
        - Respects X-RateLimit-Reset header when available
        - Maximum retry limit to prevent infinite loops
        - Connection timeout handling
        
        Args:
            url: API endpoint URL
            is_diff: Whether this is a diff request (different headers)
            max_retries: Maximum number of retry attempts (defaults to config.max_retries)
            
        Returns:
            Response object or None if all retries exhausted
        """
        if max_retries is None:
            max_retries = config.max_retries
        
        # Rate limiting: ensure minimum time between requests
        time_since_last = time.time() - self.last_request_time
        if time_since_last < 1.0:  # 1 second between requests
            time.sleep(1.0 - time_since_last)
        
        for attempt in range(max_retries + 1):
            try:
                # Prepare headers for this request
                headers = self.headers.copy()
                if is_diff:
                    headers["Accept"] = "application/vnd.github.v3.diff"
                
                # Make request with timeout (connect timeout, read timeout)
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=(5, config.request_timeout)
                )
                
                self.last_request_time = time.time()
                self.rate_limit_remaining = int(
                    response.headers.get('X-RateLimit-Remaining', '10')
                )
                
                # Handle rate limiting
                if response.status_code in (403, 429):
                    sleep_time = self._handle_rate_limit(response)
                    
                    if sleep_time is not None:
                        # Use reset time from header
                        logger.warning(
                            f"Rate limit exceeded. Waiting {sleep_time} seconds "
                            f"(attempt {attempt + 1}/{max_retries + 1})..."
                        )
                        time.sleep(sleep_time)
                        continue  # Retry after waiting
                    else:
                        # Use exponential backoff fallback
                        if attempt < max_retries:
                            backoff = min(60, (2 ** attempt) + random.uniform(0, 1))
                            logger.warning(
                                f"Rate limit exceeded. Using exponential backoff: "
                                f"{backoff:.1f}s (attempt {attempt + 1}/{max_retries + 1})..."
                            )
                            time.sleep(backoff)
                            continue
                        else:
                            logger.error("Rate limit exceeded and max retries reached")
                            return None
                
                # Check for other HTTP errors
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    backoff = min(60, (2 ** attempt) + random.uniform(0, 1))
                    logger.warning(
                        f"Request timeout. Retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})..."
                    )
                    time.sleep(backoff)
                    continue
                else:
                    logger.error(f"Request timeout after {max_retries + 1} attempts: {e}")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries:
                    backoff = min(60, (2 ** attempt) + random.uniform(0, 1))
                    logger.warning(
                        f"Connection error. Retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})..."
                    )
                    time.sleep(backoff)
                    continue
                else:
                    logger.error(f"Connection error after {max_retries + 1} attempts: {e}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                # For other request exceptions, log and return None
                logger.error(f"GitHub API request failed: {e}")
                return None
        
        # All retries exhausted
        logger.error(f"Request failed after {max_retries + 1} attempts")
        return None
    
    def get_open_pull_requests(self) -> List[Dict]:
        """
        Fetch all open pull requests from the repository.
        
        Returns:
            List of PR dictionaries with safe field access.
            Returns empty list on error or if no PRs found.
        """
        url = f"{self.base_url}/repos/{config.github_repository}/pulls"
        url += "?state=open&sort=created&direction=desc"
        
        response = self._make_request(url)
        if not response:
            return []
        
        # Parse JSON with error handling
        try:
            prs = response.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to parse JSON response from GitHub API. "
                f"Status: {response.status_code}, "
                f"Response text (first 500 chars): {response.text[:500]}"
            )
            return []
        
        # Validate that response is a list
        if not isinstance(prs, list):
            logger.error(f"Expected list of PRs, got {type(prs)}")
            return []
        
        # Extract PR data with safe field access
        result = []
        for pr in prs:
            if not isinstance(pr, dict):
                logger.warning(f"Skipping invalid PR entry: {type(pr)}")
                continue
            
            # Safely extract user login
            user_obj = pr.get('user') or {}
            author = user_obj.get('login') if isinstance(user_obj, dict) else 'unknown'
            
            # Extract required fields with defaults
            pr_dict = {
                'number': pr.get('number'),
                'title': pr.get('title') or 'Untitled',
                'body': pr.get('body') or '',
                'html_url': pr.get('html_url') or '',
                'user': author
            }
            
            # Skip if essential fields are missing
            if pr_dict['number'] is None or not pr_dict['html_url']:
                logger.warning(f"Skipping PR with missing essential fields: {pr_dict}")
                continue
            
            result.append(pr_dict)
        
        return result
    
    def get_pull_request_details(self, pr_number: int) -> Optional[Dict]:
        """
        Get detailed information about a specific PR.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            PR details dictionary with safe field access, or None if failed
        """
        url = f"{self.base_url}/repos/{config.github_repository}/pulls/{pr_number}"
        
        response = self._make_request(url)
        if not response:
            return None
        
        # Parse JSON with error handling
        try:
            pr_data = response.json()
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to parse JSON response for PR #{pr_number}. "
                f"Status: {response.status_code}, "
                f"Response text (first 500 chars): {response.text[:500]}"
            )
            return None
        
        # Validate response is a dictionary
        if not isinstance(pr_data, dict):
            logger.error(f"Expected PR data dict, got {type(pr_data)}")
            return None
        
        # Safely extract user login
        user_obj = pr_data.get('user') or {}
        author = user_obj.get('login') if isinstance(user_obj, dict) else 'unknown'
        
        # Extract fields with safe defaults
        return {
            'number': pr_data.get('number'),
            'title': pr_data.get('title') or 'Untitled',
            'body': pr_data.get('body') or '',
            'html_url': pr_data.get('html_url') or '',
            'user': author,
            'state': pr_data.get('state', 'unknown'),
            'created_at': pr_data.get('created_at', ''),
            'updated_at': pr_data.get('updated_at', '')
        }
    
    def get_pull_request_diff(self, pr_number: int) -> Optional[str]:
        """
        Get the diff for a specific pull request.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Diff content as string or None if failed or invalid
        """
        url = f"{self.base_url}/repos/{config.github_repository}/pulls/{pr_number}"
        
        response = self._make_request(url, is_diff=True)
        if not response:
            return None
        
        diff_content = response.text
        
        # Validate diff content exists
        if not diff_content or diff_content.strip() == "":
            logger.warning(f"PR #{pr_number}: No diff content found")
            return None
        
        # Check if diff is in expected format (should start with diff markers)
        # Check first 10 lines for diff format indicators
        lines = diff_content.split('\n')[:10]
        if not any(line.startswith(('+++', '---', '+', '-', '@@')) for line in lines):
            logger.warning(
                f"PR #{pr_number}: Diff format not acceptable, "
                f"missing expected diff markers (+++, ---, +, -, @@)"
            )
            return None
        
        return diff_content
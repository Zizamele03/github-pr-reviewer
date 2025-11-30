"""
HuggingFace LLM integration for generating code reviews from PR diffs.
Handles API failures, retries, and context limits.
"""
import requests
import time
import re
import json
import logging
from typing import Optional, Dict
from src.config import config

logger = logging.getLogger(__name__)

class LLMReviewer:
    """
    HuggingFace-based code reviewer with robust error handling.
    
    Features:
    - Retry logic for transient failures
    - JSON parsing error handling
    - Content truncation for large diffs
    - Fallback review generation when LLM fails
    """
    
    def __init__(self):
        """
        Initialize HuggingFace client with configuration.
        
        Uses the configured HuggingFace model endpoint. The API URL is constructed
        from the model name in config, allowing flexibility in model selection.
        """
        # Use router endpoint for better reliability
        # The router automatically routes to the correct model endpoint
        self.api_url = "https://router.huggingface.co/hf-inference"
        
        # Validate API URL is not empty
        if not self.api_url or not self.api_url.strip():
            raise ValueError("HuggingFace API URL cannot be empty")
        
        self.headers = {
            "Authorization": f"Bearer {config.huggingface_api_key}",
            "Content-Type": "application/json"
        }
        
        # Store model name for use in API requests
        self.model_name = config.huggingface_model
    
    def estimate_tokens(self, text: str) -> int:
        """
        Roughly estimate tokens (characters / 4) since we don't have tiktoken.
        
        Args:
            text: Input text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def truncate_content(self, content: str, max_chars: int = None) -> str:
        """
        Truncate content to fit within character limit.
        
        Args:
            content: Text content to truncate
            max_chars: Maximum allowed characters (defaults to config)
            
        Returns:
            Truncated content
        """
        if max_chars is None:
            max_chars = config.max_diff_length
        
        if len(content) <= max_chars:
            return content
        
        # Try to truncate at a reasonable boundary
        truncated = content[:max_chars]
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars * 0.8:  # If we have a recent newline
            return truncated[:last_newline]
        
        return truncated
    
    def _call_huggingface_api(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        """
        Make API call to HuggingFace with retry logic and error handling.
        
        Args:
            prompt: The prompt to send to the model
            retry_count: Current retry attempt (0-indexed)
            
        Returns:
            Generated text or None if all retries exhausted
        """
        if retry_count >= config.max_retries:
            logger.error(f"HuggingFace API failed after {config.max_retries} retries")
            return None
        
        # Prepare payload with model name and generation parameters
        payload = {
            "model": self.model_name,  # Specify model in request
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.3,
                "do_sample": True,
                "return_full_text": False
            }
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=(5, config.request_timeout)
            )
            
            # Handle successful response
            if response.status_code == 200:
                try:
                    result = response.json()
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(
                        f"Failed to parse JSON response from HuggingFace API. "
                        f"Status: {response.status_code}, "
                        f"Response text (first 500 chars): {response.text[:500]}"
                    )
                    return None
                
                # Extract generated text from response
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    if generated_text:
                        return generated_text.strip()
                    logger.warning("Empty generated_text in HuggingFace response")
                    return None
                elif isinstance(result, dict):
                    # Some models return dict directly
                    generated_text = result.get('generated_text', '')
                    if generated_text:
                        return generated_text.strip()
                    logger.warning("Empty generated_text in HuggingFace response")
                    return None
                else:
                    logger.warning(f"Unexpected response format: {type(result)}")
                    return None
                
            # Handle model loading (503 Service Unavailable)
            elif response.status_code == 503:
                wait_time = 10 * (retry_count + 1)
                logger.info(
                    f"Model is loading, waiting {wait_time} seconds "
                    f"(attempt {retry_count + 1}/{config.max_retries + 1})..."
                )
                time.sleep(wait_time)
                return self._call_huggingface_api(prompt, retry_count + 1)
                
            # Handle other HTTP errors
            else:
                logger.error(
                    f"HuggingFace API error {response.status_code}: "
                    f"{response.text[:500]}"
                )
                # Retry on 5xx errors, but not on 4xx (client errors)
                if 500 <= response.status_code < 600 and retry_count < config.max_retries:
                    wait_time = 5 * (retry_count + 1)
                    logger.info(f"Retrying after {wait_time}s due to server error...")
                    time.sleep(wait_time)
                    return self._call_huggingface_api(prompt, retry_count + 1)
                return None
                
        except requests.exceptions.Timeout as e:
            if retry_count < config.max_retries:
                wait_time = 5 * (retry_count + 1)
                logger.warning(
                    f"Request timeout. Retrying in {wait_time}s "
                    f"(attempt {retry_count + 1}/{config.max_retries + 1})..."
                )
                time.sleep(wait_time)
                return self._call_huggingface_api(prompt, retry_count + 1)
            else:
                logger.error(f"Request timeout after {config.max_retries + 1} attempts: {e}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if retry_count < config.max_retries:
                wait_time = 5 * (retry_count + 1)
                logger.warning(
                    f"Connection error. Retrying in {wait_time}s "
                    f"(attempt {retry_count + 1}/{config.max_retries + 1})..."
                )
                time.sleep(wait_time)
                return self._call_huggingface_api(prompt, retry_count + 1)
            else:
                logger.error(f"Connection error after {config.max_retries + 1} attempts: {e}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HuggingFace API request failed: {e}")
            if retry_count < config.max_retries:
                wait_time = 5 * (retry_count + 1)
                time.sleep(wait_time)
                return self._call_huggingface_api(prompt, retry_count + 1)
            return None
    
    def generate_review(self, pr_title: str, pr_description: str, diff_content: str) -> Optional[str]:
        """
        Generate code review using HuggingFace API.
        
        Args:
            pr_title: Pull request title
            pr_description: Pull request description
            diff_content: Git diff content
            
        Returns:
            Generated review or None if failed
        """
        # Handle empty descriptions
        if not pr_description or pr_description.strip() == "":
            pr_description = "No description provided."
        
        # Truncate diff to fit context
        truncated_diff = self.truncate_content(diff_content)
        
        # Prepare the prompt for smaller models
        prompt = f"""<s>[INST] You are an experienced software engineer reviewing a pull request. 
        Provide specific, actionable feedback focused on:

        1. CODE QUALITY: Code structure, naming, simplicity
        2. BUG RISKS: Potential errors, edge cases, null checks
        3. SECURITY: Input validation, authentication, data exposure
        4. PERFORMANCE: Inefficient operations, memory usage
        5. MAINTAINABILITY: Readability, documentation, complexity

        Be concise but thorough. Point to specific lines when possible.

        Pull Request Details:
        Title: {pr_title}
        Description: {pr_description}

        Code Changes:
        ```diff
        {truncated_diff}
        Provide your code review: [/INST]"""
        review = self._call_huggingface_api(prompt)
        
        if review:
            # Post-process the response to ensure quality
            return self._clean_review_response(review)
        
        return None

    def _clean_review_response(self, review: str) -> str:
        """
        Clean and format the review response from LLM.
        
        Removes incomplete sentences and ensures proper punctuation.
        
        Args:
            review: Raw review text from LLM
            
        Returns:
            Cleaned and formatted review text
        """
        if not review:
            return ""
        
        # Remove any incomplete sentences at the end (text without sentence-ending punctuation)
        review = re.sub(r'[^.!?]+$', '', review)
        
        # Ensure it ends with proper punctuation
        if review and review[-1] not in '.!?':
            review += '.'
        
        return review.strip()
    
    def generate_review_with_fallback(self, pr_title: str, pr_description: str, diff_content: str) -> str:
        """
        Generate review with fallback to basic analysis if LLM fails.
        
        Args:
            pr_title: Pull request title
            pr_description: Pull request description
            diff_content: Git diff content
            
        Returns:
            Generated review or fallback analysis
        """
        review = self.generate_review(pr_title, pr_description, diff_content)
        
        if review:
            return review
        else:
            # Fallback analysis when LLM fails
            return self._generate_fallback_review(diff_content)

    def _generate_fallback_review(self, diff_content: str) -> str:
        """
        Generate basic fallback review when LLM is unavailable.
        
        Provides a simple statistical analysis of the diff when the LLM service
        cannot be reached. This ensures the tool always produces some output.
        
        Args:
            diff_content: Git diff content to analyze
            
        Returns:
            Basic review analysis as markdown-formatted string
        """
        if not diff_content:
            return "## Automated Code Review (Fallback Mode)\n\nNo diff content available for analysis."
        
        lines = diff_content.split('\n')
        added_lines = len([l for l in lines if l.startswith('+') and not l.startswith('+++')])
        removed_lines = len([l for l in lines if l.startswith('-') and not l.startswith('---')])
        file_changes = len([l for l in lines if l.startswith('+++')])
        
        # Simple heuristic analysis based on lines added
        complexity = "LOW"
        if added_lines > 100:
            complexity = "HIGH"
        elif added_lines > 50:
            complexity = "MEDIUM"
        
        logger.info(
            f"Using fallback review mode. "
            f"Files: {file_changes}, Added: {added_lines}, Removed: {removed_lines}, "
            f"Complexity: {complexity}"
        )
        
        return f"""## Automated Code Review (Fallback Mode)

**Note:** AI review service is temporarily unavailable. Basic analysis provided.

### Change Summary
- **Files Modified:** {file_changes}
- **Lines Added:** {added_lines}
- **Lines Removed:** {removed_lines}
- **Change Complexity:** {complexity}

### Recommended Manual Checks
1. **Code Review:** Carefully examine all added code for logic errors
2. **Testing:** Verify adequate test coverage for new functionality
3. **Security:** Check for potential security issues in new code
4. **Documentation:** Ensure comments and docs are updated
5. **Integration:** Test integration with existing systems

Please perform a thorough manual code review of these changes."""
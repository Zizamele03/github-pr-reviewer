"""
Main entry point for GitHub PR Review tool.
Orchestrates the entire review process with HuggingFace integration.
"""
import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
from src.config import config
from src.github_client import GitHubClient
from src.llm_reviewer import LLMReviewer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PRReviewer:
    """Main class orchestrating the PR review process."""
    
    def __init__(self):
        """Initialize PR reviewer with clients."""
        self.github_client = GitHubClient()
        self.llm_reviewer = LLMReviewer()
        self.output_dir = "reviews"
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def validate_pr_data(self, pr_data: Dict) -> bool:
        """
        Validate pull request data before processing.
        
        Checks for required fields and validates data types.
        
        Args:
            pr_data: Pull request data dictionary
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(pr_data, dict):
            logger.error(f"PR data must be a dictionary, got {type(pr_data)}")
            return False
        
        required_fields = ['number', 'title', 'body', 'html_url']
        for field in required_fields:
            if field not in pr_data:
                logger.error(f"Missing required field in PR data: {field}")
                return False
        
        # Validate PR number is a positive integer
        pr_number = pr_data.get('number')
        if not isinstance(pr_number, int) or pr_number <= 0:
            logger.error(f"Invalid PR number: {pr_number} (must be positive integer)")
            return False
            
        return True
    
    def generate_review_filename(self, pr_number: int) -> str:
        """
        Generate filename for review output.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Generated filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_name = config.github_repository.replace('/', '_')
        return f"{self.output_dir}/review_{repo_name}_PR_{pr_number}_{timestamp}.md"
    
    def save_review(self, pr_data: Dict, review: str, filename: str) -> None:
        """
        Save review to markdown file with formatted output.
        
        Creates a well-formatted markdown file with PR metadata and review content.
        
        Args:
            pr_data: Pull request data dictionary
            review: Generated review content
            filename: Output filename path
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                # Write header with PR metadata
                pr_number = pr_data.get('number', 'Unknown')
                pr_title = pr_data.get('title', 'Untitled')
                pr_url = pr_data.get('html_url', '')
                author = pr_data.get('user', 'Unknown')  # Already normalized by github_client
                
                f.write(f"# Code Review for PR #{pr_number}: {pr_title}\n\n")
                f.write(f"**Repository**: {config.github_repository}\n\n")
                if pr_url:
                    f.write(f"**PR URL**: [{pr_url}]({pr_url})\n\n")
                f.write(f"**Author**: {author}\n\n")
                f.write(f"**Review Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(review)
            
            logger.info(f"Review saved to: {filename}")
            
        except OSError as e:
            logger.error(f"Failed to save review to {filename}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving review to {filename}: {e}", exc_info=True)
    
    def review_single_pr(self, pr_number: int) -> bool:
        """
        Review a single pull request by number.
        
        Orchestrates the full review process: fetch PR data, get diff,
        generate review, and save to file.
        
        Args:
            pr_number: Pull request number to review
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Fetching PR #{pr_number}...")
            pr_data = self.github_client.get_pull_request_details(pr_number)
            
            if not pr_data:
                logger.error(f"Failed to fetch PR #{pr_number}")
                return False
            
            if not self.validate_pr_data(pr_data):
                logger.error(f"Invalid data for PR #{pr_number}")
                return False
            
            logger.info(f"Fetching diff for PR #{pr_number}...")
            diff_content = self.github_client.get_pull_request_diff(pr_number)
            
            if not diff_content:
                logger.warning(f"No diff content found for PR #{pr_number}")
                return False
            
            logger.info(f"Generating review for PR #{pr_number}...")
            pr_title = pr_data.get('title', 'Untitled')
            pr_description = pr_data.get('body') or "No description provided."
            
            review = self.llm_reviewer.generate_review_with_fallback(
                pr_title,
                pr_description,
                diff_content
            )
            
            if not review:
                logger.error(f"Failed to generate review for PR #{pr_number}")
                return False
            
            filename = self.generate_review_filename(pr_number)
            self.save_review(pr_data, review, filename)
            
            logger.info(f"Successfully reviewed PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error reviewing PR #{pr_number}: {e}", exc_info=True)
            return False
    
    def review_all_open_prs(self) -> None:
        """
        Review all open pull requests in the repository.
        
        Fetches all open PRs and processes them sequentially with rate limiting.
        Logs progress and summary statistics.
        """
        try:
            logger.info("Fetching open pull requests...")
            prs = self.github_client.get_open_pull_requests()
            
            if not prs:
                logger.info("No open pull requests found.")
                return
            
            logger.info(f"Found {len(prs)} open pull request(s)")
            
            successful_reviews = 0
            for i, pr in enumerate(prs, 1):
                pr_number = pr.get('number')
                if not pr_number:
                    logger.warning(f"Skipping PR with missing number: {pr}")
                    continue
                
                logger.info(f"Processing PR {i}/{len(prs)}: #{pr_number}")
                
                if self.review_single_pr(pr_number):
                    successful_reviews += 1
                
                # Add delay to avoid rate limiting (every 3rd request)
                # This is in addition to the rate limiting in _make_request
                if i % 3 == 0 and i < len(prs):
                    logger.debug("Waiting 10 seconds to avoid rate limiting...")
                    time.sleep(10)
            
            logger.info(
                f"Review process completed: {successful_reviews} successful out of {len(prs)} total"
            )
            
        except Exception as e:
            logger.error(f"Error fetching open PRs: {e}", exc_info=True)


def main():
    """
    Main execution function.
    
    Parses command line arguments and orchestrates the review process.
    Supports reviewing a specific PR (via --pr argument) or all open PRs.
    """
    try:
        logger.info("GitHub PR Reviewer with HuggingFace")
        logger.info(f"Repository: {config.github_repository}")
        logger.info(f"Model: {config.huggingface_model}")
        logger.info("-" * 50)
        
        reviewer = PRReviewer()
        
        # Check for specific PR number from command line
        # Support both --pr 123 and just 123 formats
        pr_number = None
        if len(sys.argv) > 1:
            arg = sys.argv[1]
            # Handle --pr flag
            if arg == '--pr' and len(sys.argv) > 2:
                try:
                    pr_number = int(sys.argv[2])
                except ValueError:
                    logger.error("Invalid PR number after --pr flag. Must be numeric.")
                    sys.exit(1)
            # Handle direct PR number
            elif arg.isdigit() or (arg.startswith('-') and arg[1:].isdigit()):
                try:
                    pr_number = int(arg)
                except ValueError:
                    logger.error("Invalid PR number. Please provide a numeric PR number.")
                    sys.exit(1)
            else:
                logger.warning(f"Unknown argument: {arg}. Use --pr <number> or <number>")
                sys.exit(1)
        
        if pr_number:
            if pr_number <= 0:
                logger.error("PR number must be positive")
                sys.exit(1)
            success = reviewer.review_single_pr(pr_number)
            sys.exit(0 if success else 1)
        else:
            reviewer.review_all_open_prs()
            
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        logger.error("Please check your configuration and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
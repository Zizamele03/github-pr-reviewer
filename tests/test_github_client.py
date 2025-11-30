"""
Unit tests for GitHub client functionality.
"""
import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from src.github_client import GitHubClient
from src import github_client

@patch('src.github_client.config')
class TestGitHubClient(unittest.TestCase):
    """Test cases for GitHubClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config before creating client to avoid requiring actual environment variables
        # Access the mocked config through the patched module
        github_client.config.github_token = 'test_token'
        github_client.config.request_timeout = 30
        github_client.config.max_retries = 3
        self.client = GitHubClient()
    
    def test_handle_rate_limit_with_reset_header(self, mock_config):
        """Test rate limit handling with valid reset header."""
        response = Mock()
        response.status_code = 429
        response.headers = {
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': str(int(time.time()) + 60)  # 60 seconds in future
        }
        
        sleep_time = self.client._handle_rate_limit(response)
        self.assertIsNotNone(sleep_time)
        self.assertGreater(sleep_time, 0)
        self.assertLessEqual(sleep_time, 60)
    
    def test_handle_rate_limit_without_reset_header(self, mock_config):
        """Test rate limit handling without reset header (uses exponential backoff)."""
        response = Mock()
        response.status_code = 429
        response.headers = {
            'X-RateLimit-Remaining': '0'
            # No X-RateLimit-Reset header
        }
        
        sleep_time = self.client._handle_rate_limit(response)
        # Should return None to signal exponential backoff should be used
        self.assertIsNone(sleep_time)
    
    def test_handle_rate_limit_past_reset_time(self, mock_config):
        """Test rate limit handling when reset time is in the past."""
        response = Mock()
        response.status_code = 429
        response.headers = {
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': str(int(time.time()) - 60)  # 60 seconds in past
        }
        
        sleep_time = self.client._handle_rate_limit(response)
        # Should return None to use exponential backoff instead
        self.assertIsNone(sleep_time)
    
    def test_handle_rate_limit_non_rate_limit_status(self, mock_config):
        """Test that non-rate-limit status codes return None."""
        response = Mock()
        response.status_code = 200
        response.headers = {}
        
        sleep_time = self.client._handle_rate_limit(response)
        self.assertIsNone(sleep_time)
    
    @patch('src.github_client.requests.Session')
    def test_make_request_success(self, mock_session_class, mock_config):
        """Test successful API request."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'X-RateLimit-Remaining': '100'}
        mock_response.raise_for_status = Mock()
        
        mock_session.get.return_value = mock_response
        
        client = GitHubClient()
        response = client._make_request('https://api.github.com/test')
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
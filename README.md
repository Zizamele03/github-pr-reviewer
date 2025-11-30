# LLM-Based GitHub Pull Request Code Reviewer

## Overview

This tool automatically reviews GitHub pull requests using Large Language Models (LLMs) from HuggingFace. It fetches open PRs, analyzes code changes, and generates comprehensive code reviews saved as markdown files.

## Architecture

The tool consists of three main components:

1. **GitHub Client** (`src/github_client.py`): Fetches PR data and diff content from GitHub API with robust rate limiting and error handling
2. **LLM Reviewer** (`src/llm_reviewer.py`): Processes changes and generates reviews using HuggingFace Inference API
3. **Main Orchestrator** (`src/main.py`): Coordinates the review process and saves output to markdown files

## File Structure

```
github-pr-reviewer/
├── src/
│   ├── __init__.py          # Package initialization and exports
│   ├── config.py            # Configuration management and validation
│   ├── github_client.py     # GitHub API client with rate limiting
│   ├── llm_reviewer.py      # HuggingFace LLM integration
│   ├── main.py              # Main entry point and orchestration
│   └── utils.py             # Utility functions
├── tests/
│   ├── test_github_client.py # Unit tests for GitHub client
│   └── test_llm_reviewer.py # Unit tests for LLM reviewer
├── reviews/                 # Output directory for generated reviews
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose configuration
├── .dockerignore            # Files to exclude from Docker build
└── README.md                # This file
```

## How It Works

1. **Configuration Loading**: Reads environment variables for GitHub token, HuggingFace API key, and repository name
2. **PR Fetching**: Uses GitHub API to fetch open PRs or a specific PR by number
3. **Diff Retrieval**: Downloads the diff content for each PR
4. **Review Generation**: Sends PR metadata and diff to HuggingFace LLM for analysis
5. **Output**: Saves formatted markdown reviews to the `reviews/` directory

## Setup

### Prerequisites

- Python 3.10 or higher
- GitHub Personal Access Token with `repo` scope
- HuggingFace API Key (get one at https://huggingface.co/settings/tokens)

### Required Environment Variables

Create a `.env` file in the project root (or export these variables):

```bash
# Required
GITHUB_TOKEN=ghp_your_github_token_here
HF_API_KEY=hf_your_huggingface_api_key_here
GITHUB_REPOSITORY=owner/repo-name

# Optional (with defaults)
HUGGINGFACE_MODEL=mistralai/Mistral-7B-Instruct-v0.2
MAX_DIFF_LENGTH=4000
REQUEST_TIMEOUT=30
MAX_RETRIES=5
```

**Note**: The `.env` file should NOT be committed to version control. Add it to `.gitignore`.

## Installation & Usage

### Local Development (Terminal)

1. **Create virtual environment**:
   ```bash
   python -m venv .venv
   ```

2. **Activate virtual environment**:
   ```bash
   # On Linux/macOS:
   source .venv/bin/activate
   
   # On Windows:
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**:
   ```bash
   # Linux/macOS:
   export GITHUB_TOKEN="ghp_xxx"
   export HF_API_KEY="hf_xxx"
   export GITHUB_REPOSITORY="owner/repo"
   
   # Windows PowerShell:
   $env:GITHUB_TOKEN="ghp_xxx"
   $env:HF_API_KEY="hf_xxx"
   $env:GITHUB_REPOSITORY="owner/repo"
   
   # Windows CMD:
   set GITHUB_TOKEN=ghp_xxx
   set HF_API_KEY=hf_xxx
   set GITHUB_REPOSITORY=owner/repo
   ```

   Or use a `.env` file (loaded automatically by python-dotenv).

5. **Run the tool**:
   ```bash
   # Review all open PRs:
   python -m src.main
   
   # Review a specific PR:
   python -m src.main --pr 123
   # or
   python -m src.main 123
   ```

6. **Run tests**:
   ```bash
   pytest -q
   # or
   python -m pytest tests/
   ```

### Docker Usage

1. **Build the Docker image**:
   ```bash
   docker build -t pr-reviewer:latest .
   ```

2. **Run with environment variables**:
   ```bash
   docker run --rm \
     -e GITHUB_TOKEN="ghp_xxx" \
     -e HF_API_KEY="hf_xxx" \
     -e GITHUB_REPOSITORY="owner/repo" \
     -v $(pwd)/reviews:/app/reviews \
     pr-reviewer:latest
   ```

3. **Run with .env file**:
   ```bash
   docker run --rm \
     --env-file .env \
     -v $(pwd)/reviews:/app/reviews \
     pr-reviewer:latest
   ```

4. **Review a specific PR**:
   ```bash
   docker run --rm \
     --env-file .env \
     -v $(pwd)/reviews:/app/reviews \
     pr-reviewer:latest --pr 123
   ```

5. **Using Docker Compose**:
   ```bash
   # Review all open PRs:
   docker-compose up pr-reviewer
   
   # Review specific PR (using profile):
   docker-compose --profile single run pr-reviewer-single
   ```

   Note: Update `docker-compose.yml` with your PR number in the command.

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes | - | GitHub Personal Access Token |
| `HF_API_KEY` | Yes | - | HuggingFace API Key |
| `GITHUB_REPOSITORY` | Yes | - | Repository in `owner/repo` format or GitHub URL |
| `HUGGINGFACE_MODEL` | No | `mistralai/Mistral-7B-Instruct-v0.2` | HuggingFace model name (supports `owner/model` or single-token like `gpt2`) |
| `MAX_DIFF_LENGTH` | No | `4000` | Maximum characters in diff to send to LLM |
| `REQUEST_TIMEOUT` | No | `30` | HTTP request timeout in seconds |
| `MAX_RETRIES` | No | `5` | Maximum retry attempts for failed requests |

## Output

Reviews are saved to the `reviews/` directory with the following naming format:
```
review_{repository}_PR_{number}_{timestamp}.md
```

Example: `review_owner_repo_PR_123_20240101_120000.md`

Each review file contains:
- PR metadata (number, title, URL, author)
- Generated review content from the LLM
- Timestamp of when the review was generated

## Error Handling

The tool includes robust error handling:

- **Rate Limiting**: Automatic exponential backoff with respect for GitHub's rate limit headers
- **JSON Parsing**: Graceful handling of malformed API responses
- **Missing Fields**: Safe field access with fallback values
- **Network Errors**: Retry logic for transient failures
- **LLM Failures**: Fallback to basic statistical analysis when LLM is unavailable

## Testing

Run the test suite:
```bash
pytest -q
```

Run with verbose output:
```bash
pytest -v
```

Run specific test file:
```bash
pytest tests/test_github_client.py
```

## Module Interaction Diagram

```
┌─────────────┐
│   main.py   │  Entry point, orchestrates review process
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
       ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   config    │ │  github_    │ │   llm_      │
│    .py      │ │  client.py  │ │  reviewer.py│
└─────────────┘ └──────┬──────┘ └──────┬──────┘
                       │               │
                       │               │
              ┌────────┴────────┐      │
              │                 │      │
              ▼                 ▼      ▼
       GitHub API        HuggingFace API
       (PRs, diffs)      (LLM inference)
              │                 │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────┐
              │  reviews/   │
              │  (output)   │
              └─────────────┘
```

## API Key Usage

- **GitHub Token**: Used for authenticating GitHub API requests. Required scopes: `repo` (for private repos) or `public_repo` (for public repos only).
- **HuggingFace API Key**: Used for authenticating HuggingFace Inference API requests. Get your key from https://huggingface.co/settings/tokens.

Both keys are read from environment variables and never hardcoded or committed to the repository.

## Changes & Summary

### What Was Fixed

- **Model Name Validation**: Now supports both `owner/model` and single-token models (e.g., `gpt2`, `distilgpt2`)
- **Rate Limit Handling**: Replaced recursive retry with exponential backoff and proper rate limit header handling
- **JSON Parsing Errors**: Added try/except blocks around all `response.json()` calls with proper error logging
- **KeyError Protection**: Safe field access for PR data, especially user field which may be missing
- **User Field Consistency**: Normalized user field handling across all modules
- **Orphaned Code**: Removed stray function from `__init__.py`
- **Broken Tests**: Fixed test to work with actual `_handle_rate_limit` implementation
- **Hardcoded API URL**: Now uses configured API URL from config
- **Docker Secrets**: Removed `.env` file from Docker image, uses environment variables at runtime
- **Logging**: Replaced all `print()` statements with proper logging module
- **Type Hints**: Added type hints to public functions
- **HTTP Session**: Added connection pooling with `requests.Session()`
- **Timeout Handling**: Added proper timeout handling for network requests

### Breaking Changes

None. All changes are backward compatible.

### Verification Steps

1. **Test Configuration**:
   ```bash
   python -c "from src.config import config; print(f'Repo: {config.github_repository}')"
   ```

2. **Test GitHub Client**:
   ```bash
   python -c "from src.github_client import GitHubClient; c = GitHubClient(); print('GitHub client initialized')"
   ```

3. **Run Tests**:
   ```bash
   python -m pytest tests/
   ```

4. **Test Full Workflow** (with valid credentials):
   ```bash
   python -m src.main --pr <valid_pr_number>
   ```

5. **Check Output**:
   ```bash
   ls -la reviews/
   ```

## Troubleshooting

### "Missing required environment variable"
- Ensure all required environment variables are set
- Check that `.env` file exists and is in the project root
- Verify variable names match exactly (case-sensitive)

### "Rate limit exceeded"
- The tool automatically handles rate limits with exponential backoff
- If persistent, check your GitHub token permissions
- Consider using a token with higher rate limits

### "Failed to parse JSON response"
- Check network connectivity
- Verify API keys are valid
- Check GitHub/HuggingFace API status

### "No diff content found"
- PR may be empty or have no file changes
- PR may be from a fork with restricted access
- Check PR permissions and repository access

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

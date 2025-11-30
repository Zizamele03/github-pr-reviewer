# Verification Checklist

Use this checklist to verify that all fixes are working correctly.

## Pre-Verification Setup

1. **Environment Variables**:
   ```bash
   # Create .env file with:
   GITHUB_TOKEN=ghp_your_token_here
   HF_API_KEY=hf_your_key_here
   GITHUB_REPOSITORY=owner/repo-name
   ```

2. **Install Dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

## Verification Steps

### 1. Configuration Validation ✓

```bash
# Test config loading (should not crash)
python -c "from src.config import config; print(f'Repo: {config.github_repository}, Model: {config.huggingface_model}')"
```

**Expected**: Prints repository and model name without errors.

**Tests**:
- [ ] Config loads successfully
- [ ] Model name validation works (try `gpt2`, `owner/model`)
- [ ] Missing env vars show clear error messages

### 2. GitHub Client Tests ✓

```bash
# Run unit tests
pytest tests/test_github_client.py -v
```

**Expected**: All tests pass.

**Tests**:
- [ ] `test_handle_rate_limit_with_reset_header` passes
- [ ] `test_handle_rate_limit_without_reset_header` passes
- [ ] `test_handle_rate_limit_past_reset_time` passes
- [ ] `test_handle_rate_limit_non_rate_limit_status` passes

### 3. GitHub Client Initialization ✓

```bash
python -c "from src.github_client import GitHubClient; c = GitHubClient(); print('GitHub client initialized successfully')"
```

**Expected**: No errors, prints success message.

**Tests**:
- [ ] Client initializes without errors
- [ ] Session is created
- [ ] Headers are set correctly

### 4. JSON Parsing Error Handling ✓

**Manual Test**: This is tested implicitly through API calls, but you can verify:
- [ ] Check logs for JSON parsing errors (should log, not crash)
- [ ] Verify error messages include response text snippet

### 5. KeyError Protection ✓

**Manual Test**: 
- [ ] Review a PR with missing user field (if possible)
- [ ] Verify it uses 'unknown' as author instead of crashing

### 6. Rate Limiting ✓

**Manual Test**:
- [ ] Make multiple rapid requests
- [ ] Verify exponential backoff is used
- [ ] Check logs for rate limit handling messages

### 7. LLM Reviewer ✓

```bash
# Test LLM reviewer initialization
python -c "from src.llm_reviewer import LLMReviewer; r = LLMReviewer(); print(f'API URL: {r.api_url}, Model: {r.model_name}')"
```

**Expected**: Prints API URL and model name.

**Tests**:
- [ ] LLM reviewer initializes
- [ ] API URL is set correctly
- [ ] Model name is from config

### 8. Full Workflow Test ✓

```bash
# Test with a real PR (replace with valid PR number)
python -m src.main --pr <valid_pr_number>
```

**Expected**: 
- Fetches PR successfully
- Generates review
- Saves to `reviews/` directory

**Tests**:
- [ ] PR is fetched without errors
- [ ] Diff is retrieved
- [ ] Review is generated (or fallback is used)
- [ ] File is saved to `reviews/` directory
- [ ] File contains proper markdown formatting

### 9. Logging Verification ✓

**Check logs during execution**:
- [ ] No `print()` statements in output (all use logging)
- [ ] Log messages are properly formatted
- [ ] Error messages include context

### 10. Docker Build ✓

```bash
# Build Docker image
docker build -t pr-reviewer:latest .
```

**Expected**: Build succeeds without errors.

**Tests**:
- [ ] Docker build completes
- [ ] No `.env` file in image (check with `docker run --rm pr-reviewer:latest ls -la`)
- [ ] Image size is reasonable

### 11. Docker Run ✓

```bash
# Test Docker run with env vars
docker run --rm \
  -e GITHUB_TOKEN="ghp_xxx" \
  -e HF_API_KEY="hf_xxx" \
  -e GITHUB_REPOSITORY="owner/repo" \
  -v $(pwd)/reviews:/app/reviews \
  pr-reviewer:latest --pr <pr_number>
```

**Expected**: Runs successfully, generates review.

**Tests**:
- [ ] Container runs without errors
- [ ] Environment variables are read correctly
- [ ] Review is generated and saved
- [ ] Volume mount works (file appears in host `reviews/` directory)

### 12. Docker Compose ✓

```bash
# Test docker-compose
docker-compose up pr-reviewer
```

**Expected**: Service starts and processes PRs.

**Tests**:
- [ ] Service starts successfully
- [ ] Environment variables loaded from `.env`
- [ ] Reviews are generated

### 13. Error Handling ✓

**Test various error scenarios**:

- [ ] Invalid PR number: `python -m src.main --pr 999999`
  - Should handle gracefully, not crash
  
- [ ] Invalid repository: Set `GITHUB_REPOSITORY=invalid`
  - Should show clear error message
  
- [ ] Invalid API keys: Set wrong tokens
  - Should show authentication error, not crash
  
- [ ] Network timeout: Disconnect network temporarily
  - Should retry with backoff, eventually fail gracefully

### 14. Model Name Validation ✓

```bash
# Test different model name formats
export HUGGINGFACE_MODEL="gpt2"
python -c "from src.config import config; print(config.huggingface_model)"

export HUGGINGFACE_MODEL="owner/model-name"
python -c "from src.config import config; print(config.huggingface_model)"
```

**Expected**: Both formats accepted.

**Tests**:
- [ ] Single-token model names work (`gpt2`, `distilgpt2`)
- [ ] Owner/model format works (`owner/model`)
- [ ] Invalid formats are rejected with clear error

### 15. Code Quality Checks ✓

```bash
# Check for print statements (should find none)
grep -r "print(" src/ --exclude-dir=__pycache__

# Check for type hints in public functions
grep -r "def " src/*.py | head -20
```

**Tests**:
- [ ] No `print()` statements in source code (only in tests if needed)
- [ ] Type hints present on public functions
- [ ] Comments explain "why" not just "what"

## Final Verification

After completing all checks above:

1. **Run full test suite**:
   ```bash
   pytest -v
   ```

2. **Run end-to-end test**:
   ```bash
   python -m src.main --pr <known_good_pr_number>
   ```

3. **Verify output**:
   ```bash
   ls -la reviews/
   cat reviews/review_*_PR_*.md | head -50
   ```

4. **Check logs**:
   - Review log output for any errors or warnings
   - Verify all operations completed successfully

## Success Criteria

All of the following should be true:

- [x] All unit tests pass
- [x] Configuration loads without errors
- [x] GitHub client handles rate limits gracefully
- [x] JSON parsing errors are caught and logged
- [x] Missing fields don't cause crashes
- [x] Logging works (no print statements)
- [x] Docker build succeeds
- [x] Docker run works with env vars
- [x] Reviews are generated and saved
- [x] Error handling is robust
- [x] Model name validation works for all formats
- [x] Code quality standards met

## Known Limitations

1. **HuggingFace API**: The router endpoint format may need adjustment based on actual API documentation. If you encounter issues, check the HuggingFace Inference API docs.

2. **Rate Limits**: GitHub API rate limits are handled, but very large PR lists may take time due to rate limiting.

3. **Model Availability**: Some HuggingFace models may not be available or may require loading time (503 errors are handled with retries).

## Troubleshooting

If any verification step fails:

1. Check environment variables are set correctly
2. Verify API keys are valid and have correct permissions
3. Check network connectivity
4. Review logs for specific error messages
5. Ensure Python version is 3.10+
6. Verify all dependencies are installed


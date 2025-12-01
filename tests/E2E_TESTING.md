# End-to-End Integration Tests

This document describes the comprehensive end-to-end (E2E) integration tests for the AI Blogger (Inker) project.

## Overview

The E2E integration tests (`tests/test_e2e_integration.py`) validate the complete workflow from fetching articles through generating final blog posts. They test the integration of all major components:

- **Article Fetchers**: Hacker News, Tavily (web search), YouTube
- **Storage Backends**: SQLite, PostgreSQL
- **Queue Backends**: Memory, PostgreSQL, Redis
- **LLM Chains**: Generation, scoring, refinement
- **Job Management**: Job API, job store, persistence

## Running the Tests

### Run All E2E Tests

```bash
pytest tests/test_e2e_integration.py -v -m integration
```

### Run Specific Test Classes

```bash
# Test only the complete pipeline
pytest tests/test_e2e_integration.py::TestEndToEndPipeline -v -m integration

# Test only storage backends
pytest tests/test_e2e_integration.py::TestStorageBackendIntegration -v -m integration

# Test only queue backends
pytest tests/test_e2e_integration.py::TestQueueBackendIntegration -v -m integration

# Test only job management
pytest tests/test_e2e_integration.py::TestJobManagementIntegration -v -m integration

# Test error recovery
pytest tests/test_e2e_integration.py::TestErrorRecoveryAndEdgeCases -v -m integration
```

### Run Individual Tests

```bash
# Test complete pipeline with Hacker News only
pytest tests/test_e2e_integration.py::TestEndToEndPipeline::test_complete_pipeline_hacker_news_only -v -m integration

# Test SQLite storage workflow
pytest tests/test_e2e_integration.py::TestStorageBackendIntegration::test_sqlite_storage_full_workflow -v -m integration
```

## Environment Requirements

### Required for All Tests

- **Python 3.9+**
- **OPENAI_API_KEY**: Required for LLM-based generation, scoring, and refinement

### Optional for Enhanced Testing

- **TAVILY_API_KEY** (or **TAVILY_KEY**): Enables web search fetcher tests
- **YOUTUBE_API_KEY**: Enables YouTube fetcher tests
- **DATABASE_URL**: Enables PostgreSQL storage and queue tests (format: `postgresql://user:pass@host/db`)
- **REDIS_URL**: Enables Redis queue tests (format: `redis://host:port`)

### Example: Set Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
export TAVILY_API_KEY="tvly-..."
export YOUTUBE_API_KEY="AIza..."
export DATABASE_URL="postgresql://localhost/inker_test"
export REDIS_URL="redis://localhost:6379"
```

## Test Coverage

### 1. Complete Pipeline Tests (`TestEndToEndPipeline`)

Tests the full blog generation workflow end-to-end:

- **test_complete_pipeline_hacker_news_only**: Complete pipeline using only Hacker News (no API keys required except OpenAI)
  - Fetches articles from Hacker News
  - Generates candidate posts
  - Scores candidates
  - Refines and saves the winner
  
- **test_complete_pipeline_all_sources**: Tests with all available sources (Hacker News, Tavily, YouTube)
  - Dynamically detects available sources based on API keys
  - Validates multi-source article fetching
  - Ensures pipeline works with heterogeneous data sources

- **test_pipeline_with_insufficient_articles**: Tests pipeline with minimal article count
  - Validates graceful handling when few articles are available

- **test_pipeline_error_handling_no_articles**: Tests error handling when no articles found
  - Expects appropriate error when trying to generate with zero articles

### 2. Storage Backend Tests (`TestStorageBackendIntegration`)

Tests persistence layer integration:

- **test_sqlite_storage_full_workflow**: Complete workflow with SQLite
  - Creates temporary SQLite database
  - Creates, retrieves, and updates jobs
  - Lists jobs from storage
  - Validates all CRUD operations

- **test_postgres_storage_if_available**: Complete workflow with PostgreSQL (requires DATABASE_URL)
  - Creates jobs in PostgreSQL
  - Updates job status
  - Validates PostgreSQL-specific functionality

### 3. Queue Backend Tests (`TestQueueBackendIntegration`)

Tests job queue integration:

- **test_memory_queue_workflow**: In-memory queue operations
  - Enqueues jobs
  - Dequeues jobs
  - Completes jobs
  - Validates queue lifecycle

- **test_postgres_queue_if_available**: PostgreSQL queue workflow (requires DATABASE_URL)
  - Tests persistent queue with PostgreSQL backend

- **test_redis_queue_if_available**: Redis queue workflow (requires REDIS_URL)
  - Tests Redis-backed queue operations
  - Validates high-performance queue backend

### 4. Job Management Tests (`TestJobManagementIntegration`)

Tests the job management API:

- **test_job_creation_and_retrieval**: Job API CRUD operations
  - Creates jobs via JobService
  - Retrieves job status
  - Validates job metadata

- **test_job_submission_with_correlation_id**: Idempotency testing
  - Submits job with correlation ID
  - Re-submits same correlation ID
  - Validates duplicate detection and idempotent behavior

### 5. Error Recovery Tests (`TestErrorRecoveryAndEdgeCases`)

Tests error handling and edge cases:

- **test_missing_openai_key_fails_gracefully**: Validates behavior without OpenAI key
  - Fetching should still work
  - Generation should fail appropriately

- **test_pipeline_with_mixed_source_availability**: Mixed source availability
  - Removes some API keys
  - Validates pipeline uses only available sources

- **test_auto_storage_detection**: Auto-detection of storage backend
  - Tests SQLite fallback (default)
  - Tests PostgreSQL detection from DATABASE_URL

- **test_auto_queue_detection**: Auto-detection of queue backend
  - Tests memory queue fallback (default)
  - Tests PostgreSQL queue detection
  - Tests Redis queue detection

## Test Output Examples

### Successful Pipeline Test

```
[1/4] Fetching articles from Hacker News...
[2/4] Generating candidate blog posts...
[3/4] Scoring candidates...
[4/4] Refining winner...

✓ Complete pipeline test passed
  Articles fetched: 5
  Candidates generated: 2
  Winner score: 8.75/10
  Output file: /tmp/tmpxyz/ai-powered-blog-generation.md
```

### Multi-Source Test

```
Testing with sources: ['hacker_news', 'web', 'youtube']
Articles fetched from: {'hacker_news', 'web', 'youtube'}

✓ Multi-source pipeline test passed
  Sources used: {'hacker_news', 'web', 'youtube'}
  Total articles: 15
  Final score: 9.12/10
```

## Integration with CI/CD

The E2E tests are marked with `@pytest.mark.integration` and can be:

- **Included** in CI: `pytest -m integration`
- **Excluded** from unit tests: `pytest -m "not integration"`

### Recommended CI Setup

```yaml
# Example GitHub Actions workflow
- name: Run E2E Tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
    DATABASE_URL: postgresql://postgres:postgres@localhost/test
  run: |
    pytest tests/test_e2e_integration.py -v -m integration
```

## Skipped Tests

Tests automatically skip when dependencies are unavailable:

- **OpenAI tests**: Skip if `OPENAI_API_KEY` not set
- **Tavily tests**: Skip if `TAVILY_API_KEY` not set
- **YouTube tests**: Skip if `YOUTUBE_API_KEY` not set
- **PostgreSQL tests**: Skip if `DATABASE_URL` not set or not pointing to PostgreSQL
- **Redis tests**: Skip if `REDIS_URL` not set or Redis dependencies not installed

## Debugging Failed Tests

### Verbose Output

```bash
pytest tests/test_e2e_integration.py::TestEndToEndPipeline::test_complete_pipeline_hacker_news_only -vv -s
```

The `-s` flag shows print statements, including progress indicators.

### Common Issues

1. **"OpenAI API key required"**: Set `OPENAI_API_KEY` environment variable
2. **"Tavily API key not configured"**: Set `TAVILY_API_KEY` or run tests that don't require it
3. **Import errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`
4. **Database connection errors**: Verify `DATABASE_URL` is correct and database is accessible
5. **Redis connection errors**: Verify `REDIS_URL` is correct and Redis is running

## Best Practices

1. **Isolation**: Each test uses temporary directories and databases
2. **Cleanup**: Fixtures automatically clean up resources
3. **Idempotency**: Tests can be run multiple times safely
4. **Parallel Execution**: Tests are designed to be independent (though LLM API rate limits may apply)
5. **Cost Awareness**: Tests that call OpenAI API consume tokens; use sparingly

## Future Enhancements

Potential additions to E2E testing:

- [ ] Frontend API integration tests
- [ ] Feedback API workflow tests
- [ ] Multi-worker queue processing tests
- [ ] Performance benchmarks
- [ ] Chaos testing (network failures, API timeouts)
- [ ] Load testing with concurrent jobs
- [ ] Database migration testing
- [ ] Metrics and observability validation

## Related Documentation

- [Developer Guide](../docs/developer-guide.md)
- [Architecture](../docs/architecture.md)
- [Testing Guide](../docs/contributing.md#testing)
- [Persistence Guide](../docs/persistence.md)

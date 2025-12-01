# E2E Integration Tests - Quick Reference

## Quick Start

```bash
# Run all E2E tests
pytest tests/test_e2e_integration.py -v -m integration

# Run with minimal dependencies (no API keys needed except OpenAI)
export OPENAI_API_KEY="sk-..."
pytest tests/test_e2e_integration.py::TestEndToEndPipeline::test_complete_pipeline_hacker_news_only -v

# Run without calling LLM APIs (testing infrastructure only)
pytest tests/test_e2e_integration.py::TestStorageBackendIntegration -v -m integration
pytest tests/test_e2e_integration.py::TestQueueBackendIntegration::test_memory_queue_workflow -v
```

## Test Categories

| Category | Tests | Requires |
|----------|-------|----------|
| **Pipeline** | 4 | OPENAI_API_KEY |
| **Storage** | 2 | None (SQLite) / DATABASE_URL (PostgreSQL) |
| **Queue** | 3 | None (Memory) / DATABASE_URL (PostgreSQL) / REDIS_URL (Redis) |
| **Job API** | 2 | None |
| **Edge Cases** | 4 | Various |

## Environment Variables

| Variable | Required | Used For |
|----------|----------|----------|
| `OPENAI_API_KEY` | ✅ Yes | LLM generation, scoring, refinement |
| `TAVILY_API_KEY` | ❌ Optional | Web search fetcher tests |
| `YOUTUBE_API_KEY` | ❌ Optional | YouTube fetcher tests |
| `DATABASE_URL` | ❌ Optional | PostgreSQL storage & queue tests |
| `REDIS_URL` | ❌ Optional | Redis queue tests |

## Common Commands

```bash
# See what will run
pytest tests/test_e2e_integration.py --collect-only

# Run with verbose output
pytest tests/test_e2e_integration.py -vv -s -m integration

# Run specific test class
pytest tests/test_e2e_integration.py::TestEndToEndPipeline -v -m integration

# Run specific test
pytest tests/test_e2e_integration.py::TestEndToEndPipeline::test_complete_pipeline_hacker_news_only -v

# Show skip reasons
pytest tests/test_e2e_integration.py -v -rs -m integration

# Run all tests except integration
pytest -m "not integration"
```

## Test Matrix

### Minimum Requirements (Local Dev)
```bash
export OPENAI_API_KEY="sk-..."
# Runs: 6 tests (pipeline + job management + some edge cases)
# Skips: 9 tests (missing API keys/backends)
```

### Standard Setup (Most Tests)
```bash
export OPENAI_API_KEY="sk-..."
export TAVILY_API_KEY="tvly-..."
# Runs: 10+ tests
# Skips: PostgreSQL, Redis tests
```

### Full Setup (All Tests)
```bash
export OPENAI_API_KEY="sk-..."
export TAVILY_API_KEY="tvly-..."
export YOUTUBE_API_KEY="AIza..."
export DATABASE_URL="postgresql://localhost/inker_test"
export REDIS_URL="redis://localhost:6379"
# Runs: All 15 tests
```

## Test Behavior

✅ **Auto-Skip**: Tests skip gracefully when dependencies unavailable  
✅ **Isolated**: Each test uses temporary resources  
✅ **Cleanup**: Automatic cleanup of temp files/databases  
✅ **Idempotent**: Can run multiple times safely  
✅ **Parallel-Safe**: Tests are independent  

## Expected Output

### Successful Test
```
tests/test_e2e_integration.py::TestEndToEndPipeline::test_complete_pipeline_hacker_news_only 

[1/4] Fetching articles from Hacker News...
[2/4] Generating candidate blog posts...
[3/4] Scoring candidates...
[4/4] Refining winner...

✓ Complete pipeline test passed
  Articles fetched: 5
  Candidates generated: 2
  Winner score: 8.75/10
  Output file: /tmp/tmpxyz/blog-post.md

PASSED [100%]
```

### Skipped Test
```
tests/test_e2e_integration.py::TestQueueBackendIntegration::test_redis_queue_if_available 
SKIPPED (REDIS_URL not configured)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "OpenAI API key required" | Set `OPENAI_API_KEY` environment variable |
| "Tavily API key not configured" | Set `TAVILY_API_KEY` (or skip with `-k 'not tavily'`) |
| Import errors | Run `pip install -r requirements.txt` |
| Database errors | Check `DATABASE_URL` connection string |
| All tests skip | Check you're using `-m integration` marker |

## Integration with CI

```yaml
# .github/workflows/test.yml
- name: E2E Tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
  run: pytest tests/test_e2e_integration.py -v -m integration
```

## Documentation

- **Comprehensive Guide**: `tests/E2E_TESTING.md`
- **Summary**: `tests/E2E_SUMMARY.md`
- **This File**: `tests/E2E_QUICKREF.md`

## Test Stats

- **Total Tests**: 15
- **Test Classes**: 5
- **Lines of Code**: ~619
- **Fixtures**: 4
- **Coverage**: Complete stack (fetchers → LLM → storage → jobs)

---

For detailed information, see `tests/E2E_TESTING.md`

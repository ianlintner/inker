# AI Blogger Agent Instructions

## Overview

You are assisting with the AI Blogger (Inker) project - a LangChain-based automated daily AI blogger that discovers software engineering news, generates blog posts, scores them, and outputs polished Markdown content.

## Project Structure

```
ai_blogger/
├── __main__.py     # CLI entrypoint
├── config.py       # Topics, scoring weights, constants
├── fetchers.py     # Modular fetcher architecture (Hacker News, Web, YouTube)
├── chains.py       # LangChain chains (writer, critic, refiner)
├── models.py       # Pydantic models (Article, CandidatePost, PostScore, ScoredPost)
├── utils.py        # Utility functions (slugify, timestamps)
└── __init__.py     # Package exports
tests/
├── features/       # BDD feature files (.feature)
├── step_defs/      # Step definitions for BDD tests
└── test_*.py       # Unit tests
```

## Key Components

### Fetchers (`fetchers.py`)

- **BaseFetcher**: Abstract base class for all article fetchers
- **HackerNewsFetcher**: Fetches from Hacker News Algolia API (no API key required)
- **WebSearchFetcher**: Fetches from Tavily (requires TAVILY_API_KEY)
- **YouTubeFetcher**: Fetches from YouTube Data API v3 (requires YOUTUBE_API_KEY)

To add a new fetcher:
```python
@register_fetcher("my_source")
class MySourceFetcher(BaseFetcher):
    name = "my_source"
    env_key = "MY_SOURCE_API_KEY"
    description = "Description of my source"

    def fetch(self, topic: str, max_results: int) -> List[Article]:
        # Implementation
        pass
```

### Chains (`chains.py`)

- **generate_candidates()**: Creates candidate blog posts from articles using LLM
- **score_candidate()**: Scores a single candidate post on relevance, originality, depth, clarity, engagement
- **score_candidates()**: Scores all candidates and sorts by total score
- **refine_winner()**: Polishes the winning post into final Markdown

### Models (`models.py`)

- **Article**: News article from any source
- **CandidatePost**: Draft blog post with title, content, sources, topic
- **PostScore**: Scoring breakdown (relevance, originality, depth, clarity, engagement, total, reasoning)
- **ScoredPost**: Candidate with its score

## Testing Guidelines

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=ai_blogger

# Run specific BDD feature
pytest tests/ -v -k "hacker_news"
```

### Writing Tests

1. **Unit tests**: Test individual components in isolation with mocks
2. **BDD tests**: Test behavior using Gherkin feature files
3. **Integration tests**: Test component interactions with mocked external services

### Mocking External Services

Always mock external API calls:
- Use `unittest.mock` or `pytest-mock` for patching
- Mock `requests.get` for Hacker News and YouTube
- Mock `TavilyClient` for web search
- Mock `ChatOpenAI` for LLM calls

Example:
```python
@pytest.fixture
def mock_hacker_news_response():
    return {
        "hits": [
            {"title": "Test Article", "url": "https://example.com", "objectID": "123"}
        ]
    }

def test_fetch_articles(mock_hacker_news_response, mocker):
    mocker.patch("requests.get", return_value=Mock(json=lambda: mock_hacker_news_response))
    # Test code here
```

## Environment Variables

- `OPENAI_API_KEY` (required): For LLM interactions
- `TAVILY_API_KEY` (optional): For web search
- `YOUTUBE_API_KEY` (optional): For YouTube trending videos
- `OPENAI_MODEL` (optional): LLM model name, defaults to "gpt-4"

## Code Style

- Use Black for formatting (line-length=120)
- Use isort for import sorting (profile=black)
- Follow PEP 8 guidelines
- Add type hints to all functions
- Document functions with docstrings

## Pipeline Flow

```
1. topics → fetch_all_articles()
2. articles → generate_candidates()
3. candidates → score_candidates()
4. sorted_candidates → refine_winner()
5. final_content → write to Markdown file
```

## Common Tasks

### Adding a New Topic
Edit `config.py` and add to the `TOPICS` list.

### Changing Scoring Weights
Edit `SCORING_WEIGHTS` in `config.py`. Ensure weights sum to 1.0.

### Modifying LLM Prompts
Edit the prompt templates in `chains.py` within the respective functions.

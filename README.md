# AI Blogger (Inker)

A LangChain-based automated daily AI blogger that discovers new software-engineering news (Hacker News, web search, and trending YouTube videos), generates several draft blog posts, scores them, refines the winner, and outputs a final Markdown blog post.

Designed for **simple CLI execution** and **cron automation**.

**Requires Python 3.9 or higher.**

## Features

- **Modular, extensible architecture** for easy addition of new sources
- **Multi-source news fetching**:
  - Hacker News articles
  - Web search results (via Tavily)
  - Trending YouTube videos (via YouTube Data API v3)
- **Dynamic source selection** via CLI
- **AI-powered content generation** using LangChain and GPT-4
- **Automated scoring and selection** of best content
- **Markdown output** ready for publishing

## Project Structure

```
ai_blogger/
├── __main__.py            # CLI entrypoint
├── config.py              # Topics, scoring weights, constants
├── fetchers.py            # Modular fetcher architecture + implementations
├── chains.py              # LangChain chains (writer, critic, refiner)
├── models.py              # Pydantic models
├── utils.py               # slugify, timestamps
└── __init__.py            # Package exports
```

## Installation

```bash
# Clone the repository
git clone https://github.com/ianlintner/inker.git
cd inker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set the following environment variables:

```bash
# Required
export OPENAI_API_KEY="your-openai-api-key"

# Optional (for extended features)
export TAVILY_API_KEY="your-tavily-api-key"    # For web search
export YOUTUBE_API_KEY="your-youtube-api-key"  # For YouTube trending
```

## Usage

### Basic Usage

```bash
python -m ai_blogger
```

### With Options

```bash
# Generate 5 candidates and save to custom directory
python -m ai_blogger --num-posts 5 --out-dir ./my-posts

# Search specific topics
python -m ai_blogger --topics "AI coding" "developer tools"

# Use only specific sources
python -m ai_blogger --sources hacker_news youtube

# Set custom result counts per source
python -m ai_blogger --max-results "hacker_news:15,youtube:10"

# List available sources and their status
python -m ai_blogger --list-sources

# Dry run (see what would be done)
python -m ai_blogger --dry-run

# Verbose output
python -m ai_blogger -v
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--num-posts N` | Number of candidate posts to generate | 3 |
| `--out-dir DIR` | Output directory for blog posts | ./posts |
| `--topics TOPIC...` | Topics to search for | Config defaults |
| `--sources SOURCE...` | Sources to fetch from | All available |
| `--max-results FORMAT` | Max results per source (e.g., "hacker_news:10,youtube:5") | Config defaults |
| `--list-sources` | List all available sources and exit | - |
| `--dry-run` | Print what would be done without executing | False |
| `-v, --verbose` | Enable verbose output | False |

## Adding New Sources

The fetcher architecture is modular and extensible. To add a new source:

```python
from typing import List
from ai_blogger.fetchers import BaseFetcher, register_fetcher
from ai_blogger.models import Article

@register_fetcher("my_source")
class MySourceFetcher(BaseFetcher):
    name = "my_source"
    env_key = "MY_SOURCE_API_KEY"  # Optional, set to None if no key needed
    description = "Fetch articles from My Source"

    def fetch(self, topic: str, max_results: int) -> List[Article]:
        # Your implementation here
        articles = []
        # ... fetch and parse articles ...
        return articles
```

Once registered, the new source will automatically:
- Appear in `--list-sources`
- Be available via `--sources my_source`
- Support custom max results via `--max-results "my_source:10"`

## Cron Automation

Run daily at 6 AM:

```bash
0 6 * * * cd /opt/ai_blogger && \
  /opt/ai_blogger/venv/bin/python -m ai_blogger \
  --num-posts 3 --out-dir ./posts
```

## Topics

The default topics searched are:

- AI software engineering
- Agentic AI development
- Copilot coding assistants
- Developer productivity
- Software engineering leadership
- Cybersecurity
- AI security
- Dev tools
- Cloud infrastructure

## Pipeline Overview

```
topics → fetch_all_articles(sources=[...])
        → includes selected sources
        → generate_candidates()
        → score_candidates()
        → refine_winner()
        → write markdown
```

## API Requirements

### YouTube Data API v3

- Videos are filtered to only include those published within the last 7 days
- Results are limited to English content
- Each video is converted to an Article object with title, URL, channel, summary, and topic

### Hacker News

- Uses the Algolia API for searching stories
- No API key required

### Tavily (Web Search)

- Requires `TAVILY_API_KEY` environment variable
- Provides general web search results

## License

MIT

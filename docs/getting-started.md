# Getting Started

This guide will help you get AI Blogger (Inker) up and running quickly.

## Prerequisites

Before installing AI Blogger, ensure you have:

- **Python 3.9 or higher**
- **pip** (Python package manager)
- **OpenAI API key** (required for content generation)

Optional API keys for extended features:

- **Tavily API key** for web search
- **YouTube Data API v3 key** for YouTube trending videos

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/ianlintner/inker.git
cd inker

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### As a Package

```bash
pip install -e .
```

## Configuration

### Environment Variables

Set up your API keys as environment variables:

```bash
# Required
export OPENAI_API_KEY="your-openai-api-key"

# Optional - for extended features
export TAVILY_API_KEY="your-tavily-api-key"    # Web search
export YOUTUBE_API_KEY="your-youtube-api-key"  # YouTube trending

# Optional - customize the LLM model (defaults to gpt-4)
export OPENAI_MODEL="gpt-4"  # or gpt-4-turbo, gpt-4o, gpt-3.5-turbo
```

!!! tip "Environment File"
    Consider using a `.env` file with a tool like `python-dotenv` for local development.

## Quick Start

### Basic Usage

Generate a blog post with default settings:

```bash
python -m ai_blogger
```

This will:

1. Fetch articles from all available sources
2. Generate 3 candidate blog posts
3. Score and rank the candidates
4. Refine the winning post
5. Save the result to `./posts/` directory

### Check Available Sources

List all registered sources and their availability status:

```bash
python -m ai_blogger --list-sources
```

Output example:
```
Available sources:
  hacker_news: Fetch articles from Hacker News [✓]
  web: Fetch articles from web search (Tavily) [✗ (missing API key)]
  youtube: Fetch trending YouTube videos [✓]
```

### Dry Run

Preview what would be done without executing:

```bash
python -m ai_blogger --dry-run
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--num-posts N` | Number of candidate posts to generate | 3 |
| `--out-dir DIR` | Output directory for blog posts | ./posts |
| `--topics TOPIC...` | Topics to search for | Config defaults |
| `--sources SOURCE...` | Sources to fetch from | All available |
| `--max-results FORMAT` | Max results per source | Config defaults |
| `--list-sources` | List all available sources | - |
| `--dry-run` | Print plan without executing | False |
| `-v, --verbose` | Enable verbose output | False |

## Examples

### Custom Topics

```bash
python -m ai_blogger --topics "AI coding" "developer tools"
```

### Specific Sources

```bash
python -m ai_blogger --sources hacker_news youtube
```

### Custom Result Counts

```bash
python -m ai_blogger --max-results "hacker_news:15,youtube:10"
```

### Generate More Candidates

```bash
python -m ai_blogger --num-posts 5 --out-dir ./my-posts
```

### Full Example

```bash
python -m ai_blogger \
  --topics "AI software engineering" "developer productivity" \
  --sources hacker_news youtube \
  --max-results "hacker_news:10,youtube:5" \
  --num-posts 3 \
  --out-dir ./blog-output \
  --verbose
```

## Output

Blog posts are saved as Markdown files with the following format:

- **Filename**: `YYYY-MM-DD-{slugified-title}.md`
- **Location**: Output directory (default: `./posts/`)

Each file includes:

- YAML front matter with metadata (topic, score, sources)
- Full blog post content
- Author bio placeholder

## Next Steps

- [Architecture Overview](architecture.md) - Understand the system design
- [Developer Guide](developer-guide.md) - Learn how to extend AI Blogger
- [Operations Guide](operations.md) - Deploy and automate AI Blogger

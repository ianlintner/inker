# Architecture

This document provides an overview of the AI Blogger (Inker) system architecture, including component design, data flow, and integration patterns.

## System Overview

AI Blogger follows a modular pipeline architecture that separates concerns into distinct phases:

```mermaid
flowchart TB
    subgraph Input["Input Layer"]
        CLI[CLI Interface]
        CONFIG[Configuration]
    end
    
    subgraph Fetching["Fetching Layer"]
        FR[Fetcher Registry]
        HN[HackerNews Fetcher]
        WS[Web Search Fetcher]
        YT[YouTube Fetcher]
    end
    
    subgraph Processing["Processing Layer"]
        GEN[Candidate Generator]
        SCORE[Scoring Engine]
        REFINE[Refinement Chain]
    end
    
    subgraph LLM["LLM Integration"]
        LC[LangChain]
        OAI[OpenAI GPT-4]
    end
    
    subgraph Output["Output Layer"]
        MD[Markdown Writer]
        FS[File System]
    end
    
    CLI --> FR
    CONFIG --> CLI
    FR --> HN & WS & YT
    HN & WS & YT --> GEN
    GEN --> SCORE
    SCORE --> REFINE
    GEN & SCORE & REFINE --> LC
    LC --> OAI
    REFINE --> MD
    MD --> FS
```

## Component Architecture

### Core Components

```mermaid
classDiagram
    class BaseFetcher {
        <<abstract>>
        +name: str
        +env_key: str
        +description: str
        +is_available() bool
        +fetch(topic, max_results) List~Article~
    }
    
    class HackerNewsFetcher {
        +name = "hacker_news"
        +fetch(topic, max_results) List~Article~
    }
    
    class WebSearchFetcher {
        +name = "web"
        +env_key = "TAVILY_API_KEY"
        +fetch(topic, max_results) List~Article~
    }
    
    class YouTubeFetcher {
        +name = "youtube"
        +env_key = "YOUTUBE_API_KEY"
        +fetch(topic, max_results) List~Article~
    }
    
    BaseFetcher <|-- HackerNewsFetcher
    BaseFetcher <|-- WebSearchFetcher
    BaseFetcher <|-- YouTubeFetcher
```

### Data Models

```mermaid
classDiagram
    class Article {
        +title: str
        +url: HttpUrl
        +source: str
        +summary: str
        +topic: str
        +thumbnail: Optional~str~
    }
    
    class CandidatePost {
        +title: str
        +content: str
        +sources: List~str~
        +topic: str
    }
    
    class PostScore {
        +relevance: float
        +originality: float
        +depth: float
        +clarity: float
        +engagement: float
        +total: float
        +reasoning: str
    }
    
    class ScoredPost {
        +candidate: CandidatePost
        +score: PostScore
    }
    
    ScoredPost --> CandidatePost
    ScoredPost --> PostScore
```

## Pipeline Flow

The content generation pipeline follows these sequential phases:

```mermaid
sequenceDiagram
    participant CLI as CLI
    participant Fetchers as Fetcher Layer
    participant Generator as Generator Chain
    participant Scorer as Scoring Chain
    participant Refiner as Refiner Chain
    participant FS as File System
    
    CLI->>Fetchers: fetch_all_articles(topics, sources)
    Fetchers-->>CLI: List[Article]
    
    CLI->>Generator: generate_candidates(articles, num)
    Generator-->>CLI: List[CandidatePost]
    
    loop For each candidate
        CLI->>Scorer: score_candidate(candidate)
        Scorer-->>CLI: ScoredPost
    end
    
    CLI->>CLI: Sort by score, select winner
    
    CLI->>Refiner: refine_winner(winner)
    Refiner-->>CLI: Refined Markdown
    
    CLI->>FS: Write to file
    FS-->>CLI: Success
```

## Fetcher Architecture

The fetcher subsystem uses a registry pattern for extensibility:

```mermaid
flowchart LR
    subgraph Registry["Fetcher Registry"]
        R[(Registry Dict)]
    end
    
    subgraph Decorator["Registration"]
        D["@register_fetcher()"]
    end
    
    subgraph Fetchers["Fetcher Classes"]
        HN[HackerNewsFetcher]
        WS[WebSearchFetcher]
        YT[YouTubeFetcher]
        CUSTOM[CustomFetcher...]
    end
    
    D --> R
    HN & WS & YT & CUSTOM --> D
    
    subgraph Functions["Access Functions"]
        GA[get_available_sources]
        GF[get_fetcher]
    end
    
    R --> GA & GF
```

### Adding a New Fetcher

```python
from ai_blogger.fetchers import BaseFetcher, register_fetcher

@register_fetcher("my_source")
class MySourceFetcher(BaseFetcher):
    name = "my_source"
    env_key = "MY_SOURCE_API_KEY"  # Optional
    description = "Fetch from My Source"
    
    def fetch(self, topic: str, max_results: int) -> List[Article]:
        self._validate_inputs(topic, max_results)
        # Implementation here
        return articles
```

## LangChain Integration

AI Blogger uses LangChain for all LLM interactions:

```mermaid
flowchart TB
    subgraph Chains["LangChain Chains"]
        GC["generate_candidates()"]
        SC["score_candidate()"]
        RC["refine_winner()"]
    end
    
    subgraph Templates["Prompt Templates"]
        GT[Generator Template]
        ST[Scorer Template]
        RT[Refiner Template]
    end
    
    subgraph LLM["LLM"]
        GPT[ChatOpenAI]
    end
    
    GT --> GC
    ST --> SC
    RT --> RC
    
    GC & SC & RC --> GPT
```

### Chain Configuration

| Chain | Temperature | Purpose |
|-------|-------------|---------|
| Generator | 0.8 | Creative content generation |
| Scorer | 0.3 | Consistent, objective scoring |
| Refiner | 0.6 | Balanced refinement |

## Scoring System

The scoring system uses weighted criteria:

```mermaid
pie title Scoring Weights
    "Relevance (30%)" : 30
    "Originality (25%)" : 25
    "Depth (20%)" : 20
    "Clarity (15%)" : 15
    "Engagement (10%)" : 10
```

### Scoring Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Relevance | 0.30 | Topic relevance to software engineering |
| Originality | 0.25 | Unique perspective and insights |
| Depth | 0.20 | Thoroughness of exploration |
| Clarity | 0.15 | Writing quality and structure |
| Engagement | 0.10 | Reader attention capture |

## Directory Structure

```
ai_blogger/
├── __init__.py       # Package exports
├── __main__.py       # CLI entrypoint
├── config.py         # Configuration settings
├── fetchers.py       # Modular fetcher architecture
├── chains.py         # LangChain chains
├── models.py         # Pydantic data models
└── utils.py          # Utility functions
```

## External Dependencies

```mermaid
flowchart TB
    subgraph External["External Services"]
        OAI[OpenAI API]
        TAV[Tavily API]
        YT[YouTube Data API]
        HN[HN Algolia API]
    end
    
    subgraph Internal["AI Blogger"]
        CHAINS[chains.py]
        WEB[WebSearchFetcher]
        YOUTUBE[YouTubeFetcher]
        HACKER[HackerNewsFetcher]
    end
    
    CHAINS --> OAI
    WEB --> TAV
    YOUTUBE --> YT
    HACKER --> HN
```

### API Usage Notes

| API | Authentication | Rate Limits |
|-----|---------------|-------------|
| OpenAI | API Key | Per-minute/per-day based on tier |
| Tavily | API Key | Plan-dependent |
| YouTube Data API | API Key | 10,000 units/day default |
| HN Algolia | None | Reasonable use |

## Error Handling

The system implements graceful degradation:

```mermaid
flowchart TD
    START[Fetch Request] --> CHECK{API Available?}
    CHECK -->|Yes| FETCH[Execute Fetch]
    CHECK -->|No| SKIP[Skip Source]
    
    FETCH --> VALIDATE{Valid Response?}
    VALIDATE -->|Yes| PARSE[Parse Articles]
    VALIDATE -->|No| LOG[Log Error]
    
    PARSE --> RETURN[Return Articles]
    LOG --> EMPTY[Return Empty List]
    SKIP --> EMPTY
    
    RETURN --> CONTINUE[Continue Pipeline]
    EMPTY --> CONTINUE
```

## See Also

- [Developer Guide](developer-guide.md) - Extending the system
- [API Reference](api-reference.md) - Detailed module documentation
- [Operations](operations.md) - Deployment and monitoring

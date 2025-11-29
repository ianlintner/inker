"""Configuration settings for the AI Blogger."""

import os
from typing import Dict, List

# Topics to search for
TOPICS: List[str] = [
    "AI software engineering",
    "agentic AI development",
    "Copilot coding assistants",
    "developer productivity",
    "software engineering leadership",
    "cybersecurity",
    "AI security",
    "dev tools",
    "cloud infrastructure",
]

# Scoring weights for candidate posts (must sum to 1.0)
SCORING_WEIGHTS: Dict[str, float] = {
    "relevance": 0.3,
    "originality": 0.25,
    "depth": 0.2,
    "clarity": 0.15,
    "engagement": 0.1,
}

# Tolerance for floating-point comparison of weights
WEIGHTS_TOLERANCE: float = 0.001

# Validate scoring weights sum to 1.0
_weights_sum = sum(SCORING_WEIGHTS.values())
if abs(_weights_sum - 1.0) > WEIGHTS_TOLERANCE:
    raise ValueError(f"SCORING_WEIGHTS must sum to 1.0, got {_weights_sum}")

# Maximum age for YouTube videos (in days)
YOUTUBE_MAX_AGE_DAYS: int = 7

# Default number of results per source
DEFAULT_MAX_RESULTS: int = 5

# Source-specific default result counts
SOURCE_DEFAULTS: Dict[str, int] = {
    "hacker_news": 10,
    "web": 5,
    "youtube": 5,
}

# Number of candidate posts to generate
DEFAULT_NUM_CANDIDATES: int = 3

# Output directory for blog posts
DEFAULT_OUTPUT_DIR: str = "./posts"

# LLM model name (can be overridden via environment variable)
LLM_MODEL_NAME: str = os.environ.get("OPENAI_MODEL", "gpt-4")


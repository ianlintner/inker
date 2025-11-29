#!/usr/bin/env python3
"""AI Blogger - CLI entrypoint for generating AI-powered blog posts."""

import argparse
import logging
import os
import sys
from pathlib import Path

from .chains import generate_candidates, refine_winner, score_candidates
from .config import DEFAULT_NUM_CANDIDATES, DEFAULT_OUTPUT_DIR, SOURCE_DEFAULTS, TOPICS
from .fetchers import fetch_all_articles, get_available_sources
from .utils import generate_filename

logger = logging.getLogger(__name__)


def parse_max_results(value: str) -> dict:
    """Parse max results argument in format 'source:count,source:count'.

    Args:
        value: String in format 'hacker_news:10,web:5,youtube:5'

    Returns:
        Dict mapping source names to max results.
    """
    result = SOURCE_DEFAULTS.copy()
    for item in value.split(","):
        if ":" in item:
            source, count = item.split(":", 1)
            try:
                result[source.strip()] = int(count.strip())
            except ValueError:
                print(f"Warning: Invalid count for {source}, using default")
    return result


def main():
    """Main entry point for the AI Blogger CLI."""
    available = get_available_sources()

    parser = argparse.ArgumentParser(
        description="AI Blogger - Automated blog post generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available sources: {', '.join(available)}

Examples:
  # Use only Hacker News and YouTube
  python -m ai_blogger --sources hacker_news youtube

  # Set custom result counts per source
  python -m ai_blogger --max-results "hacker_news:15,youtube:10"

  # Combine with custom topics
  python -m ai_blogger --topics "AI" "machine learning" --sources web youtube

Requires Python 3.9 or higher.
"""
    )
    parser.add_argument(
        "--num-posts",
        type=int,
        default=DEFAULT_NUM_CANDIDATES,
        help=f"Number of candidate posts to generate (default: {DEFAULT_NUM_CANDIDATES})",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for blog posts (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--topics",
        type=str,
        nargs="+",
        default=None,
        help="Topics to search for (default: uses config topics)",
    )
    parser.add_argument(
        "--sources",
        type=str,
        nargs="+",
        default=None,
        choices=available,
        help=f"Sources to fetch from (default: all registered sources)",
    )
    parser.add_argument(
        "--max-results",
        type=str,
        default=None,
        help="Max results per source in format 'source:count,source:count' (e.g., 'hacker_news:10,youtube:5')",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List all available sources and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without actually generating posts",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Configure logging based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    # Handle list-sources
    if args.list_sources:
        print("Available sources:")
        for name in get_available_sources():
            from .fetchers import get_fetcher
            fetcher = get_fetcher(name)
            if fetcher:
                status = "✓" if fetcher.is_available() else "✗ (missing API key)"
                print(f"  {name}: {fetcher.description} [{status}]")
        return

    # Validate environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    # Warn about optional API keys
    if not os.environ.get("TAVILY_API_KEY"):
        print("Warning: TAVILY_API_KEY not set - web search will be disabled")
    if not os.environ.get("YOUTUBE_API_KEY"):
        print("Warning: YOUTUBE_API_KEY not set - YouTube trending will be disabled")

    topics = args.topics or TOPICS
    sources = args.sources or get_available_sources()
    max_results = parse_max_results(args.max_results) if args.max_results else None

    if args.dry_run:
        print("Dry run mode - would perform the following:")
        print(f"  - Topics: {topics}")
        print(f"  - Sources: {sources}")
        print(f"  - Max results: {max_results or SOURCE_DEFAULTS}")
        print(f"  - Number of candidates: {args.num_posts}")
        print(f"  - Output directory: {args.out_dir}")
        return

    # Create output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AI BLOGGER - Generating your daily blog post")
    print("=" * 60)

    # Step 1: Fetch articles
    print("\n[1/4] Fetching articles from all sources...")
    articles = fetch_all_articles(topics=topics, sources=sources, max_results=max_results)

    if not articles:
        print("Error: No articles found.")
        print("  Possible causes:")
        print("  - Missing API keys (check TAVILY_API_KEY, YOUTUBE_API_KEY)")
        print("  - Network connectivity issues")
        print("  - No results for the specified topics")
        print("  Try running with --list-sources to check source availability.")
        sys.exit(1)

    if args.verbose:
        print(f"\nFound {len(articles)} articles:")
        for article in articles[:10]:
            print(f"  - [{article.source}] {article.title[:60]}...")

    # Step 2: Generate candidates
    print(f"\n[2/4] Generating {args.num_posts} candidate blog posts...")
    try:
        candidates = generate_candidates(articles, num_candidates=args.num_posts)
    except ValueError as e:
        print(f"Error: Failed to generate candidate posts: {e}")
        sys.exit(1)

    if not candidates:
        print("Error: No candidate posts were generated.")
        sys.exit(1)

    if args.verbose:
        print(f"\nGenerated {len(candidates)} candidates:")
        for i, candidate in enumerate(candidates, 1):
            print(f"  {i}. {candidate.title}")

    # Step 3: Score candidates
    print("\n[3/4] Scoring candidate posts...")
    scored_candidates = score_candidates(candidates)

    if not scored_candidates:
        print("Error: No candidates were scored successfully.")
        sys.exit(1)

    print("\nScores:")
    for i, scored in enumerate(scored_candidates, 1):
        print(f"  {i}. {scored.candidate.title[:50]}... (Score: {scored.score.total:.2f})")

    # Step 4: Refine winner
    winner = scored_candidates[0]
    print(f"\n[4/4] Refining winning post: {winner.candidate.title}")
    final_content = refine_winner(winner)

    # Save the final post
    filename = generate_filename(winner.candidate.title)
    filepath = out_dir / filename

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_content)
    except (OSError, IOError, UnicodeEncodeError) as e:
        print(f"Error: Failed to write blog post to '{filepath}': {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SUCCESS! Blog post generated.")
    print(f"  File: {filepath}")
    print(f"  Title: {winner.candidate.title}")
    print(f"  Score: {winner.score.total:.2f}/10")
    print("=" * 60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AI Blogger - CLI entrypoint for generating AI-powered blog posts."""

import argparse
import os
import sys
from pathlib import Path

from .chains import generate_candidates, refine_winner, score_candidates
from .config import DEFAULT_NUM_CANDIDATES, DEFAULT_OUTPUT_DIR, TOPICS
from .fetchers import fetch_all_articles
from .utils import generate_filename


def main():
    """Main entry point for the AI Blogger CLI."""
    parser = argparse.ArgumentParser(
        description="AI Blogger - Automated blog post generation"
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

    # Validate environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    topics = args.topics or TOPICS

    if args.dry_run:
        print("Dry run mode - would perform the following:")
        print(f"  - Topics: {topics}")
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
    articles = fetch_all_articles(topics=topics)

    if not articles:
        print("Error: No articles found. Check your API keys and network connection.")
        sys.exit(1)

    if args.verbose:
        print(f"\nFound {len(articles)} articles:")
        for article in articles[:10]:
            print(f"  - [{article.source}] {article.title[:60]}...")

    # Step 2: Generate candidates
    print(f"\n[2/4] Generating {args.num_posts} candidate blog posts...")
    candidates = generate_candidates(articles, num_candidates=args.num_posts)

    if not candidates:
        print("Error: Failed to generate candidate posts.")
        sys.exit(1)

    if args.verbose:
        print(f"\nGenerated {len(candidates)} candidates:")
        for i, candidate in enumerate(candidates, 1):
            print(f"  {i}. {candidate.title}")

    # Step 3: Score candidates
    print("\n[3/4] Scoring candidate posts...")
    scored_candidates = score_candidates(candidates)

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

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(final_content)

    print("\n" + "=" * 60)
    print("SUCCESS! Blog post generated.")
    print(f"  File: {filepath}")
    print(f"  Title: {winner.candidate.title}")
    print(f"  Score: {winner.score.total:.2f}/10")
    print("=" * 60)


if __name__ == "__main__":
    main()

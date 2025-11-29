"""Utility functions for the AI Blogger."""

from datetime import datetime
from slugify import slugify as python_slugify


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: The text to convert to a slug.

    Returns:
        A URL-friendly slug version of the text.
    """
    return python_slugify(text, max_length=100)


def get_timestamp() -> str:
    """Get the current timestamp in ISO format.

    Returns:
        Current timestamp as a string.
    """
    return datetime.now().isoformat()


def get_date_string() -> str:
    """Get the current date as a string for filenames.

    Returns:
        Current date in YYYY-MM-DD format.
    """
    return datetime.now().strftime("%Y-%m-%d")


def generate_filename(title: str) -> str:
    """Generate a filename for a blog post.

    Args:
        title: The title of the blog post.

    Returns:
        A filename in the format 'YYYY-MM-DD-slug.md'.
    """
    date_str = get_date_string()
    slug = slugify(title)
    return f"{date_str}-{slug}.md"

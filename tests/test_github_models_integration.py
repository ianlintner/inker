"""Integration tests for GitHub Models.

These tests run against live LLM models using GitHub Models API.
They require a GITHUB_TOKEN with models access to be set as an environment variable.

Run with:
    pytest tests/test_github_models_integration.py -v -m integration
"""

import os
import re

import pytest

# Skip all tests in this module if GITHUB_TOKEN is not set
pytestmark = pytest.mark.integration


def github_models_configured():
    """Check if GitHub Models is configured."""
    return os.environ.get("GITHUB_TOKEN") is not None


def extract_json_from_response(content: str) -> str:
    """Extract JSON content from a response, handling markdown code blocks.

    Args:
        content: The raw response content that may contain markdown code blocks.

    Returns:
        The extracted JSON string.
    """
    content = content.strip()

    # Handle markdown code blocks (```json ... ``` or ``` ... ```)
    code_block_pattern = r"```(?:json)?\s*\n([\s\S]*?)\n```"
    match = re.search(code_block_pattern, content)
    if match:
        return match.group(1).strip()

    return content


@pytest.fixture
def github_models_llm():
    """Create a ChatOpenAI instance configured for GitHub Models."""
    if not github_models_configured():
        pytest.skip("GITHUB_TOKEN not set - skipping GitHub Models integration tests")

    from langchain_openai import ChatOpenAI

    token = os.environ.get("GITHUB_TOKEN")
    # Use gpt-4o as it's widely available on GitHub Models
    return ChatOpenAI(
        model="gpt-4o",
        api_key=token,
        base_url="https://models.github.ai/inference",
        temperature=0.7,
    )


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    from ai_blogger.models import Article

    return [
        Article(
            title="Introduction to AI in Software Development",
            url="https://example.com/ai-software",
            source="web",
            summary="An overview of how AI is changing software development practices.",
            topic="AI software engineering",
        ),
        Article(
            title="Building Better Code with Copilot",
            url="https://example.com/copilot",
            source="hacker_news",
            summary="Tips for maximizing productivity with AI coding assistants.",
            topic="developer productivity",
        ),
    ]


class TestGitHubModelsConnection:
    """Tests for basic GitHub Models connectivity."""

    def test_can_connect_to_github_models(self, github_models_llm):
        """Test that we can connect to GitHub Models and get a response."""
        from langchain_core.messages import HumanMessage

        messages = [HumanMessage(content="Say 'Hello, GitHub Models!' in exactly those words.")]
        response = github_models_llm.invoke(messages)

        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0

    def test_github_models_returns_valid_response(self, github_models_llm):
        """Test that GitHub Models returns a valid, coherent response."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content="You are a helpful assistant. Answer concisely."),
            HumanMessage(content="What is 2 + 2? Answer with just the number."),
        ]
        response = github_models_llm.invoke(messages)

        assert response is not None
        # The response should contain "4" somewhere
        assert "4" in response.content


class TestBlogGeneration:
    """Tests for blog generation using GitHub Models."""

    def test_can_generate_blog_content(self, github_models_llm):
        """Test that we can generate blog-like content."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content="You are a technical blogger. Write concise, informative content."),
            HumanMessage(
                content="Write a single paragraph (3-4 sentences) about the benefits of AI in software development."
            ),
        ]
        response = github_models_llm.invoke(messages)

        assert response is not None
        assert len(response.content) > 100  # Should be at least a paragraph
        # Should mention something related to AI or software
        content_lower = response.content.lower()
        assert any(term in content_lower for term in ["ai", "software", "development", "code", "productivity"])

    def test_json_output_generation(self, github_models_llm):
        """Test that the model can generate structured JSON output."""
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content="You are a helpful assistant that outputs valid JSON. Always respond with a JSON object only."
            ),
            HumanMessage(
                content='Create a simple JSON object with keys "title" and "summary" about AI in software development.'
            ),
        ]
        response = github_models_llm.invoke(messages)

        assert response is not None
        # Extract JSON and parse
        content = extract_json_from_response(response.content)
        parsed = json.loads(content)
        assert "title" in parsed or "summary" in parsed


class TestScoringCapability:
    """Tests for scoring capability using GitHub Models."""

    def test_can_score_content(self, github_models_llm):
        """Test that the model can score content on a scale."""
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content=(
                    "You are a content evaluator. Score the given content on a scale of 1-10 "
                    'for relevance. Respond with JSON: {"score": <number>, "reasoning": "<text>"}'
                )
            ),
            HumanMessage(
                content=(
                    "Score this content for relevance to software engineering: "
                    "'AI tools like GitHub Copilot are revolutionizing how developers write code.'"
                )
            ),
        ]
        response = github_models_llm.invoke(messages)

        assert response is not None
        # Extract JSON and parse
        content = extract_json_from_response(response.content)
        parsed = json.loads(content)
        assert "score" in parsed
        assert 1 <= parsed["score"] <= 10


class TestErrorHandling:
    """Tests for error handling with GitHub Models."""

    def test_handles_long_input(self, github_models_llm):
        """Test that the model handles longer inputs appropriately."""
        from langchain_core.messages import HumanMessage

        # Create a moderately long input
        long_content = "AI is transforming software development. " * 50
        messages = [HumanMessage(content=f"Summarize this in one sentence: {long_content}")]

        response = github_models_llm.invoke(messages)
        assert response is not None
        assert len(response.content) > 0

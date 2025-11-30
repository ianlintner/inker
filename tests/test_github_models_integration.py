"""Integration tests for GitHub Models.

These tests run against live LLM models using GitHub Models API.
They require a GITHUB_TOKEN with models access to be set as an environment variable.

Run with:
    pytest tests/test_github_models_integration.py -v -m integration
"""

import json
import os
import re
import time

import pytest
from openai import RateLimitError

# Skip all tests in this module if GITHUB_TOKEN is not set
pytestmark = pytest.mark.integration


def github_models_configured():
    """Check if GitHub Models is configured."""
    token = os.environ.get("GITHUB_TOKEN")
    return token is not None and token.strip() != ""


def extract_json_from_response(content: str) -> str:
    """Extract JSON content from a response, handling markdown code blocks.

    Args:
        content: The raw response content that may contain markdown code blocks.

    Returns:
        The extracted JSON string.
    """
    content = content.strip()

    # Handle markdown code blocks (```json ... ``` or ``` ... ```)
    # Use regex to robustly strip code block markers
    code_block_pattern = r"^```(?:json)?\s*\n?([\s\S]*?)\n?```$"
    match = re.match(code_block_pattern, content)
    if match:
        return match.group(1).strip()

    return content


def parse_json_response(content: str) -> dict:
    """Parse JSON from a response, with proper error handling.

    Args:
        content: The raw response content.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        pytest.fail: If JSON parsing fails, with context about the response.
    """
    extracted = extract_json_from_response(content)
    try:
        return json.loads(extracted)
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse JSON response: {e}. Response was: {extracted}")


def emit_workflow_warning(message: str):
    """Emit a GitHub Actions workflow warning annotation.

    Args:
        message: The warning message to display.
    """
    # GitHub Actions workflow command syntax for warnings
    print(f"::warning::{message}")


def emit_workflow_error(message: str):
    """Emit a GitHub Actions workflow error annotation.

    Args:
        message: The error message to display.
    """
    # GitHub Actions workflow command syntax for errors
    print(f"::error::{message}")


def invoke_with_retry(llm, messages, max_retries=3, initial_delay=2):
    """Invoke LLM with retry logic for rate limit errors.

    Args:
        llm: The LLM instance to invoke.
        messages: Messages to send to the LLM.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds between retries.

    Returns:
        The LLM response.

    Raises:
        RateLimitError: If all retries are exhausted.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except RateLimitError:
            if attempt < max_retries - 1:
                emit_workflow_warning(
                    f"GitHub Models rate limit hit (attempt {attempt + 1}/{max_retries}). " f"Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                emit_workflow_error(
                    f"GitHub Models rate limit exceeded after {max_retries} retries. "
                    "Consider reducing test frequency or increasing retry delays."
                )
                pytest.skip(f"Rate limit exceeded after {max_retries} retries - skipping test")
        except Exception as e:
            emit_workflow_error(f"GitHub Models API error: {type(e).__name__}: {e}")
            raise
    return None


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


class TestGitHubModelsConnection:
    """Tests for basic GitHub Models connectivity."""

    def test_can_connect_to_github_models(self, github_models_llm):
        """Test that we can connect to GitHub Models and get a response."""
        from langchain_core.messages import HumanMessage

        messages = [HumanMessage(content="What is 1 + 1? Please respond with just the number.")]
        response = invoke_with_retry(github_models_llm, messages)

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
        response = invoke_with_retry(github_models_llm, messages)

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
        response = invoke_with_retry(github_models_llm, messages)

        assert response is not None
        assert len(response.content) > 100  # Should be at least a paragraph
        # Should mention something related to AI or software
        content_lower = response.content.lower()
        assert any(term in content_lower for term in ["ai", "software", "development", "code", "productivity"])

    def test_json_output_generation(self, github_models_llm):
        """Test that the model can generate structured JSON output."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content="You are a helpful assistant that outputs valid JSON. Always respond with a JSON object only."
            ),
            HumanMessage(
                content='Create a simple JSON object with keys "title" and "summary" about AI in software development.'
            ),
        ]
        response = invoke_with_retry(github_models_llm, messages)

        assert response is not None
        # Extract JSON and parse with error handling
        parsed = parse_json_response(response.content)
        assert (
            "title" in parsed and "summary" in parsed
        ), f"Expected both 'title' and 'summary' keys in response, got: {list(parsed.keys())}"


class TestScoringCapability:
    """Tests for scoring capability using GitHub Models."""

    def test_can_score_content(self, github_models_llm):
        """Test that the model can score content on a scale."""
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
        response = invoke_with_retry(github_models_llm, messages)

        assert response is not None
        # Extract JSON and parse with error handling
        parsed = parse_json_response(response.content)
        assert "score" in parsed, f"Expected 'score' key in response, got: {list(parsed.keys())}"
        # Handle score as string or number
        score = float(parsed["score"])
        assert 1 <= score <= 10, f"Expected score between 1 and 10, got: {score}"


class TestErrorHandling:
    """Tests for error handling with GitHub Models."""

    def test_handles_long_input(self, github_models_llm):
        """Test that the model handles longer inputs appropriately."""
        from langchain_core.messages import HumanMessage

        # Create a moderately long input
        long_content = "AI is transforming software development. " * 50
        messages = [HumanMessage(content=f"Summarize this in one sentence: {long_content}")]

        response = invoke_with_retry(github_models_llm, messages)
        assert response is not None
        assert len(response.content) > 0

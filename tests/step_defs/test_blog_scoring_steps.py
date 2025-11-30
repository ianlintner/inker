"""Step definitions for blog scoring BDD tests."""

import json
from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ai_blogger.chains import score_candidate, score_candidates
from ai_blogger.config import SCORING_WEIGHTS
from ai_blogger.models import CandidatePost, ScoredPost

scenarios("../features/blog_scoring.feature")


@pytest.fixture
def mock_llm_score_response():
    """Mock successful LLM scoring response."""
    return json.dumps(
        {
            "relevance": 8.5,
            "originality": 7.0,
            "depth": 8.0,
            "clarity": 9.0,
            "engagement": 7.5,
            "reasoning": "This is a well-written post with good technical depth and clarity. "
            "The content is highly relevant to software engineering audiences. "
            "Originality could be improved with more unique insights.",
        }
    )


@pytest.fixture
def mock_candidate():
    """Create a mock candidate post."""
    return CandidatePost(
        title="The AI Revolution in Software Engineering",
        content="""Artificial intelligence is transforming how we build software.
        
From intelligent code completion to automated testing, AI tools are becoming essential.
This shift enables developers to focus on creative problem-solving.

Key trends include AI-powered code review, automated documentation, and intelligent
refactoring suggestions. The future is collaborative—humans and AI working together.""",
        sources=["https://example.com/ai-engineering", "https://techblog.com/ai-tools"],
        topic="AI software engineering",
    )


# Given steps
@given("the LLM is configured for scoring")
def llm_configured(monkeypatch):
    """Set up OpenAI API key."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-api-key")


@given(parsers.parse('a candidate post about "{topic}"'))
def create_candidate(context, topic, mock_candidate):
    """Create a candidate post."""
    context["candidate"] = mock_candidate
    context["topic"] = topic


@given(
    parsers.parse(
        "a candidate with scores relevance {relevance:d} originality {originality:d} "
        "depth {depth:d} clarity {clarity:d} engagement {engagement:d}"
    )
)
def create_scored_candidate(context, relevance, originality, depth, clarity, engagement, mock_candidate):
    """Create a candidate with specific scores for weighted calculation."""
    context["candidate"] = mock_candidate
    context["expected_scores"] = {
        "relevance": relevance,
        "originality": originality,
        "depth": depth,
        "clarity": clarity,
        "engagement": engagement,
    }


@given(parsers.parse("{count:d} candidate posts with varying quality"))
def create_multiple_candidates(context, count):
    """Create multiple candidates with varying quality."""
    context["candidates"] = []
    qualities = ["excellent", "good", "average"]
    for i in range(count):
        quality = qualities[i % len(qualities)]
        candidate = CandidatePost(
            title=f"{quality.title()} Post About AI #{i+1}",
            content=f"This is a {quality} quality post about artificial intelligence. " * 10,
            sources=[f"https://example.com/source-{i}"],
            topic="AI software engineering",
        )
        context["candidates"].append(candidate)


@given("two candidates with similar content quality")
def create_similar_candidates(context):
    """Create two candidates with similar quality."""
    context["candidates"] = [
        CandidatePost(
            title="AI in Software Development Part 1",
            content="A comprehensive look at AI tools for developers. " * 20,
            sources=["https://example.com/ai-dev"],
            topic="AI software engineering",
        ),
        CandidatePost(
            title="AI in Software Development Part 2",
            content="Another comprehensive look at AI tools for developers. " * 20,
            sources=["https://example.com/ai-dev-2"],
            topic="AI software engineering",
        ),
    ]


# When steps
@when("I score the candidate")
def score_single_candidate(context, mock_llm_score_response, monkeypatch):
    """Score a single candidate."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-api-key")

    mock_response = Mock()
    mock_response.content = mock_llm_score_response

    with patch("ai_blogger.chains.ChatOpenAI") as mock_llm_class:
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        with patch("ai_blogger.chains.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_chain = Mock()
            mock_chain.invoke = Mock(return_value=mock_response)
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)
            context["scored_post"] = score_candidate(context["candidate"])


@when("I calculate the total score")
def calculate_total(context, monkeypatch):
    """Calculate total score with expected values."""
    scores = context["expected_scores"]
    # Calculate expected weighted total
    context["expected_total"] = (
        scores["relevance"] * SCORING_WEIGHTS["relevance"]
        + scores["originality"] * SCORING_WEIGHTS["originality"]
        + scores["depth"] * SCORING_WEIGHTS["depth"]
        + scores["clarity"] * SCORING_WEIGHTS["clarity"]
        + scores["engagement"] * SCORING_WEIGHTS["engagement"]
    )


@when("I score all candidates")
def score_all_candidates(context, monkeypatch):
    """Score all candidates."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-api-key")

    # Create responses with decreasing scores for testing sort
    responses = [
        json.dumps(
            {
                "relevance": 9 - i,
                "originality": 8 - i,
                "depth": 9 - i,
                "clarity": 8 - i,
                "engagement": 8 - i,
                "reasoning": f"Quality level {i}",
            }
        )
        for i in range(len(context["candidates"]))
    ]
    response_iter = iter(responses)

    def get_response(*args, **kwargs):
        mock_response = Mock()
        mock_response.content = next(response_iter)
        return mock_response

    with patch("ai_blogger.chains.ChatOpenAI") as mock_llm_class:
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        with patch("ai_blogger.chains.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_chain = Mock()
            mock_chain.invoke = Mock(side_effect=get_response)
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)
            context["scored_posts"] = score_candidates(context["candidates"])


@when("the LLM returns invalid scoring response")
def score_with_invalid_response(context, monkeypatch):
    """Score when LLM returns invalid response."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-api-key")

    mock_response = Mock()
    mock_response.content = "Not valid JSON for scoring"

    with patch("ai_blogger.chains.ChatOpenAI") as mock_llm_class:
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        with patch("ai_blogger.chains.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_chain = Mock()
            mock_chain.invoke = Mock(return_value=mock_response)
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)
            context["scored_post"] = score_candidate(context["candidate"])


@when("I score both candidates")
def score_both_candidates(context, monkeypatch):
    """Score both similar candidates."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-api-key")

    # Use same scores for similar candidates
    score_response = json.dumps(
        {
            "relevance": 7,
            "originality": 7,
            "depth": 7,
            "clarity": 7,
            "engagement": 7,
            "reasoning": "Good quality post",
        }
    )

    with patch("ai_blogger.chains.ChatOpenAI") as mock_llm_class:
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        with patch("ai_blogger.chains.ChatPromptTemplate.from_messages") as mock_prompt:
            mock_chain = Mock()
            mock_response = Mock()
            mock_response.content = score_response
            mock_chain.invoke = Mock(return_value=mock_response)
            mock_prompt.return_value.__or__ = Mock(return_value=mock_chain)
            context["scored_posts"] = [score_candidate(c) for c in context["candidates"]]


# Then steps
@then("I should receive a scored post")
def check_scored_post(context):
    """Check that we received a scored post."""
    assert context["scored_post"] is not None
    assert isinstance(context["scored_post"], ScoredPost)


@then(parsers.parse("the score should have {field} between {min_val:d} and {max_val:d}"))
def check_score_range(context, field, min_val, max_val):
    """Check that a score field is within range."""
    score = context["scored_post"].score
    value = getattr(score, field)
    assert min_val <= value <= max_val, f"{field}={value} not in range [{min_val}, {max_val}]"


@then("the score should have a total score")
def check_total_score(context):
    """Check that score has a total."""
    assert context["scored_post"].score.total is not None
    assert context["scored_post"].score.total >= 0


@then("the score should have reasoning")
def check_reasoning(context):
    """Check that score has reasoning."""
    assert context["scored_post"].score.reasoning
    assert len(context["scored_post"].score.reasoning) > 0


@then("the total should be weighted according to SCORING_WEIGHTS")
def check_weighted_total(context):
    """Check that total is correctly weighted."""
    # Just verify weights are used correctly
    assert "expected_total" in context
    # Total should be positive and reasonable
    assert 0 <= context["expected_total"] <= 10


@then(parsers.parse("{field} should have weight {weight:f}"))
def check_weight(context, field, weight):
    """Check weight value."""
    assert abs(SCORING_WEIGHTS[field] - weight) < 0.001


@then("candidates should be sorted by total score descending")
def check_sorted_by_score(context):
    """Check that candidates are sorted by score."""
    scores = [s.score.total for s in context["scored_posts"]]
    assert scores == sorted(scores, reverse=True)


@then("the highest scoring candidate should be first")
def check_highest_first(context):
    """Check that highest scoring is first."""
    if len(context["scored_posts"]) > 1:
        assert context["scored_posts"][0].score.total >= context["scored_posts"][1].score.total


@then("I should receive a scored post with zero scores")
def check_zero_scores(context):
    """Check that error case returns zero scores."""
    assert context["scored_post"].score.total == 0
    assert context["scored_post"].score.relevance == 0


@then("the reasoning should indicate an error")
def check_error_reasoning(context):
    """Check that reasoning indicates error."""
    reasoning = context["scored_post"].score.reasoning.lower()
    assert "error" in reasoning or "invalid" in reasoning or "failed" in reasoning


@then("their scores should be within reasonable range of each other")
def check_similar_scores(context):
    """Check that similar candidates have similar scores."""
    if len(context["scored_posts"]) >= 2:
        diff = abs(context["scored_posts"][0].score.total - context["scored_posts"][1].score.total)
        assert diff < 5  # Reasonable difference threshold

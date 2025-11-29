"""LangChain chains for generating, scoring, and refining blog posts."""

import json
import logging
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .config import DEFAULT_NUM_CANDIDATES, LLM_MODEL_NAME, SCORING_WEIGHTS
from .models import Article, CandidatePost, PostScore, ScoredPost

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Get a configured LLM instance.

    Args:
        temperature: The temperature setting for the LLM.

    Returns:
        Configured ChatOpenAI instance.

    Note:
        The model name can be configured via the OPENAI_MODEL environment
        variable. Defaults to "gpt-4". Supported models include:
        "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-3.5-turbo".
    """
    return ChatOpenAI(model=LLM_MODEL_NAME, temperature=temperature)


def generate_candidates(articles: List[Article], num_candidates: int = DEFAULT_NUM_CANDIDATES) -> List[CandidatePost]:
    """Generate candidate blog posts from articles.

    Args:
        articles: List of Article objects to use as sources.
        num_candidates: Number of candidate posts to generate.

    Returns:
        List of CandidatePost objects.
    """
    llm = get_llm(temperature=0.8)

    # Format articles for the prompt
    articles_json = json.dumps([article.model_dump(mode="json") for article in articles], indent=2)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert technical blogger specializing in software engineering, AI, and developer productivity.
Your task is to generate {num_candidates} distinct blog post drafts based on the provided news articles and videos.

Each blog post should:
- Have a compelling, SEO-friendly title
- Be well-structured with an introduction, main points, and conclusion
- Synthesize information from multiple sources
- Provide unique insights and analysis
- Be engaging and informative for a technical audience
- Be 800-1500 words

Output your response as a valid JSON array of objects with keys: title, content, sources (list of URLs used), topic.""",
            ),
            (
                "human",
                """Here are the articles and videos to use as sources:

{articles}

Generate {num_candidates} distinct blog post candidates. Return valid JSON only.""",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke({"articles": articles_json, "num_candidates": num_candidates})

    try:
        candidates_data = json.loads(response.content)
        if not isinstance(candidates_data, list):
            error_msg = f"Expected list of candidates, got {type(candidates_data)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        candidates = []
        for data in candidates_data:
            if not isinstance(data, dict):
                continue
            title = data.get("title", "")
            content = data.get("content", "")
            if not title or not content:
                continue
            candidate = CandidatePost(
                title=title,
                content=content,
                sources=data.get("sources", []),
                topic=data.get("topic", ""),
            )
            candidates.append(candidate)
        return candidates
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing candidate posts: {e}\nRaw response: {response.content[:500]}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e


def score_candidate(candidate: CandidatePost) -> ScoredPost:
    """Score a candidate blog post.

    Args:
        candidate: The CandidatePost to score.

    Returns:
        ScoredPost with scoring breakdown.
    """
    llm = get_llm(temperature=0.3)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a critical blog post evaluator. Score the following blog post on these criteria (0-10 scale):

1. Relevance: How relevant is the content to software engineering and tech audiences?
2. Originality: How unique and insightful is the perspective?
3. Depth: How thoroughly does it explore the topic?
4. Clarity: How clear and well-structured is the writing?
5. Engagement: How likely is it to capture and hold reader attention?

Provide your response as a JSON object with keys: relevance, originality, depth, clarity, engagement, reasoning (brief explanation of scores).""",
            ),
            (
                "human",
                """Title: {title}

Content:
{content}

Sources used: {sources}

Provide your scoring as valid JSON only.""",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "title": candidate.title,
            "content": candidate.content,
            "sources": ", ".join(candidate.sources),
        }
    )

    try:
        score_data = json.loads(response.content)
        if not isinstance(score_data, dict):
            logger.error(f"Expected dict for score, got {type(score_data)}")
            logger.error(f"Raw response: {response.content[:500]}")
            raise ValueError("Invalid score format")

        # Calculate weighted total score (weights are validated in config.py to sum to 1.0)
        weights = SCORING_WEIGHTS
        total = (
            score_data.get("relevance", 0) * weights["relevance"]
            + score_data.get("originality", 0) * weights["originality"]
            + score_data.get("depth", 0) * weights["depth"]
            + score_data.get("clarity", 0) * weights["clarity"]
            + score_data.get("engagement", 0) * weights["engagement"]
        )

        score = PostScore(
            relevance=score_data.get("relevance", 0),
            originality=score_data.get("originality", 0),
            depth=score_data.get("depth", 0),
            clarity=score_data.get("clarity", 0),
            engagement=score_data.get("engagement", 0),
            total=total,
            reasoning=score_data.get("reasoning", ""),
        )
        return ScoredPost(candidate=candidate, score=score)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error parsing score: {e}")
        logger.error(f"Raw response: {response.content[:500]}")
        # Return a default low score on error
        score = PostScore(
            relevance=0,
            originality=0,
            depth=0,
            clarity=0,
            engagement=0,
            total=0,
            reasoning="Error during scoring",
        )
        return ScoredPost(candidate=candidate, score=score)


def score_candidates(candidates: List[CandidatePost]) -> List[ScoredPost]:
    """Score all candidate posts.

    Args:
        candidates: List of CandidatePost objects to score.

    Returns:
        List of ScoredPost objects, sorted by total score (descending).
    """
    scored = [score_candidate(candidate) for candidate in candidates]
    scored.sort(key=lambda x: x.score.total, reverse=True)
    return scored


def refine_winner(winner: ScoredPost) -> str:
    """Refine and polish the winning blog post.

    Args:
        winner: The winning ScoredPost to refine.

    Returns:
        The refined blog post content as Markdown.
    """
    llm = get_llm(temperature=0.6)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a professional blog editor. Your task is to refine and polish the following blog post.

Improvements to make:
- Enhance the introduction to hook readers
- Improve transitions between sections
- Add a compelling call-to-action at the end
- Ensure proper Markdown formatting (headers, lists, code blocks if applicable)
- Fix any grammatical or stylistic issues
- Add a brief author bio placeholder

Based on the scoring feedback, focus especially on areas that scored lower.

Output the final polished blog post in Markdown format.""",
            ),
            (
                "human",
                """Original post:

Title: {title}

Content:
{content}

Scoring feedback:
- Relevance: {relevance}/10
- Originality: {originality}/10
- Depth: {depth}/10
- Clarity: {clarity}/10
- Engagement: {engagement}/10

Feedback: {reasoning}

Please provide the refined blog post in Markdown format, starting with the title as an H1 header.""",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "title": winner.candidate.title,
            "content": winner.candidate.content,
            "relevance": winner.score.relevance,
            "originality": winner.score.originality,
            "depth": winner.score.depth,
            "clarity": winner.score.clarity,
            "engagement": winner.score.engagement,
            "reasoning": winner.score.reasoning,
        }
    )

    # Add metadata header
    sources_list = "\n".join(f"- {source}" for source in winner.candidate.sources)
    metadata = f"""---
topic: {winner.candidate.topic}
score: {winner.score.total:.2f}
sources:
{sources_list}
---

"""

    return metadata + response.content

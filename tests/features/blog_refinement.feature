Feature: Blog Post Refinement
    As the AI Blogger application
    I want to refine the winning blog post
    So that it is polished and ready for publishing

    Background:
        Given the LLM is configured for refinement
        And I have a winning scored post

    Scenario: Refine winning post to Markdown
        Given a winning post with title "AI Revolution in 2024"
        And the post has a score of 8.5
        When I refine the winning post
        Then I should receive Markdown content
        And the content should start with YAML frontmatter
        And the frontmatter should contain the topic
        And the frontmatter should contain the score
        And the frontmatter should contain sources

    Scenario: Refine post with low scores
        Given a winning post with low clarity score 4
        When I refine the winning post
        Then the LLM should be instructed to improve clarity
        And the refined content should be enhanced

    Scenario: Include all required sections
        Given a winning post
        When I refine the winning post
        Then the refined content should have an H1 title header
        And the content should have proper Markdown formatting

    Scenario: Preserve source references
        Given a winning post with 3 source URLs
        When I refine the winning post
        Then the frontmatter should list all 3 sources

    Scenario: Handle refinement errors
        Given a winning post
        When the LLM refinement fails
        Then the error should be handled gracefully

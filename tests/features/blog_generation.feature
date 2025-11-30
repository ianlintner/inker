Feature: Blog Post Generation
    As the AI Blogger application
    I want to generate blog post candidates from articles
    So that I can create quality content for publishing

    Background:
        Given the LLM is configured with OpenAI API key
        And I have a list of source articles

    Scenario: Generate candidate blog posts
        Given 10 source articles about "AI software engineering"
        When I generate 3 candidate blog posts
        Then I should receive 3 candidate posts
        And each candidate should have a title
        And each candidate should have content
        And each candidate should have at least one source URL
        And each candidate should have a topic

    Scenario: Handle LLM response with invalid JSON
        Given 5 source articles about "developer productivity"
        When the LLM returns invalid JSON
        Then a ValueError should be raised

    Scenario: Handle empty article list
        Given an empty list of articles
        When I try to generate candidate posts
        Then the LLM should still be invoked
        And candidates may be empty or minimal

    Scenario: Content meets quality requirements
        Given 8 source articles about "cybersecurity"
        When I generate 2 candidate blog posts
        Then each candidate content should be at least 500 characters
        And each candidate should synthesize multiple sources

    Scenario: Generate candidates with different topics
        Given articles from multiple topics
        When I generate 3 candidate blog posts
        Then candidates may cover different topics

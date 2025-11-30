Feature: Blog Post Scoring
    As the AI Blogger application
    I want to score candidate blog posts
    So that I can select the best one for publishing

    Background:
        Given the LLM is configured for scoring

    Scenario: Score a single candidate post
        Given a candidate post about "AI trends"
        When I score the candidate
        Then I should receive a scored post
        And the score should have relevance between 0 and 10
        And the score should have originality between 0 and 10
        And the score should have depth between 0 and 10
        And the score should have clarity between 0 and 10
        And the score should have engagement between 0 and 10
        And the score should have a total score
        And the score should have reasoning

    Scenario: Calculate weighted total score
        Given a candidate with scores relevance 8 originality 7 depth 9 clarity 8 engagement 7
        When I calculate the total score
        Then the total should be weighted according to SCORING_WEIGHTS
        And relevance should have weight 0.3
        And originality should have weight 0.25
        And depth should have weight 0.2
        And clarity should have weight 0.15
        And engagement should have weight 0.1

    Scenario: Score multiple candidates and rank them
        Given 3 candidate posts with varying quality
        When I score all candidates
        Then candidates should be sorted by total score descending
        And the highest scoring candidate should be first

    Scenario: Handle LLM scoring errors gracefully
        Given a candidate post about "broken topic"
        When the LLM returns invalid scoring response
        Then I should receive a scored post with zero scores
        And the reasoning should indicate an error

    Scenario: Consistent scoring for similar content
        Given two candidates with similar content quality
        When I score both candidates
        Then their scores should be within reasonable range of each other

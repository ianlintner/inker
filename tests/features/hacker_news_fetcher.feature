Feature: Hacker News Fetcher
    As the AI Blogger application
    I want to fetch articles from Hacker News
    So that I can use them as sources for blog posts

    Background:
        Given the Hacker News API is available

    Scenario: Successfully fetch articles for a topic
        Given a topic "AI software engineering"
        When I fetch 5 articles from Hacker News
        Then I should receive a list of articles
        And each article should have a title
        And each article should have a URL
        And each article should have source "hacker_news"

    Scenario: Handle empty results gracefully
        Given a topic "xyznonexistenttopic123"
        When I fetch 5 articles from Hacker News with empty results
        Then I should receive an empty list

    Scenario: Handle API errors gracefully
        Given a topic "AI software engineering"
        When the Hacker News API returns an error
        Then I should receive an empty list
        And an error should be logged

    Scenario: Validate topic cannot be empty
        Given an empty topic
        When I try to fetch articles from Hacker News
        Then a ValueError should be raised with message "Topic cannot be empty"

    Scenario: Validate max_results must be positive
        Given a topic "AI"
        When I try to fetch with max_results 0
        Then a ValueError should be raised with message "max_results must be positive"

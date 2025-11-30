Feature: Web Search Fetcher
    As the AI Blogger application
    I want to fetch articles from Tavily web search
    So that I can use them as sources for blog posts

    Background:
        Given the Tavily API key is configured

    Scenario: Successfully fetch articles for a topic
        Given a topic "developer productivity"
        When I fetch 5 articles from web search
        Then I should receive a list of articles
        And each article should have a title
        And each article should have a URL
        And each article should have source "web"
        And each article should have a summary

    Scenario: Handle missing API key
        Given the Tavily API key is not configured
        When I try to fetch articles from web search
        Then I should receive an empty list
        And a warning should be logged

    Scenario: Handle API errors gracefully
        Given a topic "AI security"
        When the Tavily API returns an error
        Then I should receive an empty list
        And an error should be logged

    Scenario: Validate input parameters
        Given an empty topic
        When I try to fetch articles from web search
        Then a ValueError should be raised with message "Topic cannot be empty"

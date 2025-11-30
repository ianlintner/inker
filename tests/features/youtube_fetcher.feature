Feature: YouTube Fetcher
    As the AI Blogger application
    I want to fetch trending YouTube videos
    So that I can use them as sources for blog posts

    Background:
        Given the YouTube API key is configured

    Scenario: Successfully fetch videos for a topic
        Given a topic "agentic AI development"
        When I fetch 5 videos from YouTube
        Then I should receive a list of articles
        And each article should have a title
        And each article should have a URL starting with "https://www.youtube.com/watch"
        And each article should have source "youtube"
        And each article should have a thumbnail

    Scenario: Filter out old videos
        Given a topic "Copilot coding assistants"
        When YouTube returns videos older than 7 days
        Then those videos should be filtered out

    Scenario: Handle missing API key
        Given the YouTube API key is not configured
        When I try to fetch videos from YouTube
        Then I should receive an empty list
        And a warning should be logged

    Scenario: Handle API errors gracefully
        Given a topic "dev tools"
        When the YouTube API returns an error
        Then I should receive an empty list
        And an error should be logged

    Scenario: Extract video metadata correctly
        Given a topic "cloud infrastructure"
        When I fetch videos with channel information
        Then each article summary should contain the channel title

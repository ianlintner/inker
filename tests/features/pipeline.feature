Feature: End-to-End Blog Generation Pipeline
    As the AI Blogger application
    I want to run the complete blog generation pipeline
    So that I can produce quality blog posts automatically

    Background:
        Given all required API keys are configured
        And the output directory exists

    Scenario: Complete pipeline execution
        Given topics "AI software engineering" and "developer productivity"
        And sources "hacker_news" and "web"
        When I run the complete blog generation pipeline
        Then articles should be fetched from all sources
        And candidate posts should be generated
        And candidates should be scored
        And the winning post should be refined
        And a Markdown file should be saved

    Scenario: Pipeline with single source
        Given topic "cybersecurity"
        And only source "hacker_news"
        When I run the blog generation pipeline
        Then only Hacker News articles should be fetched
        And the pipeline should complete successfully

    Scenario: Pipeline handles source failures gracefully
        Given all sources are configured
        When one source API fails
        Then other sources should still be fetched
        And the pipeline should continue with available articles

    Scenario: Dry run mode
        Given dry run mode is enabled
        When I run the pipeline
        Then no external API calls should be made
        And a summary of actions should be displayed

    Scenario: Custom output directory
        Given custom output directory "/tmp/test-posts"
        When I run the pipeline
        Then the output file should be in "/tmp/test-posts"

    Scenario: Pipeline with no articles found
        Given no articles are found from any source
        When I run the pipeline
        Then the pipeline should exit with an error
        And an appropriate message should be displayed

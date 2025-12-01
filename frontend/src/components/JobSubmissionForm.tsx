import { useState, type FormEvent } from 'react';
import { submitJob } from '../api';
import type { JobSubmitRequest } from '../api';
import styles from './JobSubmissionForm.module.css';

// Default options matching backend config
const DEFAULT_TOPICS = [
  'AI software engineering',
  'agentic AI development',
  'Copilot coding assistants',
  'developer productivity',
  'software engineering leadership',
  'cybersecurity',
  'AI security',
  'dev tools',
  'cloud infrastructure',
];

const AVAILABLE_SOURCES = [
  { id: 'hacker_news', label: 'Hacker News', description: 'Tech news and discussions' },
  { id: 'web', label: 'Web Search', description: 'General web search results' },
  { id: 'youtube', label: 'YouTube', description: 'Trending tech videos' },
];

interface JobSubmissionFormProps {
  onSubmit?: (jobId: string) => void;
  onError?: (error: string) => void;
}

export function JobSubmissionForm({ onSubmit, onError }: JobSubmissionFormProps) {
  const [loading, setLoading] = useState(false);
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [customTopic, setCustomTopic] = useState('');
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [numCandidates, setNumCandidates] = useState(3);
  const [correlationId, setCorrelationId] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleTopicToggle = (topic: string) => {
    setSelectedTopics((prev) =>
      prev.includes(topic) ? prev.filter((t) => t !== topic) : [...prev, topic]
    );
  };

  const handleSourceToggle = (sourceId: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceId) ? prev.filter((s) => s !== sourceId) : [...prev, sourceId]
    );
  };

  const handleAddCustomTopic = () => {
    const topic = customTopic.trim();
    if (topic && !selectedTopics.includes(topic)) {
      setSelectedTopics((prev) => [...prev, topic]);
      setCustomTopic('');
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const request: JobSubmitRequest = {
        num_candidates: numCandidates,
      };

      // Only include topics if some are selected
      if (selectedTopics.length > 0) {
        request.topics = selectedTopics;
      }

      // Only include sources if some are selected
      if (selectedSources.length > 0) {
        request.sources = selectedSources;
      }

      // Include correlation ID if provided
      if (correlationId.trim()) {
        request.correlation_id = correlationId.trim();
      }

      const response = await submitJob(request);
      onSubmit?.(response.job_id);

      // Reset form on success
      setSelectedTopics([]);
      setSelectedSources([]);
      setCorrelationId('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit job';
      onError?.(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <h2 className={styles.title}>Create Blog Post Job</h2>

      {/* Topics Section */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Topics</h3>
        <p className={styles.sectionDescription}>
          Select topics to search for articles (leave empty for defaults)
        </p>
        <div className={styles.checkboxGrid}>
          {DEFAULT_TOPICS.map((topic) => (
            <label key={topic} className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={selectedTopics.includes(topic)}
                onChange={() => handleTopicToggle(topic)}
                className={styles.checkbox}
              />
              <span>{topic}</span>
            </label>
          ))}
        </div>
        <div className={styles.customTopicRow}>
          <input
            type="text"
            value={customTopic}
            onChange={(e) => setCustomTopic(e.target.value)}
            placeholder="Add custom topic..."
            className={styles.input}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddCustomTopic();
              }
            }}
          />
          <button
            type="button"
            onClick={handleAddCustomTopic}
            className={styles.addButton}
            disabled={!customTopic.trim()}
          >
            Add
          </button>
        </div>
        {selectedTopics.filter((t) => !DEFAULT_TOPICS.includes(t)).length > 0 && (
          <div className={styles.customTopics}>
            <strong>Custom topics:</strong>{' '}
            {selectedTopics
              .filter((t) => !DEFAULT_TOPICS.includes(t))
              .map((topic) => (
                <span key={topic} className={styles.topicTag}>
                  {topic}
                  <button
                    type="button"
                    onClick={() => handleTopicToggle(topic)}
                    className={styles.removeTag}
                  >
                    ×
                  </button>
                </span>
              ))}
          </div>
        )}
      </div>

      {/* Sources Section */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Sources</h3>
        <p className={styles.sectionDescription}>
          Select sources to fetch articles from (leave empty for all available)
        </p>
        <div className={styles.sourceGrid}>
          {AVAILABLE_SOURCES.map((source) => (
            <label key={source.id} className={styles.sourceCard}>
              <input
                type="checkbox"
                checked={selectedSources.includes(source.id)}
                onChange={() => handleSourceToggle(source.id)}
                className={styles.checkbox}
              />
              <div className={styles.sourceInfo}>
                <span className={styles.sourceLabel}>{source.label}</span>
                <span className={styles.sourceDescription}>{source.description}</span>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Candidates Slider */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>Number of Candidates</h3>
        <p className={styles.sectionDescription}>
          How many draft posts to generate before selecting the best one
        </p>
        <div className={styles.sliderRow}>
          <input
            type="range"
            min="1"
            max="10"
            value={numCandidates}
            onChange={(e) => setNumCandidates(Number(e.target.value))}
            className={styles.slider}
          />
          <span className={styles.sliderValue}>{numCandidates}</span>
        </div>
      </div>

      {/* Advanced Options */}
      <div className={styles.section}>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={styles.advancedToggle}
        >
          {showAdvanced ? '▼' : '▶'} Advanced Options
        </button>
        {showAdvanced && (
          <div className={styles.advancedSection}>
            <label className={styles.fieldLabel}>
              Correlation ID (for idempotency)
              <input
                type="text"
                value={correlationId}
                onChange={(e) => setCorrelationId(e.target.value)}
                placeholder="Optional unique request ID"
                className={styles.input}
              />
            </label>
          </div>
        )}
      </div>

      {/* Submit Button */}
      <button type="submit" disabled={loading} className={styles.submitButton}>
        {loading ? 'Submitting...' : 'Generate Blog Post'}
      </button>
    </form>
  );
}

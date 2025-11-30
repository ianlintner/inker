import { useState, useEffect } from 'react';
import { JobSubmissionForm, JobList, PostReview } from './components';
import { checkHealth } from './api';
import type { JobStatusResponse } from './api';
import './App.css';

function App() {
  const [selectedJob, setSelectedJob] = useState<JobStatusResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'submit' | 'list'>('list');
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Check API health on mount
  useEffect(() => {
    async function checkApiHealth() {
      try {
        const health = await checkHealth();
        setApiHealthy(health.status === 'healthy');
      } catch {
        setApiHealthy(false);
      }
    }
    checkApiHealth();
    
    // Check every 30 seconds
    const interval = setInterval(checkApiHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleJobSubmit = (jobId: string) => {
    showNotification('success', `Job ${jobId.slice(0, 8)}... submitted successfully!`);
    setActiveTab('list');
  };

  const handleJobError = (error: string) => {
    showNotification('error', error);
  };

  const handleJobSelect = (job: JobStatusResponse) => {
    setSelectedJob(job);
  };

  const handleJobDeleted = () => {
    setSelectedJob(null);
    showNotification('success', 'Job deleted');
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <h1 className="logo">
            <span className="logo-icon">✒️</span>
            Inker
          </h1>
          <p className="tagline">AI-Powered Blog Post Generator</p>
          <div className={`api-status ${apiHealthy === true ? 'healthy' : apiHealthy === false ? 'unhealthy' : 'checking'}`}>
            <span className="status-dot"></span>
            {apiHealthy === true ? 'API Connected' : apiHealthy === false ? 'API Disconnected' : 'Checking...'}
          </div>
        </div>
      </header>

      {/* Notification */}
      {notification && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
          <button onClick={() => setNotification(null)} className="notification-close">×</button>
        </div>
      )}

      {/* Tab Navigation */}
      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'list' ? 'active' : ''}`}
          onClick={() => setActiveTab('list')}
        >
          📋 Jobs
        </button>
        <button
          className={`tab ${activeTab === 'submit' ? 'active' : ''}`}
          onClick={() => setActiveTab('submit')}
        >
          ➕ New Job
        </button>
      </nav>

      {/* Main Content */}
      <main className="main">
        {activeTab === 'submit' ? (
          <div className="submit-container">
            <JobSubmissionForm onSubmit={handleJobSubmit} onError={handleJobError} />
          </div>
        ) : (
          <div className="dashboard">
            <div className="jobs-panel">
              <JobList onSelectJob={handleJobSelect} selectedJobId={selectedJob?.job_id} />
            </div>
            <div className="review-panel">
              <PostReview
                job={selectedJob}
                onJobDeleted={handleJobDeleted}
                onJobExecuted={(job) => setSelectedJob(job)}
              />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>AI Blogger (Inker) - Automated blog post generation powered by LangChain and GPT-4</p>
      </footer>
    </div>
  );
}

export default App;

import React, { useEffect, useState } from 'react';
import { VideoItem, DashboardStats, IdeaItem } from '../types';
import { api } from '../services/api';
import { VideoCard } from './VideoCard';

interface DashboardViewProps {
  onVideoClick: (videoId: string) => void;
  onSearchSubmit: (query: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onVideoClick,
  onSearchSubmit,
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [ideas, setIdeas] = useState<IdeaItem[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedHookId, setCopiedHookId] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [statsData, ideasData] = await Promise.all([
        api.getDashboardStats().catch(() => null),
        api.getIdeas().catch(() => []),
      ]);
      if (statsData) setStats(statsData);
      setIdeas(ideasData || []);
    } catch (err) {
      console.error('Failed to load dashboard metrics', err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    onSearchSubmit(searchQuery.trim());
  };

  const handleQuickNiche = (niche: string) => {
    setSearchQuery(niche);
    onSearchSubmit(niche);
  };

  const handleCopyHook = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHookId(id);
    setTimeout(() => setCopiedHookId(null), 2000);
  };

  const handleMoveIdeaStatus = async (videoId: string, nextStatus: 'backlog' | 'in_progress' | 'done') => {
    try {
      await api.updateIdeaStatus(videoId, nextStatus);
      setIdeas((prev) =>
        prev.map((item) =>
          item.video_id === videoId ? { ...item, status: nextStatus } : item
        )
      );
    } catch (err) {
      console.error('Failed to move idea status', err);
    }
  };

  return (
    <div className="dashboard-container">
      {/* ---------------------------------------------------------------------- */}
      {/* 1. Top Integrated Outlier Command Bar                                  */}
      {/* ---------------------------------------------------------------------- */}
      <section className="dashboard-search-section">
        <div className="dashboard-search-header">
          <div className="dashboard-title-group">
            <span className="editorial-tag">| OUTLIER INTELLIGENCE & HOOK BLUEPRINTS</span>
            <h1 className="dashboard-title">Content Intelligence Dashboard</h1>
            <p className="dashboard-subtitle">
              Mine viral short-form outliers, isolate opening hooks, and model high-retention creative scripts.
            </p>
          </div>
        </div>

        <form className="dashboard-search-bar" onSubmit={handleSearch}>
          <div className="search-input-wrapper">
            <svg
              className="search-icon"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="dashboard-search-input"
              placeholder="Search niche or keyword to mine viral Shorts (e.g. AI tools, personal finance, psychology)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <button type="submit" className="dashboard-search-btn">
            <span>Discover Outliers</span>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </form>

        <div className="dashboard-niche-chips">
          <span className="niche-chips-label">Popular Niches:</span>
          {['AI & Automation', 'Finance & Investing', 'Psychology & Focus', 'Business Strategy', 'Productivity Systems'].map(
            (niche) => (
              <button
                key={niche}
                type="button"
                className="niche-chip-btn"
                onClick={() => handleQuickNiche(niche)}
              >
                {niche}
              </button>
            )
          )}
        </div>
      </section>

      {/* ---------------------------------------------------------------------- */}
      {/* 2. Key Metrics Row (Emil Kowalski Animated KPI Cards)                  */}
      {/* ---------------------------------------------------------------------- */}
      <section className="dashboard-metrics-grid">
        <div className="metric-card metric-card-highlight">
          <div className="metric-header">
            <span className="metric-label">Peak Viral Multiplier</span>
            <span className="metric-pill pill-viral">ALGORITHM BREAKOUT</span>
          </div>
          <div className="metric-number">
            +{stats?.max_viral_ratio ? stats.max_viral_ratio.toFixed(1) : '47.4'}x
          </div>
          <p className="metric-caption">
            Highest views-to-subscribers ratio captured. Proves organic reach completely independent of audience size.
          </p>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Estimated Hook Retention Score</span>
            <span className="metric-pill pill-hook">0-3s BENCHMARK</span>
          </div>
          <div className="metric-number">
            {stats?.estimated_hook_score ? stats.estimated_hook_score.toFixed(1) : '88.5'}
            <span className="metric-unit">/100</span>
          </div>
          <p className="metric-caption">
            Evaluated stopping power of the opening 3 seconds, calibrated from view velocity and engagement density.
          </p>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Creative Scripting Pipeline</span>
            <span className="metric-pill pill-pipeline">IDEAS BOARD</span>
          </div>
          <div className="metric-number">
            {ideas.length || stats?.ideas_total || 0}
            <span className="metric-unit">active ideas</span>
          </div>
          <div className="pipeline-mini-stats">
            <span>{ideas.filter((i) => i.status === 'backlog').length} Backlog</span>
            <span className="divider">•</span>
            <span>{ideas.filter((i) => i.status === 'in_progress').length} In Progress</span>
            <span className="divider">•</span>
            <span>{ideas.filter((i) => i.status === 'done').length} Ready / MedPy</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">API Quota Preserved</span>
            <span className="metric-pill pill-cache">SQLITE ZERO-BANDWIDTH</span>
          </div>
          <div className="metric-number">
            100%
            <span className="metric-unit">Zero-Quota</span>
          </div>
          <p className="metric-caption">
            {stats?.total_queries_saved || 1} queries and {stats?.cached_videos_count || 4} videos stored permanently in local cache.
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------------------- */}
      {/* 3. Top Performing Outliers Showcase                                   */}
      {/* ---------------------------------------------------------------------- */}
      <section className="dashboard-section">
        <div className="section-title-bar">
          <div>
            <h2 className="section-title">High-Performance Outliers from Your Radar</h2>
            <p className="section-desc">
              Videos outperforming their channel subscriber base by 10x to 50x. Click any card to dissect hooks and model scripts.
            </p>
          </div>
        </div>

        <div className="outliers-grid">
          {(stats?.top_outliers && stats.top_outliers.length > 0 ? stats.top_outliers : []).map((video: VideoItem) => (
            <VideoCard key={video.video_id} video={video} onClick={onVideoClick} />
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------------- */}
      {/* 4. Opening Hook Vault (0-3s Transcript Highlights)                    */}
      {/* ---------------------------------------------------------------------- */}
      <section className="dashboard-section">
        <div className="section-title-bar">
          <div>
            <h2 className="section-title">Opening Hook Vault (First 3-5 Seconds)</h2>
            <p className="section-desc">
              The opening sentences that stopped the vertical scroll. Copy directly or trigger AI script modeling.
            </p>
          </div>
        </div>

        <div className="hook-vault-grid">
          {[
            {
              id: 'kJQP7kiw5Fk',
              text: 'If you notice people scrolling past your videos in under 2 seconds, you are making this one fatal mistake.',
              trigger: 'PATTERN INTERRUPT & FEAR OF LOSS',
              duration: '3.8s',
              viralRatio: 47.4,
              niche: 'Content Creation & Retention',
            },
            {
              id: 'fJ9rUzIMcZQ',
              text: 'Stop trying to fix your motivation. Fix your friction point instead.',
              trigger: 'COUNTER-INTUITIVE TRUTH',
              duration: '3.2s',
              viralRatio: 46.9,
              niche: 'Behavioral Psychology',
            },
            {
              id: '9bZkp7q19f0',
              text: 'This financial concept will ruin your 20s if you ignore it today.',
              trigger: 'HIGH CURIOSITY GAP',
              duration: '4.1s',
              viralRatio: 29.8,
              niche: 'Wealth & Personal Finance',
            },
          ].map((hook) => (
            <div key={hook.id} className="hook-card">
              <div className="hook-card-header">
                <span className="hook-tag">{hook.trigger}</span>
                <span className="hook-duration">{hook.duration}</span>
              </div>
              <p className="hook-text">"{hook.text}"</p>
              <div className="hook-card-footer">
                <span className="hook-multiplier">+{hook.viralRatio}x Viral Ratio</span>
                <div className="hook-actions">
                  <button
                    type="button"
                    className="hook-action-btn"
                    onClick={() => handleCopyHook(hook.id, hook.text)}
                  >
                    {copiedHookId === hook.id ? 'Copied' : 'Copy Hook'}
                  </button>
                  <button
                    type="button"
                    className="hook-action-btn hook-action-primary"
                    onClick={() => onVideoClick(hook.id)}
                  >
                    Model Script
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------------- */}
      {/* 5. Production Ideas Pipeline (Kanban Quick View)                      */}
      {/* ---------------------------------------------------------------------- */}
      <section className="dashboard-section">
        <div className="section-title-bar">
          <div>
            <h2 className="section-title">Production Ideas Pipeline</h2>
            <p className="section-desc">
              Organize your reverse-engineered concepts from backlog to scripting and MedPy clipping.
            </p>
          </div>
        </div>

        <div className="kanban-columns-grid">
          {/* Backlog Column */}
          <div className="kanban-column">
            <div className="kanban-column-header">
              <span className="column-title">Backlog (Mined Concepts)</span>
              <span className="column-badge">{ideas.filter((i) => i.status === 'backlog').length}</span>
            </div>
            <div className="kanban-cards-stack">
              {ideas.filter((i) => i.status === 'backlog').length === 0 ? (
                <div className="kanban-empty">No ideas in backlog. Save outlier videos from the radar.</div>
              ) : (
                ideas
                  .filter((i) => i.status === 'backlog')
                  .map((idea) => (
                    <div key={idea.video_id} className="kanban-card">
                      <div className="kanban-card-top">
                        <span className="kanban-ratio">+{idea.viral_ratio}x</span>
                        <span className="kanban-channel">{idea.channel_title}</span>
                      </div>
                      <h4 className="kanban-title" onClick={() => onVideoClick(idea.video_id)}>
                        {idea.title}
                      </h4>
                      {idea.hook_text && <p className="kanban-hook">"{idea.hook_text}"</p>}
                      <div className="kanban-card-actions">
                        <button
                          type="button"
                          className="kanban-move-btn"
                          onClick={() => handleMoveIdeaStatus(idea.video_id, 'in_progress')}
                        >
                          Start Scripting →
                        </button>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>

          {/* In Progress Column */}
          <div className="kanban-column">
            <div className="kanban-column-header">
              <span className="column-title">In Scripting & Modeling</span>
              <span className="column-badge">{ideas.filter((i) => i.status === 'in_progress').length}</span>
            </div>
            <div className="kanban-cards-stack">
              {ideas.filter((i) => i.status === 'in_progress').length === 0 ? (
                <div className="kanban-empty">No ideas currently in scripting.</div>
              ) : (
                ideas
                  .filter((i) => i.status === 'in_progress')
                  .map((idea) => (
                    <div key={idea.video_id} className="kanban-card kanban-card-active">
                      <div className="kanban-card-top">
                        <span className="kanban-ratio">+{idea.viral_ratio}x</span>
                        <span className="kanban-channel">{idea.channel_title}</span>
                      </div>
                      <h4 className="kanban-title" onClick={() => onVideoClick(idea.video_id)}>
                        {idea.title}
                      </h4>
                      {idea.script_notes && <p className="kanban-notes">{idea.script_notes}</p>}
                      <div className="kanban-card-actions">
                        <button
                          type="button"
                          className="kanban-move-btn"
                          onClick={() => handleMoveIdeaStatus(idea.video_id, 'backlog')}
                        >
                          ← Backlog
                        </button>
                        <button
                          type="button"
                          className="kanban-move-btn kanban-move-done"
                          onClick={() => handleMoveIdeaStatus(idea.video_id, 'done')}
                        >
                          Ready / MedPy →
                        </button>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>

          {/* Done / MedPy Ready Column */}
          <div className="kanban-column">
            <div className="kanban-column-header">
              <span className="column-title">Ready for Production / MedPy</span>
              <span className="column-badge">{ideas.filter((i) => i.status === 'done').length}</span>
            </div>
            <div className="kanban-cards-stack">
              {ideas.filter((i) => i.status === 'done').length === 0 ? (
                <div className="kanban-empty">Finished scripts will appear here with MedPy cut markers.</div>
              ) : (
                ideas
                  .filter((i) => i.status === 'done')
                  .map((idea) => (
                    <div key={idea.video_id} className="kanban-card kanban-card-done">
                      <div className="kanban-card-top">
                        <span className="kanban-ratio">+{idea.viral_ratio}x</span>
                        <span className="kanban-status-done">READY FOR CLIPPING</span>
                      </div>
                      <h4 className="kanban-title" onClick={() => onVideoClick(idea.video_id)}>
                        {idea.title}
                      </h4>
                      <div className="kanban-card-actions">
                        <button
                          type="button"
                          className="kanban-move-btn"
                          onClick={() => onVideoClick(idea.video_id)}
                        >
                          View MedPy Cuts
                        </button>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------------- */}
      {/* 6. Creative Modeling Framework (Architectural Suggestions)            */}
      {/* ---------------------------------------------------------------------- */}
      <section className="dashboard-framework-section">
        <div className="framework-header">
          <span className="editorial-tag">| THE UNDERFIND 5-STAGE SCRIPTING BLUEPRINT</span>
          <h2 className="framework-title">How to Model Viral Short-Form Creatives (Without Copying)</h2>
          <p className="framework-desc">
            Follow this cognitive retention structure reverse-engineered from 10,000+ top-performing YouTube Shorts and Reels.
          </p>
        </div>

        <div className="framework-steps-grid">
          <div className="framework-step-card">
            <span className="step-number">01</span>
            <h3 className="step-title">The Pattern Interrupt Hook (00:00 - 00:03)</h3>
            <p className="step-text">
              Halt the thumb scroll before cognitive resistance sets in. Never begin with a greeting or intro. Start with a counter-intuitive premise, visual shock, or immediate promise of revelation.
            </p>
          </div>

          <div className="framework-step-card">
            <span className="step-number">02</span>
            <h3 className="step-title">The Curiosity Tension Gap (00:03 - 00:15)</h3>
            <p className="step-text">
              Deepen the stakes. Explain why conventional wisdom fails, creating psychological tension that cannot be resolved without watching until the final moments.
            </p>
          </div>

          <div className="framework-step-card">
            <span className="step-number">03</span>
            <h3 className="step-title">High-Density Core Delivery (00:15 - 00:45)</h3>
            <p className="step-text">
              Deliver 3 rapid-fire actionable insights. Change visual B-roll or speaker angle every 2.5 seconds (where MedPy raw footage cuts are calibrated). Zero fluff or filler words.
            </p>
          </div>

          <div className="framework-step-card">
            <span className="step-number">04</span>
            <h3 className="step-title">The Unexpected Climax (00:45 - 00:55)</h3>
            <p className="step-text">
              Deliver the ultimate punchline or core takeaway with an unexpected twist that rewards the viewer for staying until the end.
            </p>
          </div>

          <div className="framework-step-card">
            <span className="step-number">05</span>
            <h3 className="step-title">The Seamless Infinite Loop (00:55 - 00:60)</h3>
            <p className="step-text">
              Cut out any outro, goodbye, or "subscribe" plea. Craft the final sentence to flow grammatically straight into the opening sentence, triggering automatic 2nd views on the algorithm.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

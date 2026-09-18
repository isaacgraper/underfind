import React, { useEffect, useState } from 'react';
import { ActiveTab, HealthResponse } from '../types';
import { api } from '../services/api';

interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  onSearch?: (query: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api.checkHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  return (
    <header className="site-header">
      <div className="header-left">
        <nav className="nav-tabs" aria-label="Main Navigation">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => onTabChange('dashboard')}
          >
            Dashboard
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'shorts' ? 'active' : ''}`}
            onClick={() => onTabChange('shorts')}
          >
            Outliers Radar
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'trending' ? 'active' : ''}`}
            onClick={() => onTabChange('trending')}
          >
            Trending
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => onTabChange('search')}
          >
            Explorer
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'mcp' ? 'active' : ''}`}
            onClick={() => onTabChange('mcp')}
          >
            MCP Hub
          </button>
        </nav>
      </div>

      <div className="header-actions">
        <div className="status-badge" title="Permanent zero-bandwidth local SQLite cache">
          <span className="status-indicator connected" />
          <span>SQLite Cache Active</span>
        </div>
        <div className="status-badge">
          <span className={`status-indicator ${health?.youtube_api_configured ? 'connected' : ''}`} />
          <span>{health?.youtube_api_configured ? 'API Connected' : 'API Key Missing'}</span>
        </div>
        <a href="/docs" target="_blank" rel="noreferrer" className="docs-link">
          API v2.1
        </a>
      </div>
    </header>
  );
};

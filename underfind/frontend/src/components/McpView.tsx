import React, { useState } from 'react';

interface IntegrationApp {
  id: string;
  name: string;
  description: string;
  buttonLabel: string;
  icon: React.ReactNode;
  configSnippet: string;
  instructions: string;
}

export const McpView: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeInstructionId, setActiveInstructionId] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId(null);
    }, 2500);
  };

  const stdioCommand = 'python -m underfind.backend.mcp.server';

  const fullJsonConfig = JSON.stringify(
    {
      mcpServers: {
        underfind: {
          command: 'python',
          args: ['-m', 'underfind.backend.mcp.server'],
        },
      },
    },
    null,
    2
  );

  const apps: IntegrationApp[] = [
    {
      id: 'claude',
      name: 'Claude',
      description: 'Allow Claude to access your outlier radar, 0-3s hook transcripts, and script modeling engine',
      buttonLabel: 'Add to Claude',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="m4.93 4.93 4.24 4.24" />
          <path d="m14.83 9.17 4.24-4.24" />
          <path d="m14.83 14.83 4.24 4.24" />
          <path d="m9.17 14.83-4.24 4.24" />
        </svg>
      ),
      configSnippet: JSON.stringify(
        {
          mcpServers: {
            underfind: {
              command: 'python',
              args: ['-m', 'underfind.backend.mcp.server'],
            },
          },
        },
        null,
        2
      ),
      instructions: 'Paste into your %APPDATA%\\Claude\\claude_desktop_config.json file (Windows) or ~/Library/Application Support/Claude/claude_desktop_config.json (macOS).',
    },
    {
      id: 'chatgpt',
      name: 'ChatGPT',
      description: 'Allow ChatGPT and Custom GPTs to access your creative intelligence and viral ratios',
      buttonLabel: 'Add to ChatGPT',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12a10 10 0 0 1 10-10z" />
          <path d="M8 12h8" />
          <path d="M12 8v8" />
        </svg>
      ),
      configSnippet: JSON.stringify(
        {
          name: 'Underfind Content Intelligence',
          endpoint: 'http://localhost:8000/api',
          schema_url: 'http://localhost:8000/openapi.json',
        },
        null,
        2
      ),
      instructions: 'Import this OpenAPI schema URL into your ChatGPT Custom GPT Actions configuration.',
    },
    {
      id: 'cursor',
      name: 'Cursor',
      description: 'Allow Cursor AI to query outlier hooks and generate scene-by-scene script blueprints in your workspace',
      buttonLabel: 'Add to Cursor',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="m9 8 4 4-4 4" />
          <path d="M14 16h3" />
        </svg>
      ),
      configSnippet: JSON.stringify(
        {
          mcpServers: {
            underfind: {
              command: 'python',
              args: ['-m', 'underfind.backend.mcp.server'],
            },
          },
        },
        null,
        2
      ),
      instructions: 'Save this in your project root at .cursor/mcp.json or under Cursor Settings > Features > MCP.',
    },
    {
      id: 'gemini',
      name: 'Gemini / Antigravity',
      description: 'Direct stdio connection for Google Antigravity IDE, agy CLI, and Gemini agents',
      buttonLabel: 'Add to Gemini',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      ),
      configSnippet: JSON.stringify(
        {
          underfind: {
            command: 'python',
            args: ['-m', 'underfind.backend.mcp.server'],
          },
        },
        null,
        2
      ),
      instructions: 'Add to your Antigravity mcp_config.json under your customization root or project root.',
    },
  ];

  return (
    <div className="mcp-container">
      {/* Header section matching Wispr UX with Underfind aesthetics */}
      <header className="mcp-header">
        <h1 className="mcp-title">MCP</h1>
        <p className="mcp-subtitle">
          Sync Underfind with your favorite AI apps, so you can ask about vertical outliers, extract opening hooks,
          and model viral scripts. The Underfind MCP runs 100% locally with zero-quota SQLite caching.
        </p>
      </header>

      {/* Primary Integration Cards */}
      <section className="mcp-apps-list" aria-label="Supported AI Integrations">
        {apps.map((app) => (
          <div key={app.id} className="mcp-app-card">
            <div className="mcp-app-meta">
              <div className="mcp-app-header-row">
                <span className="mcp-app-icon" aria-hidden="true">{app.icon}</span>
                <span className="mcp-app-name">{app.name}</span>
              </div>
              <p className="mcp-app-desc">{app.description}</p>
            </div>

            <div className="mcp-app-action">
              <button
                type="button"
                className={`mcp-action-btn ${copiedId === app.id ? 'copied' : ''}`}
                onClick={() => {
                  copyToClipboard(app.configSnippet, app.id);
                  setActiveInstructionId(activeInstructionId === app.id ? null : app.id);
                }}
              >
                {copiedId === app.id ? (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Config Copied!</span>
                  </>
                ) : (
                  <span>{app.buttonLabel}</span>
                )}
              </button>
            </div>

            {activeInstructionId === app.id && (
              <div className="mcp-inline-instruction">
                <p>{app.instructions}</p>
              </div>
            )}
          </div>
        ))}
      </section>

      {/* All other apps section */}
      <section className="mcp-other-section" aria-label="Universal Connection">
        <h2 className="mcp-section-heading">All other apps:</h2>

        <div className="mcp-connect-card">
          <div className="mcp-step-row">
            <span className="mcp-step-label">1. Copy your connection command</span>
            <div className="mcp-command-box">
              <code className="mcp-code-text">{stdioCommand}</code>
              <button
                type="button"
                className="mcp-copy-icon-btn"
                title="Copy command to clipboard"
                onClick={() => copyToClipboard(stdioCommand, 'cmd')}
              >
                {copiedId === 'cmd' ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="mcp-step-row">
            <span className="mcp-step-label">2. Or copy JSON configuration</span>
            <div className="mcp-json-preview">
              <pre><code>{fullJsonConfig}</code></pre>
              <button
                type="button"
                className="mcp-json-copy-btn"
                onClick={() => copyToClipboard(fullJsonConfig, 'json')}
              >
                {copiedId === 'json' ? 'Copied to Clipboard!' : 'Copy JSON'}
              </button>
            </div>
          </div>
        </div>

        {/* Installed Tools Overview */}
        <div className="mcp-tools-panel">
          <h3 className="mcp-tools-title">Available Tools (v2.1)</h3>
          <div className="mcp-tools-grid">
            <div className="mcp-tool-card">
              <span className="mcp-tool-badge">search_shorts_outliers</span>
              <p className="mcp-tool-desc">
                Filters breakout Shorts from small creators (&lt;50k subs) with Viral Multipliers (&gt;3.0x).
              </p>
            </div>

            <div className="mcp-tool-card">
              <span className="mcp-tool-badge">get_video_blueprint</span>
              <p className="mcp-tool-desc">
                Dissects the critical 0-3s hook, extracts full transcript, and outputs structured LLM modeling prompt.
              </p>
            </div>

            <div className="mcp-tool-card">
              <span className="mcp-tool-badge">get_trending_creatives</span>
              <p className="mcp-tool-desc">
                Retrieves real-time YouTube trending Shorts by country/category for immediate macro-trend analysis.
              </p>
            </div>

            <div className="mcp-tool-card">
              <span className="mcp-tool-badge">generate_creative_script_model</span>
              <p className="mcp-tool-desc">
                Re-engineers scene-by-scene scripts with 5 MedPy cut markers (Hook, Curiosity, Value, Climax, Loop).
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

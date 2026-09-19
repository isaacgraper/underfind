import React, { useState } from 'react';
import './McpClientCard.styles.css';

export interface McpClientApp {
  id: string;
  name: string;
  description: string;
  buttonLabel: string;
  configSnippet: string;
  instructions: string;
}

export interface McpClientCardProps {
  app: McpClientApp;
}

export const McpClientCard: React.FC<McpClientCardProps> = ({ app }) => {
  const [copied, setCopied] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(app.configSnippet);
    setCopied(true);
    setShowInstructions(true);
    setTimeout(() => {
      setCopied(false);
    }, 2500);
  };

  return (
    <div className="mcp-app-card-wrapper">
      <div className="mcp-app-card">
        <div className="mcp-app-meta">
          <div className="mcp-app-header-row">
            <span className="mcp-app-name">{app.name}</span>
          </div>
          <p className="mcp-app-desc">{app.description}</p>
        </div>

        <div className="mcp-app-action">
          <button
            type="button"
            className={`mcp-action-btn ${copied ? 'copied' : ''}`}
            onClick={handleCopy}
          >
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Config Copied!</span>
              </>
            ) : (
              <span>{app.buttonLabel}</span>
            )}
          </button>
        </div>
      </div>

      {showInstructions && (
        <div className="mcp-inline-instruction">
          <p>{app.instructions}</p>
        </div>
      )}
    </div>
  );
};

import React, { useState } from 'react';
import { McpClientCard, McpClientApp } from '@/features/mcp';
import './McpHubPage.styles.css';

export const McpHubPage: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

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

  const apps: McpClientApp[] = [
    {
      id: 'claude',
      name: 'Claude Desktop',
      description: 'Permita que o Claude consulte outliers de Shorts verticais, métricas de engajamento e tags diretamente no chat.',
      buttonLabel: 'Configurar Claude',
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
      instructions: 'Cole no seu arquivo %APPDATA%\\Claude\\claude_desktop_config.json (Windows) ou ~/Library/Application Support/Claude/claude_desktop_config.json (macOS).',
    },
    {
      id: 'chatgpt',
      name: 'ChatGPT / Custom GPTs',
      description: 'Conecte ações customizadas do ChatGPT para acessar multiplicadores virais e metadados de vídeos.',
      buttonLabel: 'Configurar ChatGPT',
      configSnippet: JSON.stringify(
        {
          name: 'Underfind Content Intelligence',
          endpoint: 'http://localhost:8000/api',
          schema_url: 'http://localhost:8000/openapi.json',
        },
        null,
        2
      ),
      instructions: 'Importe a URL da OpenAPI schema (http://localhost:8000/openapi.json) nas configurações de Custom GPT Actions.',
    },
    {
      id: 'cursor',
      name: 'Cursor IDE',
      description: 'Permita que o Cursor AI descubra referências de vídeos e tags de nicho diretamente no seu fluxo de desenvolvimento.',
      buttonLabel: 'Configurar Cursor',
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
      instructions: 'Salve na raiz do seu projeto como .cursor/mcp.json ou configure em Cursor Settings > Features > MCP.',
    },
    {
      id: 'gemini',
      name: 'Gemini / Antigravity',
      description: 'Conexão nativa via stdio para Google Antigravity IDE, agy CLI e agentes autônomos.',
      buttonLabel: 'Configurar Antigravity',
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
      instructions: 'Adicione no seu arquivo mcp_config.json da Antigravity IDE em %USERPROFILE%\\.gemini\\config\\mcp_config.json.',
    },
  ];

  return (
    <div className="mcp-container">
      <header className="mcp-header">
        <h1 className="mcp-title">Protocolo MCP (Model Context Protocol)</h1>
        <p className="mcp-subtitle">
          Sincronize o Underfind com seus clientes de inteligência artificial para consultar outliers verticais, taxas virais e tags.
        </p>
      </header>

      {/* Integration Client Cards */}
      <section className="mcp-apps-list" aria-label="Aplicações MCP Suportadas">
        {apps.map((app) => (
          <McpClientCard key={app.id} app={app} />
        ))}
      </section>

      {/* Universal Connection Section */}
      <section className="mcp-other-section" aria-label="Conexão Universal MCP">
        <h2 className="mcp-section-heading">Conexão Universal (Outros Clientes):</h2>

        <div className="mcp-connect-card">
          <div className="mcp-step-row">
            <span className="mcp-step-label">1. Comando de Execução stdio</span>
            <div className="mcp-command-box">
              <code className="mcp-code-text">{stdioCommand}</code>
              <button
                type="button"
                className="mcp-copy-icon-btn"
                title="Copiar comando para a área de transferência"
                onClick={() => copyToClipboard(stdioCommand, 'cmd')}
              >
                {copiedId === 'cmd' ? (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="mcp-step-row">
            <span className="mcp-step-label">2. Configuração JSON Completa</span>
            <div className="mcp-json-preview">
              <pre><code>{fullJsonConfig}</code></pre>
              <button
                type="button"
                className="mcp-json-copy-btn"
                onClick={() => copyToClipboard(fullJsonConfig, 'json')}
              >
                {copiedId === 'json' ? 'Copiado!' : 'Copiar JSON'}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

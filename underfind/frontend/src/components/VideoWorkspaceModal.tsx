import React, { useEffect, useState } from 'react';
import { VideoBlueprint } from '../types';
import { api } from '../services/api';

interface VideoWorkspaceModalProps {
  videoId: string | null;
  onClose: () => void;
}

export const VideoWorkspaceModal: React.FC<VideoWorkspaceModalProps> = ({ videoId, onClose }) => {
  const [blueprint, setBlueprint] = useState<VideoBlueprint | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tabs inside workspace
  const [activeModalTab, setActiveModalTab] = useState<'blueprint' | 'medpy'>('blueprint');

  // Blueprint state
  const [niche, setNiche] = useState('meu nicho');
  const [showTranscript, setShowTranscript] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedMedPy, setCopiedMedPy] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!videoId) {
      setBlueprint(null);
      return;
    }

    setLoading(true);
    setError(null);
    setShowTranscript(false);

    api.getVideoBlueprint(videoId, niche)
      .then(setBlueprint)
      .catch((err: any) => setError(err?.message || 'Falha ao processar vídeo'))
      .finally(() => setLoading(false));

    // Handle ESC key to close
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [videoId]);

  const handleRecalibrate = () => {
    if (!videoId) return;
    setLoading(true);
    api.getVideoBlueprint(videoId, niche)
      .then(setBlueprint)
      .catch((err: any) => setError(err?.message || 'Falha ao recalibrar'))
      .finally(() => setLoading(false));
  };

  const handleCopyPrompt = () => {
    if (!blueprint?.suggested_prompt) return;
    navigator.clipboard.writeText(blueprint.suggested_prompt);
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2000);
  };

  const generateMedPyPayload = () => {
    if (!blueprint) return '';
    const dur = blueprint.duration_seconds || 60;
    const hookEnd = Math.min(blueprint.hook_duration || 5, 6);
    const bodyEnd = Math.min(Math.floor(dur * 0.75), dur - 5);

    const payload = {
      engine: "MedPy",
      task: "clip_and_generate_raw_footage",
      video_id: blueprint.video_id,
      video_url: blueprint.video_url,
      title: blueprint.title,
      aspect_ratio: "9:16",
      auto_subtitles: true,
      clips: [
        {
          id: "clip_hook",
          label: "Hook / Gancho",
          start_seconds: 0,
          end_seconds: hookEnd,
          notes: blueprint.hook_text
        },
        {
          id: "clip_body",
          label: "Desenvolvimento / Retenção",
          start_seconds: hookEnd,
          end_seconds: bodyEnd
        },
        {
          id: "clip_payoff",
          label: "Desfecho / CTA",
          start_seconds: bodyEnd,
          end_seconds: dur
        }
      ]
    };
    return JSON.stringify(payload, null, 2);
  };

  const handleCopyMedPy = () => {
    const json = generateMedPyPayload();
    if (!json) return;
    navigator.clipboard.writeText(json);
    setCopiedMedPy(true);
    setTimeout(() => setCopiedMedPy(false), 2000);
  };

  const handleCopyLink = () => {
    if (!blueprint?.video_url) return;
    navigator.clipboard.writeText(blueprint.video_url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  if (!videoId) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="workspace-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="workspace-header">
          <div className="workspace-title-group">
            <h2 className="workspace-title">
              {blueprint?.title || 'Processando vídeo...'}
            </h2>
            {blueprint && (
              <div className="workspace-meta">
                <span>{blueprint.channel_title}</span>
                <span>•</span>
                <span>{blueprint.views.toLocaleString()} views</span>
                <span>•</span>
                <span style={{ color: 'var(--indicator-viral)', fontWeight: 600 }}>
                  +{blueprint.viral_ratio}x Viral Ratio
                </span>
                <span>•</span>
                <span>{blueprint.duration_seconds}s</span>
              </div>
            )}
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Fechar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="workspace-body">
          {loading && (
            <div style={{ textAlign: 'center', padding: '3.5rem 1rem' }}>
              <span className="spinner-dot" style={{ margin: '0 auto' }} />
              <p style={{ marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                Dissecando transcrição, ganchos e preparando espaço de trabalho...
              </p>
            </div>
          )}

          {error && (
            <div style={{ color: '#ef4444', padding: '2rem', textAlign: 'center' }}>
              {error}
            </div>
          )}

          {!loading && blueprint && (
            <>
              {/* Embedded Player */}
              <div className="video-embed-container">
                <iframe
                  src={`https://www.youtube-nocookie.com/embed/${blueprint.video_id}?autoplay=0`}
                  title={blueprint.title}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              </div>

              {/* Action Tabs */}
              <div className="action-tabs">
                <button
                  type="button"
                  className={`action-tab-btn ${activeModalTab === 'blueprint' ? 'active' : ''}`}
                  onClick={() => setActiveModalTab('blueprint')}
                >
                  Modelar Roteiro (IA)
                </button>
                <button
                  type="button"
                  className={`action-tab-btn ${activeModalTab === 'medpy' ? 'active' : ''}`}
                  onClick={() => setActiveModalTab('medpy')}
                >
                  Preparar para MedPy (Cortes)
                </button>
              </div>

              {/* TAB 1: ROTEIRO & HOOK */}
              {activeModalTab === 'blueprint' && (
                <>
                  {/* Hook Box */}
                  <div className="hook-container">
                    <div className="hook-caption">
                      Gancho Inicial Detectado ({blueprint.hook_duration}s)
                    </div>
                    <div className="hook-quote">
                      "{blueprint.hook_text || 'Sem fala detectada nos primeiros segundos'}"
                    </div>
                  </div>

                  {/* Niche Calibrator */}
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <input
                      type="text"
                      className="segment-input"
                      value={niche}
                      onChange={(e) => setNiche(e.target.value)}
                      placeholder="Adapte para seu nicho (ex: nutrição, investimentos, marketing)..."
                      style={{
                        background: 'var(--bg-input)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '0.5rem 0.8rem',
                        flex: 1
                      }}
                    />
                    <button
                      type="button"
                      className="btn-toolbar"
                      onClick={handleRecalibrate}
                    >
                      Recalibrar
                    </button>
                  </div>

                  {/* Prompt Box */}
                  <div className="prompt-viewer">
                    <div className="prompt-viewer-header">
                      <span className="prompt-viewer-title">Prompt Estruturado para LLM</span>
                      <button
                        type="button"
                        className="btn-copy-action"
                        onClick={handleCopyPrompt}
                      >
                        {copiedPrompt ? 'Copiado' : 'Copiar Prompt'}
                      </button>
                    </div>
                    <div className="prompt-text-display">
                      {blueprint.suggested_prompt}
                    </div>
                  </div>

                  {/* Transcript Accordion */}
                  <div>
                    <button
                      type="button"
                      className="transcript-toggle"
                      onClick={() => setShowTranscript(!showTranscript)}
                      style={{ width: '100%' }}
                    >
                      <span>Transcrição Completa ({blueprint.transcript_segments.length} trechos)</span>
                      <span>{showTranscript ? '−' : '+'}</span>
                    </button>

                    {showTranscript && (
                      <div className="transcript-content">
                        {blueprint.transcript_segments.length > 0 ? (
                          blueprint.transcript_segments.map((seg, idx) => (
                            <p key={idx} style={{ marginBottom: '0.4rem' }}>
                              <span style={{ color: 'var(--text-tertiary)', fontFamily: 'monospace', marginRight: '8px' }}>
                                [{Math.floor(seg.start)}s]
                              </span>
                              {seg.text}
                            </p>
                          ))
                        ) : (
                          <p>{blueprint.full_transcript}</p>
                        )}
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* TAB 2: MEDPY CUTS & RAW FOOTAGE */}
              {activeModalTab === 'medpy' && (
                <div className="medpy-box">
                  <div className="medpy-header">
                    <span className="medpy-title">Pipeline de Mídia MedPy</span>
                    <span className="medpy-badge">Automação de Cortes</span>
                  </div>

                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', lineHeight: 1.5 }}>
                    Pontos de corte sugeridos pelo algoritmo de retenção do Underfind. Exporte esta configuração para alimentar o motor do MedPy e gerar os arquivos brutos para distribuição.
                  </p>

                  <div className="medpy-cut-list">
                    <div className="cut-item">
                      <div>
                        <strong>Corte 1: Gancho Inicial (Hook)</strong>
                        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.74rem' }}>Retenção dos primeiros segundos</div>
                      </div>
                      <span className="cut-time">00:00 → 00:0{Math.min(blueprint.hook_duration, 6)}</span>
                    </div>

                    <div className="cut-item">
                      <div>
                        <strong>Corte 2: Desenvolvimento do Roteiro</strong>
                        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.74rem' }}>Sustentação de atenção</div>
                      </div>
                      <span className="cut-time">00:0{Math.min(blueprint.hook_duration, 6)} → 00:{Math.min(Math.floor(blueprint.duration_seconds * 0.75), blueprint.duration_seconds - 5)}</span>
                    </div>

                    <div className="cut-item">
                      <div>
                        <strong>Corte 3: Conclusão & CTA</strong>
                        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.74rem' }}>Chamada para ação ou loop</div>
                      </div>
                      <span className="cut-time">00:{Math.min(Math.floor(blueprint.duration_seconds * 0.75), blueprint.duration_seconds - 5)} → 00:{blueprint.duration_seconds}</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn-medpy-export"
                      onClick={handleCopyMedPy}
                      style={{ flex: 1 }}
                    >
                      {copiedMedPy ? 'Payload MedPy Copiado!' : 'Copiar Configuração MedPy (JSON)'}
                    </button>
                  </div>
                </div>
              )}

              {/* Toolbar */}
              <div className="modal-footer-toolbar">
                <button
                  type="button"
                  className="btn-toolbar"
                  onClick={handleCopyLink}
                >
                  {copiedLink ? 'Link Copiado' : 'Copiar Link'}
                </button>
                <a
                  href={blueprint.video_url}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-toolbar"
                >
                  Assistir no YouTube ↗
                </a>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

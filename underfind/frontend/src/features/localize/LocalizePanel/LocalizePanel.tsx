import React, { useEffect, useState } from 'react';
import { Job, LocalizationMode, PageProfile, VideoItem } from '../../../types';
import { apiClient } from '../../../lib/apiClient';
import './LocalizePanel.styles.css';

export interface LocalizePanelProps {
  video: VideoItem;
}

export const LocalizePanel: React.FC<LocalizePanelProps> = ({ video }) => {
  const [pages, setPages] = useState<PageProfile[]>([]);
  const [pageId, setPageId] = useState<number | null>(null);
  const [mode, setMode] = useState<LocalizationMode>('subtitles');
  const [localOnly, setLocalOnly] = useState(true);
  const [serverMode, setServerMode] = useState<'local' | 'online'>('local');
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.listPages()
      .then((list) => {
        setPages(list);
        if (list.length > 0) {
          setPageId(list[0].id);
          setLocalOnly(list[0].local_only);
        }
      })
      .catch(() => setPages([]));
    apiClient.checkHealth()
      .then((health) => setServerMode(health.ai_mode ?? 'local'))
      .catch(() => setServerMode('local'));
  }, []);

  useEffect(() => {
    setJob(null);
    setError(null);
  }, [video.video_id]);

  const handlePageChange = (id: number) => {
    setPageId(id);
    const page = pages.find((p) => p.id === id);
    if (page) setLocalOnly(page.local_only);
  };

  const handleSubmit = async () => {
    if (pageId === null) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await apiClient.createJobFromVideo(video, { pageId, mode, localOnly });
      await apiClient.runJob(created.id);
      setJob(created);
    } catch (err: any) {
      setError(err?.message || 'Falha ao criar o job');
    } finally {
      setSubmitting(false);
    }
  };

  if (pages.length === 0) {
    return (
      <div className="localize-panel">
        <h3 className="video-info-heading">Localizar vídeo</h3>
        <p className="video-empty-text">Cadastre uma página de destino (POST /api/pages) para localizar vídeos.</p>
      </div>
    );
  }

  const onlineLocked = !localOnly && serverMode === 'local';

  return (
    <div className="localize-panel">
      <h3 className="video-info-heading">Localizar vídeo</h3>

      <div className="localize-row">
        <label className="localize-field">
          <span className="localize-label">Página</span>
          <select
            className="localize-select"
            value={pageId ?? ''}
            onChange={(e) => handlePageChange(Number(e.target.value))}
          >
            {pages.map((page) => (
              <option key={page.id} value={page.id}>
                {page.display_name} (@{page.handle}, {page.language})
              </option>
            ))}
          </select>
        </label>

        <label className="localize-field">
          <span className="localize-label">Modo</span>
          <select
            className="localize-select"
            value={mode}
            onChange={(e) => setMode(e.target.value as LocalizationMode)}
          >
            <option value="subtitles">Legendas</option>
            <option value="dub">Dublagem</option>
          </select>
        </label>
      </div>

      <label className="localize-checkbox">
        <input
          type="checkbox"
          checked={localOnly}
          onChange={(e) => setLocalOnly(e.target.checked)}
        />
        <span>Somente IA local</span>
        <span className="localize-hint">
          {localOnly
            ? 'Whisper, OPUS-MT e Piper nesta máquina; nada online.'
            : 'Permite modelos online (LLM e edge-tts) para este job.'}
        </span>
      </label>

      {onlineLocked && (
        <p className="localize-warning">
          O servidor está em modo local (--local): este job vai rodar localmente mesmo assim. Inicie com --online para liberar.
        </p>
      )}

      <div className="localize-actions">
        {job && (
          <span className="localize-success">
            Job {job.id} criado ({job.local_only === false ? 'online permitido' : 'local'})
          </span>
        )}
        {error && <span className="localize-error">{error}</span>}
        <button
          type="button"
          className="btn-toolbar localize-submit"
          disabled={submitting || pageId === null}
          onClick={handleSubmit}
        >
          {submitting ? 'Criando...' : 'Localizar'}
        </button>
      </div>
    </div>
  );
};

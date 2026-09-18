import React, { useEffect, useState } from 'react';
import { VideoItem } from '../types';
import { api } from '../services/api';
import { VideoCard } from './VideoCard';

interface TrendingViewProps {
  onVideoClick: (videoId: string) => void;
}

export const TrendingView: React.FC<TrendingViewProps> = ({ onVideoClick }) => {
  const [regionCode, setRegionCode] = useState('BR');
  const [categoryId, setCategoryId] = useState<string>('0');
  const [shortsOnly, setShortsOnly] = useState(true);

  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTrending = async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await api.getTrending({
        regionCode,
        categoryId: categoryId === '0' ? null : categoryId,
        shortsOnly,
        maxResults: 30,
      });
      setVideos(results);
    } catch (err: any) {
      setError(err?.message || 'Erro ao carregar tendências');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTrending();
  }, [regionCode, categoryId, shortsOnly]);

  return (
    <div className="search-console-container">
      <div className="search-console-header">
        <h1 className="search-console-title">Tendências em Tempo Real</h1>
        <p className="search-console-subtitle">
          Conteúdos com aceleração máxima de visualizações pelo algoritmo do YouTube.
        </p>
      </div>

      {/* Segmented Filter Bar */}
      <div className="segmented-search-bar">
        <div className="search-segment flex-main">
          <label className="segment-label">Formato</label>
          <select
            className="segment-select"
            value={shortsOnly ? 'shorts' : 'all'}
            onChange={(e) => setShortsOnly(e.target.value === 'shorts')}
          >
            <option value="shorts">Apenas Shorts Verticais</option>
            <option value="all">Todos os Formatos</option>
          </select>
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label">Categoria</label>
          <select
            className="segment-select"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="0">Todas</option>
            <option value="20">Games</option>
            <option value="28">Tecnologia</option>
            <option value="24">Entretenimento</option>
            <option value="27">Educação</option>
          </select>
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label">Região</label>
          <select
            className="segment-select"
            value={regionCode}
            onChange={(e) => setRegionCode(e.target.value)}
          >
            <option value="BR">Brasil (BR)</option>
            <option value="US">Estados Unidos (US)</option>
          </select>
        </div>

        <button
          type="button"
          className="btn-search-trigger"
          onClick={loadTrending}
          disabled={loading}
        >
          {loading ? (
            <span className="spinner-dot" />
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          )}
          <span>Atualizar</span>
        </button>
      </div>

      {error && (
        <div style={{ color: '#ef4444', fontSize: '0.85rem', margin: '1rem 0' }}>
          {error}
        </div>
      )}

      <div className="results-bar" style={{ marginTop: '2rem' }}>
        <h2 className="results-heading">Vídeos em Alta</h2>
        <span className="results-count">{videos.length} resultado(s)</span>
      </div>

      <div className="video-grid">
        {loading && (
          <div className="empty-state">
            <span className="spinner-dot" style={{ margin: '0 auto' }} />
            <p style={{ marginTop: '0.8rem' }}>Carregando dados da API do YouTube...</p>
          </div>
        )}

        {!loading && videos.length === 0 && (
          <div className="empty-state">
            <p>Nenhum vídeo em alta para esta categoria.</p>
          </div>
        )}

        {!loading &&
          videos.map((video) => (
            <VideoCard
              key={video.video_id}
              video={video}
              onClick={onVideoClick}
            />
          ))}
      </div>
    </div>
  );
};

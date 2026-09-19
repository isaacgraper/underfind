import React, { useEffect, useState } from 'react';
import { VideoItem } from '@/types';
import { apiClient } from '@/lib';
import { VideoCard } from '@/features/videos';
import './TrendingPage.styles.css';

export interface TrendingPageProps {
  onVideoClick: (videoId: string) => void;
  onBookmarkSuccess?: () => void;
}

export const TrendingPage: React.FC<TrendingPageProps> = ({
  onVideoClick,
  onBookmarkSuccess,
}) => {
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
      const results = await apiClient.getTrending({
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
    <div className="trending-container">
      <div className="trending-header">
        <h1 className="trending-title">Tendências em Tempo Real</h1>
        <p className="trending-subtitle">
          Conteúdos com aceleração máxima de visualizações detectadas pelo algoritmo do YouTube.
        </p>
      </div>

      {/* Segmented Filter Bar */}
      <div className="trending-filter-bar">
        <div className="trending-segment flex-main">
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

        <div className="trending-segment flex-param">
          <label className="segment-label">Categoria</label>
          <select
            className="segment-select"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="0">Todas as Categorias</option>
            <option value="20">Games</option>
            <option value="28">Tecnologia & Ciência</option>
            <option value="24">Entretenimento</option>
            <option value="27">Educação</option>
          </select>
        </div>

        <div className="trending-segment flex-param">
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
          className="trending-refresh-btn"
          onClick={loadTrending}
          disabled={loading}
        >
          {loading ? (
            <span className="spinner-dot" />
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          )}
          <span>Atualizar</span>
        </button>
      </div>

      {error && <div className="trending-error-box">{error}</div>}

      <div className="trending-results-bar">
        <h2 className="trending-results-heading">Vídeos em Alta</h2>
        <span className="trending-results-count">{videos.length} resultado(s)</span>
      </div>

      <div className="trending-grid">
        {loading && (
          <div className="trending-empty-state">
            <span className="spinner-dot" style={{ margin: '0 auto' }} />
            <p style={{ marginTop: '0.8rem' }}>Carregando dados da API do YouTube...</p>
          </div>
        )}

        {!loading && videos.length === 0 && (
          <div className="trending-empty-state">
            <p>Nenhum vídeo em alta para os filtros selecionados.</p>
          </div>
        )}

        {!loading &&
          videos.map((video) => (
            <VideoCard
              key={video.video_id}
              video={video}
              onClick={onVideoClick}
              onSaved={onBookmarkSuccess}
            />
          ))}
      </div>
    </div>
  );
};

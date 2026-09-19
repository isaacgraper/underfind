import React, { useState } from 'react';
import { VideoItem } from '@/types';
import { apiClient } from '@/lib';
import { VideoCard } from '@/features/videos';
import './ExplorerPage.styles.css';

export interface ExplorerPageProps {
  onVideoClick: (videoId: string) => void;
  onBookmarkSuccess?: () => void;
}

export const ExplorerPage: React.FC<ExplorerPageProps> = ({
  onVideoClick,
  onBookmarkSuccess,
}) => {
  const [query, setQuery] = useState('');
  const [order, setOrder] = useState('relevance');
  const [shortsOnly, setShortsOnly] = useState(false);
  const [minViews, setMinViews] = useState<number | ''>('');
  const [maxSubs, setMaxSubs] = useState<number | ''>('');
  const [regionCode, setRegionCode] = useState('BR');

  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const results = await apiClient.searchVideos({
        query: query.trim(),
        order,
        is_shorts_only: shortsOnly,
        min_views: minViews === '' ? null : Number(minViews),
        max_subscribers: maxSubs === '' ? null : Number(maxSubs),
        region_code: regionCode,
        max_results: 30,
      });
      setVideos(results);
      setHasSearched(true);
    } catch (err: any) {
      setError(err?.message || 'Erro na pesquisa');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="explorer-container">
      <div className="explorer-header">
        <h1 className="explorer-title">Explorador Paramétrico</h1>
        <p className="explorer-subtitle">
          Busca granular com filtros combinados de volume, tamanho de audiência e relevância.
        </p>
      </div>

      <form onSubmit={handleSearch} className="explorer-filter-bar">
        <div className="explorer-segment flex-main">
          <label className="segment-label" htmlFor="exp-query">
            Termo de Pesquisa
          </label>
          <input
            id="exp-query"
            type="text"
            className="segment-input"
            placeholder="Digite palavras-chave, nichos ou tópicos..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="explorer-segment flex-param">
          <label className="segment-label" htmlFor="exp-order">
            Ordenação
          </label>
          <select
            id="exp-order"
            className="segment-select"
            value={order}
            onChange={(e) => setOrder(e.target.value)}
          >
            <option value="relevance">Relevância</option>
            <option value="viewCount">Mais Vistos</option>
            <option value="date">Mais Recentes</option>
          </select>
        </div>

        <div className="explorer-segment flex-param">
          <label className="segment-label" htmlFor="exp-format">
            Formato
          </label>
          <select
            id="exp-format"
            className="segment-select"
            value={shortsOnly ? 'shorts' : 'all'}
            onChange={(e) => setShortsOnly(e.target.value === 'shorts')}
          >
            <option value="all">Todos os Vídeos</option>
            <option value="shorts">Apenas Shorts</option>
          </select>
        </div>

        <div className="explorer-segment flex-param">
          <label className="segment-label" htmlFor="exp-views">
            Mín. Views
          </label>
          <input
            id="exp-views"
            type="number"
            className="segment-input"
            placeholder="Qualquer"
            value={minViews}
            onChange={(e) => setMinViews(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </div>

        <div className="explorer-segment flex-param">
          <label className="segment-label" htmlFor="exp-subs">
            Máx. Inscritos
          </label>
          <input
            id="exp-subs"
            type="number"
            className="segment-input"
            placeholder="Qualquer"
            value={maxSubs}
            onChange={(e) => setMaxSubs(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </div>

        <div className="explorer-segment flex-param">
          <label className="segment-label" htmlFor="exp-region">
            Região
          </label>
          <select
            id="exp-region"
            className="segment-select"
            value={regionCode}
            onChange={(e) => setRegionCode(e.target.value)}
          >
            <option value="BR">Brasil</option>
            <option value="US">EUA</option>
          </select>
        </div>

        <button type="submit" className="explorer-search-btn" disabled={loading}>
          {loading ? (
            <span className="spinner-dot" />
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          )}
          <span>Filtrar</span>
        </button>
      </form>

      {error && <div className="explorer-error-box">{error}</div>}

      <div className="explorer-results-bar">
        <h2 className="explorer-results-heading">Resultados do Explorador</h2>
        <span className="explorer-results-count">
          {hasSearched ? `${videos.length} resultado(s)` : 'Aguardando parâmetros'}
        </span>
      </div>

      <div className="explorer-grid">
        {!hasSearched && !loading && (
          <div className="explorer-empty-state">
            <p>Defina os parâmetros acima para iniciar a varredura.</p>
          </div>
        )}

        {hasSearched && videos.length === 0 && !loading && (
          <div className="explorer-empty-state">
            <p>Nenhum vídeo localizado para esta combinação de filtros.</p>
          </div>
        )}

        {videos.map((video) => (
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

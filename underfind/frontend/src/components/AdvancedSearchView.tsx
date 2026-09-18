import React, { useState } from 'react';
import { VideoItem } from '../types';
import { api } from '../services/api';
import { VideoCard } from './VideoCard';

interface AdvancedSearchViewProps {
  onVideoClick: (videoId: string) => void;
}

export const AdvancedSearchView: React.FC<AdvancedSearchViewProps> = ({ onVideoClick }) => {
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
      const results = await api.searchVideos({
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
    <div className="search-console-container">
      <div className="search-console-header">
        <h1 className="search-console-title">Explorador Paramétrico</h1>
        <p className="search-console-subtitle">
          Busca granular com filtros combinados de volume, tamanho de audiência e relevância.
        </p>
      </div>

      <form onSubmit={handleSearch} className="segmented-search-bar">
        <div className="search-segment flex-main">
          <label className="segment-label" htmlFor="adv-query">
            Termo de Pesquisa
          </label>
          <input
            id="adv-query"
            type="text"
            className="segment-input"
            placeholder="Digite palavras-chave, nichos ou tópicos..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="adv-order">
            Ordenação
          </label>
          <select
            id="adv-order"
            className="segment-select"
            value={order}
            onChange={(e) => setOrder(e.target.value)}
          >
            <option value="relevance">Relevância</option>
            <option value="viewCount">Mais Vistos</option>
            <option value="date">Mais Recentes</option>
          </select>
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="adv-format">
            Formato
          </label>
          <select
            id="adv-format"
            className="segment-select"
            value={shortsOnly ? 'shorts' : 'all'}
            onChange={(e) => setShortsOnly(e.target.value === 'shorts')}
          >
            <option value="all">Todos os Vídeos</option>
            <option value="shorts">Apenas Shorts</option>
          </select>
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="adv-views">
            Mín. Views
          </label>
          <input
            id="adv-views"
            type="number"
            className="segment-input"
            placeholder="Qualquer"
            value={minViews}
            onChange={(e) => setMinViews(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="adv-subs">
            Máx. Inscritos
          </label>
          <input
            id="adv-subs"
            type="number"
            className="segment-input"
            placeholder="Qualquer"
            value={maxSubs}
            onChange={(e) => setMaxSubs(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </div>

        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="adv-region">
            Região
          </label>
          <select
            id="adv-region"
            className="segment-select"
            value={regionCode}
            onChange={(e) => setRegionCode(e.target.value)}
          >
            <option value="BR">Brasil</option>
            <option value="US">EUA</option>
          </select>
        </div>

        <button type="submit" className="btn-search-trigger" disabled={loading}>
          {loading ? (
            <span className="spinner-dot" />
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          )}
          <span>Filtrar</span>
        </button>
      </form>

      {error && (
        <div style={{ color: '#ef4444', fontSize: '0.85rem', margin: '1rem 0' }}>
          {error}
        </div>
      )}

      <div className="results-bar" style={{ marginTop: '2rem' }}>
        <h2 className="results-heading">Resultados do Explorador</h2>
        <span className="results-count">
          {hasSearched ? `${videos.length} resultado(s)` : 'Aguardando parâmetros'}
        </span>
      </div>

      <div className="video-grid">
        {!hasSearched && !loading && (
          <div className="empty-state">
            <p>Defina os parâmetros acima para iniciar a varredura.</p>
          </div>
        )}

        {hasSearched && videos.length === 0 && !loading && (
          <div className="empty-state">
            <p>Nenhum vídeo localizado para esta combinação de filtros.</p>
          </div>
        )}

        {videos.map((video) => (
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

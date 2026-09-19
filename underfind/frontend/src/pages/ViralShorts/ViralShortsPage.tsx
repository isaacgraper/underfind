import React, { useEffect, useState } from 'react';
import { VideoItem } from '@/types';
import { apiClient } from '@/lib';
import { VideoCard } from '@/features/videos';
import './ViralShortsPage.styles.css';

export interface ViralShortsPageProps {
  initialQuery?: string;
  onVideoClick: (videoId: string) => void;
  onBookmarkSuccess?: () => void;
}

export const ViralShortsPage: React.FC<ViralShortsPageProps> = ({
  initialQuery = '',
  onVideoClick,
  onBookmarkSuccess,
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [maxSubs, setMaxSubs] = useState<number | ''>(50000);
  const [minViews, setMinViews] = useState<number>(10000);
  const [viralRatio, setViralRatio] = useState<number>(3.0);
  const [regionCode, setRegionCode] = useState('BR');

  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeSearch = async (searchTerm: string) => {
    if (!searchTerm.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const results = await apiClient.getShortsOutliers({
        query: searchTerm.trim(),
        maxSubscribers: maxSubs === '' ? null : Number(maxSubs),
        minViews: minViews,
        minViralRatio: viralRatio,
        regionCode: regionCode,
        maxResults: 30,
      });
      setVideos(results);
      setHasSearched(true);
    } catch (err: any) {
      setError(err?.message || 'Erro ao buscar vídeos anômalos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialQuery && initialQuery.trim()) {
      setQuery(initialQuery);
      executeSearch(initialQuery);
    }
  }, [initialQuery]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    await executeSearch(query);
  };

  return (
    <div className="viral-shorts-container">
      <div className="viral-shorts-header">
        <h1 className="viral-shorts-title">Descobridor de Shorts Virais</h1>
        <p className="viral-shorts-subtitle">
          Descubra conteúdos anômalos de canais pequenos com alto multiplicador viral sobre a base de inscritos.
        </p>
      </div>

      {/* Segmented Filter Bar */}
      <form onSubmit={handleSearch} className="viral-search-bar">
        <div className="viral-search-segment flex-main">
          <label className="segment-label" htmlFor="viral-niche-input">
            Nicho ou Palavra-Chave
          </label>
          <input
            id="viral-niche-input"
            type="text"
            className="segment-input"
            placeholder="Ex: finanças, marketing, curiosidades..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="viral-search-segment flex-param">
          <label className="segment-label" htmlFor="viral-subs-select">
            Tamanho do Canal
          </label>
          <select
            id="viral-subs-select"
            className="segment-select"
            value={maxSubs}
            onChange={(e) => setMaxSubs(e.target.value === '' ? '' : Number(e.target.value))}
          >
            <option value={20000}>Até 20k inscritos</option>
            <option value={50000}>Até 50k inscritos</option>
            <option value={100000}>Até 100k inscritos</option>
            <option value="">Qualquer tamanho</option>
          </select>
        </div>

        <div className="viral-search-segment flex-param">
          <label className="segment-label" htmlFor="viral-ratio-select">
            Viral Ratio
          </label>
          <select
            id="viral-ratio-select"
            className="segment-select"
            value={viralRatio}
            onChange={(e) => setViralRatio(Number(e.target.value))}
          >
            <option value={2.0}>Mín. 2x views/subs</option>
            <option value={3.0}>Mín. 3x (Outlier)</option>
            <option value={5.0}>Mín. 5x (Alta escala)</option>
            <option value={10.0}>Mín. 10x (Explosivo)</option>
          </select>
        </div>

        <div className="viral-search-segment flex-param">
          <label className="segment-label" htmlFor="viral-views-select">
            Visualizações
          </label>
          <select
            id="viral-views-select"
            className="segment-select"
            value={minViews}
            onChange={(e) => setMinViews(Number(e.target.value))}
          >
            <option value={5000}>5k+ views</option>
            <option value={10000}>10k+ views</option>
            <option value={50000}>50k+ views</option>
            <option value={100000}>100k+ views</option>
          </select>
        </div>

        <div className="viral-search-segment flex-param">
          <label className="segment-label" htmlFor="viral-region-select">
            Região
          </label>
          <select
            id="viral-region-select"
            className="segment-select"
            value={regionCode}
            onChange={(e) => setRegionCode(e.target.value)}
          >
            <option value="BR">Brasil (BR)</option>
            <option value="US">Estados Unidos (US)</option>
          </select>
        </div>

        <button type="submit" className="viral-search-trigger" disabled={loading}>
          {loading ? (
            <span className="spinner-dot" />
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          )}
          <span>Buscar</span>
        </button>
      </form>

      {error && <div className="viral-error-box">{error}</div>}

      <div className="viral-results-bar">
        <h2 className="viral-results-heading">Vídeos Encontrados</h2>
        <span className="viral-results-count">
          {hasSearched ? `${videos.length} resultado(s)` : 'Aguardando busca'}
        </span>
      </div>

      <div className="viral-grid">
        {!hasSearched && !loading && (
          <div className="viral-empty-state">
            <p>Selecione os parâmetros e pesquise por um nicho para descobrir Shorts virais.</p>
          </div>
        )}

        {hasSearched && videos.length === 0 && !loading && (
          <div className="viral-empty-state">
            <p>Nenhum vídeo atingiu todos os filtros aplicados. Tente reduzir os critérios.</p>
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

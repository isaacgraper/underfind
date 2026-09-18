import React, { useEffect, useState } from 'react';
import { VideoItem } from '../types';
import { api } from '../services/api';
import { VideoCard } from './VideoCard';

interface ShortsOutliersViewProps {
  initialQuery?: string;
  onVideoClick: (videoId: string) => void;
}

export const ShortsOutliersView: React.FC<ShortsOutliersViewProps> = ({
  initialQuery = '',
  onVideoClick,
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
      const results = await api.getShortsOutliers({
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
      setError(err?.message || 'Erro ao buscar vídeos');
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
    <div className="search-console-container">
      <div className="search-console-header">
        <h1 className="search-console-title">Descobridor de Shorts Virais</h1>
        <p className="search-console-subtitle">
          Localize conteúdos anômalos de canais pequenos para modelagem e extração de cortes.
        </p>
      </div>

      {/* Hotel-Style Segmented Search Bar */}
      <form onSubmit={handleSearch} className="segmented-search-bar">
        {/* Segment 1: Nicho ou Tópico */}
        <div className="search-segment flex-main">
          <label className="segment-label" htmlFor="niche-input">
            Nicho ou Palavra-Chave
          </label>
          <input
            id="niche-input"
            type="text"
            className="segment-input"
            placeholder="Ex: finanças, marketing, curiosidades..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
            autoFocus
          />
        </div>

        {/* Segment 2: Inscritos */}
        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="subs-select">
            Tamanho do Canal
          </label>
          <select
            id="subs-select"
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

        {/* Segment 3: Fator Viral Ratio */}
        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="ratio-select">
            Viral Ratio
          </label>
          <select
            id="ratio-select"
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

        {/* Segment 4: Mínimo de Views */}
        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="views-select">
            Visualizações
          </label>
          <select
            id="views-select"
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

        {/* Segment 5: Região */}
        <div className="search-segment flex-param">
          <label className="segment-label" htmlFor="region-select">
            Região
          </label>
          <select
            id="region-select"
            className="segment-select"
            value={regionCode}
            onChange={(e) => setRegionCode(e.target.value)}
          >
            <option value="BR">Brasil (BR)</option>
            <option value="US">Estados Unidos (US)</option>
          </select>
        </div>

        {/* Search Trigger Button */}
        <button type="submit" className="btn-search-trigger" disabled={loading}>
          {loading ? (
            <span className="spinner-dot" />
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          )}
          <span>Buscar</span>
        </button>
      </form>

      {error && (
        <div style={{ color: '#ef4444', fontSize: '0.85rem', margin: '1rem 0' }}>
          {error}
        </div>
      )}

      {/* Results Header */}
      <div className="results-bar" style={{ marginTop: '2rem' }}>
        <h2 className="results-heading">Vídeos Encontrados</h2>
        <span className="results-count">
          {hasSearched ? `${videos.length} resultado(s)` : 'Aguardando busca'}
        </span>
      </div>

      {/* Video Grid */}
      <div className="video-grid">
        {!hasSearched && !loading && (
          <div className="empty-state">
            <p>Selecione os parâmetros e pesquise por um nicho acima.</p>
          </div>
        )}

        {hasSearched && videos.length === 0 && !loading && (
          <div className="empty-state">
            <p>Nenhum vídeo atingiu todos os filtros aplicados.</p>
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

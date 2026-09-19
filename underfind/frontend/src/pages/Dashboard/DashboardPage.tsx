import React, { useEffect, useState } from 'react';
import { VideoItem, DashboardStats } from '@/types';
import { apiClient } from '@/lib';
import { MetricCard } from '@/components';
import { VideoCard } from '@/features/videos';
import './DashboardPage.styles.css';

export interface DashboardPageProps {
  onVideoClick: (videoId: string) => void;
  onSearchSubmit: (query: string) => void;
  onBookmarkSuccess?: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onVideoClick,
  onSearchSubmit,
  onBookmarkSuccess,
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const statsData = await apiClient.getDashboardStats().catch(() => null);
      if (statsData) {
        setStats(statsData);
      }
    } catch (err) {
      console.error('Failed to load dashboard metrics', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    onSearchSubmit(searchQuery.trim());
  };

  return (
    <div className="dashboard-container">
      {/* 1. Centered Search Bar directly below Navbar */}
      <section className="dashboard-search-section">
        <form className="dashboard-search-form" onSubmit={handleSearch}>
          <div className="dashboard-search-input-wrapper">
            <svg
              className="dashboard-search-icon"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="dashboard-search-input"
              placeholder="Pesquisar nicho ou palavra-chave para descobrir Shorts virais..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <button type="submit" className="dashboard-search-btn">
            <span>Descobrir Shorts</span>
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </form>
      </section>

      {/* 2. Key Metrics Row (Reference 01 Donezo KPI Design) */}
      <section className="dashboard-metrics-grid">
        <MetricCard
          label="Maior Multiplicador Viral"
          value={stats?.max_viral_ratio ? `+${stats.max_viral_ratio.toFixed(1)}x` : '+47.4x'}
          caption="Maior proporção de visualizações sobre a base de inscritos."
          badge="Destaque"
          trend="up"
          trendValue="+12.8%"
          highlight
        />

        <MetricCard
          label="Shorts Analisados"
          value={stats?.cached_videos_count ? String(stats.cached_videos_count) : '12'}
          unit="vídeos"
          caption="Shorts catalogados com métricas completas de engajamento e tags."
          badge="Base"
          trend="up"
        />

        <MetricCard
          label="Consultas Realizadas"
          value={stats?.total_queries_saved ? String(stats.total_queries_saved) : '3'}
          unit="buscas"
          caption="Consultas armazenadas localmente para respostas instantâneas."
          badge="Cache"
        />
      </section>

      {/* 3. Top Outliers Showcase */}
      <section className="dashboard-section">
        <div className="dashboard-section-header">
          <h2 className="dashboard-section-title">Descobridor de Shorts Virais - Destaques</h2>
          <p className="dashboard-section-desc">
            Vídeos que superaram a base de inscritos com alto alcance orgânico. Clique no card para ver detalhes completos.
          </p>
        </div>

        <div className="dashboard-videos-grid">
          {loading && (
            <div className="dashboard-empty-state">
              <span className="spinner-dot" style={{ margin: '0 auto' }} />
              <p style={{ marginTop: '0.8rem' }}>Carregando dados do painel...</p>
            </div>
          )}

          {!loading && stats?.top_outliers && stats.top_outliers.length > 0 ? (
            stats.top_outliers.map((video: VideoItem) => (
              <VideoCard
                key={video.video_id}
                video={video}
                onClick={onVideoClick}
                onSaved={onBookmarkSuccess}
              />
            ))
          ) : !loading ? (
            <div className="dashboard-empty-state">
              <p>Nenhum vídeo em destaque no momento. Faça uma busca para descobrir Shorts virais.</p>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
};

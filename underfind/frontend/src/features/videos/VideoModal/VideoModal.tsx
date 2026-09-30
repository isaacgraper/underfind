import React, { useEffect, useState } from 'react';
import { VideoItem } from '../../../types';
import { apiClient } from '../../../lib/apiClient';
import { LocalizePanel } from '../../localize';
import './VideoModal.styles.css';

export interface VideoModalProps {
  videoId: string | null;
  onClose: () => void;
  isOpen?: boolean;
}

export const VideoModal: React.FC<VideoModalProps> = ({ videoId, onClose, isOpen = true }) => {
  const [video, setVideo] = useState<VideoItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!videoId) {
      setVideo(null);
      return;
    }

    setLoading(true);
    setError(null);

    apiClient.getVideoDetails(videoId)
      .then(setVideo)
      .catch(() => {
        // Fallback to blueprint endpoint if needed
        return apiClient.getVideoBlueprint(videoId).then((bp) => {
          setVideo({
            video_id: bp.video_id,
            title: bp.title,
            channel_title: bp.channel_title,
            views: bp.views,
            subscribers: bp.subscribers,
            viral_ratio: bp.viral_ratio,
            video_url: bp.video_url,
            duration_seconds: bp.duration_seconds,
            is_short: bp.is_short,
            likes: 0,
            comments_count: 0,
            tags: [],
            description: '',
          });
        });
      })
      .catch((err: any) => setError(err?.message || 'Falha ao carregar dados do vídeo'))
      .finally(() => setLoading(false));

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [videoId, onClose]);

  const handleCopyLink = () => {
    if (!video) return;
    const url = video.video_url || `https://www.youtube.com/watch?v=${video.video_id}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  if (!videoId || !isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="workspace-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="workspace-header">
          <div className="workspace-title-group">
            <h2 className="workspace-title">
              {video?.title || 'Carregando vídeo...'}
            </h2>
            {video && (
              <div className="workspace-meta">
                <span>{video.channel_title}</span>
                {video.subscribers ? (
                  <>
                    <span>•</span>
                    <span>{video.subscribers.toLocaleString()} inscritos</span>
                  </>
                ) : null}
                {video.viral_ratio > 0 && (
                  <>
                    <span>•</span>
                    <span style={{ color: 'var(--indicator-viral)', fontWeight: 600 }}>
                      +{video.viral_ratio}x Viral Ratio
                    </span>
                  </>
                )}
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
                Carregando dados do vídeo...
              </p>
            </div>
          )}

          {error && (
            <div style={{ color: '#ef4444', padding: '2rem', textAlign: 'center' }}>
              {error}
            </div>
          )}

          {!loading && video && (
            <>
              {/* Embedded Player */}
              <div className="video-embed-container">
                <iframe
                  src={`https://www.youtube-nocookie.com/embed/${video.video_id}?autoplay=0`}
                  title={video.title}
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              </div>

              {/* Metrics: Views, Likes, Comments */}
              <div className="video-details-metrics-row">
                <div className="detail-stat-box">
                  <span className="detail-stat-label">Visualizações</span>
                  <span className="detail-stat-val">{(video.views || 0).toLocaleString()}</span>
                </div>

                <div className="detail-stat-box">
                  <span className="detail-stat-label">Curtidas</span>
                  <span className="detail-stat-val">{(video.likes || 0).toLocaleString()}</span>
                </div>

                <div className="detail-stat-box">
                  <span className="detail-stat-label">Comentários</span>
                  <span className="detail-stat-val">{(video.comments_count || 0).toLocaleString()}</span>
                </div>

                <div className="detail-stat-box">
                  <span className="detail-stat-label">Multiplicador Viral</span>
                  <span className="detail-stat-val highlight-viral">+{video.viral_ratio}x</span>
                </div>
              </div>

              {/* Keywords / Tags */}
              <div className="video-info-section">
                <h3 className="video-info-heading">Palavras-chave e Tags</h3>
                {video.tags && video.tags.length > 0 ? (
                  <div className="video-tags-container">
                    {video.tags.map((tag, idx) => (
                      <span key={idx} className="video-keyword-tag">
                        #{tag}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="video-empty-text">Nenhuma palavra-chave/tag identificada no vídeo.</p>
                )}
              </div>

              {/* Description */}
              <div className="video-info-section">
                <h3 className="video-info-heading">Descrição do Vídeo</h3>
                <div className="video-description-box">
                  {video.description ? (
                    <p className="video-description-text">{video.description}</p>
                  ) : (
                    <p className="video-empty-text">Este vídeo não possui descrição.</p>
                  )}
                </div>
              </div>

              <LocalizePanel video={video} />

              {/* Footer Toolbar */}
              <div className="modal-footer-toolbar">
                <button
                  type="button"
                  className="btn-toolbar"
                  onClick={handleCopyLink}
                >
                  {copiedLink ? 'Link Copiado!' : 'Copiar Link'}
                </button>
                <a
                  href={video.video_url || `https://www.youtube.com/watch?v=${video.video_id}`}
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

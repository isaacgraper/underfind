import React, { useState } from 'react';
import { VideoItem } from '../../../types';
import { apiClient } from '../../../lib/apiClient';
import { formatCompact } from '../../../utils/formatters';
import './VideoCard.styles.css';

export interface VideoCardProps {
  video: VideoItem;
  onClick: (videoId: string) => void;
  onSaved?: () => void;
  onSavedToIdeas?: () => void;
}

export const VideoCard: React.FC<VideoCardProps> = ({
  video,
  onClick,
  onSaved,
  onSavedToIdeas,
}) => {
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handleBookmark = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isSaved || isSaving) return;

    setIsSaving(true);
    try {
      await apiClient.saveIdea({
        video,
        status: 'backlog',
        notes: video.tags && video.tags.length > 0 ? video.tags.slice(0, 3).join(', ') : '',
      });
      setIsSaved(true);
      if (onSaved) onSaved();
      if (onSavedToIdeas) onSavedToIdeas();
    } catch (err) {
      console.error('Failed to save idea to board', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <article
      className="video-card"
      onClick={() => onClick(video.video_id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(video.video_id);
        }
      }}
    >
      {/* 1. Media Thumbnail with Floating Glassmorphic Pills (Reference 02) */}
      <div className="card-media">
        <img
          src={video.thumbnail_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80'}
          className="card-thumbnail"
          alt={video.title}
          loading="lazy"
        />

        {video.viral_ratio > 0 && (
          <span className="card-badge-viral">
            +{video.viral_ratio}x Viral
          </span>
        )}

        {/* Floating Bookmark Button to Save to Ideas Board */}
        <button
          type="button"
          className={`card-bookmark-btn ${isSaved ? 'saved' : ''}`}
          title={isSaved ? 'Salvo no Quadro de Ideias' : 'Salvar no Quadro de Ideias'}
          onClick={handleBookmark}
        >
          {isSaved ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="#10b981" stroke="#10b981" strokeWidth="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
          )}
        </button>

        {video.duration_seconds ? (
          <span className="card-duration">{video.duration_seconds}s</span>
        ) : null}
      </div>

      {/* 2. Card Content & Title */}
      <div className="card-content">
        <h3 className="card-title" title={video.title}>
          {video.title}
        </h3>

        <div className="card-channel">
          <span className="channel-title">{video.channel_title || 'Criador'}</span>
          <span>{formatCompact(video.subscribers)} inscritos</span>
        </div>

        {/* 3. Real-Estate Inspired Spec Badges Row (Reference 02) */}
        <div className="card-spec-chips">
          <div className="spec-chip" title="Visualizações">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            <span>{formatCompact(video.views)}</span>
          </div>

          <div className="spec-chip" title="Curtidas">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <span>{formatCompact(video.likes)}</span>
          </div>

          <div className="spec-chip" title="Comentários">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span>{formatCompact(video.comments_count)}</span>
          </div>
        </div>

        {/* 4. Action Footer with Fluid Pill (Reference 04) */}
        <div className="card-footer">
          <div className="card-ratio-highlight">
            +{video.viral_ratio}x <span className="ratio-caption">alcance</span>
          </div>
          <button
            type="button"
            className="card-action-pill"
            onClick={(e) => {
              e.stopPropagation();
              onClick(video.video_id);
            }}
          >
            Ver Detalhes
          </button>
        </div>
      </div>
    </article>
  );
};

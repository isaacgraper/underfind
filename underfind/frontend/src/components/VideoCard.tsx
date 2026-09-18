import React from 'react';
import { VideoItem } from '../types';

interface VideoCardProps {
  video: VideoItem;
  onClick: (videoId: string) => void;
}

export const VideoCard: React.FC<VideoCardProps> = ({ video, onClick }) => {
  const formatCompact = (num?: number) => {
    if (!num && num !== 0) return '0';
    if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
    if (num >= 1_000) return (num / 1_000).toFixed(1) + 'k';
    return num.toLocaleString();
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
      <div className="card-media">
        <img
          src={video.thumbnail_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80'}
          className="card-thumbnail"
          alt={video.title}
          loading="lazy"
        />
        {video.viral_ratio > 0 && (
          <span className="card-badge-viral">
            +{video.viral_ratio}x ratio
          </span>
        )}
        {video.is_short && <span className="card-badge-format">Shorts</span>}
        {video.duration_seconds ? (
          <span className="card-duration">{video.duration_seconds}s</span>
        ) : null}
      </div>

      <div className="card-content">
        <h3 className="card-title" title={video.title}>
          {video.title}
        </h3>

        <div className="card-channel">
          <span className="channel-title">{video.channel_title || 'Creator'}</span>
          <span>{formatCompact(video.subscribers)} subs</span>
        </div>

        <div className="card-stats">
          <div>
            <span className="card-stat-value">{formatCompact(video.views)}</span> views
          </div>
          {video.likes ? (
            <div>
              <span className="card-stat-value">{formatCompact(video.likes)}</span> likes
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
};

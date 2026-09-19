import React from 'react';
import { IdeaItem } from '@/types';
import './IdeaCard.styles.css';

export interface IdeaCardProps {
  idea: IdeaItem;
  onCardClick: (videoId: string) => void;
  onMoveStatus: (videoId: string, nextStatus: 'backlog' | 'in_progress' | 'done') => void;
  onDelete: (videoId: string, e: React.MouseEvent) => void;
}

export const IdeaCard: React.FC<IdeaCardProps> = ({
  idea,
  onCardClick,
  onMoveStatus,
  onDelete,
}) => {
  const initial = idea.channel_title ? idea.channel_title.charAt(0).toUpperCase() : 'C';

  return (
    <div className="idea-card" onClick={() => onCardClick(idea.video_id)}>
      <div className="idea-card-header">
        <div className="idea-creator">
          <div className="creator-avatar-placeholder">{initial}</div>
          <span className="creator-name">{idea.channel_title || 'Ideia Autoral'}</span>
        </div>

        {idea.status === 'done' ? (
          <span className="idea-done-tag">Pronto</span>
        ) : idea.viral_ratio > 0 ? (
          <span className="idea-viral-pill">+{idea.viral_ratio}x</span>
        ) : null}
      </div>

      <h3 className="idea-card-title">{idea.title}</h3>

      {idea.script_notes && (
        <p className="idea-card-notes">{idea.script_notes}</p>
      )}

      <div className="idea-card-footer">
        <div className="idea-actions-group">
          {idea.status === 'backlog' && (
            <button
              type="button"
              className="idea-action-btn idea-advance-btn"
              onClick={(e) => {
                e.stopPropagation();
                onMoveStatus(idea.video_id, 'in_progress');
              }}
            >
              Roteirizar →
            </button>
          )}

          {idea.status === 'in_progress' && (
            <>
              <button
                type="button"
                className="idea-action-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveStatus(idea.video_id, 'backlog');
                }}
              >
                ← Backlog
              </button>
              <button
                type="button"
                className="idea-action-btn idea-advance-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveStatus(idea.video_id, 'done');
                }}
              >
                Gravar →
              </button>
            </>
          )}

          {idea.status === 'done' && (
            <button
              type="button"
              className="idea-action-btn"
              onClick={(e) => {
                e.stopPropagation();
                onMoveStatus(idea.video_id, 'in_progress');
              }}
            >
              ← Roteirizar
            </button>
          )}
        </div>

        <button
          type="button"
          className="idea-delete-icon-btn"
          title="Remover do quadro"
          onClick={(e) => onDelete(idea.video_id, e)}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>
    </div>
  );
};

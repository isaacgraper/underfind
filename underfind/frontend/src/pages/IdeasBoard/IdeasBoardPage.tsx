import React, { useState } from 'react';
import { useIdeas } from '@/hooks';
import { apiClient } from '@/lib';
import { IdeaCard, IdeaModal } from '@/features/ideas';
import './IdeasBoardPage.styles.css';

export interface IdeasBoardPageProps {
  onVideoClick: (videoId: string) => void;
}

export const IdeasBoardPage: React.FC<IdeasBoardPageProps> = ({ onVideoClick }) => {
  const { ideas, loading, error, updateStatus, deleteIdea, refresh } = useIdeas();
  const [filterQuery, setFilterQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  const handleCreateIdea = async (title: string, channel: string, notes: string) => {
    const dummyVideo = {
      video_id: `custom_${Date.now()}`,
      title: title.trim(),
      channel_title: channel.trim() || 'Ideia Autoral',
      views: 0,
      subscribers: 0,
      viral_ratio: 0,
      duration_seconds: 60,
      is_short: true,
    };

    await apiClient.saveIdea({
      video: dummyVideo,
      status: 'backlog',
      notes: notes.trim(),
    });

    await refresh();
  };

  const filteredIdeas = ideas.filter((idea) => {
    const q = filterQuery.toLowerCase();
    return (
      idea.title.toLowerCase().includes(q) ||
      (idea.channel_title && idea.channel_title.toLowerCase().includes(q)) ||
      (idea.script_notes && idea.script_notes.toLowerCase().includes(q))
    );
  });

  const backlogIdeas = filteredIdeas.filter((i) => i.status === 'backlog');
  const inProgressIdeas = filteredIdeas.filter((i) => i.status === 'in_progress');
  const doneIdeas = filteredIdeas.filter((i) => i.status === 'done');

  return (
    <div className="ideas-board-container">
      {/* 1. Header & Controls Bar */}
      <div className="ideas-board-header">
        <div>
          <h1 className="ideas-board-title">Quadro de Ideias</h1>
          <p className="ideas-board-subtitle">
            Selecione, organize e acompanhe seus Shorts minerados do backlog até a gravação.
          </p>
        </div>

        <div className="ideas-header-actions">
          <div className="ideas-search-input-box">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="Filtrar ideias..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              className="ideas-search-input"
            />
          </div>

          <button
            type="button"
            className="btn-create-idea"
            onClick={() => setShowAddModal(true)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Nova Ideia</span>
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <span className="spinner-dot" style={{ margin: '0 auto' }} />
          <p style={{ marginTop: '0.75rem', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
            Carregando quadro de ideias...
          </p>
        </div>
      )}

      {error && (
        <div style={{ color: '#ef4444', fontSize: '0.85rem', textAlign: 'center' }}>
          {error}
        </div>
      )}

      {/* 2. Three Kanban Columns (Reference 03) */}
      <div className="ideas-columns-grid">
        {/* Column 1: Backlog / Salvos */}
        <div className="ideas-column">
          <div className="ideas-col-header">
            <div className="col-title-group">
              <span className="col-indicator col-indicator-orange" />
              <h2 className="col-title">Backlog / Salvos</h2>
            </div>
            <span className="col-count-badge">{backlogIdeas.length}</span>
          </div>

          <div className="ideas-stack">
            {backlogIdeas.length === 0 ? (
              <div className="ideas-empty-slot">
                Nenhum vídeo salvo no backlog. Salve vídeos no ícone de bookmark nos cards.
              </div>
            ) : (
              backlogIdeas.map((idea) => (
                <IdeaCard
                  key={idea.video_id}
                  idea={idea}
                  onCardClick={onVideoClick}
                  onMoveStatus={updateStatus}
                  onDelete={deleteIdea}
                />
              ))
            )}
          </div>
        </div>

        {/* Column 2: Em Roteirização */}
        <div className="ideas-column">
          <div className="ideas-col-header">
            <div className="col-title-group">
              <span className="col-indicator col-indicator-yellow" />
              <h2 className="col-title">Em Roteirização</h2>
            </div>
            <span className="col-count-badge">{inProgressIdeas.length}</span>
          </div>

          <div className="ideas-stack">
            {inProgressIdeas.length === 0 ? (
              <div className="ideas-empty-slot">
                Nenhum roteiro em andamento no momento.
              </div>
            ) : (
              inProgressIdeas.map((idea) => (
                <IdeaCard
                  key={idea.video_id}
                  idea={idea}
                  onCardClick={onVideoClick}
                  onMoveStatus={updateStatus}
                  onDelete={deleteIdea}
                />
              ))
            )}
          </div>
        </div>

        {/* Column 3: Pronto para Gravação */}
        <div className="ideas-column">
          <div className="ideas-col-header">
            <div className="col-title-group">
              <span className="col-indicator col-indicator-green" />
              <h2 className="col-title">Pronto para Gravação</h2>
            </div>
            <span className="col-count-badge">{doneIdeas.length}</span>
          </div>

          <div className="ideas-stack">
            {doneIdeas.length === 0 ? (
              <div className="ideas-empty-slot">
                Nenhuma ideia pronta para gravar ainda.
              </div>
            ) : (
              doneIdeas.map((idea) => (
                <IdeaCard
                  key={idea.video_id}
                  idea={idea}
                  onCardClick={onVideoClick}
                  onMoveStatus={updateStatus}
                  onDelete={deleteIdea}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Manual Idea Creation Modal */}
      <IdeaModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSubmit={handleCreateIdea}
      />
    </div>
  );
};

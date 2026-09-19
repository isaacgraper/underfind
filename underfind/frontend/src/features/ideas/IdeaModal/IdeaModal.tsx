import React, { useState } from 'react';
import { Button } from '@/components';
import './IdeaModal.styles.css';

export interface IdeaModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (title: string, channel: string, notes: string) => Promise<void>;
}

export const IdeaModal: React.FC<IdeaModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
  const [title, setTitle] = useState('');
  const [channel, setChannel] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setSubmitting(true);
    try {
      await onSubmit(title.trim(), channel.trim(), notes.trim());
      setTitle('');
      setChannel('');
      setNotes('');
      onClose();
    } catch (err) {
      console.error('Failed to submit idea', err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="idea-modal-overlay" onClick={onClose}>
      <div className="idea-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="idea-modal-header">
          <h2 className="idea-modal-title">Nova Ideia de Vídeo</h2>
          <button
            type="button"
            className="idea-modal-close-btn"
            onClick={onClose}
            aria-label="Fechar"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="idea-modal-form">
          <div className="idea-modal-field">
            <label className="idea-modal-label" htmlFor="idea-title">
              Título da Ideia ou Ângulo
            </label>
            <input
              id="idea-title"
              type="text"
              className="idea-modal-input"
              placeholder="Ex: Como economizar R$ 10k em 6 meses..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="idea-modal-field">
            <label className="idea-modal-label" htmlFor="idea-channel">
              Criador / Canal de Referência (Opcional)
            </label>
            <input
              id="idea-channel"
              type="text"
              className="idea-modal-input"
              placeholder="Ex: Ideia Autoral, @investidor..."
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
            />
          </div>

          <div className="idea-modal-field">
            <label className="idea-modal-label" htmlFor="idea-notes">
              Anotações do Roteiro / Gancho
            </label>
            <textarea
              id="idea-notes"
              className="idea-modal-textarea"
              placeholder="Adicione ideias de gancho, palavras-chave ou estrutura do vídeo..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div className="idea-modal-actions">
            <Button
              variant="secondary"
              onClick={onClose}
              type="button"
            >
              Cancelar
            </Button>
            <Button
              variant="primary"
              type="submit"
              disabled={submitting || !title.trim()}
            >
              {submitting ? 'Salvando...' : 'Adicionar ao Backlog'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

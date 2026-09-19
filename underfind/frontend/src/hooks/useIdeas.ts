import { useState, useEffect, useCallback } from 'react';
import { IdeaItem, VideoItem } from '../types';
import { apiClient } from '../lib/apiClient';

export function useIdeas() {
  const [ideas, setIdeas] = useState<IdeaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getIdeas();
      setIdeas(data || []);
    } catch (err: any) {
      setError(err?.message || 'Falha ao carregar quadro de ideias');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIdeas();
  }, [fetchIdeas]);

  const addVideoToIdeas = useCallback(async (video: VideoItem, notes?: string) => {
    try {
      const saved = await apiClient.saveIdea({
        video,
        status: 'backlog',
        notes: notes || (video.tags && video.tags.length > 0 ? video.tags.slice(0, 3).join(', ') : ''),
      });
      setIdeas((prev) => [saved, ...prev]);
      return saved;
    } catch (err: any) {
      setError(err?.message || 'Erro ao salvar vídeo no quadro');
      throw err;
    }
  }, []);

  const updateStatus = useCallback(async (videoId: string, nextStatus: 'backlog' | 'in_progress' | 'done') => {
    try {
      await apiClient.updateIdeaStatus(videoId, nextStatus);
      setIdeas((prev) =>
        prev.map((item) =>
          item.video_id === videoId ? { ...item, status: nextStatus } : item
        )
      );
    } catch (err: any) {
      setError(err?.message || 'Erro ao atualizar status');
      throw err;
    }
  }, []);

  const deleteIdea = useCallback(async (videoId: string) => {
    try {
      await apiClient.deleteIdea(videoId);
      setIdeas((prev) => prev.filter((item) => item.video_id !== videoId));
    } catch (err: any) {
      setError(err?.message || 'Erro ao remover ideia');
      throw err;
    }
  }, []);

  return {
    ideas,
    loading,
    error,
    refresh: fetchIdeas,
    addVideoToIdeas,
    updateStatus,
    deleteIdea,
  };
}

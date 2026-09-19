import { useState, useCallback } from 'react';

export function useVideoModal() {
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  const openVideo = useCallback((videoId: string) => {
    setSelectedVideoId(videoId);
  }, []);

  const closeVideo = useCallback(() => {
    setSelectedVideoId(null);
  }, []);

  const isOpen = Boolean(selectedVideoId);

  return {
    selectedVideoId,
    isOpen,
    isModalOpen: isOpen,
    openVideo,
    openVideoModal: openVideo,
    closeVideo,
    closeVideoModal: closeVideo,
  };
}

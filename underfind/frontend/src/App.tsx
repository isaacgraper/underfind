import { useState } from 'react';
import { ActiveTab } from '@/types';
import { Navbar } from '@/components';
import { useVideoModal } from '@/hooks';
import { VideoModal } from '@/features/videos';
import {
  DashboardPage,
  ViralShortsPage,
  TrendingPage,
  IdeasBoardPage,
  ExplorerPage,
  McpHubPage,
} from '@/pages';

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const { selectedVideoId, isModalOpen, openVideoModal, closeVideoModal } = useVideoModal();
  const [initialSearchQuery, setInitialSearchQuery] = useState<string>('');

  const handleDashboardSearch = (query: string) => {
    setInitialSearchQuery(query);
    setActiveTab('shorts');
  };

  return (
    <>
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      <main>
        {activeTab === 'dashboard' && (
          <DashboardPage
            onVideoClick={openVideoModal}
            onSearchSubmit={handleDashboardSearch}
          />
        )}
        {activeTab === 'shorts' && (
          <ViralShortsPage
            initialQuery={initialSearchQuery}
            onVideoClick={openVideoModal}
          />
        )}
        {activeTab === 'trending' && (
          <TrendingPage onVideoClick={openVideoModal} />
        )}
        {activeTab === 'ideas' && (
          <IdeasBoardPage onVideoClick={openVideoModal} />
        )}
        {activeTab === 'search' && (
          <ExplorerPage onVideoClick={openVideoModal} />
        )}
        {activeTab === 'mcp' && <McpHubPage />}
      </main>

      <VideoModal
        isOpen={isModalOpen}
        videoId={selectedVideoId}
        onClose={closeVideoModal}
      />
    </>
  );
}

export default App;

import { useState } from 'react';
import { ActiveTab } from './types';
import { Navbar } from './components/Navbar';
import { DashboardView } from './components/DashboardView';
import { ShortsOutliersView } from './components/ShortsOutliersView';
import { TrendingView } from './components/TrendingView';
import { AdvancedSearchView } from './components/AdvancedSearchView';
import { McpView } from './components/McpView';
import { VideoWorkspaceModal } from './components/VideoWorkspaceModal';

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
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
          <DashboardView
            onVideoClick={setSelectedVideoId}
            onSearchSubmit={handleDashboardSearch}
          />
        )}
        {activeTab === 'shorts' && (
          <ShortsOutliersView
            initialQuery={initialSearchQuery}
            onVideoClick={setSelectedVideoId}
          />
        )}
        {activeTab === 'trending' && (
          <TrendingView onVideoClick={setSelectedVideoId} />
        )}
        {activeTab === 'search' && (
          <AdvancedSearchView onVideoClick={setSelectedVideoId} />
        )}
        {activeTab === 'mcp' && (
          <McpView />
        )}
      </main>

      <VideoWorkspaceModal
        videoId={selectedVideoId}
        onClose={() => setSelectedVideoId(null)}
      />
    </>
  );
}

export default App;

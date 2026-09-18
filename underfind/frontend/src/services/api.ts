import {
  VideoItem,
  SearchRequest,
  VideoBlueprint,
  HealthResponse,
  DashboardStats,
  IdeaItem,
} from '../types';

const API_BASE = '/api';

export const api = {
  async checkHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Failed to verify API status');
    return res.json();
  },

  async getDashboardStats(): Promise<DashboardStats> {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    if (!res.ok) throw new Error('Failed to load dashboard metrics');
    return res.json();
  },

  async getIdeas(): Promise<IdeaItem[]> {
    const res = await fetch(`${API_BASE}/ideas`);
    if (!res.ok) throw new Error('Failed to load ideas board');
    return res.json();
  },

  async saveIdea(payload: {
    video: VideoItem;
    status?: string;
    hook_text?: string;
    notes?: string;
  }): Promise<IdeaItem> {
    const res = await fetch(`${API_BASE}/ideas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to save idea to board');
    return res.json();
  },

  async updateIdeaStatus(
    videoId: string,
    status: string,
    notes?: string,
  ): Promise<{ status: string; video_id: string; new_status: string }> {
    const res = await fetch(`${API_BASE}/ideas/${videoId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, notes }),
    });
    if (!res.ok) throw new Error('Failed to update idea status');
    return res.json();
  },

  async deleteIdea(videoId: string): Promise<{ status: string; video_id: string }> {
    const res = await fetch(`${API_BASE}/ideas/${videoId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete idea');
    return res.json();
  },

  async getShortsOutliers(params: {
    query: string;
    maxSubscribers?: number | null;
    minViews?: number | null;
    minViralRatio?: number | null;
    regionCode?: string;
    maxResults?: number;
  }): Promise<VideoItem[]> {
    const queryParams = new URLSearchParams();
    queryParams.set('q', params.query);
    if (params.maxSubscribers) queryParams.set('max_subscribers', String(params.maxSubscribers));
    if (params.minViews) queryParams.set('min_views', String(params.minViews));
    if (params.minViralRatio) queryParams.set('min_viral_ratio', String(params.minViralRatio));
    if (params.regionCode) queryParams.set('region_code', params.regionCode);
    if (params.maxResults) queryParams.set('max_results', String(params.maxResults));

    const res = await fetch(`${API_BASE}/shorts/outliers?${queryParams.toString()}`);
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Failed to search Shorts outliers');
    }
    return res.json();
  },

  async getTrending(params: {
    regionCode?: string;
    categoryId?: string | null;
    shortsOnly?: boolean;
    maxResults?: number;
  }): Promise<VideoItem[]> {
    const queryParams = new URLSearchParams();
    if (params.regionCode) queryParams.set('region_code', params.regionCode);
    if (params.categoryId) queryParams.set('category_id', params.categoryId);
    queryParams.set('shorts_only', String(params.shortsOnly ?? true));
    if (params.maxResults) queryParams.set('max_results', String(params.maxResults));

    const res = await fetch(`${API_BASE}/trending?${queryParams.toString()}`);
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Failed to retrieve trending videos');
    }
    return res.json();
  },

  async searchVideos(req: SearchRequest): Promise<VideoItem[]> {
    const res = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Search request failed');
    }
    return res.json();
  },

  async getVideoBlueprint(videoId: string, niche?: string): Promise<VideoBlueprint> {
    const query = niche ? `?niche=${encodeURIComponent(niche)}` : '';
    const res = await fetch(`${API_BASE}/blueprint/${videoId}${query}`);
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Failed to extract video blueprint');
    }
    return res.json();
  },
};

export interface VideoItem {
  video_id: string;
  title: string;
  channel_id?: string;
  channel_title?: string;
  thumbnail_url?: string;
  views?: number;
  likes?: number;
  comments_count?: number;
  subscribers?: number;
  duration_seconds?: number;
  published_at?: string;
  video_url?: string;
  is_short: boolean;
  viral_ratio: number;
  description?: string;
  tags?: string[];
}

export interface SearchRequest {
  query: string;
  is_shorts_only?: boolean;
  min_views?: number | null;
  max_views?: number | null;
  max_subscribers?: number | null;
  min_viral_ratio?: number | null;
  max_results?: number;
  order?: string;
  published_after_days?: number | null;
  region_code?: string;
}

export interface TrendingRequest {
  region_code?: string;
  category_id?: string | null;
  shorts_only?: boolean;
  max_results?: number;
}

export interface TranscriptLine {
  text: string;
  start: number;
  duration: number;
}

export interface VideoBlueprint {
  video_id: string;
  title: string;
  channel_title: string;
  views: number;
  subscribers: number;
  viral_ratio: number;
  video_url: string;
  duration_seconds: number;
  is_short: boolean;
  hook_text: string;
  hook_duration: number;
  full_transcript: string;
  transcript_segments: TranscriptLine[];
  key_takeaways: string[];
  suggested_prompt: string;
}

export interface IdeaItem {
  id?: number;
  video_id: string;
  title: string;
  channel_title: string;
  thumbnail_url: string;
  views: number;
  subscribers: number;
  viral_ratio: number;
  duration_seconds: number;
  video_url: string;
  status: 'backlog' | 'in_progress' | 'done';
  hook_text?: string;
  script_notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface DashboardStats {
  cached_videos_count: number;
  max_viral_ratio: number;
  avg_viral_ratio?: number;
  total_queries_saved: number;
  estimated_hook_score?: number;
  ideas_total: number;
  ideas_backlog: number;
  ideas_in_progress: number;
  ideas_done: number;
  top_outliers?: VideoItem[];
  recent_ideas?: IdeaItem[];
}

export type ActiveTab = 'dashboard' | 'shorts' | 'trending' | 'ideas' | 'search' | 'mcp';

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  youtube_api_configured: boolean;
}

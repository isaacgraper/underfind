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

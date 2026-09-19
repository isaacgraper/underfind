import { VideoItem } from './video';
import { IdeaItem } from './idea';

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

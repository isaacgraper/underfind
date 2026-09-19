export interface IdeaItem {
  id?: number;
  video_id: string;
  title: string;
  channel_title: string;
  thumbnail_url?: string;
  views?: number;
  subscribers?: number;
  viral_ratio: number;
  duration_seconds?: number;
  video_url?: string;
  status: 'backlog' | 'in_progress' | 'done';
  hook_text?: string;
  script_notes?: string;
  created_at?: string;
  updated_at?: string;
}

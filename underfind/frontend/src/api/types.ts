export type JobStatus =
  | 'found'
  | 'downloaded'
  | 'transcribed'
  | 'translated'
  | 'voiced'
  | 'rendered'
  | 'exported'
  | 'failed'
  | 'discarded';

export const STAGES: JobStatus[] = ['found', 'downloaded', 'transcribed', 'translated', 'voiced', 'rendered', 'exported'];

export type Platform = 'youtube' | 'instagram' | 'tiktok' | 'local';
export type OutputKind = 'reel' | 'post' | 'carousel';
export type Mode = 'subtitles' | 'dub';

export interface Source {
  platform: Platform;
  source_id: string;
  url: string;
  title?: string | null;
  caption?: string | null;
  author_handle?: string | null;
  author_name?: string | null;
  thumbnail_url?: string | null;
  views?: number | null;
  likes?: number | null;
  comments_count?: number | null;
  followers?: number | null;
  duration_seconds?: number | null;
  published_at?: string | null;
  media_type?: 'video' | 'image' | 'carousel' | null;
}

export interface Job {
  id: string;
  source_key: string;
  page_id: number | null;
  status: JobStatus;
  failed_from: JobStatus | null;
  error: string | null;
  mode: Mode;
  artifacts: Record<string, string>;
  attempts: number;
  translation_approved: boolean;
  render_approved: boolean;
  local_only: boolean | null;
  created_at: string | null;
  updated_at: string | null;
  source: Source | null;
}

export interface JobEvent {
  job_id: string;
  from_status: JobStatus | null;
  to_status: JobStatus;
  note: string | null;
  created_at: string;
}

export interface PageProfile {
  id?: number | null;
  display_name: string;
  handle: string;
  avatar_path?: string | null;
  language: string;
  template_id?: number | null;
  default_hashtags: string[];
  caption_footer?: string | null;
  tts_voice?: string | null;
  auto_approve_translation: boolean;
  auto_approve_render: boolean;
  local_only: boolean;
  niche?: string | null;
  brand_tag?: string | null;
  glossary: string[];
  outputs: OutputKind[];
  audio_bed_path?: string | null;
  active: boolean;
}

export interface RenderTemplate {
  id: number;
  name: string;
}

export interface TranslatedSegment {
  index: number;
  start: number;
  end: number;
  source_text: string;
  text: string;
  max_chars: number;
}

export interface Translation {
  local: boolean;
  source_language?: string | null;
  target_language: string;
  page_id: number;
  mode: Mode;
  model?: string | null;
  segments: TranslatedSegment[];
  headline: string;
  headline_source: string;
  caption: string;
  hashtags: string[];
  approved: boolean;
  edited: boolean;
}

export interface UpdateTranslation {
  segments?: { index: number; text: string }[];
  headline?: string;
  caption?: string;
  hashtags?: string[];
  approve?: boolean;
}

export type CandidateStatus = 'new' | 'queued' | 'rejected' | 'skipped';

export interface Candidate {
  id: number;
  source_key: string;
  niche: string;
  scanner: string;
  score: number;
  scores: Record<string, number>;
  status: CandidateStatus;
  reason?: string | null;
  job_ids: string[];
  discovered_at?: string | null;
  source: Source | null;
}

export interface ScanReport {
  id?: number;
  niche: string;
  started_at: string;
  finished_at?: string | null;
  found: number;
  new: number;
  rejected: number;
  skipped: number;
  queued: number;
  dry_run: boolean;
  errors: Record<string, string>;
}

export interface Niche {
  name: string;
  description: string;
  seed_pages: Record<string, string[]>;
  regions: string[];
  hashtags: string[];
  scan: { every_minutes: number };
}

export interface Summary {
  ai_mode: 'local' | 'online';
  worker_running: boolean;
  inbox_new: number;
  needs_you: number;
  working: number;
  failed: number;
  done: number;
}

export interface ExportManifest {
  job_id: string;
  exported_at: string;
  folder: string;
  page: Record<string, string>;
  language: string;
  deliverables: { kind: string; files: string[] }[];
  caption: string;
  caption_body: string;
  hashtags: string[];
  headline: string;
  local_ai: boolean;
  source: Record<string, string | null>;
}

export interface QuotaStatus {
  provider: string;
  day: string;
  used: number;
  limit: number;
  remaining: number;
  exhausted: boolean;
}

export interface VideoItem {
  video_id: string;
  title: string;
  channel_title?: string | null;
  thumbnail_url?: string | null;
  views?: number | null;
  likes?: number | null;
  comments_count?: number | null;
  subscribers?: number | null;
  duration_seconds?: number | null;
  published_at?: string | null;
  video_url?: string | null;
  is_short: boolean;
  viral_ratio: number;
  description?: string | null;
  tags?: string[];
}

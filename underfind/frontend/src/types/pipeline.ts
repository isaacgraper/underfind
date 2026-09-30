export type LocalizationMode = 'subtitles' | 'dub';

export interface PageProfile {
  id: number;
  display_name: string;
  handle: string;
  language: string;
  local_only: boolean;
  auto_approve_translation: boolean;
  active: boolean;
}

export interface Job {
  id: string;
  source_key: string;
  page_id: number | null;
  status: string;
  mode: LocalizationMode;
  local_only: boolean | null;
  error?: string | null;
}

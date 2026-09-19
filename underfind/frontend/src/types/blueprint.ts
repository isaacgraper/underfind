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

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  youtube_api_configured: boolean;
  ai_mode?: 'local' | 'online';
}

export interface ApiErrorResponse {
  detail: string;
}

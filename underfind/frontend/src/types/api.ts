export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  youtube_api_configured: boolean;
}

export interface ApiErrorResponse {
  detail: string;
}

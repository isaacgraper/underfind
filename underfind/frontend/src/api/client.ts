import type {
  Candidate,
  CandidateStatus,
  ExportManifest,
  Job,
  JobEvent,
  JobStatus,
  Mode,
  Niche,
  PageProfile,
  QuotaStatus,
  RenderTemplate,
  ScanReport,
  Summary,
  Translation,
  UpdateTranslation,
  VideoItem,
} from './types';

const BASE = '/api';

/** An API failure with the server's own explanation, ready to show to the user. */
export class ApiError extends Error {
  status: number;
  body: Record<string, unknown>;

  constructor(status: number, message: string, body: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function detailOf(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d))).join('; ');
  }

  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;

  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, 'Não foi possível falar com o servidor do Underfind. Ele está rodando?');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, detailOf(body, `Erro ${res.status}`), (body as Record<string, unknown>) ?? {});
  }

  return (res.status === 204 ? undefined : await res.json()) as T;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const qs = (params: Record<string, string | number | boolean | null | undefined>): string => {
  const search = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  });

  const text = search.toString();
  return text ? `?${text}` : '';
};

export const api = {
  summary: () => request<Summary>('/summary'),
  quota: () => request<QuotaStatus[]>('/quota'),

  niches: () => request<Niche[]>('/niches'),
  pages: () => request<PageProfile[]>('/pages'),
  savePage: (page: PageProfile) =>
    page.id ? request<PageProfile>(`/pages/${page.id}`, json('PUT', page)) : request<PageProfile>('/pages', json('POST', page)),
  deletePage: (id: number) => request<{ status: string }>(`/pages/${id}`, json('DELETE')),
  templates: () => request<RenderTemplate[]>('/templates'),

  candidates: (niche: string | null, status: CandidateStatus) =>
    request<Candidate[]>(`/candidates${qs({ niche, status, limit: 200 })}`),
  scan: (niche: string) => request<ScanReport>(`/scan/${encodeURIComponent(niche)}`, json('POST')),
  scans: (niche: string | null) => request<ScanReport[]>(`/scans${qs({ niche, limit: 5 })}`),
  queueCandidate: (id: number, pageIds: number[] | null, mode: Mode = 'subtitles') =>
    request<Candidate>(`/candidates/${id}/queue`, json('POST', { page_ids: pageIds, mode })),
  rejectCandidate: (id: number, reason?: string) => request<Candidate>(`/candidates/${id}/reject`, json('POST', { reason })),

  jobs: () => request<Job[]>('/jobs?limit=500'),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  jobEvents: (id: string) => request<JobEvent[]>(`/jobs/${id}/events`),
  createJob: (url: string, pageId: number, mode: Mode = 'subtitles') =>
    request<Job>('/jobs', json('POST', { url, page_id: pageId, mode })),
  createJobFromVideo: (video: VideoItem, pageId: number, mode: Mode = 'subtitles') =>
    request<Job>(`/jobs/from-video${qs({ page_id: pageId, mode })}`, json('POST', video)),
  runJob: (id: string) => request<{ status: string }>(`/jobs/${id}/run`, json('POST')),
  setJobStatus: (id: string, status: JobStatus, note?: string) =>
    request<Job>(`/jobs/${id}/status`, json('PATCH', { status, note })),
  translation: (id: string) => request<Translation>(`/jobs/${id}/translation`),
  updateTranslation: (id: string, edit: UpdateTranslation) => request<Translation>(`/jobs/${id}/translation`, json('PUT', edit)),
  approveRender: (id: string) => request<Job>(`/jobs/${id}/render/approve`, json('POST')),
  fileUrl: (id: string, name: string) => `${BASE}/jobs/${id}/files/${name}`,

  exports: () => request<ExportManifest[]>('/exports?limit=100'),

  search: (query: string, region: string, shortsOnly: boolean) =>
    request<VideoItem[]>('/search', json('POST', { query, region_code: region, is_shorts_only: shortsOnly, max_results: 25, order: 'viewCount' })),
  trending: (region: string) => request<VideoItem[]>(`/trending${qs({ region_code: region, shorts_only: true, max_results: 25 })}`),
};

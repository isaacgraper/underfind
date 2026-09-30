import { useMemo, useRef } from 'react';
import { api } from '../api/client';
import type { Job, PageProfile, Summary } from '../api/types';
import { usePolling } from '../app/usePolling';
import { useToast } from '../app/toast';
import { Badge, Button, EmptyState, Skeleton, StageTrack, timeAgo } from '../ui';
import './views.css';

type Lane = 'needs' | 'working' | 'failed' | 'done';

function laneOf(j: Job): Lane | null {
  if (j.status === 'discarded') return null;
  if (j.status === 'failed') return 'failed';
  if (j.status === 'exported') return 'done';
  if ((j.status === 'translated' && !j.translation_approved) || (j.status === 'rendered' && !j.render_approved)) return 'needs';
  return 'working';
}

const LANES: { key: Lane; title: string }[] = [
  { key: 'needs', title: 'Precisa de você' },
  { key: 'working', title: 'Em andamento' },
  { key: 'failed', title: 'Falhou' },
  { key: 'done', title: 'Pronto' },
];

const STATUS_LABEL: Record<string, string> = {
  found: 'Na fila', downloaded: 'Baixado', transcribed: 'Transcrito', translated: 'Traduzido', voiced: 'Legendado', rendered: 'Renderizado', exported: 'Exportado', failed: 'Falhou',
};

export function Pipeline({ summary, onChanged }: { summary: Summary | null; onChanged: () => void }) {
  const toast = useToast();
  const jobs = usePolling(api.jobs);
  const pages = usePolling(api.pages, [], true);
  const seen = useRef<Set<string>>(new Set());

  const pageName = useMemo(() => new Map((pages.data ?? []).map((p: PageProfile) => [p.id, p.display_name])), [pages.data]);
  const grouped = useMemo(() => {
    const g: Record<Lane, Job[]> = { needs: [], working: [], failed: [], done: [] };
    (jobs.data ?? []).forEach((j) => { const l = laneOf(j); if (l) g[l].push(j); });
    g.done = g.done.slice(0, 20);
    return g;
  }, [jobs.data]);

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    try { await fn(); if (ok) toast.show(ok); await jobs.refresh(); onChanged(); }
    catch (e) { toast.show((e as Error).message, { tone: 'error' }); }
  };

  const retry = (j: Job) => act(async () => {
    if (j.failed_from) await api.setJobStatus(j.id, j.failed_from, 'Tentar de novo');
    await api.runJob(j.id);
  }, 'Tentando de novo');

  const discard = (j: Job) => {
    void act(() => api.setJobStatus(j.id, 'discarded', 'Descartado'));
    toast.show('Post descartado', { actionLabel: 'Desfazer', onAction: () => void act(() => api.setJobStatus(j.id, 'found', 'Desfeito')) });
  };

  if (jobs.loading && !jobs.data) return <><div className="view-head"><h1>Pipeline</h1></div><Skeleton /></>;

  const empty = LANES.every((l) => grouped[l.key].length === 0);

  return (
    <>
      <div className="view-head">
        <h1>Pipeline</h1>
        {summary && !summary.worker_running && <Badge tone="queued">Worker parado</Badge>}
      </div>
      {empty ? (
        <EmptyState title="Nada no pipeline" action={<Button variant="primary" onClick={() => { window.location.hash = '#/inbox'; }}>Ir para o Inbox</Button>}>
          Modele candidatos do Inbox e eles aparecem aqui.
        </EmptyState>
      ) : (
        <div className="lanes">
          {LANES.map((lane) => (
            <section key={lane.key} className="lane" data-lane={lane.key} aria-labelledby={`lane-${lane.key}`}>
              <h2 id={`lane-${lane.key}`} className="lane__title">{lane.title} <span className="num muted">{grouped[lane.key].length}</span></h2>
              <ul className="lane__list">
                {grouped[lane.key].map((j) => {
                  const fresh = lane.key === 'needs' && !seen.current.has(j.id);
                  seen.current.add(j.id);
                  const preview = j.artifacts.post ? 'post' : j.artifacts.frame ? 'frame' : null;
                  return (
                    <li key={j.id} className="jobcard" data-fresh={fresh || undefined}>
                      {preview && <img className="jobcard__img" src={api.fileUrl(j.id, preview)} alt="" loading="lazy" />}
                      <div className="jobcard__body">
                        <p className="jobcard__title">{j.source?.title || j.source_key}</p>
                        <p className="muted jobcard__meta">{pageName.get(j.page_id ?? -1) ?? 'Sem página'} · {timeAgo(j.updated_at)}</p>
                        <StageTrack status={j.status} failedFrom={j.failed_from} />
                        <p className="jobcard__status">
                          {lane.key === 'failed' ? <span className="error-text">{j.error || 'Falhou'}</span> : <span className="muted">{STATUS_LABEL[j.status]}</span>}
                        </p>
                        <div className="jobcard__actions">
                          {lane.key === 'needs' && <Button variant="primary" onClick={() => { window.location.hash = `#/review/${j.id}`; }}>{j.status === 'translated' ? 'Revisar tradução' : 'Revisar resultado'}</Button>}
                          {lane.key === 'failed' && <Button onClick={() => retry(j)}>Tentar de novo</Button>}
                          {lane.key === 'working' && summary && !summary.worker_running && <Button onClick={() => act(() => api.runJob(j.id))}>Executar</Button>}
                          {lane.key !== 'done' && <Button variant="ghost" onClick={() => discard(j)}>Descartar</Button>}
                          {lane.key === 'done' && <Button variant="ghost" onClick={() => { window.location.hash = '#/exports'; }}>Ver exportado</Button>}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

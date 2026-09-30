import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { Candidate, CandidateStatus, Mode, Niche, PageProfile, ScanReport } from '../api/types';
import { usePolling } from '../app/usePolling';
import { useToast } from '../app/toast';
import { Badge, Button, EmptyState, Field, Segmented, Skeleton, compact, timeAgo } from '../ui';
import './views.css';

const FILTERS: { value: CandidateStatus; label: string }[] = [
  { value: 'new', label: 'Novos' },
  { value: 'queued', label: 'Modelados' },
  { value: 'rejected', label: 'Descartados' },
];

export function Inbox({ onChanged }: { onChanged: () => void }) {
  const toast = useToast();
  const [niches, setNiches] = useState<Niche[]>([]);
  const [niche, setNiche] = useState<string | null>(null);
  const [status, setStatus] = useState<CandidateStatus>('new');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [cursor, setCursor] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [pages, setPages] = useState<PageProfile[]>([]);
  const [link, setLink] = useState('');
  const [linkPage, setLinkPage] = useState('');
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    void api.niches().then((n) => { setNiches(n); setNiche((cur) => cur ?? n[0]?.name ?? null); }).catch(() => undefined);
    void api.pages().then((p) => { setPages(p); setLinkPage(String(p[0]?.id ?? '')); }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (niche) void api.scans(niche).then((r) => setReport(r[0] ?? null)).catch(() => undefined);
  }, [niche]);

  const list = usePolling(() => api.candidates(niche, status), [niche, status]);
  const rows = list.data ?? [];
  const nichePages = useMemo(() => pages.filter((p) => !niche || !p.niche || p.niche === niche), [pages, niche]);

  const refreshAll = useCallback(async () => {
    await list.refresh();
    onChanged();
  }, [list, onChanged]);

  const targets = useCallback((c?: Candidate) => (c && selected.size === 0 ? [c] : rows.filter((r) => selected.has(r.id))), [rows, selected]);

  const model = useCallback(async (c?: Candidate) => {
    const items = targets(c);
    if (!items.length) return;
    if (nichePages.length === 0) { toast.show('Crie uma página para este nicho antes de modelar.', { tone: 'error' }); return; }
    try {
      for (const item of items) await api.queueCandidate(item.id, null, 'subtitles' as Mode);
      toast.show(items.length === 1 ? 'Enviado para o Pipeline' : `${items.length} enviados para o Pipeline`);
      setSelected(new Set());
      await refreshAll();
    } catch (e) { toast.show((e as Error).message, { tone: 'error' }); }
  }, [nichePages.length, refreshAll, targets, toast]);

  const reject = useCallback(async (c?: Candidate) => {
    const items = targets(c);
    if (!items.length) return;
    try {
      for (const item of items) await api.rejectCandidate(item.id);
      toast.show(items.length === 1 ? 'Candidato descartado' : `${items.length} descartados`);
      setSelected(new Set());
      await refreshAll();
    } catch (e) { toast.show((e as Error).message, { tone: 'error' }); }
  }, [refreshAll, targets, toast]);

  const scan = async () => {
    if (!niche) return;
    setScanning(true);
    try {
      const r = await api.scan(niche);
      setReport(r);
      toast.show(`${r.new} novos candidatos`);
      await refreshAll();
    } catch (e) { toast.show((e as Error).message, { tone: 'error' }); }
    finally { setScanning(false); }
  };

  const addLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!link.trim() || !linkPage) return;
    setAdding(true);
    try {
      await api.createJob(link.trim(), Number(linkPage));
      setLink('');
      toast.show('Link enviado para o Pipeline');
      onChanged();
    } catch (err) { toast.show((err as Error).message, { tone: 'error' }); }
    finally { setAdding(false); }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest('input, textarea, select, dialog') || e.metaKey || e.ctrlKey || e.altKey) return;
      const current = rows[cursor];
      if (e.key === 'j') setCursor((c) => Math.min(c + 1, rows.length - 1));
      else if (e.key === 'k') setCursor((c) => Math.max(c - 1, 0));
      else if (e.key === 'x' && current) setSelected((s) => { const n = new Set(s); n.has(current.id) ? n.delete(current.id) : n.add(current.id); return n; });
      else if (e.key === 'm' && status === 'new') void model(current);
      else if (e.key === 'd' && status === 'new') void reject(current);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [rows, cursor, model, reject, status]);

  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const errors = report ? Object.entries(report.errors) : [];

  return (
    <>
      <div className="view-head">
        <h1>Inbox</h1>
        {niches.length > 1 && (
          <Field label="Nicho"><select value={niche ?? ''} onChange={(e) => setNiche(e.target.value)}>{niches.map((n) => <option key={n.name} value={n.name}>{n.name}</option>)}</select></Field>
        )}
        <Segmented label="Status" value={status} options={FILTERS} onChange={(s) => { setStatus(s); setSelected(new Set()); setCursor(0); }} />
        <Button icon={<RefreshCw />} onClick={scan} disabled={scanning || !niche}>{scanning ? 'Buscando…' : 'Buscar agora'}</Button>
      </div>

      {report && (
        <p className="muted scan-line">
          Última busca há {timeAgo(report.started_at)}: {report.found} encontrados, {report.new} novos.
          {errors.map(([k, v]) => <span key={k} className="error-text"> {k}: {v}</span>)}
        </p>
      )}

      <form className="inline-form" onSubmit={addLink}>
        <Field label="Colar link"><input type="url" placeholder="https://www.instagram.com/reel/…" value={link} onChange={(e) => setLink(e.target.value)} /></Field>
        <Field label="Página"><select value={linkPage} onChange={(e) => setLinkPage(e.target.value)}>{pages.map((p) => <option key={p.id} value={p.id ?? ''}>{p.display_name}</option>)}</select></Field>
        <Button type="submit" disabled={adding || !link.trim() || !linkPage}>Modelar link</Button>
      </form>

      {status === 'new' && selected.size > 0 && (
        <div className="bulkbar" role="toolbar" aria-label="Ações em lote">
          <span className="num">{selected.size} selecionados</span>
          <Button variant="primary" onClick={() => model()}>Modelar</Button>
          <Button variant="ghost" onClick={() => reject()}>Descartar</Button>
        </div>
      )}

      {list.loading && !list.data ? <Skeleton /> : rows.length === 0 ? (
        <EmptyState title={status === 'new' ? 'Nenhum candidato novo' : 'Nada por aqui'} action={status === 'new' ? <Button onClick={scan} disabled={scanning || !niche}>Buscar agora</Button> : undefined}>
          {status === 'new' ? 'Busque posts virais do nicho ou cole um link acima.' : 'Os candidatos aparecem aqui conforme você decide.'}
        </EmptyState>
      ) : (
        <table className="table">
          <thead><tr><th scope="col"><span className="sr-only">Selecionar</span></th><th scope="col">Post</th><th scope="col" className="num-col">Score</th><th scope="col" className="num-col">Views</th><th scope="col">Origem</th>{status === 'new' && <th scope="col"><span className="sr-only">Ações</span></th>}</tr></thead>
          <tbody>
            {rows.map((c, i) => (
              <tr key={c.id} data-cursor={i === cursor || undefined} data-selected={selected.has(c.id) || undefined} onClick={() => setCursor(i)}>
                <td><input type="checkbox" aria-label={`Selecionar ${c.source?.title ?? c.source_key}`} checked={selected.has(c.id)} onChange={() => toggle(c.id)} /></td>
                <td className="cell-title">
                  {c.source?.thumbnail_url && <img className="thumb" src={c.source.thumbnail_url} alt="" loading="lazy" />}
                  <span><a href={c.source?.url} target="_blank" rel="noreferrer">{c.source?.title || c.source_key}</a><span className="muted sub">{c.source?.author_name || c.source?.author_handle}</span></span>
                </td>
                <td className="num-col num">{Math.round(c.score)}</td>
                <td className="num-col num">{compact(c.source?.views)}</td>
                <td><Badge tone="neutral">{c.scanner}</Badge></td>
                {status === 'new' && <td className="row-actions"><Button variant="primary" onClick={() => model(c)}>Modelar</Button><Button variant="ghost" onClick={() => reject(c)}>Descartar</Button></td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {status === 'new' && rows.length > 0 && <p className="muted keys"><kbd>j</kbd> <kbd>k</kbd> navegar · <kbd>x</kbd> selecionar · <kbd>m</kbd> modelar · <kbd>d</kbd> descartar</p>}
    </>
  );
}

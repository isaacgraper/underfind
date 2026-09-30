import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { PageProfile, VideoItem } from '../api/types';
import { useToast } from '../app/toast';
import { Button, EmptyState, Field, Segmented, Skeleton, compact } from '../ui';
import './views.css';

export function Discover({ onChanged }: { onChanged: () => void }) {
  const toast = useToast();
  const [mode, setMode] = useState<'search' | 'trending'>('search');
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('BR');
  const [items, setItems] = useState<VideoItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [pages, setPages] = useState<PageProfile[]>([]);
  const [pageId, setPageId] = useState('');

  useEffect(() => { void api.pages().then((p) => { setPages(p); setPageId(String(p[0]?.id ?? '')); }).catch(() => undefined); }, []);

  const run = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setLoading(true);
    try { setItems(mode === 'search' ? await api.search(query, region, true) : await api.trending(region)); }
    catch (err) { toast.show((err as Error).message, { tone: 'error' }); setItems([]); }
    finally { setLoading(false); }
  };

  const model = async (v: VideoItem) => {
    if (!pageId) { toast.show('Crie uma página antes de modelar.', { tone: 'error' }); return; }
    try { await api.createJobFromVideo(v, Number(pageId)); toast.show('Enviado para o Pipeline'); onChanged(); }
    catch (err) { toast.show((err as Error).message, { tone: 'error' }); }
  };

  return (
    <>
      <div className="view-head"><h1>Descobrir</h1></div>
      <form className="inline-form" onSubmit={run}>
        <Segmented label="Fonte" value={mode} options={[{ value: 'search', label: 'Busca' }, { value: 'trending', label: 'Em alta' }]} onChange={setMode} />
        {mode === 'search' && <Field label="Busca"><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="gta 6 trailer" /></Field>}
        <Field label="Região"><input type="text" value={region} maxLength={2} onChange={(e) => setRegion(e.target.value.toUpperCase())} /></Field>
        <Field label="Página de destino"><select value={pageId} onChange={(e) => setPageId(e.target.value)}>{pages.map((p) => <option key={p.id} value={p.id ?? ''}>{p.display_name}</option>)}</select></Field>
        <Button type="submit" variant="primary" disabled={loading || (mode === 'search' && !query.trim())}>{loading ? 'Buscando…' : 'Buscar'}</Button>
      </form>
      {loading ? <Skeleton /> : items === null ? null : items.length === 0 ? <EmptyState title="Sem resultados" /> : (
        <table className="table">
          <thead><tr><th scope="col">Vídeo</th><th scope="col" className="num-col">Views</th><th scope="col" className="num-col">Viral</th><th scope="col"><span className="sr-only">Ações</span></th></tr></thead>
          <tbody>{items.map((v) => (
            <tr key={v.video_id}>
              <td className="cell-title">{v.thumbnail_url && <img className="thumb" src={v.thumbnail_url} alt="" loading="lazy" />}<span><a href={v.video_url ?? '#'} target="_blank" rel="noreferrer">{v.title}</a><span className="muted sub">{v.channel_title}</span></span></td>
              <td className="num-col num">{compact(v.views)}</td>
              <td className="num-col num">{v.viral_ratio.toFixed(1)}x</td>
              <td className="row-actions"><Button variant="primary" onClick={() => model(v)}>Modelar</Button></td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

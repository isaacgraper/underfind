import { Fragment, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { Job, PageProfile, Translation } from '../api/types';
import { usePolling } from '../app/usePolling';
import { useToast } from '../app/toast';
import { go } from '../app/router';
import { Button, EmptyState, Field, Skeleton } from '../ui';
import './views.css';

/** `*word*` marks a gradient highlight, matching how the renderer draws the headline card. */
function Highlighted({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*[^*]+\*)/g).map((part, i) =>
        part.startsWith('*') && part.endsWith('*') && part.length > 2 ? <span key={i} className="hl">{part.slice(1, -1)}</span> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

const needsYou = (j: Job) => (j.status === 'translated' && !j.translation_approved) || (j.status === 'rendered' && !j.render_approved);

export function Review({ id, onChanged }: { id: string; onChanged: () => void }) {
  const toast = useToast();
  const job = usePolling(() => api.job(id), [id]);
  const queue = usePolling(api.jobs, [], true);
  const [pages, setPages] = useState<PageProfile[]>([]);
  const [tr, setTr] = useState<Translation | null>(null);
  const [headline, setHeadline] = useState('');
  const [caption, setCaption] = useState('');
  const [hashtags, setHashtags] = useState('');
  const [segments, setSegments] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [approved, setApproved] = useState(false);

  const j = job.data;
  const status = j?.status;
  const translating = status === 'translated' && !j?.translation_approved;

  useEffect(() => { void api.pages().then(setPages).catch(() => undefined); }, []);

  useEffect(() => {
    if (!j || !j.artifacts.translation || tr) return;
    void api.translation(id).then((t) => {
      setTr(t);
      setHeadline(t.headline);
      setCaption(t.caption);
      setHashtags(t.hashtags.join(' '));
      setSegments(Object.fromEntries(t.segments.map((s) => [s.index, s.text])));
    }).catch(() => undefined);
  }, [j, id, tr]);

  const page = pages.find((p) => p.id === j?.page_id);
  const order = useMemo(() => (queue.data ?? []).filter(needsYou).map((x) => x.id), [queue.data]);
  const at = order.indexOf(id);
  const next = order[at + 1] ?? order.find((x) => x !== id);

  const after = () => { onChanged(); go(next ? `/review/${next}` : '/pipeline'); };

  const edit = () => ({
    headline,
    caption,
    hashtags: hashtags.split(/\s+/).filter(Boolean).map((h) => (h.startsWith('#') ? h : `#${h}`)),
    segments: Object.entries(segments).map(([index, text]) => ({ index: Number(index), text })),
  });

  const approveTranslation = async () => {
    setBusy(true);
    try {
      await api.updateTranslation(id, { ...edit(), approve: true });
      await api.runJob(id).catch(() => undefined);
      toast.show('Tradução aprovada. Renderizando.');
      after();
    } catch (e) { toast.show((e as Error).message, { tone: 'error' }); setBusy(false); }
  };

  const saveOnly = async () => {
    try { setTr(await api.updateTranslation(id, edit())); toast.show('Edição salva'); }
    catch (e) { toast.show((e as Error).message, { tone: 'error' }); }
  };

  const approveRender = async () => {
    setBusy(true);
    try {
      await api.approveRender(id);
      await api.runJob(id).catch(() => undefined);
      setApproved(true);
      toast.show('Aprovado. Exportando.');
      window.setTimeout(after, 600);
    } catch (e) { toast.show((e as Error).message, { tone: 'error' }); setBusy(false); }
  };

  const redo = async () => {
    setBusy(true);
    try {
      await api.setJobStatus(id, 'voiced', 'Refazer renderização');
      await api.runJob(id).catch(() => undefined);
      toast.show('Renderizando de novo');
      after();
    } catch (e) { toast.show((e as Error).message, { tone: 'error' }); setBusy(false); }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !busy) {
        e.preventDefault();
        if (translating) void approveTranslation();
        else if (status === 'rendered' && !j?.render_approved) void approveRender();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (job.loading && !j) return <Skeleton />;
  if (!j) return <EmptyState title="Post não encontrado" action={<Button onClick={() => go('/pipeline')}>Voltar ao Pipeline</Button>}>{job.error}</EmptyState>;

  const source = j.artifacts.source_video ? (
    <video className="media" src={api.fileUrl(id, 'source_video')} controls muted playsInline preload="metadata" aria-label="Original" />
  ) : j.artifacts.frame ? <img className="media" src={api.fileUrl(id, 'frame')} alt="Original" /> : <div className="media media--empty">Sem prévia</div>;

  const slides = Object.keys(j.artifacts).filter((k) => /^carousel_\d+$/.test(k)).sort();

  return (
    <>
      <div className="view-head">
        <h1>{translating ? 'Revisar tradução' : 'Revisar resultado'}</h1>
        <span className="muted">{j.source?.title}</span>
        <Button variant="ghost" onClick={() => go('/pipeline')}>Voltar</Button>
      </div>

      <div className="review">
        <section className="review__col" aria-label="Original">
          <h2 className="col-title">Original</h2>
          {source}
          {tr && <p className="muted quote">{tr.headline_source}</p>}
          {j.source?.url && <a href={j.source.url} target="_blank" rel="noreferrer" className="muted">{j.source.author_handle || j.source.url}</a>}
        </section>

        <section className="review__col" aria-label="Modelado">
          <h2 className="col-title">Modelado {page && <span className="muted">· {page.display_name}</span>}</h2>

          {translating && tr && (
            <>
              <div className="cardprev" aria-hidden="true">
                <p className="cardprev__brand">{page?.brand_tag || page?.display_name}</p>
                <p className="cardprev__headline"><Highlighted text={headline} /></p>
              </div>
              <Field label="Manchete" hint="Envolva palavras com *asteriscos* para destacar em degradê.">
                <textarea className="headline-input" rows={3} value={headline} onChange={(e) => setHeadline(e.target.value)} />
              </Field>
              <Field label="Legenda"><textarea rows={4} value={caption} onChange={(e) => setCaption(e.target.value)} /></Field>
              <Field label="Hashtags"><input type="text" value={hashtags} onChange={(e) => setHashtags(e.target.value)} /></Field>
              {tr.segments.length > 0 && (
                <details className="segs">
                  <summary>Trechos da fala ({tr.segments.length})</summary>
                  {tr.segments.map((s) => (
                    <div key={s.index} className="seg">
                      <p className="muted seg__src">{s.source_text}</p>
                      <input type="text" aria-label={`Trecho ${s.index + 1}`} value={segments[s.index] ?? ''} maxLength={s.max_chars + 20} onChange={(e) => setSegments((cur) => ({ ...cur, [s.index]: e.target.value }))} />
                    </div>
                  ))}
                </details>
              )}
              <div className="actions">
                <Button variant="ghost" onClick={saveOnly}>Salvar edição</Button>
                <Button variant="primary" className="approve" disabled={busy} onClick={approveTranslation}>Aprovar tradução</Button>
              </div>
            </>
          )}

          {translating && !tr && <Skeleton rows={3} />}

          {status === 'rendered' && (
            <>
              {j.artifacts.reel && <video className="media media--reel" src={api.fileUrl(id, 'reel')} controls playsInline preload="metadata" aria-label="Reel renderizado" />}
              {j.artifacts.post && <img className="media" src={api.fileUrl(id, 'post')} alt="Post renderizado" />}
              {slides.length > 0 && <div className="slides">{slides.map((k) => <img key={k} className="media" src={api.fileUrl(id, k)} alt={`Slide ${k.slice(-2)}`} />)}</div>}
              {tr && <p className="caption-preview">{tr.caption}</p>}
              <div className="actions">
                <Button variant="ghost" disabled={busy} onClick={redo}>Refazer</Button>
                <Button variant="primary" className="approve" disabled={busy || j.render_approved} data-state={approved ? 'done' : undefined} onClick={approveRender}>
                  <span className="approve__label" data-state={approved ? 'done' : 'idle'}>{approved ? 'Aprovado' : 'Aprovar e exportar'}</span>
                </Button>
              </div>
            </>
          )}

          {!translating && status !== 'rendered' && (
            <EmptyState title="Nada para revisar agora">Este post está em “{status}”. {next && <a href={`#/review/${next}`}>Ir para o próximo</a>}</EmptyState>
          )}
        </section>
      </div>

      {order.length > 1 && (
        <p className="muted keys">{at + 1 > 0 ? `${at + 1} de ${order.length}` : `${order.length} esperando`} · <kbd>Ctrl</kbd> + <kbd>Enter</kbd> aprova</p>
      )}
    </>
  );
}

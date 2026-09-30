import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ExportManifest } from '../api/types';
import { useToast } from '../app/toast';
import { Button, EmptyState, Skeleton, timeAgo } from '../ui';
import './views.css';

export function Exports() {
  const toast = useToast();
  const [items, setItems] = useState<ExportManifest[] | null>(null);

  useEffect(() => { void api.exports().then(setItems).catch((e) => { setItems([]); toast.show((e as Error).message, { tone: 'error' }); }); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const copy = async (text: string, what: string) => {
    try { await navigator.clipboard.writeText(text); toast.show(`${what} copiado`); }
    catch { toast.show('Não foi possível copiar', { tone: 'error' }); }
  };

  return (
    <>
      <div className="view-head"><h1>Exportados</h1></div>
      {items === null ? <Skeleton /> : items.length === 0 ? (
        <EmptyState title="Nada exportado ainda">Aprove um resultado no Pipeline e a pasta de publicação aparece aqui.</EmptyState>
      ) : (
        <ul className="cards">
          {items.map((m) => (
            <li key={m.job_id + m.exported_at} className="pagecard pagecard--wide">
              <div>
                <p className="pagecard__name">{m.headline || m.source?.title || m.job_id}</p>
                <p className="muted">{m.page?.display_name ?? m.page?.name} · {m.deliverables.map((d) => d.kind).join(', ')} · há {timeAgo(m.exported_at)}</p>
                <p className="data muted folder">{m.folder}</p>
              </div>
              <div className="actions">
                <Button onClick={() => copy(m.caption, 'Legenda')}>Copiar legenda</Button>
                <Button onClick={() => copy(m.folder, 'Caminho')}>Copiar pasta</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

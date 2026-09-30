import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Niche, QuotaStatus, ScanReport, Summary } from '../api/types';
import { useToast } from '../app/toast';
import { Badge, Button } from '../ui';
import './views.css';

const COMMAND = 'python -m underfind.backend.mcp.server';
const MCP_JSON = JSON.stringify({ mcpServers: { underfind: { command: 'python', args: ['-m', 'underfind.backend.mcp.server'] } } }, null, 2);

export function Settings({ summary }: { summary: Summary | null }) {
  const toast = useToast();
  const [quota, setQuota] = useState<QuotaStatus[]>([]);
  const [niches, setNiches] = useState<Niche[]>([]);
  const [scans, setScans] = useState<ScanReport[]>([]);

  useEffect(() => {
    void api.quota().then(setQuota).catch(() => undefined);
    void api.niches().then(setNiches).catch(() => undefined);
    void api.scans(null).then(setScans).catch(() => undefined);
  }, []);

  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); toast.show('Copiado'); } catch { toast.show('Não foi possível copiar', { tone: 'error' }); }
  };

  return (
    <>
      <div className="view-head"><h1>Configurações</h1></div>

      <section className="panel" aria-labelledby="s-ai">
        <h2 id="s-ai" className="col-title">IA e worker</h2>
        <p>{summary?.ai_mode === 'online' ? 'IA online liberada para páginas sem “Somente IA local”.' : 'Tudo roda nesta máquina. Nenhum modelo online é usado.'}</p>
        <p className="muted">Worker: {summary ? (summary.worker_running ? 'rodando' : 'parado') : '–'}. O modo é definido ao iniciar o servidor: <span className="data">python app.py --local</span> ou <span className="data">--online</span>.</p>
      </section>

      <section className="panel" aria-labelledby="s-quota">
        <h2 id="s-quota" className="col-title">Cota</h2>
        {quota.length === 0 ? <p className="muted">Sem uso hoje.</p> : quota.map((q) => (
          <p key={q.provider}><span>{q.provider}</span> <span className="num">{q.used}/{q.limit}</span> {q.exhausted && <Badge tone="failed">Esgotada</Badge>}</p>
        ))}
      </section>

      <section className="panel" aria-labelledby="s-niches">
        <h2 id="s-niches" className="col-title">Nichos</h2>
        {niches.map((n) => (
          <p key={n.name}><strong>{n.name}</strong> <span className="muted">{n.description} · busca a cada <span className="num">{n.scan.every_minutes}</span> min</span></p>
        ))}
        {scans.length > 0 && (
          <ul className="scanlog">{scans.map((s, i) => <li key={i} className="muted"><span className="num">{s.started_at.slice(0, 16).replace('T', ' ')}</span> {s.niche}: {s.found} encontrados, {s.new} novos{s.dry_run ? ' (simulação)' : ''}</li>)}</ul>
        )}
      </section>

      <section className="panel" aria-labelledby="s-mcp">
        <h2 id="s-mcp" className="col-title">Conectar ao Claude, Cursor ou outro cliente MCP</h2>
        <p className="muted">Comando (stdio):</p>
        <pre className="code data">{COMMAND}</pre>
        <Button onClick={() => copy(COMMAND)}>Copiar comando</Button>
        <p className="muted">Configuração JSON:</p>
        <pre className="code data">{MCP_JSON}</pre>
        <Button onClick={() => copy(MCP_JSON)}>Copiar JSON</Button>
      </section>
    </>
  );
}

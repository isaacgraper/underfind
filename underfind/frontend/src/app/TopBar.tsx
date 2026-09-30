import { Settings, Compass } from 'lucide-react';
import type { Summary } from '../api/types';
import type { Route } from './router';

const NAV: { name: Route['name']; href: string; label: string }[] = [
  { name: 'inbox', href: '#/inbox', label: 'Inbox' },
  { name: 'pipeline', href: '#/pipeline', label: 'Pipeline' },
  { name: 'pages', href: '#/pages', label: 'Páginas' },
  { name: 'exports', href: '#/exports', label: 'Exportados' },
];

function sentence(s: Summary | null): string {
  if (!s) return '';
  if (s.needs_you > 0) return `${s.needs_you} ${s.needs_you === 1 ? 'post precisa' : 'posts precisam'} de você`;
  if (s.working > 0) return `${s.working} em andamento`;
  return 'Tudo em dia';
}

export function TopBar({ route, summary }: { route: Route; summary: Summary | null }) {
  const active = route.name === 'review' ? 'pipeline' : route.name;

  return (
    <header className="topbar">
      <a className="topbar__brand" href="#/inbox">underfind</a>
      <nav className="topbar__nav" aria-label="Principal">
        {NAV.map((n) => (
          <a key={n.name} href={n.href} className="topbar__link" aria-current={active === n.name ? 'page' : undefined}>
            {n.label}
            {n.name === 'inbox' && summary && summary.inbox_new > 0 && <span className="topbar__count num">{summary.inbox_new}</span>}
            {n.name === 'pipeline' && summary && summary.needs_you > 0 && <span className="topbar__count topbar__count--accent num">{summary.needs_you}</span>}
          </a>
        ))}
      </nav>
      <p className="topbar__status" role="status">{sentence(summary)}</p>
      {summary && (
        <span className="topbar__ai" data-mode={summary.ai_mode}>
          {summary.ai_mode === 'local' ? 'IA local' : 'IA online liberada'}
        </span>
      )}
      <a className="topbar__icon" href="#/discover" aria-label="Descobrir" aria-current={active === 'discover' ? 'page' : undefined}><Compass size={18} /></a>
      <a className="topbar__icon" href="#/settings" aria-label="Configurações" aria-current={active === 'settings' ? 'page' : undefined}><Settings size={18} /></a>
    </header>
  );
}

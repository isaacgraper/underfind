import { api } from '../api/client';
import { TopBar } from './TopBar';
import { ToastProvider } from './toast';
import { useHashRoute } from './router';
import { usePolling } from './usePolling';
import { Inbox } from '../views/Inbox';
import { Pipeline } from '../views/Pipeline';
import { Review } from '../views/Review';
import { Pages } from '../views/Pages';
import { Exports } from '../views/Exports';
import { Discover } from '../views/Discover';
import { Settings } from '../views/Settings';
import './app.css';

export function App() {
  const route = useHashRoute();
  const summary = usePolling(api.summary);

  return (
    <ToastProvider>
      <a className="skip" href="#main">Pular para o conteúdo</a>
      <TopBar route={route} summary={summary.data} />
      {summary.stale && <p className="banner" role="alert">Sem resposta do servidor. Mostrando os últimos dados.</p>}
      <main id="main" className="main" key={route.name}>
        {route.name === 'inbox' && <Inbox onChanged={summary.refresh} />}
        {route.name === 'pipeline' && <Pipeline summary={summary.data} onChanged={summary.refresh} />}
        {route.name === 'review' && <Review id={route.id} onChanged={summary.refresh} />}
        {route.name === 'pages' && <Pages />}
        {route.name === 'exports' && <Exports />}
        {route.name === 'discover' && <Discover onChanged={summary.refresh} />}
        {route.name === 'settings' && <Settings summary={summary.data} />}
      </main>
    </ToastProvider>
  );
}

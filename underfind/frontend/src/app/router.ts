import { useEffect, useState } from 'react';

export type Route =
  | { name: 'inbox' }
  | { name: 'pipeline' }
  | { name: 'review'; id: string }
  | { name: 'pages' }
  | { name: 'exports' }
  | { name: 'discover' }
  | { name: 'settings' };

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const [head, arg] = parts;

  switch (head) {
    case 'pipeline':
      return { name: 'pipeline' };
    case 'review':
      return arg ? { name: 'review', id: decodeURIComponent(arg) } : { name: 'pipeline' };
    case 'pages':
      return { name: 'pages' };
    case 'exports':
      return { name: 'exports' };
    case 'discover':
      return { name: 'discover' };
    case 'settings':
      return { name: 'settings' };
    default:
      return { name: 'inbox' };
  }
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  return route;
}

export const go = (path: string) => {
  window.location.hash = path;
};

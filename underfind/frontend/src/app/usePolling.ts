import { useCallback, useEffect, useRef, useState } from 'react';

const INTERVAL_MS = 3000;
const STALE_MS = 30000;

export interface Polled<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  stale: boolean;
  refresh: () => Promise<void>;
  setData: (next: T | ((prev: T | null) => T | null)) => void;
}

/** Polls every 3 s, pauses while the tab is hidden, and flags data older than 30 s. */
export function usePolling<T>(fetcher: () => Promise<T>, deps: unknown[] = [], paused = false): Polled<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastOk, setLastOk] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const next = await fetcherRef.current();
      if (!alive.current) return;
      setData(next);
      setError(null);
      setLastOk(Date.now());
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (alive.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    setLoading(true);
    void refresh();

    if (paused) return () => { alive.current = false; };

    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh();
    }, INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      alive.current = false;
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused, refresh, ...deps]);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 5000);
    return () => window.clearInterval(t);
  }, []);

  return { data, error, loading, stale: error !== null && now - lastOk > STALE_MS, refresh, setData };
}

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

interface ToastItem {
  id: number;
  text: string;
  tone: 'info' | 'error';
  actionLabel?: string;
  onAction?: () => void;
  leaving: boolean;
}

interface ToastApi {
  show: (text: string, opts?: { tone?: 'info' | 'error'; actionLabel?: string; onAction?: () => void; ms?: number }) => void;
}

const Ctx = createContext<ToastApi>({ show: () => undefined });
export const useToast = () => useContext(Ctx);

let seq = 0;

function Toast({ item, ms, onDone }: { item: ToastItem; ms: number; onDone: (id: number) => void }) {
  const hovering = useRef(false);
  const remaining = useRef(ms);
  const started = useRef(Date.now());
  const timer = useRef<number>();

  const arm = useCallback(() => {
    started.current = Date.now();
    timer.current = window.setTimeout(() => onDone(item.id), remaining.current);
  }, [item.id, onDone]);

  const disarm = useCallback(() => {
    window.clearTimeout(timer.current);
    remaining.current -= Date.now() - started.current;
  }, []);

  useEffect(() => {
    arm();
    const onVis = () => {
      if (document.visibilityState === 'hidden') disarm();
      else if (!hovering.current) arm();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      window.clearTimeout(timer.current);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [arm, disarm]);

  return (
    <div
      className="toast"
      data-tone={item.tone}
      data-leaving={item.leaving || undefined}
      onMouseEnter={() => { hovering.current = true; disarm(); }}
      onMouseLeave={() => { hovering.current = false; arm(); }}
    >
      <span>{item.text}</span>
      {item.actionLabel && (
        <button
          type="button"
          className="toast__action"
          onClick={() => {
            item.onAction?.();
            onDone(item.id);
          }}
        >
          {item.actionLabel}
        </button>
      )}
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<(ToastItem & { ms: number })[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((list) => list.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    window.setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), 160);
  }, []);

  const show = useCallback<ToastApi['show']>((text, opts = {}) => {
    const id = ++seq;
    setItems((list) => [
      ...list.slice(-2),
      { id, text, tone: opts.tone ?? 'info', actionLabel: opts.actionLabel, onAction: opts.onAction, leaving: false, ms: opts.ms ?? (opts.actionLabel ? 8000 : 4500) },
    ]);
  }, []);

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <Toast key={t.id} item={t} ms={t.ms} onDone={dismiss} />
        ))}
      </div>
    </Ctx.Provider>
  );
}

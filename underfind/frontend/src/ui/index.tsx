import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { STAGES, type JobStatus } from '../api/types';
import './ui.css';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  icon?: ReactNode;
};

export function Button({ variant = 'secondary', icon, children, className = '', type = 'button', ...rest }: ButtonProps) {
  return (
    <button type={type} className={`btn btn--${variant} ${className}`} {...rest}>
      {icon}
      {children}
    </button>
  );
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          className="segmented__opt"
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  );
}

export function Check({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="check__label">{label}</span>
        {hint && <span className="field__hint">{hint}</span>}
      </span>
    </label>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <h2 className="empty__title">{title}</h2>
      {children && <p className="empty__body">{children}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton__row" />
      ))}
    </div>
  );
}

export function Badge({ tone, children }: { tone: 'queued' | 'working' | 'done' | 'failed' | 'accent' | 'neutral'; children: ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function StageTrack({ status, failedFrom }: { status: JobStatus; failedFrom: JobStatus | null }) {
  const at = status === 'failed' ? STAGES.indexOf(failedFrom ?? 'found') : STAGES.indexOf(status);
  return (
    <ol className="track" aria-label={`Etapa ${Math.max(at, 0) + 1} de ${STAGES.length}`}>
      {STAGES.map((s, i) => (
        <li key={s} className="track__step" data-state={i < at ? 'past' : i === at ? (status === 'failed' ? 'failed' : 'current') : 'next'} title={s} />
      ))}
    </ol>
  );
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  return (
    <dialog ref={ref} className="dialog" onCancel={onCancel} aria-labelledby="dlg-title">
      <h2 id="dlg-title" className="dialog__title">{title}</h2>
      <p className="dialog__body">{body}</p>
      <div className="dialog__actions">
        <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
        <Button variant="danger" onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </dialog>
  );
}

/** Destructive action that only fires after the button is held for 1.5 s; keyboard: hold Enter or Space. */
export function HoldButton({ label, holdingLabel, onConfirm }: { label: string; holdingLabel: string; onConfirm: () => void }) {
  const [holding, setHolding] = useState(false);
  const timer = useRef<number>();

  const start = () => {
    setHolding(true);
    timer.current = window.setTimeout(() => {
      setHolding(false);
      onConfirm();
    }, 1500);
  };
  const stop = () => {
    window.clearTimeout(timer.current);
    setHolding(false);
  };

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <button
      type="button"
      className="btn btn--danger hold"
      data-holding={holding || undefined}
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) {
          e.preventDefault();
          start();
        }
      }}
      onKeyUp={(e) => {
        if (e.key === 'Enter' || e.key === ' ') stop();
      }}
      onBlur={stop}
    >
      <span className="hold__fill" aria-hidden="true" />
      <span className="hold__label">{holding ? holdingLabel : label}</span>
    </button>
  );
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`).getTime()) / 1000));
  if (secs < 60) return 'agora';
  if (secs < 3600) return `${Math.floor(secs / 60)} min`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h`;
  return `${Math.floor(secs / 86400)} d`;
}

export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined) return '–';
  return new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(n);
}

import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { OutputKind, PageProfile, RenderTemplate } from '../api/types';
import { useToast } from '../app/toast';
import { Badge, Button, Check, EmptyState, Field, HoldButton, Skeleton } from '../ui';
import './views.css';

const BLANK: PageProfile = {
  display_name: '', handle: '', language: 'pt-BR', default_hashtags: [], auto_approve_translation: false, auto_approve_render: false,
  local_only: true, niche: '', brand_tag: '', glossary: [], outputs: ['reel'], active: true, caption_footer: '', audio_bed_path: '', tts_voice: '',
};

const OUTPUTS: { value: OutputKind; label: string }[] = [
  { value: 'reel', label: 'Reel 9:16' },
  { value: 'post', label: 'Post 4:5' },
  { value: 'carousel', label: 'Carrossel' },
];

export function Pages() {
  const toast = useToast();
  const [pages, setPages] = useState<PageProfile[] | null>(null);
  const [templates, setTemplates] = useState<RenderTemplate[]>([]);
  const [editing, setEditing] = useState<PageProfile | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.pages().then(setPages).catch((e) => toast.show((e as Error).message, { tone: 'error' }));
  useEffect(() => { void load(); void api.templates().then(setTemplates).catch(() => undefined); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const set = <K extends keyof PageProfile>(k: K, v: PageProfile[K]) => setEditing((p) => (p ? { ...p, [k]: v } : p));
  const toggleOutput = (o: OutputKind) => setEditing((p) => (p ? { ...p, outputs: p.outputs.includes(o) ? p.outputs.filter((x) => x !== o) : [...p.outputs, o] } : p));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    try {
      await api.savePage({ ...editing, niche: editing.niche || null, template_id: editing.template_id || null });
      toast.show('Página salva');
      setEditing(null);
      await load();
    } catch (err) { toast.show((err as Error).message, { tone: 'error' }); }
    finally { setSaving(false); }
  };

  const remove = async (p: PageProfile) => {
    try { await api.deletePage(p.id as number); toast.show('Página excluída'); setEditing(null); await load(); }
    catch (err) { toast.show((err as Error).message, { tone: 'error' }); }
  };

  return (
    <>
      <div className="view-head">
        <h1>Páginas</h1>
        {!editing && <Button variant="primary" onClick={() => setEditing({ ...BLANK })}>Nova página</Button>}
      </div>

      {editing ? (
        <form className="form" onSubmit={save}>
          <h2 className="col-title">{editing.id ? 'Editar página' : 'Nova página'}</h2>
          <div className="form__grid">
            <Field label="Nome"><input type="text" required value={editing.display_name} onChange={(e) => set('display_name', e.target.value)} /></Field>
            <Field label="@ do Instagram"><input type="text" required value={editing.handle} onChange={(e) => set('handle', e.target.value)} /></Field>
            <Field label="Idioma"><select value={editing.language} onChange={(e) => set('language', e.target.value)}>{['pt-BR', 'en', 'es', 'fr', 'de', 'it'].map((l) => <option key={l}>{l}</option>)}</select></Field>
            <Field label="Nicho"><input type="text" value={editing.niche ?? ''} onChange={(e) => set('niche', e.target.value)} placeholder="gta6" /></Field>
            <Field label="Marca na manchete" hint="Texto da linha de marca no cartão."><input type="text" value={editing.brand_tag ?? ''} onChange={(e) => set('brand_tag', e.target.value)} /></Field>
            <Field label="Template"><select value={editing.template_id ?? ''} onChange={(e) => set('template_id', e.target.value ? Number(e.target.value) : null)}><option value="">Padrão</option>{templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
            <Field label="Rodapé da legenda"><input type="text" value={editing.caption_footer ?? ''} onChange={(e) => set('caption_footer', e.target.value)} /></Field>
            <Field label="Áudio de fundo (caminho)"><input type="text" value={editing.audio_bed_path ?? ''} onChange={(e) => set('audio_bed_path', e.target.value)} /></Field>
            <Field label="Voz da dublagem"><input type="text" value={editing.tts_voice ?? ''} onChange={(e) => set('tts_voice', e.target.value)} placeholder="pt_BR-faber-medium" /></Field>
          </div>
          <fieldset className="fieldset">
            <legend>Formatos de saída</legend>
            {OUTPUTS.map((o) => <Check key={o.value} label={o.label} checked={editing.outputs.includes(o.value)} onChange={() => toggleOutput(o.value)} />)}
          </fieldset>
          <fieldset className="fieldset">
            <legend>Automação</legend>
            <Check label="Somente IA local" hint="Nenhum dado sai desta máquina." checked={editing.local_only} onChange={(v) => set('local_only', v)} />
            <Check label="Aprovar traduções automaticamente" checked={editing.auto_approve_translation} onChange={(v) => set('auto_approve_translation', v)} />
            <Check label="Aprovar resultados automaticamente" checked={editing.auto_approve_render} onChange={(v) => set('auto_approve_render', v)} />
          </fieldset>
          <div className="actions">
            {editing.id ? <HoldButton label="Segure para excluir" holdingLabel="Continue segurando…" onConfirm={() => remove(editing)} /> : null}
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancelar</Button>
            <Button type="submit" variant="primary" disabled={saving}>Salvar página</Button>
          </div>
        </form>
      ) : pages === null ? <Skeleton rows={3} /> : pages.length === 0 ? (
        <EmptyState title="Nenhuma página ainda" action={<Button variant="primary" onClick={() => setEditing({ ...BLANK })}>Nova página</Button>}>Uma página define a marca, o idioma e os formatos dos posts modelados.</EmptyState>
      ) : (
        <ul className="cards">
          {pages.map((p) => (
            <li key={p.id} className="pagecard">
              <div>
                <p className="pagecard__name">{p.display_name}</p>
                <p className="muted">{p.handle} · {p.language}{p.niche ? ` · ${p.niche}` : ''}</p>
                <p className="pagecard__badges">
                  {p.outputs.map((o) => <Badge key={o} tone="neutral">{o}</Badge>)}
                  {p.local_only && <Badge tone="done">IA local</Badge>}
                </p>
              </div>
              <Button onClick={() => setEditing({ ...p })}>Editar</Button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

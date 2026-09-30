# Underfind: design decisions

How the interface for the post-modeling pipeline (Phase 8) was designed, and why. Four design skills from skills.sh were applied in the order requested, each one working from the previous one's output:

1. **ui-ux-pro-max** (nextlevelbuilder): research and evidence. Design-system search, UX rules, typography, stack guidance.
2. **frontend-design** (Anthropic): turns the evidence into a point of view, then reviews the plan against generic defaults.
3. **polish** (impeccable): audits the existing frontend and fixes the acceptance bar.
4. **bolder** (impeccable): one scoped amplification, only where the first three left something flat.

This file replaces the v2.1 design doc (YouTube discovery dashboard). Its token set and Emil Kowalski motion rules carry over where noted in section 7; everything else was decided again for the pipeline product.

---

## 0. Brief

| | |
|---|---|
| **Subject** | A local-first workshop that finds posts working abroad, models them for your own pages (your language, your brand, your layout) and hands the finished files to a publisher. |
| **Who uses it** | One creator running several pages, at a desk, usually in the evening. Not a team, not a marketer building dashboards. |
| **Primary job** | Clear a stream of decisions quickly: pick which found posts to model, then approve or fix the modeled result. The automation does the rest without being watched. |
| **Mode** (impeccable) | **Operate.** The user is completing a task. Scanability, consistency and familiar controls outrank expression; brand lives in precise details. |
| **Constraints** | Runs on the user's machine (no CDN fonts, no cloud assets). React 18 + TypeScript + Vite, hand-written CSS with tokens (no Tailwind, no component library). Interface copy in Brazilian Portuguese. |
| **Non-goal** | A landing page. The product has none; the hero of this design is the work surface. |

---

## 1. Pass one: ui-ux-pro-max

### 1.1 What was run

```
search.py "automation workflow pipeline dashboard content creator social media local-first tool dark" --design-system
search.py "creator studio content operations queue dark dense" --design-system --density 8 --variance 3 --motion 3
search.py "<topic>" --domain ux      (progress, review gates, video preview, dense tables, empty states, destructive actions)
search.py "operations console technical precise dark" --domain typography
search.py "focus visible reduced motion list" --stack react
```

**The first query was rejected.** It returned "Feature-Rich Showcase", a light rose-and-blue marketing style, because the words "social media" and "creator" pulled it toward a consumer landing page. That is not a product where someone clears a review queue. The skill's own rule applies (verify fit, retry once with a narrower query), so the query was rewritten around the real job: operations, queue, dense, dark. The second run matched.

### 1.2 What matched

| Dimension | Result | Fit |
|---|---|---|
| Pattern | Real-Time / Operations: label live state only when backed by a current source, with update time and stale state; pause controls; static snapshot under reduced motion | Direct. The pipeline board is exactly this. |
| Style | Minimalism & Swiss, dark supported, "enterprise apps, dashboards, professional tools" | Fits Operate mode. |
| Dials | Variance 3 (centered, minimal), motion 3 (subtle), density 8 (dense) | Adopted as set. |
| Palette notes | "Dark terminal + running green + failed red + queued amber" | Semantics adopted (queued, running, failed, done each own a color). The literal palette was not: see 2.3. |
| Typography | Fira Code / Fira Sans ("dashboard, data, analytics, precise") | Adopted for roles, reassigned in 2.2. |
| Avoid | "Slow dashboards, decorative charts, hidden error states" | Adopted as rules. |

### 1.3 UX rules pulled in, and the decision each one forces

| Rule (severity) | Decision |
|---|---|
| Progress indicators: step indicators for multi-step work (medium) | Every card shows its stage as a seven-step track, with elapsed time on the running step. |
| Submit feedback: loading then success/error, never silent (high) | Every action gets all three states. "Approve" turns the card into a "Exporting" state, then a toast that names the result. Failures stay on the card with the reason and a retry action. |
| Confirmation dialogs for irreversible actions (high) | Discard and delete ask first, except where undo is cheaper: discarding a job is undoable for 8 s with a toast. Deleting a page or template always confirms. |
| Auto-play video needs pause, captions, stop off-screen (medium) | Previews never auto-play. Click to play, muted by default, native controls, pause when off-screen. |
| Table handling: scroll or card layout, bulk actions (medium/low) | The inbox is a dense table with checkboxes and bulk "Modelar" / "Descartar"; below 720 px it becomes a card list. |
| Empty states: helpful message and action (medium) | Every list ships one empty state that says what fills it and offers the action that does. |
| Contextual live badge updates (high) | Lane counts announce as one sentence ("3 posts precisam de você") in a single polite status region, not a live region per badge. |
| Manage focus: trap in modals, return on close (high) | Review opens as a full workspace, not a modal; only confirmations are modal. |
| Contrast 4.5:1, visible focus, reduced motion, touch 44 px (critical) | Section 4 audits the existing UI against these. |

### 1.4 Insight carried into the next pass

The search engine's answer to "what should this look like" was a category default: near-black, one terminal-green accent, monospace labels. The next pass reviews that answer against the brief instead of accepting it.

---

## 2. Pass two: frontend-design

### 2.1 Grounding in the subject

frontend-design says distinctive choices come from the subject's own materials and vernacular. This product's materials are unusually concrete: it manufactures a specific artifact. The renderer outputs a black card with a condensed Anton headline, a brand line between two gradient rules, and highlighted words in a magenta-to-orange gradient (taken from the reference posts). Those are this product's vernacular. The interface should feel like the workshop that makes them, not like a generic admin panel next to them.

The second concrete fact: the core insight of the product is **finding what is under-found**: posts that outperform the size of the account that made them (views divided by followers). The name is the idea.

### 2.2 Plan (pass one of frontend-design's two passes)

**Color: six named values**

| Name | Hex | Role |
|---|---|---|
| Ink | `#0F0D14` | Canvas. Near-black tinted toward plum, not neutral zinc. |
| Plate | `#16131D` | Panels and rows. |
| Platen | `#1E1A28` | Raised: inputs, menus, hovered rows. |
| Paper | `#F3F0F8` | Primary text. |
| Magenta | `#E879F9` | The one accent: "this needs you". Buttons that approve, the current selection, focus rings. |
| Amber / Cyan / Green / Red | `#FBBF24` / `#38BDF8` / `#4ADE80` / `#F87171` | State only: queued / working / exported / failed. Never decoration. |

Secondary text `#B4ADC4` (8.5:1 on Plate), tertiary text `#8C849E` (5.2:1). The orange end of the brand gradient (`#FB923C`) appears only inside rendered previews, never in interface chrome.

**Type: two families, clearly distinct**

| Role | Face | Why |
|---|---|---|
| Interface and prose | **Fira Sans** | From the ui-ux-pro-max pairing; humanist, legible at 13 to 16 px, real tabular figures, a weight range wide enough for hierarchy without size jumps. |
| Data | **Fira Code** | Used only for what is actually data or measurement: job ids, scores, durations, quota units, file names. Not as a costume on labels. |
| Display | **Anton** (already bundled for the renderer) | The single headline field in the review workspace (see pass four). Nowhere else; the wordmark is Fira Sans semibold. |

All three are self-hosted (local-first). The previous design named Plus Jakarta Sans but never loaded it, so the app was rendering in the system font.

Scale for Operate, fixed rem with a 1.125 to 1.2 step: 12 / 13 / 14 (interface default) / 16 (editing prose) / 20 / 26. Nothing below 12. Body prose measure 65 to 75ch; data rows may run wider.

**Layout concept**

```
┌─ top bar ───────────────────────────────────────────────────────────────────┐
│ underfind   Inbox 12 · Pipeline · Pages · Exports            ● IA local  ⚙ │
├──────────────┬──────────────────────────────────────────────────────────────┤
│ niche ▾      │  PIPELINE                                                    │
│  gta6        │  ┌ Precisa de você 3 ┐ ┌ Em andamento 5 ┐ ┌ Falhou 1 ┐ ┌ Pronto ┐
│  cars        │  │ ▭ preview  reel   │ │ ▭ baixando…    │ │ ▭ erro   │ │        │
│ pages ▾      │  │ Traduzido  [Rever]│ │ ●●●○○○○  2:14  │ │ [Tentar] │ │        │
│  gtavibrasil │  │ ▭ preview  post   │ │ ▭ renderizando │ │          │ │        │
│  gtavies     │  └───────────────────┘ └────────────────┘ └──────────┘ └────────┘
└──────────────┴──────────────────────────────────────────────────────────────┘
```

Left-aligned throughout. A persistent rail on the left holds the niche and page filters so every screen answers "whose posts am I looking at". The lane order puts the human's work first: seven pipeline stages collapse into four lanes, and "Precisa de você" (the two review gates) is always leftmost.

**Principles**

1. The post is the hero. Previews render at their true aspect ratio (9:16 and 4:5) and are never cropped into thumbnails of a uniform size.
2. The interface stays quiet around the post. Chrome is tinted dark and low-contrast; color is reserved for state and for the one accent.
3. "Needs you" is the only loud state. Automated work is visible but calm.
4. Local is a trust signal: the top bar always says whether AI is local or online is allowed. A cloud indicator never appears unless online mode is on.
5. Names describe what a person does, not how the system is built: "Modelar", "Aprovar", not "Enqueue", "Gate".

### 2.3 Review of the plan against generic defaults

frontend-design lists the traits generated designs cluster around and asks that every part of the plan be checked against them. Result:

| Trait | Did the first plan have it? | Change made |
|---|---|---|
| Near-black with a single acid-green or vermilion accent | **Yes.** ui-ux-pro-max's "dark terminal + running green" is this, and the old palette used neutral zinc with emerald. | Accent moved off green entirely (green now only means "exported"). Canvas tinted plum from the product's own gradient. Accent is magenta and means one thing. |
| SaaS card kit: identical rounded cards, one radius, same soft shadow | The old video cards and idea cards were this. | Radius by role (full pills for state and actions, 10 px controls, 14 px panels, 6 px media). No shadows on panels; depth from surface tint and 1 px lines. Post previews are not cards; they are the media itself, at true aspect. |
| Hero-metric template (big number, small label, accent) | The old Dashboard was four of these. | Dashboard is retired. Counts live on lane headers and nav items where they are actions, not decoration. |
| Tracked all-caps eyebrow over every heading | Common in the old page headers. | None. Headings carry their own weight. |
| Monospace as a costume for small data labels | The ui-ux-pro-max typography result leans this way. | Mono only for real data (ids, scores, time, quota). Labels are Fira Sans. |
| Middle-dot meta strings, arrows appended to buttons | Present in old card footers. | Meta is laid out as structure (label and value pairs); buttons name the action and nothing else. |
| Numbered markers (01 / 02 / 03) | Not used, correctly. The seven-step track is used because the pipeline really is a sequence. | Kept, for that reason only. |

### 2.4 Restraint

One place gets the boldness: the review workspace. Everything else is disciplined and unremarkable on purpose. Motion follows the same rule (section 6): one authored moment, everything else answers a click.

---

## 3. Screens and what happens to the existing pages

| Screen | Replaces | Job |
|---|---|---|
| **Inbox** | Viral Shorts, Trending, Explorer, Dashboard top list | Scored candidates per niche, best first. Dense table: source preview, author, views, followers, score bar with its four parts, age. Bulk Modelar / Descartar. Keyboard: `j` `k` move, `x` select, `m` modelar, `d` descartar. Scan button with last-scan time and per-scanner errors. |
| **Pipeline** | Ideas Board | The four lanes above. Cards show the true-aspect preview, page, stage track, elapsed time, and the one action for that state. |
| **Review** | Translation and render approval (new) | Full workspace for one job. Source on the left, modeled result on the right (pass four). Previous and next job keys so a batch clears without returning to the board. |
| **Pages** | none (API only today) | Page profiles: identity, language, niche, brand tag, outputs, footer, voice, the three switches (local only, auto-approve translation, auto-approve render). Template editor with a live preview rendered by the backend. |
| **Exports** | none | Exported folders, manifest, caption with a copy button, open-folder action, webhook delivery state. |
| **Discover** | Explorer and Trending, kept as search tools | Manual YouTube search with the old filters; results can be sent to the Inbox. Secondary: a menu item, not a top-level tab. |
| **Settings** | MCP Hub | AI mode and model status, quota, worker state, niches (read-only view of the YAML plus a scan log), MCP hub. |

Top bar: Inbox (with count), Pipeline (with "needs you" count), Pages, Exports, then the AI-mode badge and settings. Five destinations, well under the navigation limit.

---

## 4. Pass three: polish

polish is refinement: preserve the incumbent world, find drift, fix cause at the narrowest level. The audit below was run against the current `frontend/src`; numbers are counts in the repository today.

### 4.1 Audit findings

| # | Finding | Evidence | Class | Fix |
|---|---|---|---|---|
| 1 | Tertiary text fails contrast | `--text-tertiary #71717A` is 4.1:1 on canvas and 3.8:1 on surface; used in 23 rules | local defect | New value `#8C849E` (5.2:1 on Plate) in the token; all 23 uses inherit the fix. |
| 2 | Focus rings removed, none replaced | 6 rules set `outline: none`; `:focus-visible` appears 0 times | missing token | One global `:focus-visible` ring using the accent (2 px, 2 px offset); a rule that forbids `outline: none` without a replacement. |
| 3 | No reduced-motion handling | `prefers-reduced-motion` appears 0 times | missing token | One global reduce block in `globals.css` that removes transforms and durations. |
| 4 | Colors outside the token system | 121 raw hex values in component CSS | one-off implementation | Migrate to semantic tokens during the refactor; lint rule rejects a hex in a component stylesheet. |
| 5 | The display font was never loaded | `globals.css` names Plus Jakarta Sans; no font files or imports exist | local defect | Self-host Fira Sans, Fira Code, Anton via `@fontsource`. |
| 6 | Controls below touch size | Heights of 22, 26, 30, 32 px on buttons and chips | missing token | `--control-h: 36px` on fine pointers, `44px` under `(pointer: coarse)`; chips that are not controls may stay small. |
| 7 | Tiny type | 3 rules under 12 px | local defect | Floor of 12 px. |
| 8 | Responsive coverage is thin | 7 media queries across 40+ stylesheets | conceptual mismatch | Structural breakpoints (rail collapses, lanes scroll, table becomes cards); no fluid type. |
| 9 | Different names for the same thing | "Ideia", "Vídeo", "Short", "Localizar" for one object | conceptual mismatch | Vocabulary in section 5. |

### 4.2 The bar every screen must meet before it ships

States for every interactive component: default, hover, focus, active, disabled, loading, error, success. Data screens add: empty, loading as skeleton (not a spinner over content), error with recovery, long content, missing content, offline or worker stopped.

Checked together in one round at 375, 768, 1024 and 1440 px, with mouse, keyboard and touch:

- Contrast: body and placeholder 4.5:1, large text 3:1, states and focus included.
- Keyboard: logical order, every action reachable, focus returns after dialogs, `Escape` closes.
- Names: icon-only buttons have accessible names; status dots never carry meaning alone (icon or text too).
- Layout: no horizontal page scroll, no layout shift from media (aspect-ratio reserved), overlays escape clipped containers.
- Browser surfaces themed from the palette: selection color, caret, scrollbars, tabular numerals in every data column.
- Copy: one name per thing, same verb in the button and the confirmation.

---

## 5. Vocabulary and copy rules

Interface language is pt-BR, sentence case, plain verbs. The same word is used everywhere an object appears.

| Concept | Term | Never |
|---|---|---|
| A post found by a scan | **Candidato** (in the Inbox) | "Ideia", "Vídeo" |
| A post being worked on | **Post** (card), **Job** only in logs and API | "Item", "Tarefa" |
| Turn a candidate into work | **Modelar** | "Localizar", "Enfileirar", "Clonar" |
| The two human checks | **Revisar tradução**, **Revisar resultado** | "Gate", "Aprovação" as a noun |
| Approve | **Aprovar tradução**, **Aprovar e exportar** | "OK", "Enviar" |
| Stages | Encontrado · Baixado · Transcrito · Traduzido · Narrado · Renderizado · Exportado | English stage ids |
| Lanes | **Precisa de você** · Em andamento · Falhou · Pronto | |
| AI mode | **IA local** / **IA online liberada** | "Offline", "Cloud" |

Errors name the problem and the recovery: "Não foi possível baixar: o Instagram pediu login. Configure o arquivo de cookies e tente de novo." Errors do not apologize. Empty states teach: "Nenhum candidato ainda. Rode uma varredura ou cole um link para começar." Toasts repeat the action's name: the button says "Aprovar e exportar", the toast says "Exportado".

---

## 6. Interaction and motion

- **Dial**: motion 3 of 10. Subtle. Nothing moves that does not answer an action, except one moment.
- **The one authored moment**: a card entering "Precisa de você" settles into its lane (translate and fade, 240 ms, exponential ease-out from an already-visible state). It is the only unprompted motion in the product, because it is the only event that needs the user's attention.
- **Answers to action** (kept from v2.1 because they were right): `cubic-bezier(0.23, 1, 0.32, 1)` ease-out, `:active { transform: scale(0.97) }`, exits faster than entrances, origin-aware menus. Animate transform and opacity only.
- **Live state** (from the operations pattern): pipeline data refreshes by polling every 3 s while the tab is visible; the top bar shows "atualizado há Ns" and a stale warning after 30 s; a pause control stops updates. Status is text plus icon, never color alone.
- **Reduced motion**: all of the above collapses to instant state changes.
- **No scroll reveals, no entrance animation on every section, no hover lift on every card.**

---

## 7. Final tokens

Carried over from v2.1: spacing rhythm, easing curves, the fluid-pill idea for state and action shapes. Changed: palette (plum-tinted), tertiary contrast, radii by role, focus ring, control height, type.

```css
:root {
  /* Surfaces (Ink, Plate, Platen) */
  --bg-canvas: #0F0D14;
  --bg-surface: #16131D;
  --bg-raised: #1E1A28;
  --bg-input: #1E1A28;
  --line: rgba(236, 230, 255, 0.09);
  --line-strong: rgba(236, 230, 255, 0.16);

  /* Text */
  --text-primary: #F3F0F8;     /* 15:1 on raised */
  --text-secondary: #B4ADC4;   /* 7.9:1 */
  --text-tertiary: #8C849E;    /* 4.8:1 on raised, 5.2:1 on surface */
  --text-disabled: #6B647A;    /* decorative only, never the sole carrier of meaning */

  /* The one accent: "needs you" */
  --accent: #E879F9;           /* 7.5:1 on surface; filled buttons use it with --on-accent text (7.5:1) */
  --accent-pressed: #D946EF;   /* :active fill; --on-accent text is 5.3:1 on it */
  --on-accent: #16131D;
  --accent-wash: rgba(232, 121, 249, 0.12);

  /* State only */
  --state-queued: #FBBF24;
  --state-working: #38BDF8;
  --state-done: #4ADE80;
  --state-failed: #F87171;

  /* Brand gradient: used by rendered previews and the one headline field, never chrome */
  --brand-from: #D946EF;
  --brand-to: #FB923C;

  /* Type */
  --font-ui: 'Fira Sans', system-ui, sans-serif;
  --font-data: 'Fira Code', ui-monospace, monospace;
  --font-display: 'Anton', 'Fira Sans', sans-serif;
  --text-12: 0.75rem; --text-13: 0.8125rem; --text-14: 0.875rem;
  --text-16: 1rem; --text-20: 1.25rem; --text-26: 1.625rem;

  /* Space (4 px base, dense) and controls */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-6: 24px; --space-8: 32px;
  --control-h: 36px;
  --row-h: 44px;

  /* Radius by role */
  --radius-media: 6px;
  --radius-control: 10px;
  --radius-panel: 14px;
  --radius-pill: 9999px;

  /* Motion */
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --dur-fast: 120ms; --dur-base: 200ms; --dur-settle: 240ms;
}

@media (pointer: coarse) { :root { --control-h: 44px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
::selection { background: var(--accent-wash); color: var(--text-primary); }
```

Contrast is measured, not assumed (WCAG relative luminance):

| Pair | Ratio |
|---|---|
| Primary text on Plate | 16.3:1 |
| Secondary text on Plate | 8.5:1 |
| Tertiary text on Plate / Platen | 5.2:1 / 4.8:1 |
| Magenta on Plate | 7.5:1 |
| Dark text on Magenta fill | 7.5:1 |
| Amber / Cyan / Green / Red on Plate | 11.0 / 8.6 / 10.5 / 6.6:1 |

---

## 8. Pass four: bolder

bolder answers one question: is any part of the design flat in a way the first three passes did not fix? It amplifies one target and leaves everything else alone.

**Verdict: needed, for exactly one surface, the Review workspace.** The Inbox, Pipeline, Pages, Exports and Settings stay restrained; they are operate surfaces and should disappear into the task. Nothing else is made bolder, and no color, font or primitive is added to the system.

**Why that surface reads flat.** After passes one to three, Review is a correct but ordinary form: two columns of text fields. It is the place where the human actually works, it is where the brand's own vocabulary (the headline card) matters most, and it currently opts out of everything the product makes.

**The amplification (amplify what the system already owns):**

1. **The preview is the screen.** Source on the left and the modeled result on the right each take roughly 40 percent of the viewport width, at true aspect ratio, playable in place. Fields collapse into a slim strip beneath the result.
2. **The headline field is the headline.** The translated headline is edited in Anton, in capitals, with the `*highlight*` words shown in the brand gradient as the user types, at the size the renderer will use. What you type looks like what will be posted. This is the only place in the interface where the display face and the gradient appear outside a rendered preview, and it is where they earn it.
3. **One decisive action.** "Aprovar e exportar" is the only filled accent control on the screen. Everything else is quiet text or outline.
4. **Its own rhythm.** The rest of the product is dense and even; Review is the one screen with generous space around the two previews, so it reads as the peak of the flow.

**Skeleton test.** With all copy removed, the screen is two tall frames facing each other with one wide field under the right frame and one filled control. That reads as "compare, fix, approve" without a word.

**Not done, deliberately.** No animation on the previews beyond the native video controls. No second accent color. No oversized stats. No decorative gradients on buttons, backgrounds or text anywhere else (gradient text is banned as chrome; the headline field is a WYSIWYG preview of a rendered artifact, not decoration).

Handoff back to polish: the Review screen goes through the section 4.2 bar like every other screen.

---

## 9. Implementation notes for Phase 8

- **Fonts**: `@fontsource/fira-sans`, `@fontsource/fira-code`, `@fontsource/anton` imported in `main.tsx`; no network font requests.
- **Structure**: keep the existing `components/`, `features/`, `pages/` layout; add `features/pipeline`, `features/inbox`, `features/review`, `features/pages`; tokens live only in `styles/tokens.css`.
- **Data**: one polling hook per list with visibility pause; types mirror the API schemas.
- **Icons**: one library, one stroke weight (Lucide, already the v2.1 choice). No emoji as icons.
- **Testing hooks**: every action and lane carries a stable `data-testid`; end-to-end tests drive the real pages against a backend with stubbed downloaders, transcriber and translator, and assert on the rendered output files.
- **Lint**: no `outline: none` without a `:focus-visible` replacement, no hex in component CSS, no `font-size` under 12 px.
- **Open decisions** for the user: whether the UI stays pt-BR only or gets an English pack; whether Discover keeps its own top-level tab once the Inbox has a manual search box.

# Underfind — Design System & UI Architecture (`DESIGN.md`)

> **Design Engineering Doctrine**: Crafted with Emil Kowalski's principles of tactile feedback, invisible compound details, custom cubic-bezier physics, and bespoke dark-mode minimalism.

---

## 1. Executive Summary & Design Vision

Underfind is transitioning from a standard analytical utility into a **bespoke creative intelligence workspace**. 

This document defines the complete Design System and interface architecture synthesized from the **4 visual references** provided:
1. **Reference 01 (Donezo SaaS Dashboard)**: Modular metric widgets, clean visual hierarchy, KPI cards with directional indicators, and clean separation of concerns — rendered in refined dark slate neutrals rather than light/green palettes.
2. **Reference 02 (Real Estate Listing Cards)**: High-craft media cards featuring immersive thumbnails, floating glassmorphic pills, multi-parameter spec badges (views, likes, comments, subscriber base), and instant-action footers.
3. **Reference 03 (Applicants & Talent Kanban)**: A dedicated **Quadro de Ideias (Ideas Board)** enabling creators to select, organize, tag, and advance outlier videos from backlog to production.
4. **Reference 04 (Fluid Pill Design System)**: Bespoke fluid pill buttons, segmented toggle switches, rounded filter chips, and origin-aware dropdowns that feel organic and custom-engineered rather than borrowed from an off-the-shelf component library.

---

## 2. Emil Kowalski Review & Comparison Matrix

In accordance with Emil Kowalski’s Design Engineering philosophy, every interaction and visual choice is held to strict physical standards:

| Before | After | Why |
| :--- | :--- | :--- |
| Cramped, generic search box with raw browser buttons | Fluid rounded command pill with inset Lucide search icon, focus glow, and tactile trigger | Search is the primary entry vector; it must feel inviting and responsive |
| Standard video cards with small generic meta tags | Real-estate inspired cards with floating viral ratio pill, media overlay, and structured specs chips (views, likes, comments) | Scannability: creators need to instantly digest engagement density in under 1 second |
| Static button click with no motion feedback | `:active { transform: scale(0.97); }` with `cubic-bezier(0.23, 1, 0.32, 1)` | Tactile confirmation: pressable elements must feel alive and acknowledge user input |
| Generic modal with intrusive AI prompts and MedPy cuts | Focused media theater displaying playable iframe, engagement KPIs, keywords/tags, and full description | Delivers what creators actually need: studying the footage, engagement metrics, and SEO tags |
| Unstyled kanban lists | Multi-column Idea Board inspired by talent candidate trackers, with counts, creator avatars, and status badges | Gives creators an organized pipeline to save high-performing outliers without losing track |
| Floating status tags ("SQLite Cache Active", "API Connected") | Clean, centered navigation bar with zero clutter | Eliminates visual noise and keeps the focus 100% on discovery |

---

## 3. Design Tokens & Color Palette

### 3.1 Color Palette (Dark Neutral Slate / Zinc)
We reject uncurated, harsh blacks or oversaturated primaries in favor of deep, layered neutrals:

```css
:root {
  /* Canvas & Surfaces */
  --bg-canvas: #09090b;             /* Pure deep canvas background */
  --bg-surface: #121215;            /* Primary card & component surface */
  --bg-surface-elevated: #18181b;   /* Raised cards, dropdowns & toolbars */
  --bg-surface-hover: #222226;      /* Hover states */
  --bg-input: #151518;              /* Form inputs & command bars */

  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.07);
  --border-medium: rgba(255, 255, 255, 0.12);
  --border-focus: rgba(255, 255, 255, 0.35);

  /* Typography */
  --text-primary: #fafafa;
  --text-secondary: #a1a1aa;
  --text-tertiary: #71717a;
  --text-disabled: #52525b;

  /* Accent & Status Indicators */
  --accent-primary: #ffffff;
  --accent-contrast: #09090b;
  --indicator-viral: #10b981;
  --indicator-viral-bg: rgba(16, 185, 129, 0.10);
  --indicator-viral-border: rgba(16, 185, 129, 0.25);

  --indicator-blue: #3b82f6;
  --indicator-blue-bg: rgba(59, 130, 246, 0.10);
  --indicator-purple: #a855f7;
  --indicator-purple-bg: rgba(168, 85, 247, 0.10);

  /* Border Radii (Fluid Pill Standard) */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 18px;
  --radius-xl: 24px;
  --radius-full: 9999px;
}
```

### 3.2 Motion Physics & Custom Easing Curves
Built-in CSS curves like `ease-in` or default `ease` feel sluggish. Emil Kowalski curves provide instant responsiveness:

```css
:root {
  /* Fast UI Entrance / Feedback */
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);

  /* On-screen morphing / spatial repositioning */
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);

  /* Drawers & Sheet Panels */
  --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
}
```

---

## 4. Component Design System & Architectural Adaptations

### 4.1 Component A: Centered Command Navigation
* **Placement**: Fixed sticky header, fully centered horizontally (`justify-content: center`).
* **Structure**: Pill-shaped container (`border-radius: 9999px`) with frosted glass backdrop blur (`backdrop-filter: blur(14px)`).
* **Tabs**:
  - `Dashboard`: Entry console with top search bar, KPI metrics, and high-performance video showcase.
  - `Descobridor de Shorts Virais`: High-granularity breakout miner with subscriber and viral ratio filters.
  - `Trending`: Real-time YouTube acceleration formats.
  - `Quadro de Ideias`: Kanban ideas pipeline to save, tag, and organize selected concepts.
  - `Explorer`: Parametric multi-filter query engine.
  - `MCP`: Local LLM and external AI connector hub.
* **Physics**: Active scale physics `transform: scale(0.97)` on click.

---

### 4.2 Component B: Modern KPI Cards (Reference 01 Adapted)
Inspired by the Donezo SaaS Dashboard reference, our metrics row breaks away from boring text blocks:
* **Card Frame**: Sleek elevated surface with rounded corners (`border-radius: 18px`), subtle 1px border.
* **Header**: Label on the left, directional arrow / status pill on the right (`↗ DESTAQUE`).
* **Value**: Large bold typography (`font-size: 2rem; font-weight: 700; letter-spacing: -0.03em;`).
* **Context**: Clear description below explaining what the number means in plain creator terms.

```
┌────────────────────────────────────────────────────────┐
│ Maior Multiplicador Viral                  [+47.4x ↗]  │
│                                                        │
│ +47.4x                                                 │
│ Proporção de visualizações sobre o número de inscritos.│
└────────────────────────────────────────────────────────┘
```

---

### 4.3 Component C: Media Spec Cards (Reference 02 Adapted)
Adapted directly from the luxury listing card UI:
1. **Media Hero**:
   - 16:9 thumbnail with rounded corners (`border-radius: 16px`).
   - Floating top-left pill: `+47.4x Viral Ratio` (emerald badge with glassmorphism).
   - Floating top-right bookmark button: Click to directly save video to **Quadro de Ideias**.
2. **Metadata Spec Pills** (Adapted from beds/baths into creator metrics):
   - `👁️ 1.2M views`
   - `❤️ 84.5K curtidas`
   - `💬 1,420 comentários`
   - `⏱️ 42s duração`
3. **Card Body**:
   - Video title clamped to 2 lines.
   - Channel author line with subscriber count.
4. **Card Action**:
   - Clicking opens the **Video Detail Modal** (Playable YouTube player, full stats, keywords/tags, and full description).

---

### 4.4 Component D: Quadro de Ideias / Ideas Board (Reference 03 Adapted)
Adapted from the Talent / Candidate Kanban reference:
* **Header Bar**: Search ideas, filter by niche or tag, and "+ Nova Ideia" button.
* **Three Structured Stages**:
  1. **Backlog / Salvos**: Outlier videos discovered and bookmarked for review.
  2. **Em Roteirização**: Concepts currently being adapted into creator scripts.
  3. **Pronto para Gravação**: Finalized concepts ready for shooting.
* **Idea Card Anatomy**:
  - Outlier multiplier badge (`+47.4x Outlier`).
  - Creator channel avatar & title.
  - Video title.
  - Custom creator notes / target keywords.
  - Action button to advance card to next stage.

---

### 4.5 Component E: Fluid Pill Controls & Buttons (Reference 04 Adapted)
Every button and interactive control follows Emil Kowalski's fluid pill doctrine:
* **Segmented Controls**:
  - Outer pill track: `#121215` with subtle border.
  - Active segment: `#18181b` with 1px border and crisp contrast text.
* **Action Buttons**:
  - Primary button: Solid white `#ffffff` with black text, full rounded pills (`border-radius: 9999px`), padding `0.7rem 1.4rem`.
  - Secondary button: `#18181b` with border `rgba(255, 255, 255, 0.12)`, text `#fafafa`.
  - Press feedback: `transform: scale(0.97)` on `:active`.
  - Zero emojis: All icons are pure SVG vector paths (Lucide style).
* **Dropdowns & Popovers**:
  - Transform origin anchored to the trigger position (`transform-origin: top left` or trigger alignment).
  - Entrance animation: `scale(0.96); opacity: 0` to `scale(1); opacity: 1` over 160ms with `var(--ease-out)`.

---

### 4.6 Component F: Video Detail Modal (No Hook/MedPy Bloat)
Per user request, the modal is dedicated strictly to what creators want to inspect when clicking a video:
1. **Playable Video Player**: Embedded 16:9 YouTube iframe player with clean rounded borders.
2. **Key Engagement Row**:
   - Visualizações (Views)
   - Curtidas (Likes)
   - Comentários (Comments)
   - Multiplicador Viral (+Nx)
3. **Palavras-chave e Tags**:
   - Horizontal wrapping flex container of `#tags` used by the video author for SEO.
4. **Descrição do Vídeo**:
   - Complete raw video description with clean typography and scrolling viewport.
5. **Direct Actions**:
   - "Copiar Link" button.
   - "Assistir no YouTube ↗" button.

---

## 5. Technical Implementation & Verification Plan

### Phase 1: Design Specification Approval (Current)
- Deliver `DESIGN.md` artifact incorporating all 4 reference images and Emil Kowalski design tokens.
- Review design engineering tokens and component anatomy with user.

### Phase 2: Design System Integration (`index.css`)
- Inject fluid pill variables, custom easing curves, card spec pills, and Kanban styles.
- Verify zero emoji footprint across all UI components.

### Phase 3: Component Harmonization
- Update `VideoCard.tsx` to reflect Reference 02 listing specs (views, likes, comments pills, and bookmark button).
- Update `DashboardView.tsx` with Reference 01 metric cards.
- Refine `IdeasView` (Quadro de Ideias) based on Reference 03 candidate board layout.
- Revalidate button active scale physics (`:active { transform: scale(0.97); }`).

### Phase 4: Build & Execution Validation
- Compile bundle via `npm run build`.
- Validate all routes and interactions via browser / local HTTP requests.
- Provide Before / After review table confirming all requirements.

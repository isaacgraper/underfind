# Post Modeling Workflow

Local-first automation for any niche: find international posts that work (reels, shorts, photo posts, carousels), model them for your page (same idea and media, your language, your brand tag and layout; not a copy of their branding), render reels / image posts / carousels, and hand the finished files to the batch publisher. GTA VI is the first niche preset (`config/niches/gta6.yaml`); any other niche is a new YAML file.

## 0. Output formats (from the reference posts)

| Layout | When | Look |
|---|---|---|
| `headline_card` | source has a headline band (big text across the top or bottom) | source band cropped away; media on top; black card below with the page's brand tag between gradient lines and the translated headline in a condensed font, dates/money/numbers in a gradient (`*highlight*` markup, editable in review) |
| `letterbox` | memes, infographics, AI art with labels baked in | media centered on black, untouched |
| `full_bleed` | vertical video (trailers, gameplay) | video fills the frame, translated subtitles burned in, dub audio when enabled |

`auto` (default) picks per post. Each page chooses its outputs: `reel` (9:16 mp4; images get a slow zoom and the page's audio bed or silence, carousels play image by image), `post` (4:5 jpg of the cover), `carousel` (4:5 jpg per image, card on the cover). The profile picture and name above posts are the platform's own interface, not part of the media.

## 1. The workflow

```
 SOURCE ──► FILTER ──► DOWNLOAD ──► TRANSCRIBE ──► TRANSLATE ──► VOICE ──► RENDER ──► EXPORT ──► PUBLISH
   │          │            │             │              │           │          │          │          │
 find GTA   score +     yt-dlp        Whisper       OPUS-MT +     subtitles  ffmpeg     manifest   batch
 VI videos  dedup                                   glossary     or dub     template   + mp4      publisher
                                                   ▲ REVIEW                ▲ REVIEW
```

| # | Stage | Input → Output | Tool | Job status after | Phase |
|---|---|---|---|---|---|
| 1 | **Source** | seed pages + keywords → candidate videos | IG Business Discovery, YouTube API, vidIQ outlier search, manual links | `found` | 2 (manual links: done) |
| 2 | **Filter** | candidates → ranked shortlist | velocity (views/hour), viral ratio, GTA VI relevance, used-source registry | `found` / `discarded` | 2 (registry: done) |
| 3 | **Download** | URL → `source.mp4`, audio, metadata, perceptual hash | yt-dlp, ffmpeg | `downloaded` | 3 (done) |
| 4 | **Transcribe** | audio → timestamped transcript + language, on-screen text flag | faster-whisper, OCR sampling | `transcribed` | 3 (done) |
| 5 | **Assign page** | job → target page(s) | page profiles | (page set) | done |
| 6 | **Translate** | transcript → timing-fit translated segments + localized caption/hashtags | local OPUS-MT on CTranslate2 (optional: LLM chain) + GTA VI glossary (Lucia, Jason, Vice City, Leonida stay untranslated) | `translated` | 4 (done) |
| 7 | **Voice** | translation → burned subtitles or dubbed track | ASS subtitles / Piper TTS (local) | `voiced` | 4 (done) |
| 8 | **Render** | video + page identity → 1080×1920 final | ffmpeg + Pillow (avatar, name, @ on top, video below) | `rendered` | 5 |
| 9 | **Export** | rendered files → export folder with `manifest.json` + `caption.txt`, optional webhook | folder drop (+ `EXPORT_WEBHOOK_URL`) | `exported` | 6 (done) |
| 10 | **Publish** | manifest → post | batch publisher (external) | — | external |

### Storage layout

```
data/sources/{platform}_{id}/source.mp4, audio.wav, frame.jpg, transcript.json, meta.json (yt-dlp info)
data/jobs/{job_id}/translation.json, subs.ass, dub.wav, final.mp4, manifest.json
```

Source-level artifacts are shared by every job (page) created from the same video, so a source is downloaded and transcribed once.

### Export folder (what the batch publisher reads)

```
data/exports/                      (EXPORT_DIR)
  exports.csv                      one row per export: time, job, page, deliverables, folder, caption line, source url
  <page handle>/
    20260930-120000_<job id>/      appears only when complete (written under .tmp_* and renamed)
      reel.mp4  post.jpg  carousel_01.jpg ...
      caption.txt                  full post text
      manifest.json
```

```json
{
  "schema_version": 1,
  "job_id": "3f9a1c2b7e01",
  "exported_at": "2026-09-30T12:00:00+00:00",
  "folder": "data/exports/gtavibrasil/20260930-120000_3f9a1c2b7e01",
  "page": {"handle": "gtavibrasil", "display_name": "GTA VI Brasil", "language": "pt-BR"},
  "language": "pt-BR",
  "deliverables": [
    {"kind": "reel", "files": ["reel.mp4"]},
    {"kind": "post", "files": ["post.jpg"]},
    {"kind": "carousel", "files": ["carousel_01.jpg", "carousel_02.jpg"]}
  ],
  "caption": "O trailer 3 chegou 🔥 Qual detalhe você viu?\n\n📸 @gta6news\n\n#gta6 #gtavi",
  "caption_body": "O trailer 3 chegou 🔥 Qual detalhe você viu?",
  "hashtags": ["#gta6", "#gtavi"],
  "headline": "SE SEU FILHO NASCER EM 19 DE NOVEMBRO DE 2026...",
  "duration_seconds": 8.0,
  "local_ai": true,
  "source": {"platform": "instagram", "url": "https://www.instagram.com/p/...", "author": "gta6news", "published_at": "..."},
  "source_metrics": {"views": 900000, "likes": 70000, "comments": 1200, "followers": 250000}
}
```

The page's `caption_footer` is appended to every caption and fills `{source_author}`, `{source_url}` and `{platform}` (credit lines). With `EXPORT_WEBHOOK_URL` set, each manifest is also POSTed there (publisher API, n8n webhook); a failed webhook is retried without exporting the folder twice.

## 2. Automation

### Triggers

| Job | Frequency | What it does |
|---|---|---|
| **Niche scan** | `scan.every_minutes` per niche (worker) | every scanner of the niche runs, posts are scored into the candidates inbox; with `auto_queue` the best become jobs for the niche's pages |
| **Keyword search** | part of each niche scan | YouTube Shorts search over keywords x regions, `youtube_keyword_searches` per scan (100 units each), rotating pairs across scans |
| **Outlier discovery** | daily (Claude routine / n8n) | vidIQ outlier search → `POST /api/candidates` (scored like scanned posts); good pages go into the niche's seed list |
| **Pipeline worker** | continuous | claims jobs and runs each stage until a review gate |
| **Export** | every worker poll | exports approved `rendered` jobs into the publisher folder (+ webhook) |
| **Metrics sync** | daily | pulls performance of published posts → adjusts scoring weights |

### Review gates

1. **Pick** (optional): auto-accept candidates above a score threshold, queue the rest for a click.
2. **Translation review** (on at the start): side-by-side source/translation, edit, approve.
3. **Render approval**: preview the outputs (`GET /api/jobs/{id}/files/{reel|post|carousel_01}`), then `POST /api/jobs/{id}/render/approve` or `python app.py approve <job>`; to redo, move the job back (`PATCH /status`). Pages with `auto_approve_render` skip it.

Automation levels, switchable per page:

- **Level 1:** everything automatic except gates 2 and 3. Starting point.
- **Level 2:** skip gate 3 once render quality is proven.
- **Level 3:** skip gate 2 too for pages where translation has been reliable. Fully hands-off.

### Where it runs

| Option | Scheduler | Worker | Best when |
|---|---|---|---|
| **A. In-app (default)** | APScheduler inside FastAPI | in-app worker (`python app.py worker` or `PIPELINE_WORKER_ENABLED=true`) | single machine/VPS, one Docker container |
| **B. n8n** | n8n cron nodes calling `/api/...` endpoints | still the in-app worker | the batch publisher already lives in n8n |
| **C. Claude routine** | scheduled Claude session | calls vidIQ MCP → `POST /api/jobs` | outlier discovery through vidIQ |

Chosen setup: **A for everything, plus C for daily vidIQ discovery.** B only replaces the folder hand-off if the publisher runs in n8n.

### Failure handling

- A stage error retries with exponential backoff (3 attempts), then the job goes to `failed` with the failing stage stored; it can be retried from that stage.
- Permanent errors (private/removed video, login wall) fail immediately without retries.
- YouTube quota exhausted → keyword scans pause until midnight Pacific; IG/TikTok continue.
- Duplicates are rejected before download (same URL/ID) and right after download (perceptual hash match against another platform's used source → `discarded`).

### Niche config driving the scans

```yaml
# niches/gta6.yaml
include: ["gta 6", "gta vi", "vice city", "lucia", "jason", "leonida", "rockstar trailer"]
exclude: ["gta 5", "gta v", "gta online", "mod", "fivem", "roleplay"]
seed_pages:
  instagram: ["<page handle>"]
  tiktok: ["<page handle>"]
  youtube_channels: ["<channel id>"]
regions: ["US", "GB", "ES", "MX", "DE", "FR"]
min_score: 70
max_duration_seconds: 90
pages: ["gta6br", "gta6es"]   # auto-assign targets
```

### A day in automated mode

1. **06:00:** scans find 40 candidates → filter keeps 12 (dupes, off-topic, low score dropped).
2. **06:05–06:30:** worker downloads, transcribes, translates for 2 pages → 24 jobs at translation review.
3. **Review (~10 min):** approve/edit 24 translations.
4. Worker voices and renders → render approval (or skipped at Level 2).
5. The worker exports approved jobs: files + `caption.txt` + `manifest.json` in the publisher folder.
6. The batch publisher picks them up, schedules and posts.
7. Overnight: metrics sync scores yesterday's posts → ranking adjusts for tomorrow's scans.

## 3. Sourcing

Each niche YAML (`config/niches/<name>.yaml`) drives its scans:

```yaml
seed_pages:
  instagram: [somepage]        # Graph API Business Discovery (IG_GRAPH_USER_ID + IG_GRAPH_TOKEN), else gallery-dl + cookies
  tiktok: [someuser]           # yt-dlp flat listing
  youtube_channels: ["@handle"] # uploads playlist, ~4 quota units per channel
keywords: {include: [...], exclude: [...]}  # include drives YouTube keyword search and relevance; exclude rejects
regions: [US, BR]
scan: {every_minutes: 120, max_age_days: 7, max_duration_seconds: 120, per_source_limit: 12, youtube_keyword_searches: 2}
scoring: {weights: {velocity: 0.4, ratio: 0.3, engagement: 0.2, relevance: 0.1}, target_views_per_hour: 5000, target_ratio: 10, target_engagement: 0.08, min_score: 60}
auto_queue: {enabled: false, max_per_scan: 5, mode: subtitles}
```

| Scanner | Source | Cost / needs |
|---|---|---|
| `youtube_keywords` | Shorts search, keywords x regions, rotated across scans | 100 quota units per search; `YOUTUBE_API_KEY` |
| `youtube_channel:<id>` | latest uploads of a seed channel | ~4 units; `YOUTUBE_API_KEY` |
| `instagram:<user>` | Business Discovery (official, free) | your professional account id + token; no view counts (estimated from likes) |
| `instagram:<user>` (fallback) | gallery-dl profile listing | login cookies (`YTDLP_COOKIES_FILE`) |
| `tiktok:<user>` | yt-dlp flat profile listing | sometimes cookies |
| `external` | `POST /api/candidates` (vidIQ via Claude routine, n8n, ...) | — |

Scoring (0-100): **velocity** (views per hour since posting), **ratio** (views / followers), **engagement** ((likes + comments) / views) and **relevance** (niche keywords; seed pages and external picks count as relevant), each log-scaled against the niche's targets and weighted. Exclude keywords, age and duration limits, missing keywords (search results only) and scores under `min_score` reject automatically (`auto:` reasons); sources already used by a job are skipped. A rescan refreshes metrics but never undoes a queue or a hand rejection.

Candidates inbox: `GET /api/candidates?niche=gta6` (best first), `POST /api/candidates/{id}/queue` (one job per page of the niche, or chosen pages), `POST /api/candidates/{id}/reject`. CLI: `python app.py scan [niche] [--dry-run]`, `python app.py queue <candidate id> [--page N]`. The worker runs due scans on each poll (`SOURCING_ENABLED=false` turns that off).

## 4. Pending live verification

Built and covered by automated tests (real ffmpeg on generated clips; mocked network services), but not yet run against the real services because the development environment's network blocks them:

| Step | Service | Blocked host |
|---|---|---|
| Download | yt-dlp | www.youtube.com, www.instagram.com, www.tiktok.com |
| Transcribe | faster-whisper model download | huggingface.co |
| Translate | local OPUS-MT model download (once) | argos-net.com (index on raw.githubusercontent.com is reachable) |
| Dub | Piper voice download (once) | huggingface.co |

To verify on a machine with open network access (no API keys needed):

```bash
python scripts/smoke_live.py --check
python scripts/smoke_live.py "https://www.youtube.com/shorts/<id>" --language pt-BR --mode subtitles
python scripts/smoke_live.py "https://www.instagram.com/reel/<code>/" --language pt-BR --mode dub --workdir data/smoke
```

The script uses its own temp database and workspace (never `data/cache.sqlite3`), auto-approves the translation, and prints status, events, artifacts, caption and the first translated lines. Things to check by hand: Instagram/TikTok need `YTDLP_COOKIES_FILE`; Whisper model size vs CPU speed (`WHISPER_MODEL`); dub timing in `data/smoke/jobs/<id>/dub.json` (speedups near 1.35x mean the translation is still too long).

## 5. AI model usage: local only

Every AI step runs on the local CPU with no API, no key and no usage limits. Models download once into `data/models/` (or ahead of time with `python app.py models`), after which the pipeline runs offline.

| Step | Model | Runtime | Size / speed |
|---|---|---|---|
| Transcribe | Whisper (`WHISPER_MODEL`, default `small`) | faster-whisper (CTranslate2, int8) | ~0.5 GB; roughly real-time or faster on CPU |
| Translate | OPUS-MT (Marian, same family as Firefox's offline translation) per language pair, from the Argos Translate index | CTranslate2 int8 + SentencePiece | ~100 MB per pair; milliseconds per line |
| Dub voice | Piper (`pt_BR-faber-medium`, `es_MX-ald-medium`, ...) | ONNX Runtime | ~60 MB per voice; faster than real-time |
| On-screen text (optional) | RapidOCR | ONNX Runtime | small |

Translation details: `pt-BR` pages use the Brazilian `pb` model when published, then `pt`; pairs without a direct model pivot through English (es→en→pt); glossary terms are masked so the model copies them verbatim; same-language sources pass through untouched.

Limits of local translation versus an LLM: literal phrasing (less slang adaptation), no condensing of lines that overrun their time slot (subtitles wrap to 2 lines, dubs speed up to 1.35×), and the post caption is translated rather than rewritten. The review gate is where these get fixed by hand.

### Switching between local and online

| Level | Control | Default | Effect |
|---|---|---|---|
| Server / worker | `--local` / `--online` flag on `python app.py`, `serve`, `worker`, `run` (or `AI_MODE` env) | `local` | `local` is a hard lock: nothing online, whatever pages/jobs say. `online` lets the settings below decide. |
| Page | "Somente IA local" checkbox (`local_only`) | checked | Unchecked pages may use online models when the server runs `--online`. |
| Job | same checkbox in the "Localizar" panel of the video modal, `local_only` on `POST /api/jobs`, `PATCH /api/jobs/{id}/local-only` | inherits page | Overrides the page for one job (`null` inherits again). |

Online means: translation through the free LLM chain (NVIDIA → Atria → OpenRouter in `config/llm.yaml`; Claude only as an explicit role) with condensing of lines that overrun, and edge-tts voices for dubs. Each `translation.json` records `local: true/false` and the model that produced it; `dub.json` records the voice backend. `GET /api/health` reports the server's `ai_mode`.

## 6. Build phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Jobs, used-source registry, quota | done |
| 3 | Download + transcribe (+ images, carousels, OCR, headline) | done |
| 4 | Translate + voice (local by default) | done |
| 5 | Render: headline card / letterbox / full bleed as reel, post, carousel | done |
| 6 | Export folder + manifest + webhook, render review gate | done |
| 7 | Automated sourcing: niche seed pages and keywords, scoring, scheduled scans | done |
| 8 | Frontend refactor (pipeline board, candidates inbox, review screens, pages/templates) + end-to-end tests through the real UI | done |

Phase 8 details: the UI lives in `underfind/frontend/src/{app,ui,views,theme,api}` (DESIGN.md), `npm run lint:design` enforces the design rules, and `npm run e2e` builds the UI and drives it with Playwright against `underfind/backend/e2e/server.py` (real API, worker, ffmpeg render and exporter; fake download, Whisper, translation, OCR and scanners).

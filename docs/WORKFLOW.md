# GTA VI Localization Workflow

Find international GTA VI reels/shorts, translate them into each target page's language, render them in the "profile picture + name on top, video below" format, and hand the finished files to the batch publisher.

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
| 9 | **Export** | final → `final.mp4` + `manifest.json` in the export folder | file drop or publisher API | `exported` | 6 |
| 10 | **Publish** | manifest → post | batch publisher (external) | — | external |

### Storage layout

```
data/sources/{platform}_{id}/source.mp4, audio.wav, frame.jpg, transcript.json, meta.json (yt-dlp info)
data/jobs/{job_id}/translation.json, subs.ass, dub.wav, final.mp4, manifest.json
```

Source-level artifacts are shared by every job (page) created from the same video, so a source is downloaded and transcribed once.

### Manifest handed to the publisher

```json
{
  "job_id": "3f9a1c2b7e01",
  "page": "gta6br",
  "video": "data/jobs/3f9a1c2b7e01/final.mp4",
  "caption": "O mapa de GTA VI é MAIOR do que parecia ...",
  "hashtags": ["#gta6", "#gtavi", "#vicecity"],
  "source": {"platform": "instagram", "url": "https://www.instagram.com/reel/...", "author": "@gta6news"},
  "duration_seconds": 34,
  "language": "pt-BR",
  "priority_score": 87.4
}
```

## 2. Automation

### Triggers

| Job | Frequency | What it does |
|---|---|---|
| **Seed page scan** | every 2h | Business Discovery pulls latest reels of each watched international GTA page → new `found` jobs |
| **Keyword scan** | every 4h | YouTube Shorts search over the GTA VI keyword list (~20 searches/day = 2,000 units, well under the 10k quota) |
| **Outlier discovery** | daily | vidIQ outlier search on IG/TikTok → proposes new pages for the seed list (approved manually) |
| **Pipeline worker** | continuous | claims jobs and runs each stage until a review gate |
| **Export sweep** | every 30 min | moves approved `rendered` jobs to `exported`, drops files in the publisher folder |
| **Metrics sync** | daily | pulls performance of published posts → adjusts scoring weights |

### Review gates

1. **Pick** (optional): auto-accept candidates above a score threshold, queue the rest for a click.
2. **Translation review** (on at the start): side-by-side source/translation, edit, approve.
3. **Render approval**: preview the final file, approve or reject.

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
5. Export sweep drops the approved `final.mp4` + `manifest.json` files into the publisher folder.
6. The batch publisher picks them up, schedules and posts.
7. Overnight: metrics sync scores yesterday's posts → ranking adjusts for tomorrow's scans.

## 3. Sourcing options

| Tool | Cost | Gives | Limits |
|---|---|---|---|
| Instagram Graph API (Business Discovery) | free | recent posts of any public business/creator page by @: caption, permalink, likes, comments, timestamp, media URL | needs own IG professional account + FB page + Meta app token |
| yt-dlp | free | reliable single Reel/TikTok/Shorts download + metadata | profile listing unreliable on IG, intermittent on TikTok |
| Instaloader | free | profile listing + download | needs a logged-in account, which IG rate-limits/flags |
| Apify | ~$5/month free credit | Reel/TikTok scrapers with view counts | low volume on free tier |
| vidIQ (via Claude MCP) | vidIQ plan credits | IG/TikTok outlier search, profile reels | only reachable from a Claude session/routine |

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

Opt-in online backends, never used unless configured: `TRANSLATION_BACKEND=llm` (free LLM chain NVIDIA → Atria → OpenRouter in `config/llm.yaml`, Claude only as an explicit role) and `TTS_BACKEND=edge` (edge-tts).

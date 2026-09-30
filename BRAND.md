# Underfind: brand and product

Everything the product does, how to say it, and how it looks. Built from the repository as of this commit and the design decisions in [DESIGN.md](DESIGN.md).

---

## 1. The pitch

**Find what's under-found. Model it for your page. Keep it on your machine.**

*Pt-BR:* **Ache o que está subestimado. Modele para a sua página. Tudo na sua máquina.**

Underfind is a local-first studio for creators who run pages. It watches the niches you care about, finds posts that beat the size of the account that made them, and rebuilds each one for your page: your language, your brand tag, your layout, your caption. You review the result in one screen. Approved posts land in a folder, with a manifest, ready for whatever publishes for you.

It is not a reposter. It takes the idea and the media that proved it works, then reworks the headline, caption, language and framing for your niche and brand, with a credit line when you want one.

It runs on your computer. Transcription, translation, voices and text recognition all use models that live on your disk. No account, no API key, no per-post cost, and nothing leaves the machine unless you switch online mode on for a page.

### One line, 25 words, 60 words

- **One line:** A local-first studio that finds posts working abroad and models them for your own page.
- **25 words:** Underfind scans your niche for posts that outperform their account, translates and re-brands them on your machine, and hands finished reels and posts to your publisher.
- **60 words:** Underfind is a local-first studio for creators who run pages. It scans your niche for posts that outperform the size of their account, downloads them, translates and re-brands them with models running on your own computer, and renders reels, feed posts and carousels in your layout. You approve in one screen; the files land in a folder with a manifest for your publisher.

### The name

*Under-found.* The product's core insight is that the best material is not the viral post everybody has already seen. It is the post that earned far more reach than the account behind it should have, the outlier from a small page. That is what the scoring looks for (views against followers, views per hour, engagement) and it is what the name says. Always written **Underfind**, capital U, one word. The wordmark is set lowercase in the interface top bar: **underfind**.

---

## 2. Who it is for

| | |
|---|---|
| **Primary** | A solo creator running one or several pages (for example a Brazilian GTA VI news page, a Spanish one, a cars page) who models posts from international pages into their own language. |
| **Their problem** | Finding the right posts takes hours of scrolling; reworking each one (translate the headline, rebuild the card, write a caption, render the reel) takes another hour; doing it across languages and pages multiplies it. Tools that do it in the cloud charge per post and keep the media. |
| **Their job with Underfind** | Decide, review, approve. Not scroll, download, retype, export. |
| **Not for** | Teams that need shared workspaces and permissions, or people who want a scheduler and analytics suite. Underfind makes the files; your publisher posts them. |

---

## 3. What it does: every feature

Organized by the path a post takes. Status is noted in section 4.

### 3.1 Find

| Feature | Detail |
|---|---|
| **Niches** | One YAML file per niche (`config/niches/<name>.yaml`): keywords to include and exclude, regions, seed pages per platform, hashtags, the never-translate glossary, scan schedule, scoring targets, auto-queue settings. GTA VI ships as the first preset; a new niche is a new file. |
| **Seed pages and channels** | Instagram (official Graph API Business Discovery with your own token, or gallery-dl with cookies), TikTok (yt-dlp), YouTube (channel uploads, about 4 quota units per channel). |
| **Keyword search** | YouTube Shorts search across keywords and regions, rotated across scans so every pair gets its turn within the per-scan search budget. |
| **External candidates** | `POST /api/candidates` accepts posts found elsewhere (vidIQ in a Claude routine, n8n, a bookmarklet) and scores them like scanned ones. |
| **Scoring, 0 to 100** | Views per hour, views against followers, engagement, keyword relevance; each log-scaled against per-niche targets and weighted. Hard rejects for excluded keywords, age, duration and minimum score. Likes-based view estimate where a platform hides views. |
| **Candidates inbox** | Scored posts, best first; queue one into jobs for every page of its niche (or chosen pages), reject, or let auto-queue do it. A rescan refreshes numbers and never undoes your decision. |
| **Scheduled scans** | The worker runs each niche's scan on its own interval; a dry run scores and prints without saving. |
| **Manual discovery** | The original YouTube tools (search with outlier filters, trending by region, viral ratio) remain for exploring by hand. |
| **Quota guard** | YouTube API units are reserved before each call against a daily budget in Pacific time, with retry on transient errors and a clear stop when spent. |

### 3.2 Bring in

| Feature | Detail |
|---|---|
| **Any link** | YouTube, Instagram and TikTok URLs, including TikTok share links. |
| **Videos, photo posts, carousels** | yt-dlp for video; gallery-dl for photo posts and carousels; automatic fallback when a link has no video. |
| **Local files** | Saved posts or your own media: `python app.py add img1.jpg img2.jpg --page 1`. |
| **Used-source registry** | A source with a job is never modeled twice, even when it reappears on another platform: a perceptual hash of the first frame catches cross-platform reposts. |
| **Metadata kept** | Title, caption, author, views, likes, comments, followers, duration, date. |

### 3.3 Understand

| Feature | Detail |
|---|---|
| **Transcription** | Whisper on your CPU (faster-whisper): language detection, word timestamps, speech-only segments. |
| **On-screen text** | Local OCR reads the text baked into images and video frames. |
| **Headline detection** | Finds the post's headline band (big text lines plus the small brand tag beside it) and whether it is a full-width band at the top or bottom, tolerant of OCR slips such as N0VEMBER. |

### 3.4 Model

| Feature | Detail |
|---|---|
| **Local translation** | OPUS-MT models on CTranslate2, on the CPU, milliseconds per line. Brazilian Portuguese uses the dedicated model; pairs without a direct model pivot through English. |
| **Glossary** | Names and titles that must never be translated (niche terms plus per-page additions) are protected so "Vice City" stays "Vice City". |
| **Caption and hashtags** | Caption translated; hashtags merged from the original post, the page's defaults and the niche's. A page footer can carry a credit line with `{source_author}`, `{source_url}`, `{platform}`. |
| **Headline** | Translated on its own; dates, money, percentages and large numbers are auto-marked as highlights for the gradient treatment. |
| **Timing budget** | Each translated line is limited to what can be read (subtitles) or spoken (dub) in its time slot. |
| **Optional online mode** | A free LLM chain (NVIDIA, then Atria, then OpenRouter) that adapts slang and condenses long lines, available only where both the server and the page allow it. Claude can be added as an explicit opt-in role. |

### 3.5 Review

Two human checkpoints, both skippable per page:

1. **Translation review.** Source and translation side by side; edit lines, headline, caption, hashtags; approve.
2. **Result review.** Preview the rendered reel, post or carousel; approve to export, or send the job back a stage.

### 3.6 Make

| Feature | Detail |
|---|---|
| **Three layouts** | **Headline card:** media on top, a black card below with the page's brand tag between gradient rules and the translated headline in a condensed face with gradient highlights, the source's own band cropped away. **Letterbox:** media centered, untouched, for memes, infographics and art with labels baked in. **Full bleed:** vertical video fills the frame. `auto` chooses per post. |
| **Three outputs** | **Reel** (9:16 video; images get a slow zoom and the page's audio bed or silence; carousels play image by image), **post** (4:5 image), **carousel** (4:5 image per slide with the card on the cover). Each page picks which it wants. |
| **Subtitles** | Styled from the page's template; `.ass` burned into video and `.srt` for platforms. |
| **Dubbing** | Local Piper voices per language, sped up to fit each slot (capped so speech stays natural), mixed over the original audio turned down. |
| **Templates** | Colors, gradients, fonts, card size, headline size limits, still duration, zoom, subtitle style. A bundled open-license condensed font ships by default. |

### 3.7 Hand off

| Feature | Detail |
|---|---|
| **Export folder** | One folder per post per page: the rendered files, `caption.txt`, and `manifest.json` with deliverables, full caption, hashtags, headline, source, metrics and whether only local AI was used. Written under a temporary name and renamed when complete so a watching publisher never sees half a post. `exports.csv` indexes everything. |
| **Webhook** | Optional POST of each manifest to your publisher's API or an n8n webhook; a failed delivery retries without exporting twice. |

### 3.8 Run it

| Feature | Detail |
|---|---|
| **Local by default** | `--local` is a hard lock: no job can reach an online model. `--online` lets pages and jobs opt out with a "Somente IA local" checkbox, checked by default. The top bar always shows which mode is on. |
| **Job pipeline** | Every post is a job moving through found, downloaded, transcribed, translated, voiced, rendered, exported (plus failed and discarded), resumable at each stage. Transient errors retry with backoff; permanent ones fail with a reason; a failed stage retries from where it stopped. |
| **Worker** | Polls and advances jobs in parallel, with per-job locks so nothing is processed twice; runs standalone or inside the server. |
| **CLI** | `add`, `run`, `approve`, `scan`, `queue`, `worker`, `serve`, `models`, plus the original `search`, `trending`, `blueprint`. |
| **API and MCP** | A documented HTTP API for everything above, and an MCP server so Claude Desktop, Cursor, ChatGPT and Gemini can search, blueprint and model from their own chat. |
| **Offline setup** | `python app.py models` downloads the translation models and voices once; after that the pipeline needs no network beyond the source platforms. |
| **Pages** | Each page profile holds its identity, language, niche, brand tag, outputs, footer, voice, template and its own switches for local only, auto-approve translation and auto-approve result. |

---

## 4. Status, stated plainly

| Area | State |
|---|---|
| Backend pipeline, API, CLI, worker, sourcing, render, export | Built and covered by 200+ automated tests, including real ffmpeg renders and the real OCR on the reference posts. |
| Live services (downloads from Instagram, TikTok, YouTube; Whisper, translation model and Piper voice downloads; the Graph API) | **Not yet exercised against the real services.** The build environment blocked those hosts, so they are tested with recorded responses. `scripts/smoke_live.py` is the first thing to run on an open network. |
| Frontend | Discovery screens exist from v2.1; the "Localizar" panel in the video modal is built. The pipeline board, inbox, review workspace and page management are Phase 8, designed in DESIGN.md. |
| Online mode | Built; free-provider chain untested against the real providers. |

---

## 5. How to say it

### Voice

Plain, specific, calm. A tool used in the evening by one person who knows their niche better than the tool does.

| Do | Don't |
|---|---|
| Say what happens: "Aprovar e exportar" | "Submit", "Confirm", "Continue" |
| Name the object once and keep it: candidato, post, página | "Item", "asset", "content piece" |
| Put the recovery in the error: "O Instagram pediu login. Configure o arquivo de cookies e tente de novo." | "Something went wrong", "Oops" |
| Teach in empty states: "Nenhum candidato ainda. Rode uma varredura ou cole um link para começar." | "Nothing here" |
| Claim what is measured: "200+ tests", "4 quota units" | "Blazing fast", "AI-powered", "revolutionary" |
| Say local when it is local, and say when it is not | Any cloud wording when online mode is off |

Do not write "AI-powered" as a selling point; the models are plumbing. The promise is the outcome (posts ready for your page) and the property (it stays on your machine).

### Words

| Use | For |
|---|---|
| **Modelar** / model | Taking a post's idea and rebuilding it for your page. Never "clone" or "copy". |
| **Candidato** | A scored post in the inbox. |
| **Página** | One of your accounts, with its language and brand. |
| **Nicho** | A topic with its sources, rules and glossary. |
| **Precisa de você** | Jobs waiting at a review checkpoint. |
| **IA local** | The default mode. |

### Taglines (pick by context)

- Find what's under-found. *(primary)*
- Model it. Don't repost it.
- Your niche, on your machine.
- One post in, every page out.
- Os melhores posts ainda não foram vistos por ninguém na sua língua. *(Pt-BR long form)*

---

## 6. Look and feel

Full reasoning in [DESIGN.md](DESIGN.md). The short version:

- **The post is the hero.** Previews at true aspect ratio, never a uniform thumbnail crop. The interface stays quiet around them.
- **Plum-tinted dark** (`#0F0D14` canvas, `#16131D` panels, `#1E1A28` raised), chosen from the use scene: one person, at a desk, at night, judging images and video.
- **One accent, one meaning.** Magenta `#E879F9` means "this needs you". Amber, cyan, green and red mean queued, working, exported, failed and nothing else.
- **The brand gradient** (`#D946EF` to `#FB923C`) belongs to the artifact: the highlighted words in rendered headlines. In the interface it appears once, in the review workspace's headline field, because that field is a live preview of the artifact.
- **Type:** Fira Sans for the interface and the wordmark, Fira Code only for real data (ids, scores, durations), Anton only in the review workspace's headline field. All self-hosted.
- **Motion:** subtle and crisp (emil-design-eng rules). Keyboard actions never animate; hover is color only; one authored moment (a post arriving in "Precisa de você"); everything else answers a click in under 250 ms with a strong ease-out, and exits are faster than entrances.
- **Local is visible.** The top bar always states the AI mode; there is no cloud iconography unless online mode is on.

### Logo direction

A lowercase wordmark, **underfind**, in Fira Sans semibold with tight tracking. The mark is the word's own shape: the crossbar of the **f** is drawn as a short horizontal rule in the accent color, read as "the post that sits above the line". No icon beside it; at small sizes the **f** alone with its accent crossbar is the app icon.

---

## 7. Positioning

| | Underfind | Cloud repurposing tools | Manual workflow |
|---|---|---|---|
| Where it runs | Your machine | Their servers | Your machine |
| Cost per post | Zero (models are local) | Credits per export or per minute | Your time |
| Finds sources | Scans your niche and scores outliers | Usually needs you to bring the link | You scroll |
| Translation and branding | Local, glossary-protected, in your layout | Often generic templates | By hand |
| Your media | Stays on disk | Uploaded | Stays on disk |
| Review | Two checkpoints, skippable per page | Varies | You do everything |
| Output | Reels, 4:5 posts, carousels plus manifest | Usually video only | Whatever you make |

The honest trade-off: local models translate literally and do not adapt slang the way a large online model does. Underfind offers an online mode for that, off by default, and puts a review step exactly where literal translation needs a human eye.

---

## 8. Boilerplate

**README opener**

> Underfind finds posts that are working abroad and models them for your own page. It scans the niches you define, scores posts by how far they outperform their account, then downloads, translates and re-brands them with models that run on your computer, renders reels, posts and carousels in your layout, and exports them with a manifest for your publisher.

**Store or repository description (under 160 characters)**

> Local-first studio that finds under-found posts in your niche and models them for your page: translate, re-brand, render, export. No cloud required.

**Release note style**

> Added: translation review now shows the headline in the same face and gradient as the rendered card. Fixed: a failed webhook no longer exports the post twice.

State what changed in the user's terms, then what was fixed. No adjectives.

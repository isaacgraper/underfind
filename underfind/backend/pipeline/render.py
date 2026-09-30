from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from underfind.backend.core.errors import PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.pipeline.media import has_audio_stream, probe_duration, run_ffmpeg
from underfind.backend.pipeline.subtitles import build_cues, write_ass
from underfind.backend.schemas.pipeline import Headline, Layout, MediaType, RenderTemplate, TranslatedSegment

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
DEFAULT_FONT = FONTS_DIR / "Anton-Regular.ttf"
FALLBACK_FONTS = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
FPS = 30
_HIGHLIGHT = re.compile(r"\*([^*]+)\*")
# Cropping the source band leaves at least this share of the media; otherwise the band stays (rare full-text posts).
_MIN_KEPT_MEDIA = 0.4
_BAND_MARGIN = 0.03
# Condensed display fonts are tall; accents (Ê, Á) need room above the cap height.
_LINE_SPACING = 1.2


# ------------------------------------------------------------------ fonts & colors


def font_path(template: RenderTemplate) -> Path:
    for candidate in [Path(template.font_path) if template.font_path else None, DEFAULT_FONT, *FALLBACK_FONTS]:
        if candidate and candidate.exists():
            return candidate

    raise PermanentStageError("No usable font: set font_path on the render template")


def _font(template: RenderTemplate, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(template)), size)


def _rgb(hex_color: str) -> Tuple[int, int, int]:
    clean = hex_color.lstrip("#")
    return tuple(int(clean[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(size: Tuple[int, int], colors: List[str]) -> Image.Image:
    """Horizontal gradient through the given colors."""
    width, height = size
    stops = [_rgb(c) for c in (colors or ["#FFFFFF"])] or [(255, 255, 255)]

    if len(stops) == 1:
        return Image.new("RGB", size, stops[0])

    row = Image.new("RGB", (max(1, width), 1))
    pixels = row.load()

    for x in range(max(1, width)):
        t = x / max(1, width - 1) * (len(stops) - 1)
        i = min(int(t), len(stops) - 2)
        f = t - i
        pixels[x, 0] = tuple(int(stops[i][c] + (stops[i + 1][c] - stops[i][c]) * f) for c in range(3))

    return row.resize(size)


# ------------------------------------------------------------------ headline card


@dataclass
class _Word:
    text: str
    highlight: bool
    glue: bool = False  # drawn right after the previous word, no space (punctuation after a highlight)


_PUNCTUATION = re.compile(r"^[,.;:!?…)\]»”\"']+")


def parse_markup(markup: str, uppercase: bool = True) -> List[_Word]:
    """'ON *NOVEMBER 19 2026*, YOU…' -> words flagged as highlighted or not; ',' glued to the highlight."""
    words: List[_Word] = []
    cursor = 0

    def plain(chunk: str) -> None:
        for i, token in enumerate(chunk.split()):
            glue = i == 0 and not chunk[:1].isspace() and bool(words)
            words.append(_Word(token, False, glue))

    for match in _HIGHLIGHT.finditer(markup):
        plain(markup[cursor:match.start()])
        words.extend(_Word(w, True) for w in match.group(1).split())
        cursor = match.end()

    plain(markup[cursor:])
    return [_Word(w.text.upper() if uppercase else w.text, w.highlight, w.glue) for w in words]


def _units(words: List[_Word]) -> List[List[_Word]]:
    """
    Groups words that must stay on one line: glued punctuation with its word, a short number with the word before
    it ("GTA 6"), and a one/two-letter word with the word after it ("DE NOVEMBRO", "EM 2026").
    """
    units: List[List[_Word]] = []
    bind_next = False

    for word in words:
        short_number = len(word.text) <= 2 and word.text.isdigit()

        if units and (word.glue or short_number or bind_next):
            units[-1].append(word)
        else:
            units.append([word])

        bind_next = len(word.text) <= 2 and word.text.isalpha()

    return units


def _unit_width(unit: List[_Word], font: ImageFont.FreeTypeFont) -> float:
    space = font.getlength(" ")
    return sum(font.getlength(w.text) for w in unit) + sum(0 if w.glue else space for w in unit[1:])


def _line_width(line: List[_Word], font: ImageFont.FreeTypeFont) -> float:
    return _unit_width(line, font)


def _wrap(words: List[_Word], font: ImageFont.FreeTypeFont, max_width: int) -> List[List[_Word]]:
    space = font.getlength(" ")
    lines: List[List[_Word]] = []
    current: List[_Word] = []
    width = 0.0

    for unit in _units(words):
        w = _unit_width(unit, font)

        if current and width + space + w > max_width:
            lines.append(current)
            current, width = list(unit), w
        else:
            width += (space if current else 0) + w
            current.extend(unit)

    if current:
        lines.append(current)

    return lines


def _fit_headline(words: List[_Word], template: RenderTemplate, box_w: int, box_h: int) -> Tuple[ImageFont.FreeTypeFont, List[List[_Word]], int]:
    """Largest font size whose wrapped lines fit the box and the line limit."""
    for size in range(template.headline_max_font_size, template.headline_min_font_size - 1, -4):
        font = _font(template, size)
        lines = _wrap(words, font, box_w)
        line_height = int(size * _LINE_SPACING)

        if len(lines) <= template.headline_max_lines and len(lines) * line_height <= box_h and all(
            _line_width(line, font) <= box_w for line in lines
        ):
            return font, lines, line_height

    font = _font(template, template.headline_min_font_size)
    return font, _wrap(words, font, box_w), int(template.headline_min_font_size * _LINE_SPACING)


def render_card(
    width: int,
    height: int,
    brand_tag: Optional[str],
    headline_markup: str,
    template: RenderTemplate,
) -> Image.Image:
    """
    The headline card: brand tag between gradient lines, then the headline centered, highlighted words in the
    highlight gradient (each highlighted run shares one gradient across its width, like the reference post).
    """
    card = Image.new("RGBA", (width, height), _rgb(template.background_color) + (255,))
    draw = ImageDraw.Draw(card)
    pad_x = int(width * 0.05)
    top = int(height * 0.06)

    if brand_tag:
        tag_font = _font(template, template.brand_tag_font_size)
        tag_w = int(tag_font.getlength(brand_tag))
        ascent, descent = tag_font.getmetrics()
        tag_h = ascent + descent
        tag_x = (width - tag_w) // 2
        mask = Image.new("L", (tag_w, tag_h), 0)
        ImageDraw.Draw(mask).text((0, 0), brand_tag, font=tag_font, fill=255)
        card.paste(_gradient((tag_w, tag_h), template.brand_tag_colors), (tag_x, top), mask)
        line_y = top + tag_h // 2
        gap = int(template.brand_tag_font_size * 0.6)
        thickness = max(2, template.brand_tag_font_size // 14)

        for x0, x1, colors in (
            (pad_x, tag_x - gap, [template.background_color, template.brand_tag_colors[0]]),
            (tag_x + tag_w + gap, width - pad_x, [template.brand_tag_colors[-1], template.background_color]),
        ):
            if x1 > x0:
                card.paste(_gradient((x1 - x0, thickness), colors), (x0, line_y - thickness // 2))

        top += tag_h + int(height * 0.05)

    words = parse_markup(headline_markup, uppercase=template.headline_uppercase)

    if not words:
        return card

    box_w = width - 2 * pad_x
    box_h = height - top - int(height * 0.05)
    font, lines, line_height = _fit_headline(words, template, box_w, box_h)
    space = font.getlength(" ")
    block_h = len(lines) * line_height
    y = top + max(0, (box_h - block_h) // 2)
    base = _rgb(template.headline_color)

    for line in lines:
        line_w = _line_width(line, font)
        x = (width - line_w) / 2
        run_start: Optional[float] = None
        run_mask: Optional[Image.Image] = None

        for i, word in enumerate(line):
            w = font.getlength(word.text)

            if i > 0 and word.glue:
                x -= space

            if word.highlight:
                if run_start is None:
                    run_start = x
                    run_mask = Image.new("L", (width, line_height * 2), 0)

                ImageDraw.Draw(run_mask).text((x, 0), word.text, font=font, fill=255)
            else:
                draw.text((x, y), word.text, font=font, fill=base)

            next_is_highlight = i + 1 < len(line) and line[i + 1].highlight

            if word.highlight and not next_is_highlight:
                run_end = x + w
                gradient = Image.new("RGB", run_mask.size, (0, 0, 0))
                span = max(1, int(run_end - run_start))
                gradient.paste(_gradient((span, run_mask.size[1]), template.highlight_colors), (int(run_start), 0))
                card.paste(gradient, (0, y), run_mask)
                run_start, run_mask = None, None

            x += w + space

        y += line_height

    return card


# ------------------------------------------------------------------ layout


def resolve_layout(
    template: RenderTemplate,
    media_type: MediaType,
    headline: Optional[Headline],
    headline_text: str,
    first_size: Tuple[int, int],
) -> Layout:
    if template.layout != Layout.AUTO:
        if template.layout == Layout.HEADLINE_CARD and not headline_text:
            return Layout.LETTERBOX
        return template.layout

    if headline_text and headline and headline.position:
        return Layout.HEADLINE_CARD

    width, height = first_size

    if media_type == MediaType.VIDEO and height / max(1, width) >= 1.6:
        return Layout.FULL_BLEED

    return Layout.LETTERBOX


def band_crop(size: Tuple[int, int], headline: Optional[Headline]) -> Optional[Tuple[int, int, int, int]]:
    """Box of the media without the source's headline band, or None when there's nothing (safe) to crop."""
    if not headline or not headline.region or not headline.position:
        return None

    width, height = size
    scale_x = width / headline.media_size[0] if headline.media_size else 1.0
    scale_y = height / headline.media_size[1] if headline.media_size else 1.0
    margin = int(_BAND_MARGIN * height)
    y0 = int(headline.region[1] * scale_y)
    y1 = int(headline.region[3] * scale_y)

    if headline.position == "bottom":
        box = (0, 0, width, max(0, y0 - margin))
    else:
        box = (0, min(height, y1 + margin), width, height)

    kept = box[3] - box[1]
    return box if kept >= _MIN_KEPT_MEDIA * height and scale_x > 0 else None


def media_area(layout: Layout, canvas: Tuple[int, int], template: RenderTemplate) -> Tuple[int, int]:
    width, height = canvas

    if layout == Layout.HEADLINE_CARD:
        return width, height - int(height * template.card_ratio)

    return width, height


def place_media(media: Image.Image, layout: Layout, canvas: Tuple[int, int], template: RenderTemplate) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    Scales media for its area: full_bleed covers the frame; letterbox fits inside it; headline_card fills the
    width of the top area, anchored to the card (cropping the top if too tall).
    """
    area_w, area_h = media_area(layout, canvas, template)
    src_w, src_h = media.size

    if layout == Layout.FULL_BLEED or (template.video_fit == "fill" and layout == Layout.LETTERBOX):
        scale = max(area_w / src_w, area_h / src_h)
    elif layout == Layout.HEADLINE_CARD:
        scale = area_w / src_w
    else:
        scale = min(area_w / src_w, area_h / src_h)

    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = media.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if new_w > area_w or new_h > area_h:
        left = (new_w - area_w) // 2 if new_w > area_w else 0
        top = new_h - area_h if layout == Layout.HEADLINE_CARD and new_h > area_h else max(0, (new_h - area_h) // 2)
        resized = resized.crop((left, top, left + min(new_w, area_w), top + min(new_h, area_h)))

    x = (area_w - resized.size[0]) // 2
    y = area_h - resized.size[1] if layout == Layout.HEADLINE_CARD else (area_h - resized.size[1]) // 2
    return resized, (x, y)


def headline_block_offset(placed_height: int, layout: Layout, canvas: Tuple[int, int], template: RenderTemplate) -> int:
    """
    Vertical shift that centers media + card as one block when the media is shorter than its area
    (a 4:5 image in a 9:16 reel), instead of leaving an empty band above it.
    """
    if layout != Layout.HEADLINE_CARD:
        return 0

    area_h = media_area(layout, canvas, template)[1]
    return -((area_h - placed_height) // 2)


def compose_still(
    media: Image.Image,
    layout: Layout,
    canvas: Tuple[int, int],
    template: RenderTemplate,
    card: Optional[Image.Image] = None,
) -> Image.Image:
    frame = Image.new("RGB", canvas, _rgb(template.background_color))
    placed, (x, y) = place_media(media.convert("RGB"), layout, canvas, template)
    shift = headline_block_offset(placed.size[1], layout, canvas, template)
    frame.paste(placed, (x, y + shift))

    if card is not None and layout == Layout.HEADLINE_CARD:
        frame.paste(card, (0, canvas[1] - card.size[1] + shift), card)

    return frame


def card_overlay(card: Image.Image, placed_height: int, canvas: Tuple[int, int], template: RenderTemplate) -> Image.Image:
    """Transparent full-frame layer with the card where compose_still puts it (for reels: zoom below, card on top)."""
    overlay = Image.new("RGBA", canvas, (0, 0, 0, 0))
    shift = headline_block_offset(placed_height, Layout.HEADLINE_CARD, canvas, template)
    overlay.paste(card, (0, canvas[1] - card.size[1] + shift))
    return overlay


# ------------------------------------------------------------------ video encoding

_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart"]


def _audio_inputs(audio_bed: Optional[Path], seconds: float) -> List[str]:
    if audio_bed and audio_bed.exists():
        return ["-stream_loop", "-1", "-i", str(audio_bed)]

    return ["-f", "lavfi", "-t", f"{seconds:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]


def still_to_reel(
    still_layer: Image.Image,
    overlay: Optional[Image.Image],
    template: RenderTemplate,
    out_path: Path,
    seconds: float,
    audio_bed: Optional[Path] = None,
) -> Path:
    """Image post as a reel: slow zoom (Ken Burns) on the media layer, static card on top, audio bed or silence."""
    with tempfile.TemporaryDirectory() as tmp:
        layer_path = Path(tmp) / "layer.png"
        still_layer.save(layer_path)
        frames = max(1, int(seconds * FPS))
        width, height = still_layer.size
        zoom = template.ken_burns_zoom
        # One input frame; zoompan expands it to exactly `frames` output frames.
        inputs = ["-i", str(layer_path)]
        filters = [
            f"[0:v]scale={width * 2}:{height * 2},"
            f"zoompan=z='1+({zoom - 1:.4f})*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={width}x{height}:fps={FPS}[bg]"
        ]
        last = "[bg]"

        if overlay is not None:
            overlay_path = Path(tmp) / "overlay.png"
            overlay.save(overlay_path)
            inputs += ["-loop", "1", "-i", str(overlay_path)]
            filters.append(f"{last}[1:v]overlay=0:0:shortest=1[ov]")
            last = "[ov]"

        filters.append(f"{last}format=yuv420p[v]")
        audio_index = inputs.count("-i")
        inputs += _audio_inputs(audio_bed, seconds)
        run_ffmpeg([
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", f"{audio_index}:a",
            "-t", f"{seconds:.3f}", *_ENCODE, str(out_path),
        ], timeout=900)

    return out_path


def concat_reels(parts: List[Path], out_path: Path) -> Path:
    if len(parts) == 1:
        shutil.copyfile(parts[0], out_path)
        return out_path

    listing = out_path.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(out_path)], timeout=900)
    listing.unlink(missing_ok=True)
    return out_path


def video_to_reel(
    video_path: Path,
    layout: Layout,
    template: RenderTemplate,
    out_path: Path,
    crop: Optional[Tuple[int, int, int, int]] = None,
    overlay: Optional[Image.Image] = None,
    segments: Optional[List[TranslatedSegment]] = None,
    audio_path: Optional[Path] = None,
) -> Path:
    """Video reel: optional band crop, scaled into the layout's media area, card overlay, burned subtitles, audio."""
    duration = probe_duration(video_path)

    if not duration:
        raise PermanentStageError(f"Unreadable video: {video_path}")

    width, height = template.width, template.height
    area_w, area_h = media_area(layout, (width, height), template)

    with tempfile.TemporaryDirectory() as tmp:
        chain = []

        if crop:
            x0, y0, x1, y1 = crop
            chain.append(f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}")

        if layout == Layout.FULL_BLEED:
            chain.append(f"scale={area_w}:{area_h}:force_original_aspect_ratio=increase,crop={area_w}:{area_h}")
            pad_y = "0"
        elif layout == Layout.HEADLINE_CARD:
            chain.append(f"scale={area_w}:-2,crop='min(iw,{area_w})':'min(ih,{area_h})':0:'max(0,ih-{area_h})'")
            pad_y = f"{area_h}-ih"
        else:
            chain.append(f"scale={area_w}:{area_h}:force_original_aspect_ratio=decrease")
            pad_y = "(oh-ih)/2"

        chain.append(f"pad={width}:{height}:(ow-iw)/2:{pad_y}:color={template.background_color}")
        chain.append("setsar=1")
        inputs = ["-i", str(video_path)]
        filters = [f"[0:v]{','.join(chain)}[base]"]
        last = "[base]"

        if overlay is not None:
            overlay_path = Path(tmp) / "overlay.png"
            overlay.save(overlay_path)
            inputs += ["-loop", "1", "-i", str(overlay_path)]
            filters.append(f"{last}[1:v]overlay=0:0:shortest=1[ov]")
            last = "[ov]"

        if segments:
            sub_template = template.model_copy(update={
                "subtitle_position_y": min(template.subtitle_position_y, 1 - template.card_ratio - 0.03)
                if layout == Layout.HEADLINE_CARD else template.subtitle_position_y,
            })
            cues = build_cues(segments, sub_template)

            if cues:
                ass_path = write_ass(cues, sub_template, Path(tmp) / "subs.ass")
                escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
                fonts = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")
                filters.append(f"{last}subtitles='{escaped}':fontsdir='{fonts}'[subs]")
                last = "[subs]"

        filters.append(f"{last}format=yuv420p[v]")
        audio_index = inputs.count("-i")

        if audio_path and audio_path.exists():
            inputs += ["-i", str(audio_path)]
            audio_map = f"{audio_index}:a"
        elif has_audio_stream(video_path):
            audio_map = "0:a"
        else:
            inputs += _audio_inputs(None, duration)
            audio_map = f"{audio_index}:a"

        run_ffmpeg([
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", audio_map,
            "-t", f"{duration:.3f}", *_ENCODE, str(out_path),
        ], timeout=1800)

    logger.debug("Rendered video reel %s (%s, %.1fs)", out_path.name, layout.value, duration)
    return out_path

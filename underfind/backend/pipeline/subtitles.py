from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from underfind.backend.core.constants import (
    SUBTITLE_MAX_LINES,
    SUBTITLE_CHAR_WIDTH_RATIO,
    SUBTITLE_SIDE_MARGIN_RATIO,
)
from underfind.backend.schemas.pipeline import RenderTemplate, TranslatedSegment


@dataclass
class Cue:
    start: float
    end: float
    lines: List[str]


def max_line_chars(template: RenderTemplate) -> int:
    usable_width = template.width * (1 - 2 * SUBTITLE_SIDE_MARGIN_RATIO)
    return max(10, int(usable_width / (template.subtitle_font_size * SUBTITLE_CHAR_WIDTH_RATIO)))


def wrap_words(
    text: str,
    width: int,
) -> List[str]:
    lines: List[str] = []
    current = ""

    for word in text.split():
        candidate = f"{current} {word}".strip()

        if len(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def build_cues(
    segments: List[TranslatedSegment],
    template: RenderTemplate,
) -> List[Cue]:
    """Splits each segment into on-screen cues of at most SUBTITLE_MAX_LINES lines, timed by character share."""
    width = max_line_chars(template)
    cues: List[Cue] = []

    for seg in segments:
        lines = wrap_words(seg.text, width)

        if not lines:
            continue

        groups = [lines[i:i + SUBTITLE_MAX_LINES] for i in range(0, len(lines), SUBTITLE_MAX_LINES)]
        total_chars = sum(len(line) for line in lines)
        duration = max(0.0, seg.end - seg.start)
        cursor = seg.start

        for i, group in enumerate(groups):
            share = sum(len(line) for line in group) / total_chars
            end = seg.end if i == len(groups) - 1 else cursor + duration * share
            cues.append(Cue(start=round(cursor, 3), end=round(end, 3), lines=group))
            cursor = end

    return cues


def _ass_time(seconds: float) -> str:
    centis = int(round(seconds * 100))
    h, rem = divmod(centis, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    h, rem = divmod(millis, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB -> &HAABBGGRR (ASS stores blue-green-red with inverted alpha)."""
    clean = hex_color.lstrip("#")
    r, g, b = clean[0:2], clean[2:4], clean[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_escape(text: str) -> str:
    # Braces open override blocks and a backslash starts a tag in ASS.
    return text.replace("\\", "/").replace("{", "(").replace("}", ")")


def write_ass(
    cues: List[Cue],
    template: RenderTemplate,
    out_path: Path,
) -> Path:
    family, _, weight = template.subtitle_font.partition("-")
    bold = -1 if "bold" in weight.lower() or "black" in weight.lower() else 0
    margin_side = int(template.width * SUBTITLE_SIDE_MARGIN_RATIO)
    margin_v = int(template.height * (1 - template.subtitle_position_y))
    outline = max(2, template.subtitle_font_size // 16)

    header = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {template.width}",
        f"PlayResY: {template.height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{family},{template.subtitle_font_size},{_ass_color(template.subtitle_color)},&H000000FF,"
        f"{_ass_color(template.subtitle_outline_color)},&H64000000,{bold},0,0,0,100,100,0,0,1,{outline},0,2,"
        f"{margin_side},{margin_side},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    line_break = "\\N"
    events = [
        f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,0,0,0,,"
        + line_break.join(_ass_escape(line) for line in c.lines)
        for c in cues
    ]
    out_path.write_text(header + "\n" + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


def write_srt(
    cues: List[Cue],
    out_path: Path,
) -> Path:
    blocks = [
        f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n" + "\n".join(c.lines)
        for i, c in enumerate(cues, start=1)
    ]
    out_path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return out_path

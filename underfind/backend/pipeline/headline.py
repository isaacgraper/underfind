from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List, Optional

from underfind.backend.schemas.pipeline import Headline, OnScreenText

# Headline text is big: at least this share of the media height per line, and close to the tallest line.
_MIN_LINE_HEIGHT_RATIO = 0.03
_SIMILAR_HEIGHT_RATIO = 0.55
# Lines further apart than this (in tallest-line heights) belong to different blocks.
_MAX_LINE_GAP = 0.9
_MIN_HEADLINE_CHARS = 8
# A band spanning this share of the width, in the lower/upper part, can be cropped away and replaced by our card.
_BAND_MIN_WIDTH_RATIO = 0.6

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|"
    "enero|febrero|marzo|mayo|junio|julio|septiembre|setiembre|octubre|noviembre|diciembre|"
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre|"
    "januar|februar|märz|juni|juli|oktober|dezember|"
    "jan|feb|fev|mar|apr|abr|jun|jul|aug|ago|sep|set|oct|out|nov|dec|dez|dic"
)
_CONNECTORS = r"(?:\s+(?:de|del|of)\s+|[\s,./-]+)"
_HIGHLIGHT_PATTERNS = [
    # dates: "NOVEMBER 19 2026", "19 de novembro de 2026", "19/11/2026"
    re.compile(rf"\b(?:{_MONTHS})\.?{_CONNECTORS}\d{{1,2}}(?:{_CONNECTORS}\d{{4}})?\b", re.IGNORECASE),
    re.compile(rf"\b\d{{1,2}}{_CONNECTORS}(?:{_MONTHS})\.?(?:{_CONNECTORS}\d{{4}})?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
    # money, percentages, big numbers: "$2 BILLION", "R$ 10 mil", "85%", "1,1M"
    re.compile(r"(?:\bUS\$|\bR\$|\$|€|£)\s?\d[\d.,]*(?:\s?(?:billion|million|bilhões|bilhão|milhões|milhão|mil|millones|mil millones|k|m|b))?\b", re.IGNORECASE),
    re.compile(r"\b\d[\d.,]*\s?(?:%|billion|million|bilhões|bilhão|milhões|milhão|millones)", re.IGNORECASE),
    re.compile(r"\b\d{2,}(?:[.,]\d+)?[kKmM]?\b"),
]
_MAX_HIGHLIGHT_SHARE = 0.6


def _norm(text: str) -> str:
    # OCR confuses 0/O and 1/l in stylized fonts; normalize both sides the same way.
    return re.sub(r"[^a-z0-9]", "", text.lower()).replace("0", "o").replace("1", "l")


def clean_ocr_text(text: str) -> str:
    """Fixes common OCR slips in headlines: a 0 between letters is an O ("N0VEMBER"); letters glued to numbers get a space."""
    text = re.sub(r"(?<=[A-Za-zÀ-ÿ])0(?=[A-Za-zÀ-ÿ])", lambda m: "O", text)
    text = re.sub(r"(?<=[A-Za-zÀ-ÿ])(?=\d)|(?<=\d)(?=[A-Za-zÀ-ÿ])", " ", text)
    return text


def _height(item: OnScreenText) -> int:
    return item.box[3] - item.box[1]


def _is_brand(item: OnScreenText, hints: Iterable[str]) -> bool:
    norm = _norm(item.text)
    return bool(norm) and any(
        h and (norm == h or (len(h) >= 5 and h in norm) or (len(norm) >= 5 and norm in h) or SequenceMatcher(None, norm, h).ratio() >= 0.85)
        for h in hints
    )


def _reading_order(items: List[OnScreenText]) -> str:
    """Joins OCR boxes into lines (same vertical center) left to right, lines top to bottom."""
    lines: List[List[OnScreenText]] = []

    for item in sorted(items, key=lambda i: (i.box[1] + i.box[3]) / 2):
        center = (item.box[1] + item.box[3]) / 2

        if lines:
            last = lines[-1][0]
            last_center = (last.box[1] + last.box[3]) / 2

            if abs(center - last_center) < 0.5 * _height(last):
                lines[-1].append(item)
                continue

        lines.append([item])

    return "\n".join(" ".join(i.text for i in sorted(line, key=lambda i: i.box[0])) for line in lines)


def detect_headline(
    items: List[OnScreenText],
    width: int,
    height: int,
    brand_hints: Iterable[str] = (),
    media_file: Optional[str] = None,
) -> Optional[Headline]:
    """
    Finds the post's headline: the largest block of big, vertically adjacent text lines, plus the small brand tag
    right next to it (matched against the author handle/name). Reports whether the block is a full-width band at
    the top or bottom, which the headline_card layout crops away and re-types in the page's own card.
    """
    boxed = [i for i in items if i.box and (media_file is None or i.media_file in (None, media_file))]

    if not boxed or not width or not height:
        return None

    hints = [_norm(h) for h in brand_hints if h]
    brand = [i for i in boxed if _is_brand(i, hints)]
    text_items = [i for i in boxed if i not in brand]
    big = [i for i in text_items if _height(i) >= _MIN_LINE_HEIGHT_RATIO * height]

    if not big:
        return None

    tallest = max(_height(i) for i in big)
    big = sorted((i for i in big if _height(i) >= _SIMILAR_HEIGHT_RATIO * tallest), key=lambda i: i.box[1])
    blocks: List[List[OnScreenText]] = [[big[0]]]

    for item in big[1:]:
        if item.box[1] - max(b.box[3] for b in blocks[-1]) <= _MAX_LINE_GAP * tallest:
            blocks[-1].append(item)
        else:
            blocks.append([item])

    block = max(blocks, key=lambda b: sum(len(i.text) for i in b))
    text = clean_ocr_text(_reading_order(block))

    if len(re.sub(r"\s", "", text)) < _MIN_HEADLINE_CHARS:
        return None

    x0 = min(i.box[0] for i in block)
    y0 = min(i.box[1] for i in block)
    x1 = max(i.box[2] for i in block)
    y1 = max(i.box[3] for i in block)
    # Small lines hugging the block (brand tag, kicker, "swipe" line) belong to the band even when unrecognized.
    near = [
        i for i in boxed
        if i not in block
        and i.box[3] >= y0 - 1.5 * tallest and i.box[1] <= y1 + 1.5 * tallest
        and i.box[2] > x0 and i.box[0] < x1
    ]
    brand_item = next((i for i in near if i in brand), None) or next(
        (i for i in near if i.box[3] <= y0 and _height(i) < _SIMILAR_HEIGHT_RATIO * tallest), None
    )

    for item in near:
        x0, y0 = min(x0, item.box[0]), min(y0, item.box[1])
        x1, y1 = max(x1, item.box[2]), max(y1, item.box[3])

    position: Optional[str] = None

    if x1 - x0 >= _BAND_MIN_WIDTH_RATIO * width:
        if y0 >= 0.4 * height:
            position = "bottom"
        elif y1 <= 0.6 * height:
            position = "top"

    return Headline(
        text=text,
        brand_text=brand_item.text if brand_item else None,
        media_file=media_file,
        region=[x0, y0, x1, y1],
        position=position,
        media_size=[width, height],
    )


def auto_highlight(text: str) -> str:
    """Marks dates, money, percentages and big numbers as *highlights* (the gradient words of the headline card)."""
    if not text or "*" in text:
        return text

    spans: List[tuple[int, int]] = []

    for pattern in _HIGHLIGHT_PATTERNS:
        for match in pattern.finditer(text):
            spans.append(match.span())

    if not spans:
        return text

    spans.sort()
    merged: List[List[int]] = [list(spans[0])]

    for start, end in spans[1:]:
        between = text[merged[-1][1]:start]

        if start <= merged[-1][1] or re.fullmatch(_CONNECTORS, between or " ", re.IGNORECASE):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    if sum(e - s for s, e in merged) > _MAX_HIGHLIGHT_SHARE * len(text):
        return text

    out, cursor = [], 0

    for start, end in merged:
        out.append(text[cursor:start])
        out.append(f"*{text[start:end].strip()}*")
        trailing = text[start:end][len(text[start:end].rstrip()):]
        out.append(trailing)
        cursor = end

    out.append(text[cursor:])
    return "".join(out)

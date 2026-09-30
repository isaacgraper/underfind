from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from underfind.backend.pipeline.media import probe_duration, run_ffmpeg
from underfind.backend.pipeline.render import (
    _units,
    _wrap,
    _font,
    band_crop,
    card_overlay,
    compose_still,
    parse_markup,
    place_media,
    render_card,
    resolve_layout,
    still_to_reel,
    video_to_reel,
)
from underfind.backend.schemas.pipeline import Headline, Layout, MediaType, RenderTemplate, TranslatedSegment

TEMPLATE = RenderTemplate(name="t")


def test_parse_markup_highlights_and_glued_punctuation():
    words = parse_markup("se nascer em *19 de novembro de 2026*, você ganha GTA 6")

    assert [w.text for w in words if w.highlight] == ["19", "DE", "NOVEMBRO", "DE", "2026"]
    comma = next(w for w in words if w.text.startswith(","))
    assert comma.text == "," and comma.glue and not comma.highlight
    assert parse_markup("Sem *caixa*", uppercase=False)[0].text == "Sem"


def test_units_keep_short_words_together():
    units = [" ".join(w.text for w in u) for u in _units(parse_markup("VOCÊ GANHA UMA CÓPIA DE GTA 6 EM 2026"))]
    assert units == ["VOCÊ", "GANHA", "UMA", "CÓPIA", "DE GTA 6", "EM 2026"]


def test_wrap_never_splits_gta_6():
    font = _font(TEMPLATE, 120)
    lines = _wrap(parse_markup("VOCÊ GANHA UMA CÓPIA GRÁTIS DE GTA 6"), font, 700)
    assert all(not (line[0].text == "6") for line in lines)


def test_render_card_size_and_colors():
    card = render_card(1080, 690, "GTAVIBRASIL", "GTA 6 CHEGA EM *19 DE NOVEMBRO DE 2026*", TEMPLATE)

    assert card.size == (1080, 690)
    pixels = card.convert("RGB").getcolors(1_000_000)
    colors = {c for _, c in pixels}
    assert (255, 255, 255) in colors
    assert any(r > 150 and b > 150 and g < 120 for r, g, b in colors), "highlight gradient (magenta end) missing"


def test_band_crop_and_layout_resolution():
    headline = Headline(text="X", region=[67, 961, 1086, 1437], position="bottom", media_size=[1170, 1465])

    assert band_crop((1170, 1465), headline) == (0, 0, 1170, 961 - int(0.03 * 1465))
    assert band_crop((585, 732), headline)[3] == int(961 * 732 / 1465) - int(0.03 * 732)
    assert band_crop((1170, 1465), Headline(text="X", region=[0, 100, 1170, 1300], position="bottom", media_size=[1170, 1465])) is None
    assert band_crop((1170, 1465), None) is None

    assert resolve_layout(TEMPLATE, MediaType.IMAGE, headline, "GTA 6", (1170, 1465)) == Layout.HEADLINE_CARD
    assert resolve_layout(TEMPLATE, MediaType.IMAGE, headline, "", (1170, 1465)) == Layout.LETTERBOX
    assert resolve_layout(TEMPLATE, MediaType.VIDEO, None, "", (1080, 1920)) == Layout.FULL_BLEED
    assert resolve_layout(TEMPLATE, MediaType.IMAGE, None, "", (1080, 1080)) == Layout.LETTERBOX
    forced = TEMPLATE.model_copy(update={"layout": Layout.HEADLINE_CARD})
    assert resolve_layout(forced, MediaType.IMAGE, None, "", (1, 1)) == Layout.LETTERBOX


def test_compose_headline_card_centers_block():
    media = Image.new("RGB", (1170, 1000), "red")
    canvas = (1080, 1920)
    card = render_card(1080, int(1920 * TEMPLATE.card_ratio), "BRAND", "HELLO *2026*", TEMPLATE)
    frame = compose_still(media, Layout.HEADLINE_CARD, canvas, TEMPLATE, card)
    placed_h = place_media(media, Layout.HEADLINE_CARD, canvas, TEMPLATE)[0].size[1]
    overlay = card_overlay(card, placed_h, canvas, TEMPLATE)

    assert frame.size == canvas
    top_black = next(y for y in range(canvas[1]) if frame.getpixel((540, y)) != (0, 0, 0))
    bottom_black = canvas[1] - next(y for y in range(canvas[1] - 1, 0, -1) if overlay.getpixel((540, y))[3] > 0) - 1
    assert abs(top_black - bottom_black) <= 2


@pytest.mark.parametrize("layout, size", [(Layout.LETTERBOX, (1080, 1080)), (Layout.FULL_BLEED, (720, 1280))])
def test_compose_other_layouts(layout, size):
    frame = compose_still(Image.new("RGB", size, "blue"), layout, (1080, 1920), TEMPLATE)
    assert frame.size == (1080, 1920)
    assert frame.getpixel((540, 960)) == (0, 0, 255)


def test_still_to_reel_with_overlay_and_audio_bed(tmp_path: Path):
    bed = tmp_path / "bed.mp3"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=300:duration=1", "-c:a", "libmp3lame", str(bed)])
    template = TEMPLATE.model_copy(update={"width": 360, "height": 640})
    layer = Image.new("RGB", (360, 640), "green")
    overlay = Image.new("RGBA", (360, 640), (0, 0, 0, 0))
    out = still_to_reel(layer, overlay, template, tmp_path / "r.mp4", 2.0, audio_bed=bed)

    assert probe_duration(out) == pytest.approx(2.0, abs=0.1)


def test_video_reel_headline_card_with_crop_and_subtitles(tmp_path: Path):
    video = tmp_path / "v.mp4"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=320x400:rate=10:duration=2", "-c:v", "mpeg4", str(video)])
    template = TEMPLATE.model_copy(update={"width": 360, "height": 640, "subtitle_font_size": 24})
    overlay = Image.new("RGBA", (360, 640), (0, 0, 0, 0))
    segments = [TranslatedSegment(index=0, start=0, end=1.5, source_text="x", text="Legenda", max_chars=20)]

    out = video_to_reel(video, Layout.HEADLINE_CARD, template, tmp_path / "r.mp4", crop=(0, 0, 320, 300), overlay=overlay, segments=segments)

    assert probe_duration(out) == pytest.approx(2.0, abs=0.15)

from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from underfind.backend.core.errors import MediaToolError
from underfind.backend.core.logger import logger

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_AUDIO_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?: Audio:")


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """ffmpeg from PATH, falling back to the static binary bundled by imageio-ffmpeg."""
    found = shutil.which("ffmpeg")

    if found:
        return found

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as err:
        raise MediaToolError("ffmpeg not found. Install ffmpeg or the imageio-ffmpeg package.") from err


def run_ffmpeg(
    args: List[str],
    timeout: float = 600,
) -> subprocess.CompletedProcess:
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", *args]
    logger.trace("ffmpeg %s", " ".join(args))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise MediaToolError(f"ffmpeg failed ({result.returncode}): {tail}")

    return result


def _probe_stderr(path: Path) -> str:
    """ffmpeg -i without an output prints stream info to stderr and exits non-zero by design."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stderr


def probe_duration(path: Path) -> Optional[float]:
    match = _DURATION_RE.search(_probe_stderr(path))

    if not match:
        return None

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def has_audio_stream(path: Path) -> bool:
    return bool(_AUDIO_STREAM_RE.search(_probe_stderr(path)))


def extract_audio(
    video_path: Path,
    out_path: Path,
) -> Path:
    """16 kHz mono PCM WAV, the input format Whisper expects."""
    run_ffmpeg(["-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out_path)])
    return out_path


def extract_frame(
    video_path: Path,
    at_seconds: float,
    out_path: Path,
) -> Path:
    run_ffmpeg(["-ss", f"{max(0.0, at_seconds):.3f}", "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(out_path)])

    if not out_path.exists():
        raise MediaToolError(f"No frame extracted at {at_seconds:.2f}s from {video_path.name}")

    return out_path

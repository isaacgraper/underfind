from __future__ import annotations

import io
import json
import os
import re
import threading
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol

import requests

from underfind.backend.core.constants import (
    ARGOS_INDEX_URL,
    LOCAL_TRANSLATION_BEAM_SIZE,
    PIVOT_LANGUAGE,
    TRANSLATION_MODELS_DIR,
)
from underfind.backend.core.errors import PermanentStageError
from underfind.backend.core.logger import logger
from underfind.backend.pipeline.translate import SegmentInput, TranslationDraft, TranslationInput

_HASHTAG = re.compile(r"#\w+", re.UNICODE)
_MENTION = re.compile(r"@[\w.]+", re.UNICODE)


# Page languages that have a dedicated regional model, tried before the base language.
REGIONAL_MODEL_CODES: Dict[str, List[str]] = {"pt-br": ["pb", "pt"]}


def model_codes(language: str) -> List[str]:
    """Model pair codes to try for a page language: 'pt-BR' -> ['pb', 'pt'] (Brazilian model first)."""
    return REGIONAL_MODEL_CODES.get(language.lower().replace("_", "-"), [base_language(language)])


def base_language(code: Optional[str]) -> Optional[str]:
    """'pt-BR' -> 'pt'. Whisper and page languages both reduce to the model pair codes."""
    return code.split("-")[0].split("_")[0].lower() if code else None


class TranslationEngine(Protocol):
    def translate(self, texts: List[str]) -> List[str]:
        ...


class CT2MarianEngine:
    """
    One OPUS-MT (Marian) model converted to CTranslate2, run on CPU with int8 weights.
    Same model family Firefox's offline translation (Bergamot) uses; milliseconds per line.
    Accepts Argos Translate package layouts: model/ + sentencepiece.model (or source.spm/target.spm).
    """

    def __init__(self, package_dir: Path, beam_size: int = LOCAL_TRANSLATION_BEAM_SIZE):
        import ctranslate2
        import sentencepiece

        model_dir = package_dir / "model" if (package_dir / "model").exists() else package_dir
        shared = package_dir / "sentencepiece.model"
        source_spm = shared if shared.exists() else package_dir / "source.spm"
        target_spm = shared if shared.exists() else package_dir / "target.spm"

        if not source_spm.exists() or not target_spm.exists():
            raise PermanentStageError(f"No SentencePiece model in {package_dir}")

        threads = int(os.environ.get("LOCAL_TRANSLATION_THREADS", "0"))
        self.translator = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8", intra_threads=threads)
        self.source_sp = sentencepiece.SentencePieceProcessor(model_file=str(source_spm))
        self.target_sp = sentencepiece.SentencePieceProcessor(model_file=str(target_spm))
        self.beam_size = beam_size
        self._lock = threading.Lock()

    def translate(self, texts: List[str]) -> List[str]:
        if not texts:
            return []

        batch = [self.source_sp.encode(t, out_type=str) for t in texts]

        with self._lock:
            results = self.translator.translate_batch(batch, beam_size=self.beam_size, max_decoding_length=256)

        return [self.target_sp.decode(r.hypotheses[0]).strip() for r in results]


class ModelStore:
    """
    Finds language-pair models under data/models/translate/{from}_{to}, downloading an Argos package
    from the public index the first time a pair is needed (disable with LOCAL_MODELS_AUTO_DOWNLOAD=false).
    """

    def __init__(
        self,
        root: Path = TRANSLATION_MODELS_DIR,
        engine_factory: Callable[[Path], TranslationEngine] = CT2MarianEngine,
        fetch: Callable[[str], bytes] = lambda url: requests.get(url, timeout=120).content,
        auto_download: Optional[bool] = None,
    ):
        self.root = root
        self.engine_factory = engine_factory
        self.fetch = fetch
        self.auto_download = auto_download if auto_download is not None else os.environ.get("LOCAL_MODELS_AUTO_DOWNLOAD", "true").lower() != "false"
        self._engines: Dict[str, TranslationEngine] = {}
        self._index: Optional[List[dict]] = None
        self._lock = threading.Lock()

    def pair_dir(self, source: str, target: str) -> Path:
        return self.root / f"{source}_{target}"

    def _load_index(self) -> List[dict]:
        if self._index is None:
            self._index = json.loads(self.fetch(os.environ.get("ARGOS_INDEX_URL", ARGOS_INDEX_URL)))

        return self._index

    def available_remote(self, source: str, target: str) -> Optional[dict]:
        return next((p for p in self._load_index() if p.get("from_code") == source and p.get("to_code") == target), None)

    def download(self, source: str, target: str) -> Path:
        entry = self.available_remote(source, target)

        if not entry:
            raise PermanentStageError(f"No local translation model published for {source}->{target}")

        dest = self.pair_dir(source, target)
        logger.info("Downloading translation model %s->%s (%s)", source, target, entry.get("package_version", "?"))

        with zipfile.ZipFile(io.BytesIO(self.fetch(entry["links"][0]))) as archive:
            names = archive.namelist()
            prefix = names[0].split("/")[0] + "/" if names and all(n.startswith(names[0].split("/")[0] + "/") for n in names) else ""
            dest.mkdir(parents=True, exist_ok=True)

            for name in names:
                relative = name[len(prefix):]

                if not relative or name.endswith("/") or relative.startswith("stanza/"):
                    continue

                target_path = dest / relative
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(archive.read(name))

        return dest

    def has_pair(self, source: str, target: str) -> bool:
        if self.pair_dir(source, target).exists():
            return True

        if not self.auto_download:
            return False

        try:
            return self.available_remote(source, target) is not None
        except requests.RequestException:
            return False

    def engine(self, source: str, target: str) -> TranslationEngine:
        key = f"{source}_{target}"

        with self._lock:
            if key not in self._engines:
                directory = self.pair_dir(source, target)

                if not directory.exists():
                    if not self.auto_download:
                        raise PermanentStageError(f"Translation model {key} not installed at {directory}")

                    directory = self.download(source, target)

                self._engines[key] = self.engine_factory(directory)

            return self._engines[key]

    def route(self, source: str, target: str) -> List[tuple[str, str]]:
        """Direct pair when available, otherwise pivot through English (es->en->pt)."""
        if self.has_pair(source, target):
            return [(source, target)]

        if PIVOT_LANGUAGE not in (source, target) and self.has_pair(source, PIVOT_LANGUAGE) and self.has_pair(PIVOT_LANGUAGE, target):
            return [(source, PIVOT_LANGUAGE), (PIVOT_LANGUAGE, target)]

        raise PermanentStageError(f"No local translation model for {source}->{target} (direct or via {PIVOT_LANGUAGE})")


def _mask_glossary(text: str, glossary: List[str]) -> tuple[str, Dict[str, str]]:
    """Swaps glossary terms for opaque tokens the model copies verbatim (so 'Vice City' never becomes 'Cidade do Vício')."""
    mapping: Dict[str, str] = {}

    for i, term in enumerate(sorted(glossary, key=len, reverse=True)):
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)

        if pattern.search(text):
            token = f"ZQ{i}X"
            mapping[token] = term
            text = pattern.sub(token, text)

    return text, mapping


def _unmask(text: str, mapping: Dict[str, str]) -> Optional[str]:
    for token, term in mapping.items():
        if token not in text:
            return None

        text = text.replace(token, term)

    return text


class LocalTranslator:
    """
    Offline machine translation (no API, no key, no usage limits). Keeps glossary terms verbatim,
    pivots through English when no direct model exists, and passes same-language text through.
    Lines can't be condensed to fit their time slot, so shorten() returns nothing: subtitles wrap and dubs speed up instead.
    """

    def __init__(self, store: Optional[ModelStore] = None):
        self.store = store or ModelStore()
        self.model: Optional[str] = None

    def _route(self, source: str, targets: List[str]) -> List[tuple[str, str]]:
        errors: List[str] = []

        for target in targets:
            try:
                return self.store.route(source, target)
            except PermanentStageError as err:
                errors.append(str(err))

        raise PermanentStageError("; ".join(errors))

    def _translate_texts(self, texts: List[str], source: str, targets: List[str], glossary: List[str]) -> List[str]:
        if not texts:
            return []

        if source in targets or base_language(source) in {base_language(t) for t in targets}:
            return list(texts)

        route = self._route(source, targets)
        masked = [_mask_glossary(t, glossary) for t in texts]
        current = [m[0] for m in masked]

        for step_source, step_target in route:
            current = self.store.engine(step_source, step_target).translate(current)

        results: List[str] = []
        retry_indexes: List[int] = []

        for i, (output, (_, mapping)) in enumerate(zip(current, masked)):
            restored = _unmask(output, mapping)

            if restored is None:
                retry_indexes.append(i)
                results.append("")
            else:
                results.append(restored)

        if retry_indexes:
            # The model dropped a placeholder: translate those lines unmasked rather than lose content.
            plain = [texts[i] for i in retry_indexes]

            for step_source, step_target in route:
                plain = self.store.engine(step_source, step_target).translate(plain)

            for i, text in zip(retry_indexes, plain):
                results[i] = text

        self.model = "local/opus-mt:" + "+".join(f"{a}-{b}" for a, b in route)
        return results

    def translate(self, req: TranslationInput) -> TranslationDraft:
        targets = model_codes(req.target_language)
        texts = [s.text for s in req.segments]
        source = base_language(req.source_language) or PIVOT_LANGUAGE

        caption_source = req.source_caption or ""
        source_tags = _HASHTAG.findall(caption_source)
        caption_text = _MENTION.sub("", _HASHTAG.sub("", caption_source))
        caption_lines = [line.strip() for line in caption_text.splitlines() if line.strip()]

        translated = self._translate_texts([*texts, *caption_lines, *req.onscreen_text], source, targets, req.glossary)
        n_seg, n_cap = len(texts), len(caption_lines)

        return TranslationDraft.model_validate({
            "segments": [{"index": s.index, "text": t} for s, t in zip(req.segments, translated[:n_seg])],
            "caption": "\n".join(translated[n_seg:n_seg + n_cap]),
            "hashtags": source_tags,
            "onscreen_text": [{"source": src, "text": t} for src, t in zip(req.onscreen_text, translated[n_seg + n_cap:])],
        })

    def shorten(self, target_language: str, segments: List[SegmentInput], glossary: List[str]) -> list:
        return []

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from PIL import Image
from io import BytesIO


@dataclass
class Video:
    """
    Modelo simples que representa um vídeo retornado pela busca.
    Campos pensados para mostrar thumbnail, título, views, inscritos e canal.
    """

    video_id: str
    title: str
    channel_title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    views: Optional[int] = None
    subscribers: Optional[int] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    video_url: Optional[str] = field(default=None)

    def __post_init__(self):
        # Gerar video_url padrão se não informado
        if not self.video_url and self.video_id:
            self.video_url = f"https://www.youtube.com/watch?v={self.video_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Retorna um dicionário simples (serializável) do modelo."""
        out = asdict(self)
        # converte datetime para iso se necessário
        if isinstance(out.get("published_at"), datetime):
            out["published_at"] = out["published_at"].isoformat()
        return out

    @classmethod
    def _safe_int(cls, value: Optional[Any]) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    @classmethod
    def from_youtube_api_item(cls, item: Dict[str, Any]) -> "Video":
        """
        Constrói um Video a partir de um item parcial/composto vindo da API do YouTube.
        Aceita tanto a resposta de `search.list` (que contém snippet + id.videoId)
        quanto a resposta de `videos.list` (que pode conter statistics e contentDetails).

        Exemplo de handling:
        - item['id']['videoId'] ou item['id'] (quando já é o id string)
        - item['snippet']['thumbnails']['high']['url']
        - item['statistics']['viewCount']
        - item['contentDetails']['duration'] (ISO 8601 -> segundos, se disponível)
        """
        # video id
        vid = None
        if isinstance(item.get("id"), dict):
            vid = item["id"].get("videoId") or item["id"].get("kind")
        else:
            vid = item.get("id")

        snippet = item.get("snippet", {}) or {}
        statistics = item.get("statistics", {}) or {}
        content_details = item.get("contentDetails", {}) or {}

        # thumbnail prefer high, then medium, then default
        thumb = None
        thumbs = snippet.get("thumbnails", {}) if snippet else {}
        for key in ("high", "medium", "default"):
            t = thumbs.get(key)
            if t and t.get("url"):
                thumb = t["url"]
                break

        # title and channel
        title = snippet.get("title") or item.get("title") or "Untitled"
        channel_title = snippet.get("channelTitle") or item.get("channelTitle")

        # views and subs
        views = cls._safe_int(statistics.get("viewCount"))
        subs = cls._safe_int(statistics.get("subscriberCount") or statistics.get("subscriberCountHidden"))

        # duration (try parse ISO 8601 like PT1M30S) or content provided in seconds
        duration_seconds = None
        dur = content_details.get("duration")
        if dur and isinstance(dur, str):
            # Parse minimal ISO 8601 durations (PT#H#M#S). We'll do a simple parser.
            try:
                s = dur
                s = s.upper().replace("PT", "")
                hours = minutes = seconds = 0
                num = ""
                for ch in s:
                    if ch.isdigit():
                        num += ch
                    else:
                        if ch == "H":
                            hours = int(num)
                        elif ch == "M":
                            minutes = int(num)
                        elif ch == "S":
                            seconds = int(num)
                        num = ""
                duration_seconds = hours * 3600 + minutes * 60 + seconds
            except Exception:
                duration_seconds = None
        else:
            # sometimes API may return duration in seconds under another key
            duration_seconds = cls._safe_int(content_details.get("lengthSeconds"))

        # published_at
        published_at = None
        pub_raw = snippet.get("publishedAt")
        if pub_raw:
            try:
                published_at = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            except Exception:
                published_at = None

        return cls(
            video_id=vid or "",
            title=title,
            channel_title=channel_title,
            thumbnail_url=thumb,
            views=views,
            subscribers=subs,
            duration_seconds=duration_seconds,
            published_at=published_at,
        )

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "Video":
        """
        Constrói um Video a partir de uma linha de CSV (mapeada para dict).
        Campos esperados (opcionais): video_id, title, channel_title, thumbnail_url,
        views, subscribers, duration_seconds, published_at

        published_at pode estar em ISO format.
        """
        vid = row.get("video_id") or row.get("id") or ""
        title = row.get("title") or ""
        channel = row.get("channel_title") or row.get("channel") or None
        thumb = row.get("thumbnail_url") or row.get("thumbnail") or None
        views = cls._safe_int(row.get("views"))
        subs = cls._safe_int(row.get("subscribers"))
        dur = cls._safe_int(row.get("duration_seconds") or row.get("duration"))
        pub = None
        if row.get("published_at"):
            try:
                pub = datetime.fromisoformat(row.get("published_at").replace("Z", "+00:00"))
            except Exception:
                pub = None

        return cls(
            video_id=vid,
            title=title,
            channel_title=channel,
            thumbnail_url=thumb,
            views=views,
            subscribers=subs,
            duration_seconds=dur,
            published_at=pub,
        )

    def fetch_thumbnail_image(self, timeout: int = 6) -> Optional[Image.Image]:
        """
        Faz download da thumbnail e retorna um objeto PIL.Image.
        Retorna None se não houver thumbnail ou se ocorrer erro.
        NOTA: operação bloqueante — chamar de uma thread / worker se necessário.
        """
        if not self.thumbnail_url:
            return None
        try:
            resp = requests.get(self.thumbnail_url, timeout=timeout)
            resp.raise_for_status()
            buf = BytesIO(resp.content)
            img = Image.open(buf)
            # converte para RGB para facilitar uso no UI
            return img.convert("RGB")
        except Exception:
            return None

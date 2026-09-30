from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

import httplib2
import pytest
from googleapiclient.errors import HttpError

from underfind.backend.core.errors import QuotaExceededError
from underfind.backend.core.quota import QuotaTracker
from underfind.backend.schemas.video import SearchRequest, VideoItem
from underfind.backend.services.youtube_service import YouTubeService


@pytest.fixture
def quota(tmp_path: Path) -> QuotaTracker:
    return QuotaTracker(db_path=tmp_path / "quota.sqlite3", daily_limit=250)


def _http_error(status: int, reason: str = "") -> HttpError:
    resp = httplib2.Response({"status": status})
    body = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()
    return HttpError(resp, body)


class FakeRequest:
    def __init__(self, outcomes: List[Any]):
        self.outcomes = outcomes
        self.calls = 0

    def execute(self):
        outcome = self.outcomes[self.calls]
        self.calls += 1

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def test_quota_consume_and_limit(quota: QuotaTracker):
    assert quota.consume(100) == 100
    assert quota.consume(100) == 200

    with pytest.raises(QuotaExceededError):
        quota.consume(100)

    status = quota.status()
    assert status.used == 200
    assert status.remaining == 50
    assert status.exhausted is False


def test_quota_mark_exhausted_blocks_calls(quota: QuotaTracker):
    quota.mark_exhausted()

    with pytest.raises(QuotaExceededError):
        quota.consume(1)

    assert quota.status().remaining == 0
    assert quota.status().exhausted is True


def test_execute_retries_transient_errors_and_charges_each_attempt(tmp_path: Path):
    tracker = QuotaTracker(db_path=tmp_path / "q.sqlite3", daily_limit=10000)
    sleeps: List[float] = []
    svc = YouTubeService(api_key="k", quota=tracker, sleep=sleeps.append)
    request = FakeRequest([_http_error(503), _http_error(500), {"items": []}])

    assert svc._execute(request, "search.list") == {"items": []}
    assert request.calls == 3
    assert sleeps == [1.0, 2.0]
    assert tracker.status().used == 300


def test_execute_refuses_before_spending_over_budget(quota: QuotaTracker):
    svc = YouTubeService(api_key="k", quota=quota, sleep=lambda _: None)
    request = FakeRequest([_http_error(503), _http_error(503), {"items": []}])

    with pytest.raises(QuotaExceededError):
        svc._execute(request, "search.list")

    assert request.calls == 2
    assert quota.status().used == 200


def test_execute_does_not_retry_client_errors(quota: QuotaTracker):
    svc = YouTubeService(api_key="k", quota=quota, sleep=lambda _: None)
    request = FakeRequest([_http_error(400, "badRequest")])

    with pytest.raises(HttpError):
        svc._execute(request, "videos.list")

    assert request.calls == 1


def test_execute_stops_on_provider_quota_exhaustion(quota: QuotaTracker):
    svc = YouTubeService(api_key="k", quota=quota, sleep=lambda _: None)

    with pytest.raises(QuotaExceededError):
        svc._execute(FakeRequest([_http_error(403, "quotaExceeded")]), "videos.list")

    assert quota.status().exhausted is True


def test_hidden_subscribers_do_not_fake_viral_ratio(quota: QuotaTracker):
    svc = YouTubeService(api_key="k", quota=quota, sleep=lambda _: None)
    svc._fetch_channels_subscribers = lambda ids: {"c1": None, "c2": 1000}

    items = [
        {"id": "v1", "snippet": {"title": "a", "channelId": "c1"}, "statistics": {"viewCount": "500000"}, "contentDetails": {"duration": "PT30S"}},
        {"id": "v2", "snippet": {"title": "b", "channelId": "c2"}, "statistics": {"viewCount": "50000"}, "contentDetails": {"duration": "PT30S"}},
    ]
    videos = {v.video_id: v for v in svc._process_video_items(items)}

    assert videos["v1"].subscribers is None
    assert videos["v1"].viral_ratio == 0.0
    assert videos["v2"].viral_ratio == 50.0


def test_unknown_subscribers_fail_max_subscribers_filter():
    req = SearchRequest(query="gta 6", max_subscribers=50000)

    assert YouTubeService._passes_filters(VideoItem(video_id="a", title="a", subscribers=None), req) is False
    assert YouTubeService._passes_filters(VideoItem(video_id="b", title="b", subscribers=4000), req) is True

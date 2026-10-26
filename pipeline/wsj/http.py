"""HTTP 클라이언트 — 호스트별 레이트리밋, 재시도, User-Agent 를 한 곳에서 처리한다.

수집기는 `ctx.http.get_json(url, params=...)` / `post_json(...)` 만 호출한다.
레이트리밋 숫자는 docs/DATA_SOURCES.md 의 검증값을 따른다.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

# 호스트별 초당 허용 요청 수. 없는 호스트는 DEFAULT_RPS.
HOST_RPS: dict[str, float] = {
    "data.sec.gov": 8.0,  # 공식 한도 10 rps, 여유
    "www.sec.gov": 8.0,
    "efts.sec.gov": 8.0,
    "api.finra.org": 15.0,  # 1,200/분
    "api.fda.gov": 3.0,  # 240/분
    "clinicaltrials.gov": 2.0,  # 비공식 ~50/분
    "api.usaspending.gov": 4.0,
}
DEFAULT_RPS = 2.0
RETRY_STATUS = {429, 500, 502, 503, 504}


class _TokenBucket:
    def __init__(self, rps: float) -> None:
        self.interval = 1.0 / rps
        self.next_at = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            if now < self.next_at:
                time.sleep(self.next_at - now)
                now = time.monotonic()
            self.next_at = now + self.interval


class HttpClient:
    def __init__(self, user_agent: str, timeout: float = 60.0, max_retries: int = 4) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        self._buckets: dict[str, _TokenBucket] = {}
        self.max_retries = max_retries
        self.stats = {"requests": 0, "retries": 0}

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _safe(url: str) -> str:
        """로그·예외용: 쿼리스트링(API 키가 들어갈 수 있음)을 뗀 URL."""
        return urlsplit(url)._replace(query="", fragment="").geturl()

    def _bucket(self, url: str) -> _TokenBucket:
        host = urlsplit(url).netloc
        if host not in self._buckets:
            self._buckets[host] = _TokenBucket(HOST_RPS.get(host, DEFAULT_RPS))
        return self._buckets[host]

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        bucket = self._bucket(url)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            bucket.wait()
            self.stats["requests"] += 1
            try:
                resp = self._client.request(method, url, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                log.warning(
                    "%s %s transport error (%s), attempt %d", method, self._safe(url), exc, attempt + 1
                )
                self._backoff(attempt, None)
                continue
            if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                self.stats["retries"] += 1
                log.warning("%s %s -> %d, attempt %d", method, self._safe(url), resp.status_code, attempt + 1)
                self._backoff(attempt, resp.headers.get("Retry-After"))
                continue
            return resp
        raise RuntimeError(f"{method} {self._safe(url)}: retries exhausted ({last_exc})")

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> None:
        delay = 2.0**attempt
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        time.sleep(min(delay, 60.0))

    # --- 편의 메서드 -------------------------------------------------------

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> Any:
        resp = self.request("GET", url, params=params, headers=headers)
        self._raise(resp)
        return resp.json()

    def get_text(self, url: str, params: dict | None = None, headers: dict | None = None) -> str:
        resp = self.request("GET", url, params=params, headers=headers)
        self._raise(resp)
        return resp.text

    def post_json(self, url: str, json: Any, headers: dict | None = None) -> Any:
        resp = self.request("POST", url, json=json, headers=headers)
        self._raise(resp)
        return resp.json()

    def get_json_or_none(
        self,
        url: str,
        params: dict | None = None,
        not_found_ok: bool = True,
        auth: tuple[str, str] | None = None,
    ) -> Any:
        """openFDA 처럼 결과 없음을 404 로 주는 API 용. 키는 auth(basic) 로 보내 URL 에 남기지 않는다."""
        resp = self.request("GET", url, params=params, auth=auth)
        if resp.status_code == 404 and not_found_ok:
            return None
        self._raise(resp)
        return resp.json()

    def _raise(self, resp: httpx.Response) -> None:
        """raise_for_status 대신: 예외 메시지에 쿼리스트링이 남지 않게 한다."""
        if resp.status_code >= 400:
            raise RuntimeError(
                f"HTTP {resp.status_code} for {self._safe(str(resp.request.url))}: {resp.text[:200]}"
            )

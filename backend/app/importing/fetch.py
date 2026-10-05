"""외부 주소를 안전하게 가져온다.

서버가 사용자가 준 주소로 대신 요청하는 구조라(SSRF), 내부망 주소·http(s) 외 스킴을 막고
크기·시간·리다이렉트 횟수를 제한한다. 리다이렉트는 직접 따라가며 매번 주소를 다시 검사한다.
DNS 검사와 실제 연결 사이에 응답이 바뀌는 공격(DNS rebinding)까지는 막지 않는다.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.importing.base import SourceError

USER_AGENT = "Reader/0.1 (personal paper reader)"
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 30.0

Resolver = Callable[[str], list[str]]


def _system_resolver(host: str) -> list[str]:
    return list({info[4][0] for info in socket.getaddrinfo(host, None)})


@dataclass
class Response:
    url: str  # 리다이렉트를 따라간 최종 주소
    content_type: str
    body: bytes

    @property
    def is_pdf(self) -> bool:
        return self.body.startswith(b"%PDF")

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        resolver: Resolver = _system_resolver,
        max_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self.client = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        self.resolver = resolver
        self.max_bytes = max_bytes

    async def get(self, url: str, accept: str = "*/*") -> Response:
        try:
            return await self._get(url, accept)
        except httpx.TimeoutException as exc:
            raise SourceError("응답이 너무 느려서 중단했어요. 잠시 후 다시 시도해 주세요.") from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"주소에 연결하지 못했어요: {urlsplit(url).hostname}") from exc

    async def _get(self, url: str, accept: str) -> Response:
        for _ in range(MAX_REDIRECTS + 1):
            await self._check_url(url)
            async with self.client.stream(
                "GET", url, headers={"User-Agent": USER_AGENT, "Accept": accept}, follow_redirects=False
            ) as res:
                if res.is_redirect:
                    url = urljoin(url, res.headers["location"])
                    continue
                if res.status_code == 404:
                    raise SourceError("주소에서 페이지를 찾을 수 없어요 (404).")
                if res.status_code in (401, 403):
                    raise SourceError(
                        "사이트가 접근을 막고 있어요. 브라우저에서 PDF를 받아 직접 올려 주세요."
                    )
                if res.status_code >= 400:
                    raise SourceError(f"주소를 불러오지 못했어요 (HTTP {res.status_code}).")
                body = await self._read_limited(res)
                return Response(str(res.url), res.headers.get("content-type", ""), body)
        raise SourceError("리다이렉트가 너무 많아요.")

    async def _read_limited(self, res: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in res.aiter_bytes():
            size += len(chunk)
            if size > self.max_bytes:
                raise SourceError(f"파일이 너무 커요 ({self.max_bytes // (1024 * 1024)}MB 제한).")
            chunks.append(chunk)
        return b"".join(chunks)

    async def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise SourceError("http 또는 https 주소만 불러올 수 있어요.")
        try:
            addresses = await asyncio.to_thread(self.resolver, parts.hostname)
        except OSError as exc:
            raise SourceError(f"주소를 찾을 수 없어요: {parts.hostname}") from exc
        for addr in addresses:
            ip = ipaddress.ip_address(addr)
            if not ip.is_global:
                raise SourceError("내부망 주소는 불러올 수 없어요.")

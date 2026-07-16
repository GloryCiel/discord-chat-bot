"""Media metadata and stream URL extraction with yt-dlp."""

import asyncio
from collections.abc import Callable, Mapping
from typing import Any, Protocol
from urllib.parse import urlparse

import yt_dlp

from src.domain.music import Track


class MediaExtractionError(RuntimeError):
    """A user-facing media lookup or extraction failure."""


class MediaExtractor(Protocol):
    async def search(self, query: str, requested_by: int) -> Track: ...

    async def get_stream_url(self, track: Track) -> str: ...


YdlFactory = Callable[[dict[str, Any]], Any]


class YtDlpMediaExtractor:
    """Resolve public searches and page URLs without blocking Discord."""

    DEFAULT_OPTIONS: dict[str, Any] = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 3,
    }

    def __init__(
        self,
        options: Mapping[str, Any] | None = None,
        ydl_factory: YdlFactory = yt_dlp.YoutubeDL,
    ):
        self.options = {**self.DEFAULT_OPTIONS, **(options or {})}
        self._ydl_factory = ydl_factory

    async def search(self, query: str, requested_by: int) -> Track:
        normalized_query = query.strip()
        if not normalized_query:
            raise MediaExtractionError("검색어나 URL을 입력해 주세요.")

        target = (
            normalized_query
            if self._is_http_url(normalized_query)
            else f"ytsearch1:{normalized_query}"
        )
        info = await self._extract(target)
        media = self._first_media(info)

        title = media.get("title")
        webpage_url = media.get("webpage_url") or media.get("original_url")
        if not title or not webpage_url:
            raise MediaExtractionError("검색 결과에서 곡 정보를 찾지 못했습니다.")

        duration = media.get("duration")
        return Track(
            title=str(title),
            webpage_url=str(webpage_url),
            requested_by=requested_by,
            duration_seconds=int(duration) if duration is not None else None,
        )

    async def get_stream_url(self, track: Track) -> str:
        info = await self._extract(track.webpage_url)
        media = self._first_media(info)
        stream_url = media.get("url")
        if not stream_url:
            raise MediaExtractionError("재생 가능한 오디오 주소를 찾지 못했습니다.")
        return str(stream_url)

    async def _extract(self, target: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(self._extract_sync, target)
        except yt_dlp.utils.DownloadError as exc:
            raise MediaExtractionError(
                "미디어 정보를 가져오지 못했습니다. URL이나 검색어를 확인해 주세요."
            ) from exc

    def _extract_sync(self, target: str) -> dict[str, Any]:
        with self._ydl_factory(self.options) as ydl:
            result = ydl.extract_info(target, download=False)
        if not isinstance(result, dict):
            raise MediaExtractionError("미디어 검색 결과가 비어 있습니다.")
        return result

    @staticmethod
    def _first_media(info: dict[str, Any]) -> dict[str, Any]:
        entries = info.get("entries")
        if entries is None:
            return info
        first = next((entry for entry in entries if isinstance(entry, dict)), None)
        if first is None:
            raise MediaExtractionError("검색 결과가 없습니다.")
        return first

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

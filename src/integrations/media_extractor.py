"""Media metadata and stream URL extraction.

Implement TODO(MUSIC-2) after adding yt-dlp to ``requirements.txt``.
"""

from typing import Protocol

from src.domain.music import Track


class MediaExtractor(Protocol):
    async def search(self, query: str, requested_by: int) -> Track: ...

    async def get_stream_url(self, track: Track) -> str: ...


class YtDlpMediaExtractor:
    """Resolve searches and page URLs with yt-dlp without blocking Discord."""

    async def search(self, query: str, requested_by: int) -> Track:
        # TODO(MUSIC-2):
        # 1. Detect a URL or convert text to ytsearch1:<query>.
        # 2. Run YoutubeDL.extract_info in asyncio.to_thread().
        # 3. Convert the first result to Track.
        raise NotImplementedError("TODO(MUSIC-2): extract track metadata")

    async def get_stream_url(self, track: Track) -> str:
        # TODO(MUSIC-2): Resolve track.webpage_url immediately before playback.
        raise NotImplementedError("TODO(MUSIC-2): resolve a fresh stream URL")

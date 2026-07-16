import unittest

from src.domain.music import Track
from src.integrations.media_extractor import (
    MediaExtractionError,
    YtDlpMediaExtractor,
)


class FakeYoutubeDL:
    def __init__(self, options, responses, calls):
        self.options = options
        self.responses = responses
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, target, download):
        self.calls.append((target, download, self.options))
        return self.responses[target]


class ExtractorFixture:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def factory(self, options):
        return FakeYoutubeDL(options, self.responses, self.calls)


class YtDlpMediaExtractorTests(unittest.IsolatedAsyncioTestCase):
    async def test_searches_first_result_for_text_query(self) -> None:
        fixture = ExtractorFixture(
            {
                "ytsearch1:test song": {
                    "entries": [
                        {
                            "title": "Test Song",
                            "webpage_url": "https://example.com/watch/1",
                            "duration": 185,
                        }
                    ]
                }
            }
        )
        extractor = YtDlpMediaExtractor(ydl_factory=fixture.factory)

        track = await extractor.search("test song", requested_by=123)

        self.assertEqual(track.title, "Test Song")
        self.assertEqual(track.duration_seconds, 185)
        self.assertEqual(track.requested_by, 123)
        self.assertEqual(fixture.calls[0][0], "ytsearch1:test song")
        self.assertFalse(fixture.calls[0][1])
        self.assertTrue(fixture.calls[0][2]["noplaylist"])
        self.assertTrue(fixture.calls[0][2]["skip_download"])

    async def test_uses_http_url_without_converting_it_to_search(self) -> None:
        url = "https://example.com/watch/2"
        fixture = ExtractorFixture(
            {url: {"title": "URL Song", "webpage_url": url, "duration": None}}
        )
        extractor = YtDlpMediaExtractor(ydl_factory=fixture.factory)

        track = await extractor.search(url, requested_by=1)

        self.assertEqual(track.webpage_url, url)
        self.assertEqual(track.duration_label, "LIVE")
        self.assertEqual(fixture.calls[0][0], url)

    async def test_resolves_fresh_stream_url_from_webpage_url(self) -> None:
        webpage_url = "https://example.com/watch/3"
        fixture = ExtractorFixture(
            {webpage_url: {"url": "https://media.example.com/audio-stream"}}
        )
        extractor = YtDlpMediaExtractor(ydl_factory=fixture.factory)
        track = Track("Song", webpage_url, 1, 30)

        stream_url = await extractor.get_stream_url(track)

        self.assertEqual(stream_url, "https://media.example.com/audio-stream")
        self.assertEqual(fixture.calls[0][0], webpage_url)

    async def test_rejects_empty_query(self) -> None:
        extractor = YtDlpMediaExtractor(ydl_factory=lambda options: None)

        with self.assertRaisesRegex(MediaExtractionError, "검색어나 URL"):
            await extractor.search("   ", requested_by=1)

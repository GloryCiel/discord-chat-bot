import unittest

from src.domain.music import Track


class TrackTests(unittest.TestCase):
    def test_formats_duration(self) -> None:
        track = Track("title", "https://example.com/track", 1, 185)

        self.assertEqual(track.duration_label, "3:05")

    def test_formats_missing_duration_as_live(self) -> None:
        track = Track("live", "https://example.com/live", 1, None)

        self.assertEqual(track.duration_label, "LIVE")

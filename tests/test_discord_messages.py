import unittest

from src.utils.discord_messages import split_message


class SplitMessageTests(unittest.TestCase):
    def test_splits_at_requested_limit(self) -> None:
        self.assertEqual(split_message("abcdef", limit=2), ["ab", "cd", "ef"])

    def test_empty_message_returns_one_chunk(self) -> None:
        self.assertEqual(split_message(""), [""])

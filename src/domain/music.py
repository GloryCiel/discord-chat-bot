"""Music domain models.

Start with TODO(MUSIC-1) in ``docs/music-todo.md``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    """Metadata kept in a guild's queue.

    ``webpage_url`` is the stable page URL. Do not store the temporary direct
    media URL here because media URLs can expire before a queued track starts.
    """

    title: str
    webpage_url: str
    requested_by: int
    duration_seconds: int | None = None

    @property
    def duration_label(self) -> str:
        """Return a user-facing duration such as ``3:05`` or ``LIVE``."""
        if self.duration_seconds is None:
            return "LIVE"
        minute,second = divmod(self.duration_seconds, 60)
        return f"{minute}:{second:02d}"


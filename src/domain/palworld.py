"""Shared game-server infrastructure state models."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GameKind(str, Enum):
    PALWORLD = "palworld"
    RUST = "rust"

    @classmethod
    def parse(cls, value: Optional[str]) -> Optional["GameKind"]:
        if not value:
            return None
        try:
            return cls(value.lower())
        except ValueError:
            return None

    @property
    def label(self) -> str:
        return "팰월드" if self is GameKind.PALWORLD else "러스트"


@dataclass(frozen=True)
class InstanceState:
    status: str
    external_ip: Optional[str]
    selected_game: Optional[GameKind] = None

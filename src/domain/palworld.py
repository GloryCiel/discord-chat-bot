"""Palworld infrastructure state models."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InstanceState:
    status: str
    external_ip: Optional[str]

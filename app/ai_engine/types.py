from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(slots=True)
class PitchFrame:
	timestamp_ms: float
	f0_hz: Optional[float]
	midi: Optional[float]
	cents: Optional[float]
	voiced: bool
	confidence: float
	source: str

	def to_dict(self) -> dict:
		return asdict(self)

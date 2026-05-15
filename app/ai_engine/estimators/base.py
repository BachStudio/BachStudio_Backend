from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(slots=True)
class EstimateResult:
	f0_hz: Optional[float]
	confidence: float
	voiced: bool
	source: str


class PitchEstimator(ABC):
	@abstractmethod
	def estimate(self, frame: Sequence[float]) -> EstimateResult:
		raise NotImplementedError

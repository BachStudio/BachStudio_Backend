from __future__ import annotations

import math
import statistics
from collections import deque
from typing import Optional


class PitchPostProcessor:
	def __init__(
		self,
		*,
		confidence_threshold: float,
		median_window: int,
		max_octave_jump_factor: float,
	):
		self.confidence_threshold = confidence_threshold
		self.max_octave_jump_factor = max_octave_jump_factor
		self._history: deque[float] = deque(maxlen=max(3, median_window))
		self._last_valid_f0: Optional[float] = None

	def process(self, f0_hz: Optional[float], confidence: float, voiced: bool) -> tuple[Optional[float], float, bool]:
		if not voiced or f0_hz is None or f0_hz <= 0.0 or confidence < self.confidence_threshold:
			return None, confidence, False

		corrected = self._suppress_octave_jump(f0_hz)
		self._history.append(corrected)
		smoothed = float(statistics.median(self._history))
		self._last_valid_f0 = smoothed
		return smoothed, confidence, True

	def _suppress_octave_jump(self, current_f0: float) -> float:
		if self._last_valid_f0 is None:
			return current_f0

		low = min(current_f0, self._last_valid_f0)
		high = max(current_f0, self._last_valid_f0)
		ratio = high / max(low, 1e-6)

		if ratio < self.max_octave_jump_factor:
			return current_f0

		candidates = [current_f0, current_f0 * 0.5, current_f0 * 2.0]
		return min(candidates, key=lambda value: abs(value - self._last_valid_f0 or 0.0))


def hz_to_midi_and_cents(f0_hz: Optional[float]) -> tuple[Optional[float], Optional[float]]:
	if f0_hz is None or f0_hz <= 0.0:
		return None, None

	midi = 69.0 + 12.0 * math.log2(f0_hz / 440.0)
	nearest = round(midi)
	cents = (midi - nearest) * 100.0
	return float(midi), float(cents)

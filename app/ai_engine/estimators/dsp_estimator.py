from __future__ import annotations

import math
from typing import Sequence

from app.ai_engine.estimators.base import EstimateResult, PitchEstimator


class DspAutocorrEstimator(PitchEstimator):
	def __init__(self, *, sample_rate: int, fmin_hz: float, fmax_hz: float, min_rms_energy: float):
		self.sample_rate = sample_rate
		self.fmin_hz = fmin_hz
		self.fmax_hz = fmax_hz
		self.min_rms_energy = min_rms_energy

	def estimate(self, frame: Sequence[float]) -> EstimateResult:
		if not frame:
			return EstimateResult(f0_hz=None, confidence=0.0, voiced=False, source="dsp_acf")

		samples = [float(value) for value in frame]
		rms = math.sqrt(sum(value * value for value in samples) / len(samples))
		if rms < self.min_rms_energy:
			return EstimateResult(f0_hz=None, confidence=min(0.2, rms), voiced=False, source="dsp_acf")

		min_lag = max(1, int(self.sample_rate / self.fmax_hz))
		max_lag = min(len(samples) - 2, int(self.sample_rate / self.fmin_hz))
		if min_lag >= max_lag:
			return EstimateResult(f0_hz=None, confidence=0.0, voiced=False, source="dsp_acf")

		centered = self._remove_mean(samples)
		ac0 = self._autocorr(centered, 0)
		if ac0 <= 1e-9:
			return EstimateResult(f0_hz=None, confidence=0.0, voiced=False, source="dsp_acf")

		best_lag = None
		best_score = -1.0
		for lag in range(min_lag, max_lag + 1):
			score = self._autocorr(centered, lag) / ac0
			if score > best_score:
				best_score = score
				best_lag = lag

		if best_lag is None or best_score < 0.2:
			return EstimateResult(f0_hz=None, confidence=max(0.0, best_score), voiced=False, source="dsp_acf")

		f0_hz = float(self.sample_rate / best_lag)
		confidence = float(max(0.0, min(1.0, best_score)))
		voiced = confidence >= 0.5
		return EstimateResult(f0_hz=f0_hz if voiced else None, confidence=confidence, voiced=voiced, source="dsp_acf")

	@staticmethod
	def _remove_mean(samples: list[float]) -> list[float]:
		average = sum(samples) / len(samples)
		return [sample - average for sample in samples]

	@staticmethod
	def _autocorr(samples: list[float], lag: int) -> float:
		n = len(samples) - lag
		if n <= 1:
			return 0.0
		total = 0.0
		for index in range(n):
			total += samples[index] * samples[index + lag]
		return total

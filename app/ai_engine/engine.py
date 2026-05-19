from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from app.ai_engine.audio_io import load_wav_mono
from app.ai_engine.config import EngineConfig
from app.ai_engine.estimators import DspAutocorrEstimator, RmvpePitchEstimator
from app.ai_engine.postprocess import PitchPostProcessor, hz_to_midi_and_cents
from app.ai_engine.types import PitchFrame


class RealtimePitchEngine:
	def __init__(self, config: EngineConfig):
		self.config = config
		self.estimator = self._build_estimator()
		self.post = PitchPostProcessor(
			confidence_threshold=config.confidence_threshold,
			median_window=config.median_window,
			max_octave_jump_factor=config.max_octave_jump_factor,
		)

	def _build_estimator(self):
		if self.config.prefer_rmvpe:
			try:
				return RmvpePitchEstimator(
					sample_rate=self.config.sample_rate,
					model_path=self.config.rmvpe_model_path,
				)
			except Exception:
				pass

		return DspAutocorrEstimator(
			sample_rate=self.config.sample_rate,
			fmin_hz=self.config.fmin_hz,
			fmax_hz=self.config.fmax_hz,
			min_rms_energy=self.config.min_rms_energy,
		)

	def process_frame(self, frame: list[float], timestamp_ms: float) -> PitchFrame:
		raw = self.estimator.estimate(frame)
		return self._to_pitch_frame(raw, timestamp_ms)

	def _to_pitch_frame(self, raw, timestamp_ms: float) -> PitchFrame:
		f0_hz, confidence, voiced = self.post.process(raw.f0_hz, raw.confidence, raw.voiced)
		midi, cents = hz_to_midi_and_cents(f0_hz)

		return PitchFrame(
			timestamp_ms=timestamp_ms,
			f0_hz=f0_hz,
			midi=midi,
			cents=cents,
			voiced=voiced,
			confidence=max(0.0, min(1.0, confidence)),
			source=raw.source,
		)

	def run_wav(self, wav_path: str | Path, on_frame: Callable[[PitchFrame], None]) -> None:
		samples, _ = load_wav_mono(wav_path, self.config.sample_rate)
		self.run_samples(samples, on_frame)

	def run_samples(self, samples: list[float], on_frame: Callable[[PitchFrame], None]) -> None:
		if hasattr(self.estimator, "estimate_series"):
			for timestamp_ms, raw in self.estimator.estimate_series(samples):
				on_frame(self._to_pitch_frame(raw, timestamp_ms))
			return

		index = 0
		while index + self.config.frame_length <= len(samples):
			frame = samples[index : index + self.config.frame_length]
			timestamp_ms = (index / self.config.sample_rate) * 1000.0
			on_frame(self.process_frame(frame, timestamp_ms))
			index += self.config.hop_length

	@staticmethod
	def print_json_line(frame: PitchFrame) -> None:
		print(json.dumps(frame.to_dict(), ensure_ascii=True), flush=True)

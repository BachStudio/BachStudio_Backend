from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EngineConfig:
	sample_rate: int = 16000

	frame_length: int = 1024
	hop_length: int = 160

	fmin_hz: float = 50.0
	fmax_hz: float = 1200.0
	min_rms_energy: float = 0.01

	confidence_threshold: float = 0.12
	median_window: int = 5
	max_octave_jump_factor: float = 1.8

	prefer_rmvpe: bool = True
	rmvpe_model_path: str | None = None

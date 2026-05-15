from __future__ import annotations

import os
from typing import Any, Sequence

from app.ai_engine.estimators.base import EstimateResult, PitchEstimator


class RmvpePitchEstimator(PitchEstimator):
	def __init__(self, *, sample_rate: int, model_path: str | None = None):
		self.sample_rate = sample_rate
		self.model_path = model_path or os.getenv("RMVPE_MODEL_PATH")
		self._model = self._load_model()

	def _load_model(self) -> Any:
		try:
			from rmvpe_onnx import RMVPE  # type: ignore

			if self.model_path:
				try:
					return RMVPE(model_path=self.model_path)
				except TypeError:
					return RMVPE(self.model_path)
			return RMVPE()
		except Exception:
			pass

		try:
			from rmvpe import RMVPE  # type: ignore
		except Exception as exc:
			raise RuntimeError("RMVPE backend is not installed") from exc

		if self.model_path:
			try:
				return RMVPE(model_path=self.model_path)
			except TypeError:
				return RMVPE(self.model_path)
		return RMVPE()

	def estimate(self, frame: Sequence[float]) -> EstimateResult:
		out = self._predict(frame)
		f0_hz, confidence = self._parse_output(out)
		voiced = f0_hz is not None and f0_hz > 0.0
		if not voiced:
			return EstimateResult(f0_hz=None, confidence=confidence, voiced=False, source="rmvpe")
		return EstimateResult(f0_hz=f0_hz, confidence=confidence, voiced=True, source="rmvpe")

	def estimate_series(self, samples: Sequence[float]) -> list[tuple[float, EstimateResult]]:
		out = self._predict(samples)
		if not isinstance(out, tuple) or len(out) < 3:
			return [(0.0, self.estimate(samples))]

		times = self._to_float_list(out[0])
		frequencies = self._to_float_list(out[1])
		confidences = self._to_float_list(out[2])
		n = min(len(times), len(frequencies), len(confidences))
		frames: list[tuple[float, EstimateResult]] = []

		for index in range(n):
			f0_hz = frequencies[index] if frequencies[index] > 0.0 else None
			confidence = max(0.0, min(1.0, confidences[index]))
			frames.append(
				(
					max(0.0, times[index] * 1000.0),
					EstimateResult(
						f0_hz=f0_hz,
						confidence=confidence,
						voiced=f0_hz is not None,
						source="rmvpe",
					),
				)
			)

		return frames

	def _predict(self, frame: Sequence[float]):
		model = self._model
		audio = frame

		try:
			import numpy as np  # type: ignore

			audio = np.asarray(frame, dtype=np.float32)
		except Exception:
			pass

		if hasattr(model, "infer_from_audio"):
			out = model.infer_from_audio(audio, sample_rate=self.sample_rate)
		elif hasattr(model, "infer"):
			out = model.infer(audio, sample_rate=self.sample_rate)
		elif hasattr(model, "predict"):
			out = model.predict(audio, self.sample_rate)
		else:
			raise RuntimeError("Unsupported RMVPE API")
		return out

	def _parse_output(self, out: Any) -> tuple[float | None, float]:
		if isinstance(out, tuple) and len(out) >= 3:
			frequencies = self._to_float_list(out[1])
			confidences = self._to_float_list(out[2])
			n = min(len(frequencies), len(confidences))
			if n > 0:
				start = int(n * 0.6)
				best_index = -1
				best_confidence = -1.0
				for index in range(start, n):
					if frequencies[index] > 0.0 and confidences[index] > best_confidence:
						best_index = index
						best_confidence = confidences[index]
				if best_index >= 0:
					return frequencies[best_index], max(0.0, min(1.0, confidences[best_index]))

			f0 = self._last_or_none(out[1])
			confidence = self._last_or_none(out[2])
			return self._clean_f0_confidence(f0, confidence)

		if isinstance(out, dict):
			return self._clean_f0_confidence(self._last_or_none(out.get("f0")), self._last_or_none(out.get("confidence")))

		f0 = self._last_or_none(out)
		return self._clean_f0_confidence(f0, None)

	@staticmethod
	def _clean_f0_confidence(f0: Any, confidence: Any) -> tuple[float | None, float]:
		f0_hz = float(f0) if f0 not in (None, 0) else None
		value = float(confidence) if confidence is not None else (1.0 if f0_hz is not None else 0.0)
		return f0_hz, max(0.0, min(1.0, value))

	@staticmethod
	def _last_or_none(value: Any):
		if value is None:
			return None
		if isinstance(value, (list, tuple)):
			return value[-1] if value else None
		try:
			if hasattr(value, "__len__") and len(value) > 0:
				return value[-1]
		except Exception:
			pass
		return value

	@staticmethod
	def _to_float_list(value: Any) -> list[float]:
		if value is None:
			return []
		if isinstance(value, list):
			return [float(item) for item in value]
		if isinstance(value, tuple):
			return [float(item) for item in value]
		try:
			if hasattr(value, "tolist"):
				raw = value.tolist()
				if isinstance(raw, list):
					return [float(item) for item in raw]
		except Exception:
			pass
		try:
			if hasattr(value, "__len__"):
				return [float(item) for item in value]
		except Exception:
			pass
		try:
			return [float(value)]
		except Exception:
			return []

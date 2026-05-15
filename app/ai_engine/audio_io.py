from __future__ import annotations

import wave
from array import array
from pathlib import Path


def _linear_resample(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
	if src_rate == dst_rate or not samples:
		return samples

	src_len = len(samples)
	dst_len = max(1, int(src_len * dst_rate / src_rate))
	out = [0.0] * dst_len

	for i in range(dst_len):
		pos = i * (src_len - 1) / max(dst_len - 1, 1)
		left = int(pos)
		right = min(left + 1, src_len - 1)
		frac = pos - left
		out[i] = (1.0 - frac) * samples[left] + frac * samples[right]

	return out


def load_wav_mono(path: str | Path, target_sample_rate: int) -> tuple[list[float], int]:
	with wave.open(str(path), "rb") as wav_file:
		channels = wav_file.getnchannels()
		sample_width = wav_file.getsampwidth()
		sample_rate = wav_file.getframerate()
		n_frames = wav_file.getnframes()
		raw = wav_file.readframes(n_frames)

	if sample_width != 2:
		raise ValueError("Only 16-bit PCM WAV is supported")

	ints = array("h")
	ints.frombytes(raw)

	if channels == 1:
		mono = [value / 32768.0 for value in ints]
	else:
		mono = [ints[index] / 32768.0 for index in range(0, len(ints), channels)]

	if sample_rate != target_sample_rate:
		mono = _linear_resample(mono, sample_rate, target_sample_rate)
		sample_rate = target_sample_rate

	return mono, sample_rate

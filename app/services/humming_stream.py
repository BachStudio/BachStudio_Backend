from __future__ import annotations

import json
import math
import sys
from array import array
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.ai_engine.config import EngineConfig
from app.ai_engine.engine import RealtimePitchEngine
from app.ai_engine.types import PitchFrame
from app.core.config import settings
from app.schemas.humming import HummingNote
from app.services.humming import (
	DEFAULT_QUANTIZE,
	estimate_key,
	frames_to_notes,
	midi_to_note_name,
	ms_to_beats,
	parse_quantize,
	quantize_floor,
	quantize_round,
)


TARGET_SAMPLE_RATE = 16000
DEFAULT_SOURCE_SAMPLE_RATE = 48000


@dataclass(slots=True)
class LiveSegment:
	start_ms: float
	end_ms: float
	midis: list[int] = field(default_factory=list)
	confidences: list[float] = field(default_factory=list)


class RealtimeHummingSession:
	def __init__(
		self,
		*,
		source_sample_rate: int = DEFAULT_SOURCE_SAMPLE_RATE,
		bpm: float = 120.0,
		clip_length_beats: float = 8.0,
		quantize: str = DEFAULT_QUANTIZE,
		prefer_rmvpe: bool = True,
	):
		self.source_sample_rate = max(1, int(source_sample_rate))
		self.bpm = max(1.0, float(bpm))
		self.clip_length_beats = max(0.25, float(clip_length_beats))
		self.quantize = quantize or DEFAULT_QUANTIZE
		self.quantum = parse_quantize(self.quantize)
		self.prefer_rmvpe = bool(prefer_rmvpe)

		frame_length = 5120 if self.prefer_rmvpe else 1024
		hop_length = 800 if self.prefer_rmvpe else 160
		self.engine = RealtimePitchEngine(
			EngineConfig(
				sample_rate=TARGET_SAMPLE_RATE,
				frame_length=frame_length,
				hop_length=hop_length,
				prefer_rmvpe=self.prefer_rmvpe,
				rmvpe_model_path=settings.AI_RMVPE_MODEL_PATH,
				confidence_threshold=settings.AI_CONFIDENCE_THRESHOLD,
			)
		)
		if self.prefer_rmvpe and self.engine.estimator.__class__.__name__ != "RmvpePitchEstimator":
			self.prefer_rmvpe = False
			self.engine = RealtimePitchEngine(
				EngineConfig(
					sample_rate=TARGET_SAMPLE_RATE,
					frame_length=1024,
					hop_length=160,
					prefer_rmvpe=False,
					confidence_threshold=settings.AI_CONFIDENCE_THRESHOLD,
				)
			)

		self.buffer: list[float] = []
		self.processed_samples = 0
		self.current_segment: LiveSegment | None = None
		self.last_timestamp: float | None = None
		self.last_midi: int | None = None
		self.notes: list[HummingNote] = []
		self.final_samples: list[float] = []
		self.max_final_samples = max(1, int(settings.AI_MAX_AUDIO_SECONDS * TARGET_SAMPLE_RATE))

	def accept_bytes(self, payload: bytes) -> list[dict[str, Any]]:
		samples = decode_float32le(payload)
		target_samples = resample_mono(samples, self.source_sample_rate, TARGET_SAMPLE_RATE)
		self.buffer.extend(target_samples)
		self.append_final_samples(target_samples)

		events: list[dict[str, Any]] = []
		while len(self.buffer) >= self.engine.config.frame_length:
			frame_samples = self.buffer[: self.engine.config.frame_length]
			timestamp_ms = (self.processed_samples / TARGET_SAMPLE_RATE) * 1000.0
			frame = self.engine.process_frame(frame_samples, timestamp_ms)
			events.append(self.frame_event(frame))
			events.extend(self.update_note_tracking(frame))

			del self.buffer[: self.engine.config.hop_length]
			self.processed_samples += self.engine.config.hop_length

		return events

	def finish(self) -> list[dict[str, Any]]:
		events: list[dict[str, Any]] = []
		final_event = self.close_current_segment(reason="stop")
		if final_event is not None:
			events.append(final_event)

		final_notes, final_source = self.finalize_with_rmvpe()
		events.append(
			{
				"type": "complete",
				"mode": "hybrid_rmvpe",
				"key": estimate_key(final_notes),
				"source": final_source,
				"liveSource": "rmvpe" if self.engine.estimator.__class__.__name__ == "RmvpePitchEstimator" else "dsp_acf",
				"notes": [note.model_dump() for note in final_notes],
				"liveNotes": [note.model_dump() for note in self.notes],
			}
		)
		return events

	def append_final_samples(self, samples: list[float]) -> None:
		if len(self.final_samples) >= self.max_final_samples:
			return
		remaining = self.max_final_samples - len(self.final_samples)
		self.final_samples.extend(samples[:remaining])

	def finalize_with_rmvpe(self) -> tuple[list[HummingNote], str]:
		if not self.final_samples:
			source = "rmvpe" if self.engine.estimator.__class__.__name__ == "RmvpePitchEstimator" else "dsp_acf"
			return self.notes, source

		final_engine = RealtimePitchEngine(
			EngineConfig(
				sample_rate=TARGET_SAMPLE_RATE,
				frame_length=5120,
				hop_length=800,
				prefer_rmvpe=True,
				rmvpe_model_path=settings.AI_RMVPE_MODEL_PATH,
				confidence_threshold=settings.AI_CONFIDENCE_THRESHOLD,
			)
		)
		frames: list[PitchFrame] = []
		final_engine.run_samples(self.final_samples, frames.append)
		final_notes = frames_to_notes(
			frames,
			bpm=self.bpm,
			clip_length_beats=self.clip_length_beats,
			quantize=self.quantize,
		)
		final_source = "rmvpe" if final_engine.estimator.__class__.__name__ == "RmvpePitchEstimator" else "dsp_acf"
		return final_notes or self.notes, final_source

	def frame_event(self, frame: PitchFrame) -> dict[str, Any]:
		midi = int(round(frame.midi)) if frame.midi is not None and math.isfinite(frame.midi) else None
		return {
			"type": "pitch",
			"timestampMs": round(frame.timestamp_ms, 3),
			"beat": round(ms_to_beats(frame.timestamp_ms, self.bpm), 4),
			"f0Hz": round(frame.f0_hz, 4) if frame.f0_hz is not None else None,
			"midi": midi,
			"note": midi_to_note_name(midi) if midi is not None else None,
			"cents": round(frame.cents, 4) if frame.cents is not None else None,
			"voiced": frame.voiced,
			"confidence": round(frame.confidence, 4),
			"source": frame.source,
		}

	def update_note_tracking(self, frame: PitchFrame) -> list[dict[str, Any]]:
		midi = self.frame_midi(frame)
		if midi is None:
			event = self.close_current_segment(reason="unvoiced")
			self.last_timestamp = None
			self.last_midi = None
			return [event] if event is not None else []

		timestamp = max(0.0, float(frame.timestamp_ms))
		should_start = self.current_segment is None
		if self.last_timestamp is not None and timestamp - self.last_timestamp > settings.AI_MAX_FRAME_GAP_MS:
			should_start = True
		if self.last_midi is not None and abs(midi - self.last_midi) > settings.AI_MAX_PITCH_JUMP_SEMITONES:
			should_start = True

		if should_start:
			events: list[dict[str, Any]] = []
			previous_event = self.close_current_segment(reason="pitch_change")
			if previous_event is not None:
				events.append(previous_event)
			self.current_segment = LiveSegment(
				start_ms=timestamp,
				end_ms=timestamp + self.hop_ms,
				midis=[midi],
				confidences=[frame.confidence],
			)
			self.last_timestamp = timestamp
			self.last_midi = midi
			note = self.segment_to_note(self.current_segment)
			events.append({"type": "note_on", "note": note.model_dump()})
			return events

		if self.current_segment is not None:
			self.current_segment.midis.append(midi)
			self.current_segment.confidences.append(frame.confidence)
			self.current_segment.end_ms = timestamp + self.hop_ms

		self.last_timestamp = timestamp
		self.last_midi = midi
		if self.current_segment is None:
			return []
		return [{"type": "note_update", "note": self.segment_to_note(self.current_segment).model_dump()}]

	def close_current_segment(self, *, reason: str) -> dict[str, Any] | None:
		if self.current_segment is None:
			return None

		note = self.segment_to_note(self.current_segment)
		self.current_segment = None
		if note.durationBeats < settings.AI_MIN_NOTE_DURATION_BEATS:
			return None
		if note.startBeat >= self.clip_length_beats:
			return None

		self.notes.append(note)
		return {"type": "note_off", "reason": reason, "note": note.model_dump()}

	def segment_to_note(self, segment: LiveSegment) -> HummingNote:
		midi = int(round(median(segment.midis)))
		start_beat = quantize_floor(ms_to_beats(segment.start_ms, self.bpm), self.quantum)
		duration_beat = ms_to_beats(max(self.hop_ms, segment.end_ms - segment.start_ms), self.bpm)
		duration_beat = max(self.quantum, quantize_round(duration_beat, self.quantum))
		if start_beat < self.clip_length_beats:
			duration_beat = min(duration_beat, self.clip_length_beats - start_beat)

		return HummingNote(
			midi=max(0, min(127, midi)),
			note=midi_to_note_name(midi),
			startBeat=round(max(0.0, start_beat), 4),
			durationBeats=round(max(self.quantum, duration_beat), 4),
			confidence=round(max(0.0, min(1.0, mean(segment.confidences))), 4),
		)

	def frame_midi(self, frame: PitchFrame) -> int | None:
		if not frame.voiced or frame.midi is None:
			return None
		if frame.confidence < settings.AI_CONFIDENCE_THRESHOLD:
			return None
		if not math.isfinite(frame.midi):
			return None
		return int(round(frame.midi))

	@property
	def hop_ms(self) -> float:
		return (self.engine.config.hop_length / TARGET_SAMPLE_RATE) * 1000.0


async def stream_humming(websocket: WebSocket) -> None:
	await websocket.accept()
	try:
		session = session_from_mapping(websocket.query_params)
	except Exception as exc:
		await websocket.send_json({"type": "error", "message": f"Invalid stream config: {exc}"})
		await websocket.close(code=1003)
		return
	await websocket.send_json(ready_event(session))

	try:
		while True:
			message = await websocket.receive()
			if message.get("type") == "websocket.disconnect":
				break

			text = message.get("text")
			if text is not None:
				session = await handle_text_message(websocket, session, text)
				continue

			payload = message.get("bytes")
			if payload is None:
				continue

			try:
				events = session.accept_bytes(payload)
			except ValueError as exc:
				await websocket.send_json({"type": "error", "message": str(exc)})
				continue

			for event in events:
				await websocket.send_json(event)
	except WebSocketDisconnect:
		return


async def handle_text_message(
	websocket: WebSocket,
	session: RealtimeHummingSession,
	text: str,
) -> RealtimeHummingSession:
	try:
		payload = json.loads(text)
	except json.JSONDecodeError:
		await websocket.send_json({"type": "error", "message": "Text messages must be JSON."})
		return session

	message_type = payload.get("type")
	if message_type in {"start", "config"}:
		try:
			session = session_from_mapping(payload)
		except Exception as exc:
			await websocket.send_json({"type": "error", "message": f"Invalid stream config: {exc}"})
			return session
		await websocket.send_json(ready_event(session))
		return session

	if message_type == "stop":
		for event in session.finish():
			await websocket.send_json(event)
		return session

	if message_type == "ping":
		await websocket.send_json({"type": "pong"})
		return session

	await websocket.send_json({"type": "error", "message": f"Unsupported message type: {message_type}"})
	return session


def session_from_mapping(mapping: Any) -> RealtimeHummingSession:
	return RealtimeHummingSession(
		source_sample_rate=int(read_value(mapping, "sampleRate", DEFAULT_SOURCE_SAMPLE_RATE)),
		bpm=float(read_value(mapping, "bpm", 120.0)),
		clip_length_beats=float(read_value(mapping, "clipLengthBeats", 8.0)),
		quantize=str(read_value(mapping, "quantize", DEFAULT_QUANTIZE)),
		prefer_rmvpe=read_bool(mapping, "preferRmvpe", settings.AI_PREFER_RMVPE),
	)


def ready_event(session: RealtimeHummingSession) -> dict[str, Any]:
	return {
		"type": "ready",
		"inputFormat": "float32le",
		"channels": 1,
		"sourceSampleRate": session.source_sample_rate,
		"analysisSampleRate": TARGET_SAMPLE_RATE,
		"frameLength": session.engine.config.frame_length,
		"hopLength": session.engine.config.hop_length,
		"bpm": session.bpm,
		"clipLengthBeats": session.clip_length_beats,
		"quantize": session.quantize,
		"source": "rmvpe" if session.engine.estimator.__class__.__name__ == "RmvpePitchEstimator" else "dsp_acf",
	}


def read_value(mapping: Any, key: str, default: Any) -> Any:
	if hasattr(mapping, "get"):
		value = mapping.get(key, default)
		return default if value in (None, "") else value
	return default


def read_bool(mapping: Any, key: str, default: bool) -> bool:
	value = read_value(mapping, key, default)
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def decode_float32le(payload: bytes) -> list[float]:
	if len(payload) % 4 != 0:
		raise ValueError("Audio binary payload must be Float32 little-endian PCM.")

	samples = array("f")
	samples.frombytes(payload)
	if sys.byteorder != "little":
		samples.byteswap()
	return [clamp_sample(value) for value in samples]


def clamp_sample(value: float) -> float:
	if not math.isfinite(value):
		return 0.0
	return max(-1.0, min(1.0, float(value)))


def resample_mono(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
	if src_rate == dst_rate or not samples:
		return samples

	src_len = len(samples)
	dst_len = max(1, int(src_len * dst_rate / src_rate))
	out = [0.0] * dst_len
	for index in range(dst_len):
		pos = index * (src_len - 1) / max(dst_len - 1, 1)
		left = int(pos)
		right = min(left + 1, src_len - 1)
		frac = pos - left
		out[index] = (1.0 - frac) * samples[left] + frac * samples[right]
	return out

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.ai_engine.config import EngineConfig
from app.ai_engine.engine import RealtimePitchEngine
from app.ai_engine.types import PitchFrame
from app.schemas.humming import HummingNote, HummingTranscriptionResponse


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
DEFAULT_QUANTIZE = "1/16"
SUPPORTED_EXTENSIONS = {".wav", ".webm", ".mp3", ".m4a", ".ogg", ".flac"}


@dataclass(slots=True)
class _Segment:
	start_ms: float
	end_ms: float
	midis: list[int]
	confidences: list[float]


def transcribe_upload(
	audio: UploadFile,
	*,
	bpm: float,
	clip_length_beats: float,
	quantize: str = DEFAULT_QUANTIZE,
) -> HummingTranscriptionResponse:
	if bpm <= 0:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bpm must be greater than 0")

	if clip_length_beats <= 0:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail="clipLengthBeats must be greater than 0",
		)

	suffix = Path(audio.filename or "").suffix.lower()
	if suffix and suffix not in SUPPORTED_EXTENSIONS:
		raise HTTPException(
			status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
			detail=f"Unsupported audio extension: {suffix}",
		)

	with tempfile.TemporaryDirectory(prefix="bachstudio-humming-") as temp_dir:
		temp_path = Path(temp_dir)
		input_path = temp_path / f"upload{suffix or '.audio'}"
		wav_path = temp_path / "input.wav"
		_write_upload(audio, input_path)
		normalize_audio(input_path, wav_path)

		frames = analyze_wav(wav_path)
		notes = frames_to_notes(
			frames,
			bpm=bpm,
			clip_length_beats=clip_length_beats,
			quantize=quantize,
		)

	return HummingTranscriptionResponse(key=estimate_key(notes), notes=notes)


def normalize_audio(input_path: Path, output_path: Path) -> None:
	if input_path.suffix.lower() == ".wav":
		shutil.copyfile(input_path, output_path)
		return

	ffmpeg_path = shutil.which("ffmpeg")
	if ffmpeg_path:
		command = [
			ffmpeg_path,
			"-hide_banner",
			"-loglevel",
			"error",
			"-y",
			"-i",
			str(input_path),
			"-t",
			str(settings.AI_MAX_AUDIO_SECONDS),
			"-ac",
			"1",
			"-ar",
			"16000",
			"-sample_fmt",
			"s16",
			str(output_path),
		]
		result = subprocess.run(command, capture_output=True, text=True, check=False)
		if result.returncode != 0:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail=f"Could not decode uploaded audio: {result.stderr.strip() or 'ffmpeg failed'}",
		)
		return

	raise HTTPException(
		status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
		detail="ffmpeg is required for webm/mp3/m4a/ogg/flac uploads. Install ffmpeg or upload WAV.",
	)


def analyze_wav(wav_path: Path) -> list[PitchFrame]:
	engine = RealtimePitchEngine(
		EngineConfig(
			prefer_rmvpe=settings.AI_PREFER_RMVPE,
			rmvpe_model_path=settings.AI_RMVPE_MODEL_PATH,
			confidence_threshold=settings.AI_CONFIDENCE_THRESHOLD,
		)
	)
	frames: list[PitchFrame] = []
	engine.run_wav(wav_path, frames.append)
	return frames


def frames_to_notes(
	frames: list[PitchFrame],
	*,
	bpm: float,
	clip_length_beats: float,
	quantize: str = DEFAULT_QUANTIZE,
) -> list[HummingNote]:
	if not frames:
		return []

	quantum = parse_quantize(quantize)
	hop_ms = infer_hop_ms(frames)
	segments = build_segments(frames, hop_ms)
	notes: list[HummingNote] = []

	for segment in segments:
		midi = int(round(median(segment.midis)))
		start_beat, duration_beat = quantize_note_bounds(
			ms_to_beats(segment.start_ms, bpm),
			ms_to_beats(max(segment.start_ms + hop_ms, segment.end_ms), bpm),
			quantum,
			clip_length_beats,
		)

		if start_beat >= clip_length_beats:
			continue
		if duration_beat < settings.AI_MIN_NOTE_DURATION_BEATS:
			continue

		notes.append(
			HummingNote(
				midi=max(0, min(127, midi)),
				note=midi_to_note_name(midi),
				startBeat=round(start_beat, 4),
				durationBeats=round(duration_beat, 4),
				confidence=round(max(0.0, min(1.0, mean(segment.confidences))), 4),
			)
		)

	return merge_adjacent_notes(notes, quantum)


def build_segments(frames: list[PitchFrame], hop_ms: float) -> list[_Segment]:
	segments: list[_Segment] = []
	current: _Segment | None = None
	last_voiced_timestamp: float | None = None
	last_midi: int | None = None

	for frame in frames:
		timestamp = max(0.0, float(frame.timestamp_ms))
		midi = frame_midi(frame)
		if midi is None:
			if (
				current is not None
				and last_voiced_timestamp is not None
				and timestamp - last_voiced_timestamp > settings.AI_MAX_FRAME_GAP_MS
			):
				current.end_ms = last_voiced_timestamp + hop_ms
				current = None
				last_voiced_timestamp = None
				last_midi = None
			continue

		should_start = current is None
		if last_voiced_timestamp is not None and timestamp - last_voiced_timestamp > settings.AI_MAX_FRAME_GAP_MS:
			should_start = True
		if last_midi is not None and abs(midi - last_midi) > settings.AI_MAX_PITCH_JUMP_SEMITONES:
			should_start = True

		if should_start:
			current = _Segment(
				start_ms=timestamp,
				end_ms=timestamp + hop_ms,
				midis=[midi],
				confidences=[frame.confidence],
			)
			segments.append(current)
		else:
			current.midis.append(midi)
			current.confidences.append(frame.confidence)
			current.end_ms = timestamp + hop_ms

		last_voiced_timestamp = timestamp
		last_midi = midi

	return segments


def merge_adjacent_notes(notes: list[HummingNote], quantum: float) -> list[HummingNote]:
	if not notes:
		return []

	merged: list[HummingNote] = [notes[0]]
	for note in notes[1:]:
		previous = merged[-1]
		previous_end = previous.startBeat + previous.durationBeats
		if note.midi == previous.midi and note.startBeat - previous_end <= quantum:
			previous.durationBeats = round(note.startBeat + note.durationBeats - previous.startBeat, 4)
			previous.confidence = round((previous.confidence + note.confidence) / 2.0, 4)
			continue
		merged.append(note)

	return merged


def frame_midi(frame: PitchFrame) -> int | None:
	if not frame.voiced or frame.midi is None:
		return None
	if frame.confidence < settings.AI_CONFIDENCE_THRESHOLD:
		return None
	if not math.isfinite(frame.midi):
		return None
	return int(round(frame.midi))


def parse_quantize(value: str) -> float:
	clean = (value or DEFAULT_QUANTIZE).strip()
	try:
		if "/" in clean:
			numerator, denominator = clean.split("/", 1)
			numerator_value = float(numerator)
			denominator_value = float(denominator)
			if numerator_value <= 0 or denominator_value <= 0:
				raise ValueError
			return max(0.015625, 4.0 * numerator_value / denominator_value)

		number_value = float(clean)
		if number_value <= 0:
			raise ValueError
		return number_value
	except ValueError as exc:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail="quantize must be a positive beat value or a fraction like 1/16",
		) from exc


def infer_hop_ms(frames: list[PitchFrame]) -> float:
	deltas = [
		frames[index].timestamp_ms - frames[index - 1].timestamp_ms
		for index in range(1, len(frames))
		if frames[index].timestamp_ms > frames[index - 1].timestamp_ms
	]
	if not deltas:
		return 10.0
	return max(1.0, float(median(deltas)))


def ms_to_beats(ms: float, bpm: float) -> float:
	return (ms / 1000.0) * (bpm / 60.0)


def quantize_floor(value: float, quantum: float) -> float:
	return math.floor(value / quantum) * quantum


def quantize_round(value: float, quantum: float) -> float:
	return round(value / quantum) * quantum


def quantize_note_bounds(
	start_beat: float,
	end_beat: float,
	quantum: float,
	clip_length_beats: float,
) -> tuple[float, float]:
	start = max(0.0, quantize_round(start_beat, quantum))
	end = max(start + quantum, quantize_round(end_beat, quantum))
	if start >= clip_length_beats:
		return start, quantum
	end = min(max(end, start + quantum), clip_length_beats)
	return start, max(quantum, end - start)


def midi_to_note_name(midi: int) -> str:
	note = NOTE_NAMES[midi % 12]
	octave = (midi // 12) - 1
	return f"{note}{octave}"


def estimate_key(notes: list[HummingNote]) -> str:
	if not notes:
		return "Unknown"

	pitch_classes = [note.midi % 12 for note in notes]
	root = max(set(pitch_classes), key=pitch_classes.count)
	return f"{NOTE_NAMES[root]} major/minor"


def _write_upload(audio: UploadFile, destination: Path) -> None:
	with destination.open("wb") as file:
		while chunk := audio.file.read(1024 * 1024):
			file.write(chunk)

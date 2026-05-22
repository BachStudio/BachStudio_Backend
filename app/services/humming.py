from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import wave
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
SCALE_PATTERNS = {
	"major": (0, 2, 4, 5, 7, 9, 11),
	"minor": (0, 2, 3, 5, 7, 8, 10),
}
ROBUST_PITCH_WINDOW_SEMITONES = 0.85


@dataclass(slots=True)
class _Segment:
	start_ms: float
	end_ms: float
	midi_values: list[float]
	confidences: list[float]


@dataclass(slots=True)
class AudioProcessingInfo:
	original_seconds: float | None
	analyzed_seconds: float
	max_seconds: float | None
	truncated: bool


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
		audio_info = normalize_audio(input_path, wav_path)

		frames = analyze_wav(wav_path)
		effective_clip_length_beats = max(
			clip_length_beats,
			ms_to_beats(audio_info.analyzed_seconds * 1000.0, bpm),
		)
		notes = frames_to_notes(
			frames,
			bpm=bpm,
			clip_length_beats=effective_clip_length_beats,
			quantize=quantize,
		)

	return HummingTranscriptionResponse(
		key=estimate_key(notes),
		notes=notes,
		truncated=audio_info.truncated,
		maxSeconds=audio_info.max_seconds,
		analyzedSeconds=round(audio_info.analyzed_seconds, 3),
		originalSeconds=round(audio_info.original_seconds, 3) if audio_info.original_seconds is not None else None,
	)


def normalize_audio(input_path: Path, output_path: Path) -> AudioProcessingInfo:
	max_seconds = positive_seconds_or_none(settings.AI_MAX_UPLOAD_AUDIO_SECONDS)
	original_seconds = probe_audio_duration_seconds(input_path)

	if input_path.suffix.lower() == ".wav":
		if max_seconds is None or original_seconds is None or original_seconds <= max_seconds:
			shutil.copyfile(input_path, output_path)
		else:
			copy_wav_with_limit(input_path, output_path, max_seconds)
		return build_audio_processing_info(
			output_path,
			original_seconds=original_seconds,
			max_seconds=max_seconds,
		)

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
		]
		if max_seconds is not None:
			command.extend(["-t", str(max_seconds)])
		command.extend(
			[
				"-ac",
				"1",
				"-ar",
				"16000",
				"-sample_fmt",
				"s16",
				str(output_path),
			]
		)
		result = subprocess.run(command, capture_output=True, text=True, check=False)
		if result.returncode != 0:
			raise HTTPException(
				status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
				detail=f"Could not decode uploaded audio: {result.stderr.strip() or 'ffmpeg failed'}",
			)
		return build_audio_processing_info(
			output_path,
			original_seconds=original_seconds,
			max_seconds=max_seconds,
		)

	raise HTTPException(
		status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
		detail="ffmpeg is required for webm/mp3/m4a/ogg/flac uploads. Install ffmpeg or upload WAV.",
	)


def build_audio_processing_info(
	output_path: Path,
	*,
	original_seconds: float | None,
	max_seconds: float | None,
) -> AudioProcessingInfo:
	analyzed_seconds = probe_audio_duration_seconds(output_path) or 0.0
	truncated = is_audio_truncated(
		original_seconds=original_seconds,
		analyzed_seconds=analyzed_seconds,
		max_seconds=max_seconds,
	)
	return AudioProcessingInfo(
		original_seconds=original_seconds,
		analyzed_seconds=analyzed_seconds,
		max_seconds=max_seconds,
		truncated=truncated,
	)


def copy_wav_with_limit(input_path: Path, output_path: Path, max_seconds: float) -> None:
	try:
		with wave.open(str(input_path), "rb") as source:
			params = source.getparams()
			max_frames = max(1, int(max_seconds * params.framerate))
			with wave.open(str(output_path), "wb") as destination:
				destination.setparams(params)
				destination.writeframes(source.readframes(max_frames))
	except wave.Error as exc:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail=f"Could not read uploaded WAV audio: {exc}",
		) from exc


def probe_audio_duration_seconds(path: Path) -> float | None:
	if path.suffix.lower() == ".wav":
		try:
			with wave.open(str(path), "rb") as wav_file:
				frame_rate = wav_file.getframerate()
				if frame_rate <= 0:
					return None
				return wav_file.getnframes() / frame_rate
		except wave.Error:
			return None

	ffprobe_path = shutil.which("ffprobe")
	if not ffprobe_path:
		return None

	command = [
		ffprobe_path,
		"-v",
		"error",
		"-show_entries",
		"format=duration",
		"-of",
		"default=noprint_wrappers=1:nokey=1",
		str(path),
	]
	result = subprocess.run(command, capture_output=True, text=True, check=False)
	if result.returncode != 0:
		return None

	try:
		duration = float(result.stdout.strip())
	except ValueError:
		return None
	return duration if math.isfinite(duration) and duration >= 0.0 else None


def is_audio_truncated(
	*,
	original_seconds: float | None,
	analyzed_seconds: float,
	max_seconds: float | None,
) -> bool:
	if max_seconds is None:
		return False
	if original_seconds is not None:
		return original_seconds > max_seconds + 0.05
	return analyzed_seconds >= max_seconds - 0.05


def positive_seconds_or_none(value: float | None) -> float | None:
	if value is None:
		return None
	value = float(value)
	return value if math.isfinite(value) and value > 0.0 else None


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
		midi = segment_midi(segment)
		if midi is None:
			continue

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

	return postprocess_notes(notes, quantum)


def build_segments(frames: list[PitchFrame], hop_ms: float) -> list[_Segment]:
	segments: list[_Segment] = []
	current: _Segment | None = None
	last_voiced_timestamp: float | None = None

	for frame in frames:
		timestamp = max(0.0, float(frame.timestamp_ms))
		midi_value = frame_midi_value(frame)
		if midi_value is None:
			if (
				current is not None
				and last_voiced_timestamp is not None
				and timestamp - last_voiced_timestamp > settings.AI_MAX_FRAME_GAP_MS
			):
				current.end_ms = last_voiced_timestamp + hop_ms
				current = None
				last_voiced_timestamp = None
			continue

		should_start = current is None
		if last_voiced_timestamp is not None and timestamp - last_voiced_timestamp > settings.AI_MAX_FRAME_GAP_MS:
			should_start = True
		current_center = segment_pitch_center(current) if current is not None else None
		if current_center is not None and abs(midi_value - current_center) > settings.AI_MAX_PITCH_JUMP_SEMITONES:
			should_start = True

		if should_start:
			current = _Segment(
				start_ms=timestamp,
				end_ms=timestamp + hop_ms,
				midi_values=[midi_value],
				confidences=[frame.confidence],
			)
			segments.append(current)
		else:
			current.midi_values.append(midi_value)
			current.confidences.append(frame.confidence)
			current.end_ms = timestamp + hop_ms

		last_voiced_timestamp = timestamp

	return segments


def postprocess_notes(notes: list[HummingNote], quantum: float) -> list[HummingNote]:
	notes = correct_octave_outliers(notes)
	if settings.AI_SNAP_TO_SCALE:
		notes = snap_notes_to_inferred_scale(notes)
	notes = absorb_short_pitch_glitches(notes, quantum)
	return merge_adjacent_notes(notes, quantum)


def correct_octave_outliers(notes: list[HummingNote]) -> list[HummingNote]:
	if len(notes) < 2:
		return notes

	corrected: list[HummingNote] = []
	for index, note in enumerate(notes):
		neighbors: list[int] = []
		if index > 0:
			neighbors.append(corrected[-1].midi)
		if index + 1 < len(notes):
			neighbors.append(notes[index + 1].midi)

		if not neighbors:
			corrected.append(note)
			continue

		current_distance = min(abs(note.midi - neighbor) for neighbor in neighbors)
		best_midi = note.midi
		best_distance = current_distance
		for shift in (-24, -12, 0, 12, 24):
			candidate = note.midi + shift
			if candidate < 0 or candidate > 127:
				continue
			distance = min(abs(candidate - neighbor) for neighbor in neighbors)
			if distance < best_distance:
				best_midi = candidate
				best_distance = distance

		if current_distance - best_distance >= 7 and best_distance <= 5:
			corrected.append(copy_note_with_midi(note, best_midi))
		else:
			corrected.append(note)

	return corrected


def snap_notes_to_inferred_scale(notes: list[HummingNote]) -> list[HummingNote]:
	scale = infer_scale(notes)
	if scale is None:
		return notes

	root, mode = scale
	allowed = {(root + interval) % 12 for interval in SCALE_PATTERNS[mode]}
	unique_pitch_classes = {note.midi % 12 for note in notes}
	if len(unique_pitch_classes) < 3:
		return notes

	snapped: list[HummingNote] = []
	for note in notes:
		if note.midi % 12 in allowed:
			snapped.append(note)
			continue

		candidate = nearest_midi_in_scale(note.midi, allowed)
		if abs(candidate - note.midi) <= settings.AI_SCALE_SNAP_MAX_SEMITONES:
			snapped.append(copy_note_with_midi(note, candidate))
		else:
			snapped.append(note)

	return snapped


def absorb_short_pitch_glitches(notes: list[HummingNote], quantum: float) -> list[HummingNote]:
	if len(notes) < 3:
		return notes

	out: list[HummingNote] = []
	index = 0
	while index < len(notes):
		if index + 2 < len(notes):
			first = notes[index]
			middle = notes[index + 1]
			third = notes[index + 2]
			if (
				first.midi == third.midi
				and middle.durationBeats <= quantum
				and abs(middle.midi - first.midi) <= 2
			):
				out.append(
					first.model_copy(
						update={
							"durationBeats": round(third.startBeat + third.durationBeats - first.startBeat, 4),
							"confidence": round(mean([first.confidence, middle.confidence, third.confidence]), 4),
						}
					)
				)
				index += 3
				continue

		out.append(notes[index])
		index += 1

	return out


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


def segment_midi(segment: _Segment) -> int | None:
	center = segment_pitch_center(segment)
	if center is None:
		return None
	return max(0, min(127, int(round(center))))


def segment_pitch_center(segment: _Segment | None) -> float | None:
	if segment is None or not segment.midi_values:
		return None
	return robust_pitch_center(segment.midi_values, segment.confidences)


def robust_pitch_center(values: list[float], confidences: list[float]) -> float | None:
	if not values:
		return None

	center = weighted_median(values, confidences)
	filtered_values: list[float] = []
	filtered_weights: list[float] = []
	for value, confidence in zip(values, confidences, strict=False):
		if abs(value - center) <= ROBUST_PITCH_WINDOW_SEMITONES:
			filtered_values.append(value)
			filtered_weights.append(confidence)

	if not filtered_values:
		return center
	return weighted_median(filtered_values, filtered_weights)


def weighted_median(values: list[float], weights: list[float]) -> float:
	pairs = sorted(
		(float(value), max(0.0, float(weight)))
		for value, weight in zip(values, weights, strict=False)
		if math.isfinite(value)
	)
	if not pairs:
		return float(median(values))

	total = sum(weight for _, weight in pairs)
	if total <= 0.0:
		return float(median([value for value, _ in pairs]))

	cumulative = 0.0
	cutoff = total / 2.0
	for value, weight in pairs:
		cumulative += weight
		if cumulative >= cutoff:
			return value

	return pairs[-1][0]


def frame_midi(frame: PitchFrame) -> int | None:
	value = frame_midi_value(frame)
	if value is None:
		return None
	return int(round(value))


def frame_midi_value(frame: PitchFrame) -> float | None:
	if not frame.voiced or frame.midi is None:
		return None
	if frame.confidence < settings.AI_CONFIDENCE_THRESHOLD:
		return None
	if not math.isfinite(frame.midi):
		return None
	return float(frame.midi)


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
	scale = infer_scale(notes)
	if scale is None:
		return "Unknown"

	root, mode = scale
	return f"{NOTE_NAMES[root]} {mode}"


def infer_scale(notes: list[HummingNote]) -> tuple[int, str] | None:
	if not notes:
		return None

	weights_by_pitch_class: dict[int, float] = {}
	for note in notes:
		weight = max(0.05, note.durationBeats) * max(0.1, note.confidence)
		pitch_class = note.midi % 12
		weights_by_pitch_class[pitch_class] = weights_by_pitch_class.get(pitch_class, 0.0) + weight

	if not weights_by_pitch_class:
		return None

	best: tuple[float, int, str] | None = None
	for root in range(12):
		for mode, intervals in SCALE_PATTERNS.items():
			allowed = {(root + interval) % 12 for interval in intervals}
			score = 0.0
			for pitch_class, weight in weights_by_pitch_class.items():
				score += weight if pitch_class in allowed else -0.65 * weight
			candidate = (score, root, mode)
			if best is None or candidate > best:
				best = candidate

	if best is None:
		return None
	return best[1], best[2]


def nearest_midi_in_scale(midi: int, allowed_pitch_classes: set[int]) -> int:
	candidates = [
		candidate
		for candidate in range(max(0, midi - 2), min(127, midi + 2) + 1)
		if candidate % 12 in allowed_pitch_classes
	]
	if not candidates:
		return midi
	return min(candidates, key=lambda candidate: (abs(candidate - midi), candidate))


def copy_note_with_midi(note: HummingNote, midi: int) -> HummingNote:
	clean_midi = max(0, min(127, int(midi)))
	return note.model_copy(update={"midi": clean_midi, "note": midi_to_note_name(clean_midi)})


def _write_upload(audio: UploadFile, destination: Path) -> None:
	with destination.open("wb") as file:
		while chunk := audio.file.read(1024 * 1024):
			file.write(chunk)

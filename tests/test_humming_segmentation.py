import math
import unittest

from app.ai_engine.types import PitchFrame
from app.services.humming import frames_to_notes, make_segmentation_debug


SAMPLE_RATE = 16000


def make_pulsed_hum(
	pulses: list[tuple[float, float]],
	*,
	total_seconds: float,
	frequency: float = 440.0,
) -> tuple[list[PitchFrame], list[float]]:
	samples: list[float] = []
	for index in range(int(SAMPLE_RATE * total_seconds)):
		t = index / SAMPLE_RATE
		active = any(start <= t < end for start, end in pulses)
		samples.append(0.35 * math.sin(2 * math.pi * frequency * t) if active else 0.0)

	frames: list[PitchFrame] = []
	frame_count = int(total_seconds / 0.01)
	for index in range(frame_count):
		t = index * 0.01
		active = any(start <= t < end for start, end in pulses)
		frames.append(
			PitchFrame(
				timestamp_ms=t * 1000,
				f0_hz=frequency if active else None,
				midi=69.0 if active else None,
				cents=0.0 if active else None,
				voiced=active,
				confidence=0.9 if active else 0.0,
				source="test",
			)
		)
	return frames, samples


class HummingSegmentationTest(unittest.TestCase):
	def test_ta_ta_ta_same_pitch_creates_three_notes(self) -> None:
		frames, samples = make_pulsed_hum(
			[(0.00, 0.12), (0.20, 0.32), (0.40, 0.52)],
			total_seconds=0.62,
		)
		debug = make_segmentation_debug()

		notes = frames_to_notes(
			frames,
			bpm=120,
			clip_length_beats=2,
			quantize="1/16",
			samples=samples,
			sample_rate=SAMPLE_RATE,
			debug=debug,
		)

		self.assertEqual([note.midi for note in notes], [69, 69, 69])
		self.assertEqual(len(notes), 3)
		self.assertEqual(len(debug["mergedSamePitchNotes"]), 0)
		self.assertGreaterEqual(len(debug["detectedOnsets"]), 3)
		self.assertGreaterEqual(len(debug["silenceBreaks"]), 2)

	def test_sub_50ms_note_is_reported_as_removed_short_note(self) -> None:
		frames, samples = make_pulsed_hum([(0.00, 0.04)], total_seconds=0.12)
		debug = make_segmentation_debug()

		notes = frames_to_notes(
			frames,
			bpm=120,
			clip_length_beats=1,
			quantize="1/16",
			samples=samples,
			sample_rate=SAMPLE_RATE,
			debug=debug,
		)

		self.assertEqual(notes, [])
		self.assertEqual(debug["removedShortNotes"][0]["reason"], "raw_duration")


if __name__ == "__main__":
	unittest.main()

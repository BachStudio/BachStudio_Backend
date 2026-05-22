from typing import Any

from pydantic import BaseModel, Field


class HummingNote(BaseModel):
	midi: int = Field(ge=0, le=127)
	note: str
	startBeat: float = Field(ge=0)
	durationBeats: float = Field(gt=0)
	confidence: float = Field(ge=0, le=1)
	rawStartSec: float | None = None
	rawEndSec: float | None = None
	quantizedStartBeat: float | None = None
	quantizedDurationBeats: float | None = None


class HummingTranscriptionResponse(BaseModel):
	key: str = "Unknown"
	notes: list[HummingNote]
	truncated: bool = False
	maxSeconds: float | None = None
	analyzedSeconds: float = 0
	originalSeconds: float | None = None
	debug: dict[str, Any] = Field(default_factory=dict)

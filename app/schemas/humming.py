from pydantic import BaseModel, Field


class HummingNote(BaseModel):
	midi: int = Field(ge=0, le=127)
	note: str
	startBeat: float = Field(ge=0)
	durationBeats: float = Field(gt=0)
	confidence: float = Field(ge=0, le=1)


class HummingTranscriptionResponse(BaseModel):
	key: str = "Unknown"
	notes: list[HummingNote]


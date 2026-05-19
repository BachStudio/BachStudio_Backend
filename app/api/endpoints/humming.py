from fastapi import APIRouter, File, Form, UploadFile, WebSocket

from app.schemas.humming import HummingTranscriptionResponse
from app.services import humming as humming_service
from app.services import humming_stream

router = APIRouter(prefix="/humming", tags=["humming"])


@router.post("/transcribe", response_model=HummingTranscriptionResponse)
def transcribe_humming(
	audio: UploadFile = File(...),
	bpm: float = Form(...),
	clipLengthBeats: float = Form(...),
	quantize: str = Form(default="1/16"),
) -> HummingTranscriptionResponse:
	return humming_service.transcribe_upload(
		audio,
		bpm=bpm,
		clip_length_beats=clipLengthBeats,
		quantize=quantize,
	)


@router.websocket("/stream")
async def stream_humming(websocket: WebSocket) -> None:
	await humming_stream.stream_humming(websocket)

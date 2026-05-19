# BachStudio Backend

BachStudio 백엔드는 프론트엔드 웹 DAW와 음정 분석 엔진을 연결하는 FastAPI 서버입니다.

현재 가장 중요한 역할은 브라우저 마이크에서 들어오는 허밍/보컬 오디오를 실시간으로 분석해서, 프론트엔드 피아노롤에 바로 넣을 수 있는 pitch/note 이벤트를 돌려주는 것입니다. 이 기능에 필요한 기본 DSP 음정 분석 엔진은 백엔드 폴더 안에 내장되어 있어서 `BachStudio_Ai` 폴더가 없어도 동작합니다. 그 외에 녹음 후 파일 변환 API, 로그인, 유저, 아이템 API는 보조 기능 또는 Supabase 연동을 위한 기본 구조로 들어가 있습니다.

## 이 백엔드가 하는 일

- 프론트엔드가 WebSocket으로 보내는 실시간 PCM 오디오 chunk를 받습니다.
- 오디오 chunk를 16 kHz mono 분석 샘플로 맞춘 뒤 pitch frame을 즉시 분석합니다.
- 분석 결과를 `pitch`, `note_on`, `note_update`, `note_off`, `complete` 이벤트로 반환합니다.
- 녹음 후 파일 업로드 방식도 보조 API로 지원합니다.
- `webm`, `wav`, `mp3` 같은 녹음 파일을 16 kHz mono WAV로 변환할 수 있습니다.
- 프론트엔드가 기대하는 형태인 `midi`, `note`, `startBeat`, `durationBeats`, `confidence` JSON을 반환합니다.
- 프론트엔드 개발 서버에서 호출할 수 있도록 CORS를 허용합니다.
- Supabase 기반 유저/아이템 API를 붙일 수 있는 기본 구조를 제공합니다.

## 전체 구조

```text
BachStudio_Backend/
├── app/
│   ├── main.py                    # FastAPI 앱 생성, CORS, 라우터 등록
│   ├── ai_engine/                 # 내장 음정 분석 엔진
│   │   ├── engine.py              # WAV 분석 실행
│   │   ├── audio_io.py            # WAV 로딩, resample
│   │   ├── postprocess.py         # pitch smoothing, MIDI 변환
│   │   └── estimators/
│   │       ├── dsp_estimator.py   # 기본 DSP 음정 추정기
│   │       └── rmvpe_estimator.py # 선택적 RMVPE 추정기
│   ├── core/
│   │   ├── config.py              # 환경변수와 서버 설정
│   │   ├── security.py            # JWT 생성/검증
│   │   └── supabase.py            # Supabase 클라이언트 생성
│   ├── api/
│   │   ├── deps.py                # 공통 의존성: 현재 유저, Supabase
│   │   ├── router.py              # /api/v1 라우터 모음
│   │   └── endpoints/
│   │       ├── auth.py            # 회원가입, 로그인, 토큰 검증
│   │       ├── humming.py         # Humming AI 변환 API
│   │       ├── user.py            # 유저 조회 API
│   │       └── item.py            # 아이템 샘플 API
│   ├── schemas/
│   │   ├── humming.py             # Humming AI 응답 스키마
│   │   ├── user.py                # 유저 요청/응답 스키마
│   │   └── item.py                # 아이템 요청/응답 스키마
│   ├── services/
│   │   ├── humming.py             # 오디오 변환, AI 분석, 노트 변환 로직
│   │   ├── user.py                # Supabase 유저 접근 로직
│   │   └── item.py                # Supabase 아이템 접근 로직
│   └── utils/
├── requirements.txt
└── requirements-rmvpe.txt          # 선택: RMVPE 사용 시 설치
```

## 실행 방법

백엔드 폴더로 이동합니다.

```bash
cd BachStudio_Backend
```

가상환경을 만들고 활성화합니다.

```bash
python -m venv .venv
source .venv/bin/activate
```

백엔드 의존성을 설치합니다.

```bash
python -m pip install -r requirements.txt
```

기본 DSP 분석만 쓸 거라면 여기까지 설치하면 됩니다. RMVPE까지 쓰고 싶으면 추가 의존성을 설치합니다.

```bash
python -m pip install -r requirements-rmvpe.txt
```

서버를 실행합니다.

```bash
python -m uvicorn app.main:app --reload
```

기본 주소는 아래와 같습니다.

```text
http://127.0.0.1:8000
```

서버가 켜졌는지 확인하려면 아래 주소를 열면 됩니다.

```text
GET http://127.0.0.1:8000/api/v1/health
```

## Humming AI 실시간 기능

프론트엔드의 피아노롤 `Humming AI` 패널에서 마이크 입력을 받으면, 프론트는 짧은 PCM 오디오 chunk를 WebSocket으로 계속 보냅니다. 백엔드는 chunk가 들어올 때마다 RMVPE로 pitch를 분석하고, 프론트가 바로 그릴 수 있는 이벤트를 다시 보냅니다. 동시에 서버는 들어온 오디오를 짧게 누적했다가 stop 시점에 RMVPE로 전체 재분석을 한 번 더 수행합니다.

실시간 흐름은 아래와 같습니다.

1. 프론트엔드가 `ws://127.0.0.1:8000/api/humming/stream`에 연결합니다.
2. 연결 직후 백엔드는 `ready` 이벤트를 보냅니다.
3. 프론트엔드는 `AudioContext` 또는 `AudioWorklet`에서 얻은 mono `Float32Array` PCM chunk를 binary message로 보냅니다.
4. 백엔드는 chunk를 16 kHz mono 분석 샘플로 맞추고 내부 `app/ai_engine`의 `RealtimePitchEngine`으로 pitch frame을 분석합니다.
5. 백엔드는 RMVPE 기반 `pitch` 이벤트를 계속 반환합니다.
6. voiced frame이 이어지면 `note_on`, `note_update`, `note_off` 이벤트로 note segment를 실시간 추적합니다.
7. 프론트가 `{"type":"stop"}`을 보내면 백엔드는 누적 오디오 전체를 RMVPE로 다시 분석합니다.
8. `complete.notes`에는 최종 RMVPE 재분석 결과를, `complete.liveNotes`에는 실시간 추적 중 만들어진 미리보기 note를 반환합니다.

### WebSocket 요청

```text
WS /api/humming/stream
WS /api/v1/humming/stream
```

쿼리 파라미터로 기본 설정을 줄 수 있습니다.

```text
ws://127.0.0.1:8000/api/humming/stream?sampleRate=48000&bpm=120&clipLengthBeats=8&quantize=1/16
```

또는 연결 후 첫 text message로 설정을 보낼 수 있습니다.

```json
{
  "type": "start",
  "sampleRate": 48000,
  "bpm": 120,
  "clipLengthBeats": 8,
  "quantize": "1/16",
  "preferRmvpe": true
}
```

필드 의미는 아래와 같습니다.

| 필드 | 설명 | 기본값 |
| --- | --- | --- |
| `sampleRate` | 브라우저 `AudioContext.sampleRate` 값입니다. 보통 `48000` 또는 `44100`입니다. | `48000` |
| `bpm` | 현재 프로젝트 BPM입니다. | `120` |
| `clipLengthBeats` | 현재 피아노롤 클립 길이입니다. | `8` |
| `quantize` | 노트 시작/길이 보정 단위입니다. | `1/16` |
| `preferRmvpe` | 실시간 스트림에서 RMVPE를 먼저 쓸지 여부입니다. 생략하면 `.env`의 `AI_PREFER_RMVPE` 값을 따릅니다. 낮은 지연이 더 중요하면 `false`로 보낼 수 있습니다. | `.env`의 `AI_PREFER_RMVPE` |

### 오디오 binary 형식

WebSocket binary message는 아래 형식이어야 합니다.

```text
Float32 little-endian PCM
mono
range: -1.0 ~ 1.0
```

즉 프론트에서 `Float32Array`를 만들고 그 `ArrayBuffer`를 그대로 보내면 됩니다.

```ts
socket.send(float32Chunk.buffer);
```

`MediaRecorder`가 만드는 `webm` chunk를 실시간 WebSocket에 바로 보내면 안 됩니다. `webm`은 압축 컨테이너라서 chunk마다 바로 pitch frame으로 해석하기 어렵습니다. 실시간 기능은 `AudioWorklet`이나 `ScriptProcessorNode`에서 나온 raw PCM을 보내는 방식입니다.

### 서버 이벤트

연결 직후 백엔드는 `ready` 이벤트를 보냅니다.

```json
{
  "type": "ready",
  "inputFormat": "float32le",
  "channels": 1,
  "sourceSampleRate": 48000,
  "analysisSampleRate": 16000,
  "frameLength": 5120,
  "hopLength": 800,
  "bpm": 120,
  "clipLengthBeats": 8,
  "quantize": "1/16",
  "source": "rmvpe"
}
```

실시간 pitch frame은 아래처럼 옵니다.

```json
{
  "type": "pitch",
  "timestampMs": 120,
  "beat": 0.24,
  "f0Hz": 440.1,
  "midi": 69,
  "note": "A4",
  "cents": 0.4,
  "voiced": true,
  "confidence": 0.91,
  "source": "rmvpe"
}
```

노트가 시작되면 `note_on`이 옵니다.

```json
{
  "type": "note_on",
  "note": {
    "midi": 69,
    "note": "A4",
    "startBeat": 0,
    "durationBeats": 0.25,
    "confidence": 0.91
  }
}
```

노트가 이어지는 동안 `note_update`가 오고, 음이 끊기거나 pitch가 크게 바뀌면 `note_off`가 옵니다.

```json
{
  "type": "note_off",
  "reason": "unvoiced",
  "note": {
    "midi": 69,
    "note": "A4",
    "startBeat": 0,
    "durationBeats": 1,
    "confidence": 0.9
  }
}
```

프론트가 stop을 보내면:

```json
{
  "type": "stop"
}
```

백엔드는 최종 결과를 반환합니다. 이때 `notes`는 stop 후 RMVPE로 전체 오디오를 다시 분석한 최종 결과이고, `liveNotes`는 실시간 이벤트를 만들면서 누적한 미리보기 결과입니다. 프론트에서 피아노롤에 최종 반영할 때는 `notes`를 쓰는 것을 권장합니다.

```json
{
  "type": "complete",
  "mode": "hybrid_rmvpe",
  "key": "A major/minor",
  "source": "rmvpe",
  "liveSource": "rmvpe",
  "notes": [
    {
      "midi": 69,
      "note": "A4",
      "startBeat": 0,
      "durationBeats": 1,
      "confidence": 0.9
    }
  ],
  "liveNotes": [
    {
      "midi": 69,
      "note": "A4",
      "startBeat": 0,
      "durationBeats": 0.75,
      "confidence": 0.88
    }
  ]
}
```

### DSP와 RMVPE

백엔드에는 두 가지 음정 추정 경로가 있습니다.

| 방식 | 설명 | 필요한 설치 |
| --- | --- | --- |
| DSP | 백엔드에 기본 내장된 autocorrelation 기반 pitch 추정기입니다. 설치가 가볍고 바로 동작합니다. | `requirements.txt` |
| RMVPE | 보컬/허밍 pitch 추정 품질을 높이기 위한 모델 기반 추정기입니다. 실시간 스트림에서는 지연이 더 커질 수 있습니다. | `requirements.txt` + `requirements-rmvpe.txt` |

녹음 후 변환 API와 실시간 WebSocket은 기본적으로 `.env`의 `AI_PREFER_RMVPE=true`를 따릅니다. 따라서 현재 기본 동작은 RMVPE 우선입니다. 실시간 WebSocket은 live pitch도 RMVPE로 분석하고, stop 후 최종 `complete.notes`도 누적 오디오를 RMVPE로 다시 분석해서 만듭니다. 낮은 지연이 더 중요하면 WebSocket 연결 설정에서 `preferRmvpe=false`를 보내 live 분석만 DSP로 강제할 수 있지만, 현재 권장값은 `true`입니다. RMVPE 패키지나 모델 로딩에 실패하면 자동으로 DSP로 fallback합니다.

```env
AI_PREFER_RMVPE=true
AI_RMVPE_MODEL_PATH=
```

`AI_RMVPE_MODEL_PATH`는 `BachStudio_Ai` 폴더 경로가 아니라 RMVPE 모델 파일 경로입니다. `rmvpe-onnx`가 기본 모델을 알아서 찾을 수 있는 환경이면 비워둬도 됩니다. 직접 받은 모델 파일을 쓰는 경우에만 아래처럼 적습니다.

```env
AI_RMVPE_MODEL_PATH=/absolute/path/to/rmvpe.onnx
```

## 녹음 후 변환 API

실시간이 아니라 “녹음 완료 후 한 번에 변환”하고 싶을 때는 기존 HTTP API를 사용할 수 있습니다.

### 요청

```http
POST /api/humming/transcribe
Content-Type: multipart/form-data
```

같은 API를 버전 prefix로도 호출할 수 있습니다.

```http
POST /api/v1/humming/transcribe
Content-Type: multipart/form-data
```

폼 필드는 아래와 같습니다.

| 필드 | 설명 | 예시 |
| --- | --- | --- |
| `audio` | 녹음 파일입니다. `wav`, `webm`, `mp3`, `m4a`, `ogg`, `flac`를 지원합니다. | `recording.webm` |
| `bpm` | 현재 프로젝트 BPM입니다. | `120` |
| `clipLengthBeats` | 현재 피아노롤 클립 길이입니다. | `8` |
| `quantize` | 노트 시작/길이 보정 단위입니다. 생략하면 `1/16`입니다. | `1/16` |

### 응답

```json
{
  "key": "A major/minor",
  "notes": [
    {
      "midi": 69,
      "note": "A4",
      "startBeat": 0,
      "durationBeats": 1,
      "confidence": 0.9
    }
  ]
}
```

응답 필드 의미는 아래와 같습니다.

| 필드 | 설명 |
| --- | --- |
| `key` | 현재는 간단한 추정값입니다. 정확한 조성 분석보다는 표시용에 가깝습니다. |
| `notes[].midi` | 실제 피아노롤 변환에 써야 하는 MIDI 번호입니다. |
| `notes[].note` | 화면에 보여주기 좋은 음 이름입니다. 예: `A4`, `C#5` |
| `notes[].startBeat` | 클립 시작점을 0으로 봤을 때 음이 시작하는 beat 위치입니다. |
| `notes[].durationBeats` | 음 길이입니다. beat 단위입니다. |
| `notes[].confidence` | AI가 해당 pitch를 얼마나 확신했는지 나타내는 0~1 값입니다. |

### 프론트엔드에서 사용하는 방식

프론트엔드는 응답의 `midi`, `startBeat`, `durationBeats`를 피아노롤 모델로 변환하면 됩니다.

프론트엔드 README 기준 변환 규칙은 아래와 같습니다.

```text
pitch = MIDI_HIGH - midi
start = startBeat * PIANO_STEPS_PER_BEAT
length = durationBeats * PIANO_STEPS_PER_BEAT
```

예를 들어 `midi=69`, `startBeat=0`, `durationBeats=1`, `PIANO_STEPS_PER_BEAT=4`라면 피아노롤에는 `start=0`, `length=4`인 노트로 들어갑니다.

## 현재 제공하는 API 목록

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/` | 서버가 실행 중인지 간단히 확인합니다. |
| `GET` | `/api/v1/health` | health check API입니다. |
| `WS` | `/api/humming/stream` | 프론트 권장 Humming AI 실시간 스트리밍 API입니다. |
| `WS` | `/api/v1/humming/stream` | 버전 prefix가 붙은 Humming AI 실시간 스트리밍 API입니다. |
| `POST` | `/api/humming/transcribe` | 녹음 후 파일 업로드 변환 API입니다. |
| `POST` | `/api/v1/humming/transcribe` | 버전 prefix가 붙은 녹음 후 파일 업로드 변환 API입니다. |
| `POST` | `/api/v1/auth/signup` | 유저 생성 API입니다. Supabase `users` 테이블에 저장을 시도합니다. |
| `POST` | `/api/v1/auth/login` | 이메일 기반 JWT 토큰을 발급합니다. 현재는 실제 비밀번호 검증이 아니라 개발용 기본 구현입니다. |
| `GET` | `/api/v1/auth/validate` | `Authorization: Bearer <token>` 토큰을 검증합니다. |
| `GET` | `/api/v1/users/me` | 현재 토큰의 payload를 반환합니다. |
| `GET` | `/api/v1/users/{user_id}` | Supabase에서 유저를 조회합니다. 실패하면 개발용 fallback 응답을 반환합니다. |
| `GET` | `/api/v1/items/` | Supabase `items` 목록을 조회합니다. 실패하면 빈 목록을 반환합니다. |
| `POST` | `/api/v1/items/` | 인증된 유저의 item 생성을 시도합니다. 실패하면 개발용 fallback 응답을 반환합니다. |

## 환경 변수

`.env` 파일에서 서버 동작을 바꿀 수 있습니다.

```env
PROJECT_NAME=BachStudio Backend
API_PREFIX=/api/v1
DEBUG=true

SUPABASE_URL=https://example.supabase.co
SUPABASE_ANON_KEY=example-anon-key
SUPABASE_JWT_SECRET=change-me

JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000","http://127.0.0.1:3000"]

AI_PREFER_RMVPE=true
AI_RMVPE_MODEL_PATH=
AI_CONFIDENCE_THRESHOLD=0.12
AI_MIN_NOTE_DURATION_BEATS=0.0625
AI_MAX_FRAME_GAP_MS=140
AI_MAX_PITCH_JUMP_SEMITONES=1
AI_MAX_AUDIO_SECONDS=12
```

주요 설정 설명은 아래와 같습니다.

| 변수 | 설명 |
| --- | --- |
| `CORS_ORIGINS` | 프론트엔드 개발 서버 주소입니다. `.env`에서는 JSON 배열 형태로 넣습니다. |
| `AI_PREFER_RMVPE` | `true`면 RMVPE를 먼저 시도하고, 실패하면 내장 DSP 추정기로 fallback합니다. |
| `AI_RMVPE_MODEL_PATH` | 선택적 RMVPE 모델 파일 경로입니다. 없으면 비워둡니다. `BachStudio_Ai` 폴더 경로를 넣는 값이 아닙니다. |
| `AI_CONFIDENCE_THRESHOLD` | 이 값보다 confidence가 낮은 pitch frame은 버립니다. |
| `AI_MIN_NOTE_DURATION_BEATS` | 너무 짧은 노트를 제거하기 위한 최소 beat 길이입니다. |
| `AI_MAX_FRAME_GAP_MS` | 이 시간보다 frame 간격이 벌어지면 다른 노트로 분리합니다. |
| `AI_MAX_PITCH_JUMP_SEMITONES` | pitch가 이 semitone 이상 튀면 다른 노트로 분리합니다. |
| `AI_MAX_AUDIO_SECONDS` | 한 번에 분석할 최대 오디오 길이입니다. 기본값은 12초입니다. |

## 필요한 외부 프로그램

브라우저 녹음은 보통 `webm`으로 들어옵니다. 이런 파일을 AI 엔진이 읽을 수 있는 WAV로 바꾸려면 서버 머신에 `ffmpeg`가 필요합니다.

설치되어 있는지 확인:

```bash
ffmpeg -version
```

`ffmpeg`가 없으면 WAV 업로드만 안전하게 동작하고, `webm`, `mp3` 같은 파일은 변환할 수 없습니다.

## 개발 상태와 주의할 점

- Humming AI 실시간 WebSocket API가 실제 프론트 연결을 위한 핵심 기능입니다.
- `POST /api/humming/transcribe`는 녹음 후 변환용 보조 API로 남겨두었습니다.
- 기본 음정 분석은 백엔드 내부 `app/ai_engine`으로 동작하므로 `BachStudio_Ai` 폴더가 없어도 서버를 실행할 수 있습니다.
- `BachStudio_Ai` 폴더는 별도 AI 개발/실험용으로 남겨둘 수 있고, 현재 백엔드 런타임 필수 의존성은 아닙니다.
- Auth/User/Item API는 기본 구조와 개발용 fallback이 들어간 상태입니다.
- `/api/v1/auth/login`은 현재 실제 Supabase Auth 비밀번호 검증이 아니라 JWT 발급 샘플에 가깝습니다.
- 프로젝트 저장은 아직 백엔드가 아니라 프론트엔드 `localStorage` 중심입니다.
- 실제 서비스 수준으로 가려면 Supabase Auth 연동, 프로젝트 저장 API, 파일 저장소, 테스트가 추가로 필요합니다.

## 빠른 테스트 예시

서버 실행 후 `curl`로 Humming AI API를 호출할 수 있습니다.

```bash
curl -X POST http://127.0.0.1:8000/api/humming/transcribe \
  -F "audio=@sample.wav" \
  -F "bpm=120" \
  -F "clipLengthBeats=8" \
  -F "quantize=1/16"
```

정상 응답이면 `notes` 배열이 반환되고, 프론트엔드는 이 배열을 현재 열린 피아노롤 클립에 넣으면 됩니다.

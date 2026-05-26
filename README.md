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
- 작곡 프로젝트를 백엔드 로컬 JSON 파일로 저장/불러오기/목록 조회/삭제할 수 있습니다.
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
│   │       ├── project.py         # 작곡 프로젝트 저장 API
│   │       ├── user.py            # 유저 조회 API
│   │       └── item.py            # 아이템 샘플 API
│   ├── schemas/
│   │   ├── humming.py             # Humming AI 응답 스키마
│   │   ├── project.py             # 프로젝트 저장 요청/응답 스키마
│   │   ├── user.py                # 유저 요청/응답 스키마
│   │   └── item.py                # 아이템 요청/응답 스키마
│   ├── services/
│   │   ├── humming.py             # 오디오 변환, AI 분석, 노트 변환 로직
│   │   ├── project.py             # 프로젝트 JSON 파일 저장 로직
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
| `clipLengthBeats` | 현재 피아노롤 클립 길이입니다. 업로드 오디오가 이보다 길면 백엔드는 실제 분석된 오디오 길이에 맞춰 내부 범위를 자동 확장합니다. | `8` |
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

백엔드는 최종 결과를 반환합니다. 이때 `notes`는 stop 후 RMVPE로 누적 오디오를 다시 분석한 최종 결과이고, `liveNotes`는 실시간 이벤트를 만들면서 누적한 미리보기 결과입니다. 프론트에서 피아노롤에 최종 반영할 때는 `notes`를 쓰는 것을 권장합니다. `truncated=true`면 실시간 최종 재분석용 오디오가 `maxSeconds`까지만 저장된 상태입니다.

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
      "confidence": 0.9,
      "rawStartSec": 0,
      "rawEndSec": 0.48,
      "quantizedStartBeat": 0,
      "quantizedDurationBeats": 1
    }
  ],
  "truncated": false,
  "maxSeconds": 300,
  "analyzedSeconds": 4,
  "receivedSeconds": 4,
  "debug": {
    "live": {
      "removedShortNotes": [],
      "mergedSamePitchNotes": [],
      "detectedOnsets": [],
      "silenceBreaks": []
    },
    "final": {
      "removedShortNotes": [],
      "mergedSamePitchNotes": [],
      "detectedOnsets": [],
      "silenceBreaks": []
    }
  },
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
AI_CONFIDENCE_THRESHOLD=0.30
AI_MAX_PITCH_JUMP_SEMITONES=0.75
AI_SNAP_TO_SCALE=true
AI_SCALE_SNAP_MAX_SEMITONES=1.0
```

`AI_RMVPE_MODEL_PATH`는 `BachStudio_Ai` 폴더 경로가 아니라 RMVPE 모델 파일 경로입니다. `rmvpe-onnx`가 기본 모델을 알아서 찾을 수 있는 환경이면 비워둬도 됩니다. 직접 받은 모델 파일을 쓰는 경우에만 아래처럼 적습니다.

```env
AI_RMVPE_MODEL_PATH=/absolute/path/to/rmvpe.onnx
```

### 음정 안정화 방식

허밍은 실제로 한 음을 불러도 pitch가 계속 흔들립니다. 그래서 백엔드는 RMVPE가 준 pitch를 바로 MIDI로 확정하지 않고 아래 보정을 거칩니다.

- confidence가 낮은 pitch frame은 버립니다. 기본값은 `AI_CONFIDENCE_THRESHOLD=0.30`입니다.
- 반음 정도의 실제 이동은 새 노트로 분리합니다. 기본값 `AI_MAX_PITCH_JUMP_SEMITONES=0.75`라서 E→F, B→C 같은 반음 이동도 놓치지 않습니다.
- 한 노트 안에서 튀는 pitch는 confidence 가중 median으로 중심음을 잡습니다.
- 짧게 생긴 지나가는 오탐 노트는 앞뒤 음이 같으면 흡수합니다.
- 갑자기 한 옥타브 위/아래로 튄 노트는 앞뒤 문맥을 보고 보정합니다.
- `AI_SNAP_TO_SCALE=true`이면 최종 노트를 추정한 major/minor scale에 맞춰 한 칸까지 보정합니다. 크로매틱 멜로디를 그대로 살리고 싶으면 `false`로 바꾸면 됩니다.

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
      "confidence": 0.9,
      "rawStartSec": 0,
      "rawEndSec": 0.48,
      "quantizedStartBeat": 0,
      "quantizedDurationBeats": 1
    }
  ],
  "truncated": false,
  "maxSeconds": 300,
  "analyzedSeconds": 180,
  "originalSeconds": 180,
  "debug": {
    "removedShortNotes": [],
    "mergedSamePitchNotes": [],
    "detectedOnsets": [],
    "silenceBreaks": []
  }
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
| `notes[].rawStartSec` | quantize 전 실제 note 시작 시간입니다. 디버그와 리듬 확인에 사용합니다. |
| `notes[].rawEndSec` | quantize 전 실제 note 종료 시간입니다. |
| `notes[].quantizedStartBeat` | 최종 quantize가 적용된 시작 beat입니다. 현재 `startBeat`와 같은 값입니다. |
| `notes[].quantizedDurationBeats` | 최종 quantize가 적용된 길이입니다. 현재 `durationBeats`와 같은 값입니다. |
| `truncated` | `true`면 백엔드가 설정된 최대 길이까지만 분석한 것입니다. |
| `maxSeconds` | 현재 요청에서 허용된 최대 분석 길이입니다. `null`이면 제한이 없습니다. |
| `analyzedSeconds` | 실제로 AI 분석에 사용된 오디오 길이입니다. |
| `originalSeconds` | 업로드 원본 파일 길이입니다. 읽을 수 없는 포맷이면 `null`일 수 있습니다. |
| `debug.removedShortNotes` | 너무 짧아서 제거된 note 후보입니다. |
| `debug.mergedSamePitchNotes` | 같은 pitch라서 합쳐진 note 후보입니다. |
| `debug.detectedOnsets` | RMS 기준으로 감지한 발음 시작 후보입니다. |
| `debug.silenceBreaks` | note를 분리시킨 silence gap입니다. |

### 프론트엔드에서 사용하는 방식

프론트엔드는 응답의 `midi`, `startBeat`, `durationBeats`를 피아노롤 모델로 변환하면 됩니다.

프론트엔드 README 기준 변환 규칙은 아래와 같습니다.

```text
pitch = MIDI_HIGH - midi
start = startBeat * PIANO_STEPS_PER_BEAT
length = durationBeats * PIANO_STEPS_PER_BEAT
```

예를 들어 `midi=69`, `startBeat=0`, `durationBeats=1`, `PIANO_STEPS_PER_BEAT=4`라면 피아노롤에는 `start=0`, `length=4`인 노트로 들어갑니다.

## 프로젝트 저장 API

프론트엔드의 작곡 프로젝트 저장 기능이 사용하는 API입니다. 현재 구현은 Supabase 테이블 없이도 바로 쓸 수 있도록 백엔드 로컬 JSON 파일에 저장합니다. 기본 저장 위치는 `BachStudio_Backend/data/projects/`이고, 이 폴더는 `.gitignore`에 들어가서 개인 작업물이 git에 올라가지 않습니다.

프론트엔드의 `ProjectData` 형태를 그대로 받습니다.

```json
{
  "projectName": "My Song",
  "bpm": 128,
  "tracks": [],
  "timestamp": 1716350000000
}
```

### 저장 또는 덮어쓰기

```http
POST /api/v1/projects/
Content-Type: application/json
```

같은 `projectName`으로 다시 저장하면 기존 파일을 덮어씁니다. 응답은 저장된 프로젝트 JSON입니다.

### 목록 조회

```http
GET /api/v1/projects/
```

저장된 프로젝트 배열을 반환합니다. 최신 `timestamp` 순서로 정렬됩니다.

### 단건 불러오기

```http
GET /api/v1/projects/{projectName}
```

프로젝트 이름에 공백이나 한글이 들어가면 프론트에서 `encodeURIComponent(projectName)`으로 인코딩해서 보내면 됩니다. 없으면 `404 Project not found`를 반환합니다.

### 삭제

```http
DELETE /api/v1/projects/{projectName}
```

삭제 성공 시 body 없이 `204 No Content`를 반환합니다. 프론트 README에 적힌 주의사항처럼 `204`에는 응답 body를 넣지 않습니다.

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
| `GET` | `/api/v1/auth/google/login` | Google OAuth 로그인 URL과 `state`를 발급합니다. |
| `GET` | `/api/v1/auth/google/url` | `/google/login`과 같은 Google OAuth URL 발급 API입니다. |
| `POST` | `/api/v1/auth/google/callback` | 프론트 콜백에서 받은 Google `code`를 백엔드 JWT로 교환합니다. |
| `GET` | `/api/v1/auth/validate` | `Authorization: Bearer <token>` 토큰을 검증합니다. |
| `POST` | `/api/v1/projects/` | 작곡 프로젝트를 저장하거나 같은 이름의 프로젝트를 덮어씁니다. |
| `GET` | `/api/v1/projects/` | 저장된 프로젝트 목록을 조회합니다. |
| `GET` | `/api/v1/projects/{projectName}` | 프로젝트 이름으로 단건을 불러옵니다. |
| `DELETE` | `/api/v1/projects/{projectName}` | 프로젝트를 삭제하고 `204 No Content`를 반환합니다. |
| `GET` | `/api/v1/users/me` | 현재 토큰의 payload를 반환합니다. |
| `GET` | `/api/v1/users/{user_id}` | Supabase에서 유저를 조회합니다. 실패하면 개발용 fallback 응답을 반환합니다. |
| `GET` | `/api/v1/items/` | Supabase `items` 목록을 조회합니다. 실패하면 빈 목록을 반환합니다. |
| `POST` | `/api/v1/items/` | 인증된 유저의 item 생성을 시도합니다. 실패하면 개발용 fallback 응답을 반환합니다. |

## Google 로그인

현재 Google OAuth는 프론트엔드가 콜백을 받고, 백엔드가 Google `code`를 검증해서 BachStudio JWT를 발급하는 구조입니다.

1. 프론트가 로그인 버튼을 누르면 아래 API를 호출합니다.

```http
GET /api/v1/auth/google/login
```

응답:

```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random-state"
}
```

2. 프론트는 `state`를 `sessionStorage` 등에 저장한 뒤 `authorization_url`로 이동합니다.
3. Google 로그인 후 `GOOGLE_OAUTH_REDIRECT_URL`로 설정한 프론트 주소에 `code`와 `state`가 붙어서 돌아옵니다.
4. 프론트는 받은 `state`가 저장해 둔 값과 같은지 확인하고, `code`를 백엔드에 보냅니다.

```http
POST /api/v1/auth/google/callback
Content-Type: application/json
```

```json
{
  "code": "google-auth-code",
  "state": "random-state",
  "redirectUri": "http://localhost:5173/auth/callback"
}
```

응답:

```json
{
  "access_token": "bachstudio-jwt",
  "token_type": "bearer",
  "user": {
    "id": "user-id",
    "email": "user@example.com",
    "name": "User Name",
    "picture": "https://...",
    "provider": "google"
  }
}
```

이후 프론트는 기존 API처럼 `Authorization: Bearer <access_token>` 헤더를 붙이면 됩니다. Supabase `users` 테이블에 `provider`, `provider_id`, `avatar_url` 컬럼이 있으면 같이 저장하고, 없으면 `email`, `name`만 저장을 시도합니다.

## 환경 변수

`.env` 파일에서 서버 동작을 바꿀 수 있습니다.

```env
PROJECT_NAME=BachStudio Backend
API_PREFIX=/api/v1
DEBUG=true

SUPABASE_URL=https://example.supabase.co
SUPABASE_PUBLISHABLE_KEY=example-publishable-key
SUPABASE_SECRET_KEY=change-me

GOOGLE_CLIENT_ID=example-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=example-google-client-secret
GOOGLE_OAUTH_REDIRECT_URL=http://localhost:5173/auth/callback

PROJECT_STORAGE_DIR=data/projects

JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000","http://127.0.0.1:3000"]

AI_PREFER_RMVPE=true
AI_RMVPE_MODEL_PATH=
AI_CONFIDENCE_THRESHOLD=0.30
AI_MIN_NOTE_DURATION_BEATS=0.0625
AI_MIN_NOTE_DURATION_MS=50
AI_MAX_FRAME_GAP_MS=70
AI_SILENCE_BREAK_MS=50
AI_SEGMENT_MIN_RMS=0.008
AI_ONSET_RMS_INCREASE_RATIO=1.8
AI_ONSET_MIN_RMS_DELTA=0.025
AI_SAME_PITCH_MERGE_GAP_MS=35
AI_MAX_PITCH_JUMP_SEMITONES=0.75
AI_SNAP_TO_SCALE=true
AI_SCALE_SNAP_MAX_SEMITONES=1.0
AI_MAX_UPLOAD_AUDIO_SECONDS=300
AI_MAX_REALTIME_AUDIO_SECONDS=300
```

주요 설정 설명은 아래와 같습니다.

| 변수 | 설명 |
| --- | --- |
| `CORS_ORIGINS` | 프론트엔드 개발 서버 주소입니다. `.env`에서는 JSON 배열 형태로 넣습니다. |
| `SUPABASE_URL` | Supabase 프로젝트 URL입니다. |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase publishable/anon key입니다. 기존 이름인 `SUPABASE_ANON_KEY`도 지원합니다. |
| `SUPABASE_SECRET_KEY` | 백엔드 JWT 서명에 쓰는 비밀값 fallback입니다. 가능하면 실제 배포에서는 별도 `SUPABASE_JWT_SECRET` 또는 `JWT_SECRET`을 쓰는 것을 권장합니다. |
| `GOOGLE_CLIENT_ID` | Google Cloud OAuth Client ID입니다. |
| `GOOGLE_CLIENT_SECRET` | Google Cloud OAuth Client Secret입니다. 백엔드에서만 사용합니다. |
| `GOOGLE_OAUTH_REDIRECT_URL` | Google 로그인 후 돌아올 프론트엔드 콜백 URL입니다. Google Cloud Console의 Authorized redirect URI와 같아야 합니다. |
| `PROJECT_STORAGE_DIR` | 프로젝트 JSON 파일을 저장할 폴더입니다. 상대 경로면 `BachStudio_Backend/` 기준으로 해석합니다. 기본값은 `data/projects`입니다. |
| `AI_PREFER_RMVPE` | `true`면 RMVPE를 먼저 시도하고, 실패하면 내장 DSP 추정기로 fallback합니다. |
| `AI_RMVPE_MODEL_PATH` | 선택적 RMVPE 모델 파일 경로입니다. 없으면 비워둡니다. `BachStudio_Ai` 폴더 경로를 넣는 값이 아닙니다. |
| `AI_CONFIDENCE_THRESHOLD` | 이 값보다 confidence가 낮은 pitch frame은 버립니다. |
| `AI_MIN_NOTE_DURATION_BEATS` | quantize 후 너무 짧은 노트를 제거하기 위한 최소 beat 길이입니다. |
| `AI_MIN_NOTE_DURATION_MS` | quantize 전 raw note가 이 시간보다 짧으면 제거합니다. 기본값은 50ms입니다. |
| `AI_MAX_FRAME_GAP_MS` | pitch frame 간격이 이 시간보다 벌어지면 다른 노트로 분리합니다. |
| `AI_SILENCE_BREAK_MS` | 같은 pitch라도 RMS silence가 이 시간 이상 이어지면 새 note로 분리합니다. 기본값은 50ms입니다. |
| `AI_SEGMENT_MIN_RMS` | note segmentation에서 silence로 볼 최소 RMS 기준입니다. |
| `AI_ONSET_RMS_INCREASE_RATIO` | RMS가 이전 frame보다 이 비율 이상 커지면 onset 후보로 봅니다. |
| `AI_ONSET_MIN_RMS_DELTA` | onset으로 인정하기 위한 최소 RMS 증가량입니다. |
| `AI_SAME_PITCH_MERGE_GAP_MS` | 같은 pitch note를 다시 합칠 수 있는 최대 raw gap입니다. silence 분리를 살리기 위해 기본값은 35ms입니다. |
| `AI_MAX_PITCH_JUMP_SEMITONES` | pitch 중심이 이 semitone보다 크게 바뀌면 다른 노트로 분리합니다. 기본값 `0.75`는 반음 이동을 새 노트로 잡기 위한 값입니다. |
| `AI_SNAP_TO_SCALE` | `true`면 최종 결과를 추정한 major/minor scale에 맞춰 보정합니다. |
| `AI_SCALE_SNAP_MAX_SEMITONES` | scale 보정 시 최대 몇 semitone까지 이동할 수 있는지 정합니다. |
| `AI_MAX_UPLOAD_AUDIO_SECONDS` | 파일 업로드 분석에서 허용하는 최대 오디오 길이입니다. 기본값은 300초입니다. `0` 이하로 두면 ffmpeg 변환 시 `-t` 제한을 걸지 않습니다. |
| `AI_MAX_REALTIME_AUDIO_SECONDS` | 실시간 WebSocket에서 stop 후 최종 재분석을 위해 누적하는 최대 오디오 길이입니다. 기본값은 300초입니다. `0` 이하로 두면 제한 없이 누적합니다. |

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
- 프로젝트 저장 API는 현재 로컬 JSON 파일 기반입니다. 혼자 개발하거나 데모할 때는 바로 쓸 수 있지만, 여러 기기/여러 사용자 동기화가 필요하면 Supabase `projects` 테이블이나 별도 DB 저장소로 옮기는 것이 좋습니다.
- 실제 서비스 수준으로 가려면 Supabase Auth 연동 강화, 프로젝트 소유자 분리, 파일 저장소, 배포 환경 테스트가 추가로 필요합니다.

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

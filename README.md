# BachStudio Backend

BachStudio 백엔드는 프론트엔드 웹 DAW와 음정 분석 엔진을 연결하는 FastAPI 서버입니다.

현재 가장 중요한 역할은 브라우저에서 녹음한 허밍/보컬 오디오를 받아서, 프론트엔드 피아노롤에 바로 넣을 수 있는 MIDI 노트 데이터로 바꿔주는 것입니다. 이 기능에 필요한 기본 DSP 음정 분석 엔진은 백엔드 폴더 안에 내장되어 있어서 `BachStudio_Ai` 폴더가 없어도 동작합니다. 그 외에 로그인, 유저, 아이템 API는 Supabase 연동을 위한 기본 구조로 들어가 있습니다.

## 이 백엔드가 하는 일

- 프론트엔드에서 보낸 오디오 파일을 받습니다.
- `webm`, `wav`, `mp3` 같은 브라우저 녹음 파일을 16 kHz mono WAV로 변환합니다.
- 백엔드 내부 AI 엔진을 실행해 시간별 pitch frame을 분석합니다.
- 분석 결과를 피아노롤에서 쓰기 쉬운 노트 목록으로 묶습니다.
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

## Humming AI 기능

프론트엔드의 피아노롤 `Humming AI` 패널에서 녹음된 오디오를 서버로 보내면, 백엔드는 다음 순서로 처리합니다.

1. 업로드된 오디오 파일을 임시 폴더에 저장합니다.
2. `ffmpeg`가 설치되어 있으면 오디오를 16 kHz mono WAV로 변환합니다.
3. 백엔드 내부 `app/ai_engine`의 `RealtimePitchEngine`으로 pitch frame을 분석합니다.
4. 연속된 voiced frame을 하나의 음표 segment로 묶습니다.
5. BPM과 quantize 값을 기준으로 `startBeat`, `durationBeats`를 계산합니다.
6. MIDI 번호와 화면 표시용 음 이름을 만들어 JSON으로 반환합니다.

### DSP와 RMVPE

백엔드에는 두 가지 음정 추정 경로가 있습니다.

| 방식 | 설명 | 필요한 설치 |
| --- | --- | --- |
| DSP | 백엔드에 기본 내장된 autocorrelation 기반 pitch 추정기입니다. 설치가 가볍고 바로 동작합니다. | `requirements.txt` |
| RMVPE | 보컬/허밍 pitch 추정 품질을 높이기 위한 모델 기반 추정기입니다. 패키지와 모델 로딩이 필요할 수 있습니다. | `requirements.txt` + `requirements-rmvpe.txt` |

`.env`에서 `AI_PREFER_RMVPE=true`이면 서버는 RMVPE를 먼저 시도합니다. RMVPE 패키지나 모델 로딩에 실패하면 자동으로 DSP로 fallback합니다.

```env
AI_PREFER_RMVPE=true
AI_RMVPE_MODEL_PATH=
```

`AI_RMVPE_MODEL_PATH`는 `BachStudio_Ai` 폴더 경로가 아니라 RMVPE 모델 파일 경로입니다. `rmvpe-onnx`가 기본 모델을 알아서 찾을 수 있는 환경이면 비워둬도 됩니다. 직접 받은 모델 파일을 쓰는 경우에만 아래처럼 적습니다.

```env
AI_RMVPE_MODEL_PATH=/absolute/path/to/rmvpe.onnx
```

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
| `POST` | `/api/humming/transcribe` | 프론트 권장 Humming AI 변환 API입니다. |
| `POST` | `/api/v1/humming/transcribe` | 버전 prefix가 붙은 Humming AI 변환 API입니다. |
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

- Humming AI API는 실제 프론트 연결을 위한 핵심 기능입니다.
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

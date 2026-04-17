# BachStudio Backend

BachStudio 백엔드 API 서버입니다.
FastAPI, Supabase Auth, Google OAuth 연동을 중심으로 회원가입/로그인과 기본 리소스 API를 제공합니다.

## 1. 현재 구현된 기능 전체

1. 서버 기본 기능
	 - FastAPI 앱 기동
	 - 루트 상태 확인 API: GET /
	 - 헬스체크 API: GET /api/v1/health

2. 인증(Auth) 기능
	 - 이메일 회원가입: POST /api/v1/auth/signup
	 - 이메일 로그인: POST /api/v1/auth/login
	 - 토큰 유효성 검사: GET /api/v1/auth/validate
	 - Google OAuth 로그인 URL 발급: GET /api/v1/auth/login/google
	 - Google ID 토큰 기반 로그인: POST /api/v1/auth/login/google/id-token
	 - Google OAuth 인증 코드 교환(POST): POST /api/v1/auth/login/google/code
	 - Google OAuth 인증 코드 교환(GET 콜백): GET /api/v1/auth/login/google/callback?code=...

3. 사용자(User) 기능
	 - 내 정보 조회: GET /api/v1/users/me
	 - 특정 사용자 조회: GET /api/v1/users/{user_id}

4. 아이템(Item) 기능
	 - 아이템 목록 조회: GET /api/v1/items/
	 - 아이템 생성: POST /api/v1/items/

5. 인증 의존성 처리
	 - Authorization: Bearer <token> 헤더 파싱
	 - Supabase auth.get_user 기반 토큰 검증
	 - 인증 사용자 컨텍스트(sub, email, user) 생성

6. Supabase 연동
	 - users 테이블 조회/생성 로직
	 - items 테이블 조회/생성 로직

7. 개발 편의 동작
	 - users 조회/생성 실패 시 개발용 fallback 데이터 반환
	 - items 생성 실패 시 개발용 fallback 데이터 반환

## 2. 기술 스택

- Python 3.10+
- FastAPI
- Pydantic v2
- Supabase Python SDK
- Uvicorn

## 3. 프로젝트 구조

```text
project_root/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── core/
│   │   ├── config.py              # 환경 변수/설정
│   │   ├── security.py            # 보안 유틸(토큰 파싱)
│   │   └── supabase.py            # Supabase 클라이언트 생성
│   ├── api/
│   │   ├── deps.py                # 공통 의존성(인증/클라이언트)
│   │   ├── router.py              # 엔드포인트 라우터 집계
│   │   └── endpoints/
│   │       ├── auth.py            # 회원가입/로그인/토큰검증/Google 로그인
│   │       ├── user.py            # 사용자 API
│   │       └── item.py            # 아이템 API
│   ├── schemas/                   # 요청/응답 스키마
│   ├── services/                  # 비즈니스 로직 + DB 접근
│   └── utils/                     # 기타 유틸 함수
├── .env.example
├── requirements.txt
└── README.md
```

## 4. 시작하기

### 4-1. 사전 준비

1. Python 3.10 이상 설치
2. Supabase 프로젝트 생성
3. Google Cloud 프로젝트 및 OAuth Client 생성

### 4-2. 가상환경 생성 및 활성화

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 4-3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4-4. 환경 변수 파일 준비

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

### 4-5. 서버 실행

```bash
uvicorn app.main:app --reload
```

실행 후 기본 확인:

- GET http://localhost:8000/
- GET http://localhost:8000/api/v1/health

## 5. 환경 변수 설명

| 변수명 | 설명 | 예시 |
| --- | --- | --- |
| PROJECT_NAME | FastAPI 문서/앱 이름 | BachStudio Backend |
| API_PREFIX | API 공통 prefix | /api/v1 |
| DEBUG | 디버그 모드 | true |
| SUPABASE_URL | Supabase 프로젝트 URL | https://xxxx.supabase.co |
| SUPABASE_PUBLISHABLE_KEY | Supabase 공개 키(anon/publishable) | eyJ... |
| SUPABASE_SECRET_KEY | Supabase 서비스 키(현재 코드에서 직접 사용하지 않음) | eyJ... |
| GOOGLE_CLIENT_ID | Google OAuth Client ID | xxxxx.apps.googleusercontent.com |
| GOOGLE_CLIENT_SECRET | Google OAuth Client Secret | GOCSPX-... |
| GOOGLE_OAUTH_REDIRECT_URL | Google OAuth 시작 시 redirect_to 옵션으로 전달할 URL | http://localhost:5173/auth/callback |

참고:

- 설정 로더는 SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY 별칭도 인식합니다.

## 6. Supabase + Google Cloud 연동 상세

1. Google Cloud Console에서 OAuth 2.0 Client를 생성합니다.
2. Google OAuth Redirect URI에 아래 Supabase 콜백을 등록합니다.

```text
https://<your-project-ref>.supabase.co/auth/v1/callback
```

3. Supabase Dashboard의 Authentication > Providers > Google에서 Client ID/Secret을 입력합니다.
4. Supabase Dashboard의 Authentication > URL Configuration에서 허용 Redirect URL을 등록합니다.
5. 프로젝트 .env 파일에 SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, GOOGLE_OAUTH_REDIRECT_URL 등을 입력합니다.

## 7. API 엔드포인트 상세

### 7-1. 서버 상태

- GET /
	- 설명: 서버 동작 메시지 반환
	- 인증: 불필요

- GET /api/v1/health
	- 설명: 헬스체크
	- 인증: 불필요

### 7-2. 인증 API

- POST /api/v1/auth/signup
	- 설명: 이메일 회원가입
	- 인증: 불필요
	- 요청 예시:

```json
{
	"email": "user@example.com",
	"password": "password1234",
	"name": "홍길동"
}
```

- POST /api/v1/auth/login
	- 설명: 이메일/비밀번호 로그인
	- 인증: 불필요

- GET /api/v1/auth/login/google
	- 설명: Google OAuth 시작 URL 발급
	- 인증: 불필요

- POST /api/v1/auth/login/google/id-token
	- 설명: 모바일/네이티브 환경에서 받은 Google ID Token으로 로그인
	- 인증: 불필요
	- 요청 예시:

```json
{
	"id_token": "google-id-token",
	"nonce": "optional-nonce"
}
```

- POST /api/v1/auth/login/google/code
	- 설명: OAuth 인증 코드를 세션으로 교환
	- 인증: 불필요
	- 요청 예시:

```json
{
	"auth_code": "code-from-google-oauth-flow"
}
```

- GET /api/v1/auth/login/google/callback?code=...
	- 설명: OAuth 콜백 URL로 직접 코드 교환
	- 인증: 불필요

- GET /api/v1/auth/validate
	- 설명: Access Token 유효성 검증
	- 인증: 필요

### 7-3. 사용자 API

- GET /api/v1/users/me
	- 설명: 현재 인증 사용자 정보 조회
	- 인증: 필요

- GET /api/v1/users/{user_id}
	- 설명: user_id로 사용자 조회
	- 인증: 필요

### 7-4. 아이템 API

- GET /api/v1/items/
	- 설명: 아이템 목록 조회
	- 인증: 불필요

- POST /api/v1/items/
	- 설명: 아이템 생성
	- 인증: 필요
	- 요청 예시:

```json
{
	"title": "새 아이템",
	"description": "설명"
}
```

## 8. 권장 인증 흐름

1. 이메일 회원가입은 POST /api/v1/auth/signup 호출
2. 이메일 로그인은 POST /api/v1/auth/login 호출
3. 웹 Google 로그인은 GET /api/v1/auth/login/google로 URL을 받아 이동
4. 콜백에서 code를 얻으면 POST /api/v1/auth/login/google/code 또는 GET /api/v1/auth/login/google/callback 사용
5. 발급된 access_token으로 보호 API 호출 시 Authorization 헤더 사용

```text
Authorization: Bearer <access_token>
```

## 9. 현재 구현 상태 기준 주의사항

1. Supabase Auth에서 이메일 확인이 켜져 있으면 signup 직후 session이 null일 수 있습니다.
2. users/items 서비스에는 개발용 fallback 반환 로직이 있어, DB 실패 시에도 일부 응답이 반환될 수 있습니다.
3. GET /api/v1/users/{user_id}는 현재 인증 여부를 확인하지만, 소유권/권한 세분화는 추가 구현이 필요합니다.
4. GET /api/v1/items/는 현재 공개 엔드포인트입니다.

## 10. 다음 권장 작업

1. 서비스 계층 fallback 제거 및 명시적 에러 처리 강화
2. 사용자 조회 권한 정책(본인/관리자) 추가
3. pytest 기반 인증/인가 테스트 추가
4. 프론트엔드 연동 예제(로그인, 토큰 저장, 재인증) 문서화
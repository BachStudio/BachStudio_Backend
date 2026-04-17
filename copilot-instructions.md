# BachStudio Backend Copilot Instructions

## Purpose
- Keep all generated changes aligned with this repository's FastAPI backend architecture.
- Prefer small, safe, reviewable edits over broad refactors.

## Project Context
- Stack: FastAPI, Pydantic v2, Supabase Python client.
- API prefix: `/api/v1`.
- Entry point: `app/main.py`.
- Main modules follow the structure documented in `README.md`.

## Directory Responsibilities
- `app/main.py`: app bootstrap and router registration.
- `app/api/endpoints/`: route handlers only.
- `app/api/deps.py`: dependency injection and auth context.
- `app/services/`: business logic and Supabase table access.
- `app/schemas/`: request and response models.
- `app/core/`: configuration, security utilities, external clients.
- `app/utils/`: pure utility helpers.

## Editing Rules
- Follow existing naming, style, and module boundaries.
- Do not move logic across layers unless explicitly requested.
- Keep diffs minimal and focused on the asked task.
- Update related docs when behavior changes (especially endpoint changes in `README.md`).

## API Design Rules
- Validate all request bodies with Pydantic schemas.
- Use `response_model` and explicit status codes for endpoints.
- Raise `HTTPException` with clear, actionable details.
- Do not return fake fallback payloads for real failures.
- Protect private endpoints with `Depends(get_current_user)`.
- Never expose secrets, raw tokens, or passwords in responses.

## Supabase Rules
- Access Supabase through dependency injection (`get_supabase`).
- Keep table operations inside `app/services/`.
- Avoid broad `except Exception: pass` patterns.
- Handle database errors explicitly and surface meaningful API errors.
- Preserve ownership semantics (for example, `owner_id` from authenticated user context).

## Config and Environment
- Add new environment variables in both `.env.example` and `app/core/config.py`.
- Keep defaults safe for local development only.
- Do not hardcode credentials or API keys.

## Code Quality
- Use type hints for function signatures and return values.
- Prefer clear, small functions.
- Add short comments only when logic is not obvious.
- Avoid unused imports and dead code.

## Verification Checklist
After implementing changes, verify:
1. The app starts successfully.
2. Health endpoint responds (`GET /api/v1/health`).
3. Changed endpoints behave as expected for success and failure paths.
4. Updated schemas and responses stay consistent.

## Collaboration Preference
- Explain code changes and rationale in Korean when responding to the user.

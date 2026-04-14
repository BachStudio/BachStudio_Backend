# BachStudio_Backend

FastAPI backend baseline scaffold for BachStudio.

## Project Structure

```text
project_root/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── supabase.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── endpoints/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   └── item.py
│   │   └── router.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── item.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── item.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── .env
├── requirements.txt
└── README.md
```

## Quick Start

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Update values in `.env` for your Supabase project.

4. Run the API server.

```bash
uvicorn app.main:app --reload
```

## Endpoints

- Health: `GET /api/v1/health`
- Auth signup: `POST /api/v1/auth/signup`
- Auth login: `POST /api/v1/auth/login`
- Auth validate: `GET /api/v1/auth/validate`
- User me: `GET /api/v1/users/me`
- User by id: `GET /api/v1/users/{user_id}`
- Item list: `GET /api/v1/items/`
- Item create: `POST /api/v1/items/`
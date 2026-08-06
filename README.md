# SCT_PreweightQRcodeLabel

Internal Flask application for the approved preweight QR-code label workflow.

## Stage 1 local setup

Environment: macOS development workstation, Codex Desktop, zsh, Python 3.13, SQLite for local tests. Production uses SQL Server 2022 Express through ODBC Driver 18.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
APP_ENV=development .venv/bin/flask --app run.py db upgrade
APP_ENV=development .venv/bin/flask --app run.py seed-uat
APP_ENV=development .venv/bin/flask --app run.py run
```

Set `SECRET_KEY` and `DATABASE_URL` from the environment for production. Never commit `.env` or credentials.

## Development/UAT seed credentials

These accounts exist only after running `seed-uat` and must not be used as production defaults:

| Role | Username | Password |
|---|---|---|
| Operator | `uat_operator` | `Uat-OPERATOR-Only!` |
| Production | `uat_production` | `Uat-PRODUCTION-Only!` |
| Supervisor | `uat_supervisor` | `Uat-SUPERVISOR-Only!` |
| Admin | `uat_admin` | `Uat-ADMIN-Only!` |

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check .
APP_ENV=testing .venv/bin/flask --app run.py db upgrade
APP_ENV=testing .venv/bin/flask --app run.py db downgrade
APP_ENV=testing .venv/bin/flask --app run.py db upgrade
```

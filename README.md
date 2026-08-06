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

## Stage 2 UAT

After migration and `seed-uat`, start the application and open `http://127.0.0.1:5000`.
Use the development/UAT accounts above to verify valid and invalid login, inactive-user blocking,
station selection, session persistence, and logout. Stage 2 authorization is enforced in server-side
route decorators; later role-specific screens will use the same control.

## Stage 3 UAT data

For an existing UAT database created before Stage 3, add the approved negative cases once:

```bash
APP_ENV=development .venv/bin/flask --app run.py seed-stage3
```

The command is idempotent. Stage 3 preparation is available from Home for Operator, Supervisor,
and Admin accounts. The Basic Master Data view is Admin-only.

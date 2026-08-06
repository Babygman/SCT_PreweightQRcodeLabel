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

## Redesigned Stage 4 UAT — Mock ERP and document scanning

The approved Stage 4 correction uses Production Order + Formula Sheet as a 1:1 pair before
weighing. Development enables a separate **Mock ERP / Document Generator** for Supervisor/Admin.

1. Sign in and select a station.
2. Open `Mock ERP / Print QR Documents`.
3. Enter Production Order No., Finished Good code/name, Production Lot, Quantity (KG), Formula
   Sheet No., Production Date, and Expected Finish Date.
4. The generator automatically creates 30 mock raw-material lines. Their target weights sum to
   the entered production quantity.
5. Open/print the A4 Production Order and Formula Sheet. Each document contains a scannable QR.
6. Open `Prepare PO + Formula`, scan both printed QR codes, and validate them.
7. A matched pair becomes READY and may open the Weighing screen; a mismatched scan is blocked
   and retained in the audit log.

The Mock ERP is disabled by default in production configuration. It does not replace future ERP
integration. Raw-material Vendor Lot/QC/expiry validation from the superseded Stage 4 design is
not performed here; those values belong to the upstream Material Tag/ERP receiving process.

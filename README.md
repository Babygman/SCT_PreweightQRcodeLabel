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

## Weighing Workflow UAT

The primary production workflow is **Material-centric**. Prepare multiple PO + Formula pairs into
the station's active work set, scan one Material Tag, and weigh that material continuously across
every applicable prepared Production Order. The validated tag remains active between queue items.

The existing **Formula / Production Order-centric** screen remains available as an optional mode.
Both modes enforce station material capability, server-side Material Tag validation, positive
Actual Weight, duplicate prevention, immutable transaction traceability, and sticker reprint.

1. Select a pending Formula line.
2. Scan an 11-field Material Tag QR and confirm the immediate `MATCH` result.
3. Confirm Actual Weight remains disabled for invalid or `UN-MATCH` tags.
4. After `MATCH`, enter an Actual Weight greater than zero and save.
5. Confirm the printable Preweight Sticker opens with its ERP QR and print dialog.
6. Confirm the same Formula line cannot be weighed twice.
7. Confirm the same Material Tag can be used for another applicable Formula line.

Vendor Lot, QC status, expiry and remaining quantity do not authorize or block this workflow.
The immutable ERP QR payload is stored with the completed transaction so Reprint reproduces the
same QR content. ERP consumption remains outside this application's scope.

The current versioned JSON ERP QR format is intentionally preserved. Redesigning that payload is
deferred until a later approved requirement defines the target ERP format.

## Material Tag Issuance foundation

Stage A adds the schema and pure services for future Material Master import and Material Tag
issuance. It includes exact three-decimal container-weight splitting, six-calendar-month expiry
calculation, and construction of the existing eleven-field Material Tag QR payload. There are no
Material import, Tag issuance, history, or printing routes in Stage A.

Migration `b0551011c146` is additive, but its downgrade becomes destructive once issued Material
Tag records exist and therefore requires a separate approval at that point. The migration has not
been applied to the live UAT database as part of Stage A.

## Material Master import (Stage B)

Stage B adds an Admin-only, CSRF-protected `.xlsx` validation, persistent preview, and confirmed
apply workflow. It validates the exact `Sheet1` header contract, normalizes Material codes,
categories, names, classifies every row, and applies an idempotent Material-code upsert. Duplicate
Material names remain valid. Existing Material unit, classification, and active status are not
changed by an import. Uploads are limited to 5 MB and 5,000 data rows; unsafe ZIP/XML structures,
macros, external links, merged cells, formulas, and control characters are rejected. Any rejected
row blocks the entire Apply operation, so no partial Material import is possible.

The import routes and Master Data link are controlled by `MATERIAL_TAG_ISSUANCE_ENABLED`, which is
disabled by default. It must remain disabled in any environment where migration `b0551011c146` has
not been approved and applied. Stage B development tests enable the feature explicitly against an
isolated SQLite database; they do not apply the migration or import Materials into live UAT.

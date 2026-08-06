# SCT_PreweightQRcodeLabel — Baseline Addendum

Status: **APPROVED — 2026-08-06**
Date: 2026-08-06
Purpose: Close the documentation gaps that block Codex Stage 1. This addendum does not create Phase 7 and does not reopen the approved Version 1 business scope from Phases 1–6.

### Product Owner correction — Stage 4 (2026-08-06)

The Product Owner corrected the physical production workflow during Stage 4 UAT. This correction
supersedes only the conflicting raw-material-centric Stage 4 rules below; Stage 1–3 approved work
remains intact.

- Production Order and Formula Sheet are physical documents related 1:1 for the production job.
  The operator scans both QR codes before weighing. Product, Production Lot and the exact linked
  Formula Sheet must match. A mismatch is blocked and audit-logged.
- Version 1 includes a Development/UAT-only Mock ERP / Document Generator. The user enters PO No.,
  Finished Good code/name, Production Lot, production quantity, Formula Sheet No., Production Date,
  and Expected Finish Date. The generator creates about 30 raw-material lines and distributes target
  weights so their total equals the production quantity, then produces printable A4 PO and Formula
  Sheet documents with scannable QR identifiers.
- A Material Tag is 1:1 with one physical material bag. The same tag may be scanned repeatedly while
  that bag is used; this is normal and is not a duplicate condition.
- Material Tag data includes Item Code, Item Name, Vendor Lot No., and Expire Date. Preweight retains
  these values for weighing traceability. It does not create any lot number.
- Preweight does not validate Vendor Lot existence, QC HOLD/REJECT, expiry, or remaining bag
  quantity. Those controls occur upstream in ERP/Material Receiving/QC before the Material Tag is
  printed. Expire Date is retained as tag data and does not block weighing in Version 1.
- During weighing, the required Preweight validation is that the scanned Material Item Code matches
  the Formula Item being weighed. A wrong material scan is blocked and audit-logged.

## 1. Authority and precedence

1. `PROJECT_STANDARD.md` remains mandatory for engineering workflow, quality, testing, security, documentation, Git, and Definition of Done.
2. The approved Phase 1–6 business workflow and controls remain frozen.
3. After user approval, this addendum is the source of truth for the previously undocumented technical baseline required to implement Version 1.
4. Codex must not add business rules, integrations, infrastructure, or scope beyond these sources.
5. If an implementation decision is still genuinely undefined and affects business behavior, Codex must stop only that affected part and ask the user.

## 2. Version 1 technology baseline

| Area | Baseline |
|---|---|
| Language | Python 3.13 |
| Web framework | Flask |
| ORM | SQLAlchemy 2.x via Flask-SQLAlchemy |
| Database migration | Alembic via Flask-Migrate |
| Database | Microsoft SQL Server 2022 Express |
| SQL Server driver | Microsoft ODBC Driver 18 for SQL Server via `pyodbc` |
| Authentication | Local application accounts; password hashes only, never plaintext |
| Server-side session/auth | Flask-Login |
| Forms / CSRF | Flask-WTF / CSRF protection for state-changing web requests |
| UI | Server-rendered Jinja2 templates + Bootstrap 5; minimal JavaScript only where needed |
| QR generation | Server-generated QR containing the `PreweightId` identifier only |
| Tests | Pytest |
| Production WSGI | Waitress |

No SPA framework, Node.js application layer, Redis, Celery, Docker, cloud platform, or separate API service is required for Version 1.

## 3. Deployment baseline

- Target: one internal Windows Server 2019 application server on the company LAN.
- Application: Flask served by Waitress as a Windows-hosted service/process according to `PROJECT_STANDARD.md` deployment requirements.
- Database: Microsoft SQL Server 2022 Express. It may be on the same internal server for Version 1; the connection string must remain configuration-driven so SQL Server can be moved later without code changes.
- Client: supported desktop web browser on internal PCs.
- Secrets and database connection strings: environment/configuration only; never committed to Git.
- Version 1 is an internal web application and does not require public Internet exposure.

## 4. Application architecture

Use a Flask application-factory structure with clear separation of concerns:

```text
SCT_PreweightQRcodeLabel/
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models/
│   ├── auth/
│   ├── master_data/
│   ├── preparation/
│   ├── weighing/
│   ├── printing/
│   ├── verification/
│   ├── traceability/
│   ├── services/
│   ├── templates/
│   └── static/
├── migrations/
├── tests/
├── config.py
├── requirements.txt
├── run.py
├── PROJECT_STANDARD.md
└── APPROVED_BASELINE_ADDENDUM.md
```

Architecture rules:

- Blueprints own HTTP routes and page-level behavior.
- SQLAlchemy models own persistence mappings, not business workflows.
- Business rules that span multiple routes/models belong in service functions/classes.
- Authorization must be enforced server-side.
- Database transactions must protect Save/Complete, Void, and Confirm Use operations.
- Timestamps are stored in UTC; presentation may convert to the configured local timezone.
- Primary keys use SQL Server integer identity keys internally. Human-readable business identifiers/codes are separate unique columns.
- Do not implement D365 or scale adapters in Version 1.

## 5. Approved Version 1 schema baseline after user approval

Names below are canonical logical names. Codex may use Pythonic snake_case physical names consistently, but must not change the meaning or relationships.

### 5.1 `roles`

- `id` INT IDENTITY PK
- `code` NVARCHAR(30) NOT NULL UNIQUE — `OPERATOR`, `PRODUCTION`, `SUPERVISOR`, `ADMIN`
- `name` NVARCHAR(100) NOT NULL

### 5.2 `users`

- `id` INT IDENTITY PK
- `username` NVARCHAR(50) NOT NULL UNIQUE
- `password_hash` NVARCHAR(255) NOT NULL
- `display_name` NVARCHAR(100) NOT NULL
- `is_active` BIT NOT NULL DEFAULT 1
- `created_at_utc` DATETIME2 NOT NULL
- `updated_at_utc` DATETIME2 NOT NULL

### 5.3 `user_roles`

- `user_id` INT NOT NULL FK -> `users.id`
- `role_id` INT NOT NULL FK -> `roles.id`
- Composite PK (`user_id`, `role_id`)

### 5.4 `stations`

- `id` INT IDENTITY PK
- `code` NVARCHAR(30) NOT NULL UNIQUE
- `name` NVARCHAR(100) NOT NULL
- `printer_name` NVARCHAR(255) NULL — configured logical printer name used for print logging/routing
- `is_active` BIT NOT NULL DEFAULT 1

There is no Material-to-Station mapping.

### 5.5 `materials`

- `id` INT IDENTITY PK
- `code` NVARCHAR(50) NOT NULL UNIQUE
- `name` NVARCHAR(200) NOT NULL
- `unit` NVARCHAR(20) NOT NULL
- `is_active` BIT NOT NULL DEFAULT 1

### 5.6 `raw_material_lots`

- `id` INT IDENTITY PK
- `material_id` INT NOT NULL FK -> `materials.id`
- `lot_no` NVARCHAR(100) NOT NULL
- `qc_status` NVARCHAR(20) NOT NULL — allowed Version 1 values: `PASS`, `HOLD`, `REJECT`
- `expiry_date` DATE NULL
- `is_active` BIT NOT NULL DEFAULT 1
- UNIQUE (`material_id`, `lot_no`)

This table is retained for compatibility with the already-approved foundation, but after the Stage 4
Product Owner correction it is not a weighing validation authority. Preweight must not block a
Material Tag by QC status, expiry, or Vendor Lot lookup in this table.

### 5.7 `products`

- `id` INT IDENTITY PK
- `code` NVARCHAR(50) NOT NULL UNIQUE
- `name` NVARCHAR(200) NOT NULL
- `is_active` BIT NOT NULL DEFAULT 1

### 5.8 `formulas`

- `id` INT IDENTITY PK
- `code` NVARCHAR(50) NOT NULL UNIQUE
- `name` NVARCHAR(200) NOT NULL
- `product_id` INT NOT NULL FK -> `products.id`
- `is_active` BIT NOT NULL DEFAULT 1

### 5.9 `formula_items`

- `id` INT IDENTITY PK
- `formula_id` INT NOT NULL FK -> `formulas.id`
- `line_no` INT NOT NULL
- `material_id` INT NOT NULL FK -> `materials.id`
- `target_weight` DECIMAL(18,3) NOT NULL
- `unit` NVARCHAR(20) NOT NULL
- UNIQUE (`formula_id`, `line_no`)

Version 1 does not apply weight-tolerance blocking.

### 5.10 `production_orders`

- `id` INT IDENTITY PK
- `po_no` NVARCHAR(50) NOT NULL UNIQUE
- `product_id` INT NOT NULL FK -> `products.id`
- `production_lot` NVARCHAR(100) NOT NULL
- `formula_id` INT NULL FK -> `formulas.id`
- `status` NVARCHAR(20) NOT NULL — `OPEN`, `READY`, `COMPLETED`, `CANCELLED`
- `prepared_by_user_id` INT NULL FK -> `users.id`
- `prepared_at_utc` DATETIME2 NULL

Preparation rule: an `OPEN` PO becomes `READY` only after the scanned/selected formula belongs to the PO product. `COMPLETED` and `CANCELLED` orders cannot be opened for new weighing.

### 5.11 `weighing_transactions`

- `id` INT IDENTITY PK
- `preweight_id` NVARCHAR(40) NOT NULL UNIQUE
- `production_order_id` INT NOT NULL FK -> `production_orders.id`
- `formula_item_id` INT NOT NULL FK -> `formula_items.id`
- `raw_material_lot_id` INT NOT NULL FK -> `raw_material_lots.id`
- `target_weight_snapshot` DECIMAL(18,3) NOT NULL
- `actual_weight` DECIMAL(18,3) NOT NULL
- `unit_snapshot` NVARCHAR(20) NOT NULL
- `station_id` INT NOT NULL FK -> `stations.id`
- `weighed_by_user_id` INT NOT NULL FK -> `users.id`
- `weighed_at_utc` DATETIME2 NOT NULL
- `status` NVARCHAR(20) NOT NULL — `COMPLETED`, `CONSUMED`, `VOIDED`
- `consumed_by_user_id` INT NULL FK -> `users.id`
- `consumed_at_utc` DATETIME2 NULL
- `voided_by_user_id` INT NULL FK -> `users.id`
- `voided_at_utc` DATETIME2 NULL
- `void_reason` NVARCHAR(500) NULL

Critical database control: create a SQL Server filtered UNIQUE index on (`production_order_id`, `formula_item_id`) for rows whose `status` is `COMPLETED` or `CONSUMED`. A `VOIDED` row does not block a replacement weighing. Application-level checks are also required, but are not a substitute for this database constraint.

`preweight_id` format for Version 1: `PW-YYYYMMDD-NNNNNN`. Generation must be concurrency-safe and must never reuse an ID.

### 5.12 `label_print_logs`

- `id` INT IDENTITY PK
- `weighing_transaction_id` INT NOT NULL FK -> `weighing_transactions.id`
- `print_type` NVARCHAR(20) NOT NULL — `ORIGINAL`, `RETRY`, `REPRINT`
- `result` NVARCHAR(20) NOT NULL — `SUCCESS`, `FAILED`
- `printer_name` NVARCHAR(255) NULL
- `printed_by_user_id` INT NOT NULL FK -> `users.id`
- `printed_at_utc` DATETIME2 NOT NULL
- `reason` NVARCHAR(500) NULL
- `error_message` NVARCHAR(1000) NULL

`REPRINT` requires a reason. Retry/Reprint always uses the existing transaction and existing `preweight_id`; it never creates another weighing transaction or QR identity.

### 5.13 `verification_logs`

- `id` INT IDENTITY PK
- `expected_production_order_id` INT NULL FK -> `production_orders.id`
- `scanned_preweight_id` NVARCHAR(40) NOT NULL
- `weighing_transaction_id` INT NULL FK -> `weighing_transactions.id`
- `result` NVARCHAR(10) NOT NULL — `PASS`, `FAIL`
- `reason_code` NVARCHAR(50) NULL
- `detail` NVARCHAR(500) NULL
- `verified_by_user_id` INT NOT NULL FK -> `users.id`
- `verified_at_utc` DATETIME2 NOT NULL

Failed scans must be logged even when the scanned Preweight ID does not exist; therefore `weighing_transaction_id` is nullable and the scanned text is stored separately.

### 5.14 `audit_logs`

- `id` BIGINT IDENTITY PK
- `event_type` NVARCHAR(50) NOT NULL
- `entity_type` NVARCHAR(50) NOT NULL
- `entity_id` NVARCHAR(100) NULL
- `user_id` INT NULL FK -> `users.id`
- `station_id` INT NULL FK -> `stations.id`
- `occurred_at_utc` DATETIME2 NOT NULL
- `detail` NVARCHAR(MAX) NULL

Use this for security/business audit events that are not already completely represented by the immutable print/verification/weighing records. Do not store passwords or secrets in audit detail.

## 6. Weighing and consistency rules

These rules restate the frozen Phase 4–6 behavior so the technical schema cannot be interpreted incorrectly:

1. PO + Formula must match before the PO becomes ready for weighing.
2. After the Production Order and its exact 1:1 Formula Sheet are scanned and matched, the Weighing
   screen loads that Formula's lines. A scanned Material Tag must match the Formula Item code being
   weighed; Vendor Lot/QC/expiry lookup is not a blocking rule.
3. One PO formula line may have only one active `COMPLETED`/`CONSUMED` weighing transaction.
4. Save the weighing transaction and commit successfully before attempting label printing.
5. Actual weight is manually entered, numeric, and greater than zero; there is no tolerance blocking in Version 1.
6. A completed transaction cannot be edited. Correction is `VOID -> reason -> new weighing -> new Preweight ID`.
7. A Preweight ID is never changed by Retry/Reprint.
8. Production verification must block invalid/non-completed/voided/wrong-PO/wrong-product-lot/wrong-formula/already-consumed material.
9. Successful Confirm Use changes the transaction from `COMPLETED` to `CONSUMED` atomically and can happen only once.
10. Failed verification attempts are retained for audit/RCA.

## 7. UI baseline

Use server-rendered responsive pages with a consistent Bootstrap 5 layout. Version 1 requires functional internal screens, not a custom design system.

Required screen groups:

- Login and Station selection
- Home/menu showing signed-in user and selected station
- Admin Master Data: Users, Stations, Materials, Raw Material Lots, Products, Formulas/Items, Production Orders
- PO/Formula Preparation
- Material Scan / Pending Orders
- Weigh / Save & Print
- Print Retry/Reprint
- Void transaction
- Production Verification / Confirm Use
- Traceability Search / Detail

Validation and authorization must remain server-side even when client-side validation is also present.

## 8. Label/printing baseline

- Version 1 generates a printable label containing the approved Phase 6 fields and a QR code whose payload is the `PreweightId` only.
- Printer targeting uses the selected station's configured `printer_name` as the logical printer identity recorded in print logs.
- Keep physical printer transport behind a small printing service/interface so printer-specific behavior is not embedded in weighing routes.
- Do not add a printer-vendor SDK, D365 integration, digital-scale integration, or new hardware dependency without an explicit user decision.
- A printing error must never roll back or delete an already committed weighing transaction.

## 9. Seed/UAT baseline

Stage 1 must seed only enough clearly marked test data to exercise the approved workflow, including:

- The four Version 1 roles
- At least one test user per role
- At least two stations
- Multiple materials and legacy raw-material-lot examples may remain for regression compatibility;
  HOLD/REJECT/expired values are not Stage 4 blocking cases after the Product Owner correction
- At least two products/formulas with formula items
- Multiple OPEN production orders so later UAT can test one material required by more than one PO

Seed credentials must be development/test-only and must not be production defaults.

## 10. Explicit Version 1 exclusions

Do not implement:

- D365 integration
- Digital scale integration
- Weight tolerance rule
- Material-to-Station mapping
- Automatic raw-material issue
- Automatic production scheduling
- Mobile app
- SPA/front-end framework migration
- New business rules not present in the frozen Phase 1–6 design

## 11. Approval effect

Before approval, this file is a proposal and Codex must not treat it as approved authority.

After the user explicitly approves this addendum:

1. Change the status at the top to `APPROVED — 2026-08-06`.
2. Commit this file to the repository.
3. Codex may proceed with Stage 1 using `PROJECT_STANDARD.md`, the Phase 1–6 frozen business design, and this addendum as the implementation baseline.
4. No Phase 7 is created by this approval.

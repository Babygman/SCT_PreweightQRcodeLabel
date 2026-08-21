# Changelog

## v1.0.0-rc.1 — 2026-08-21

UAT-approved prerelease; no Production deployment is included.

### Added

- Material-centric multi-order weighing workspace with guarded completion and read-only completed
  Work Sets.
- Secure ADMIN-only Material Master workbook Preview/Apply workflow with transactional,
  idempotent Material Code upserts and row-level results.
- Immutable Material Tag receiving, issuance, eleven-field QR payload, original printing,
  reason-controlled reprinting, and auditable Print History.
- Accessible Print Preview navigation to batch details, Material Tag History, and Home, hidden from
  the physical 3 × 2.5 inch label output.

### Deployment notes

- Database migration head is `b0551011c146`; back up and migrate each environment before enabling
  the feature.
- Material Tag functionality remains disabled by default and requires explicit approved environment
  configuration.
- Runtime controls include authentication, roles, Station context, CSRF, immutable issuance, and
  audited import/print/reprint operations without DELETE permission.
- Use 100% print scale, no margins, disabled browser headers/footers, and Fit to Page off.
- `RENDERED` confirms page preparation only, not physical printer success. Disable the feature to
  deactivate it; never delete issued or imported audit evidence.

## Unreleased

### Added

- Approved technical baseline addendum.
- Flask application factory, configuration, logging, and error pages.
- Approved Version 1 SQLAlchemy schema and initial Alembic migration.
- Development/UAT seed command and documented test-only accounts.
- Stage 1 automated tests, template compile, and SQL smoke checks.
- Login with active-user validation and generic invalid-credential responses.
- Active station selection stored in session context.
- CSRF-protected logout and authentication audit records.
- Reusable server-side station and role authorization decorators.
- Admin-only Basic Master Data visibility for approved core records.
- Production Order and Formula preparation with server-side status, availability, and product checks.
- Idempotent Stage 3 UAT seed supplement for cancelled, completed, and inactive-formula cases.
- Redesigned Stage 4 Production Order / Formula Sheet scan with exact-pair and Production Lot checks.
- Failed PO / Formula scans retained in the business audit log.
- Development/UAT Mock ERP generator with user-defined production job fields, 30 automatic raw
  materials, balanced target weights, printable A4 Production Order / Formula Sheet, and QR codes.
- READY-order Weighing screen showing the matched production context and formula lines.
- Material Tag parsing, material-code validation, actual-weight capture, traceability snapshots,
  concurrency-safe Preweight IDs, and completed Weighing transactions.
- Immediate Material Tag MATCH/UN-MATCH feedback, guarded Actual Weight entry, and printable
  Preweight Stickers with immutable versioned ERP QR payloads and reprint support.
- Primary Material-centric work sets and queues for weighing one validated material continuously
  across multiple Production Orders, with station material-classification enforcement.
- Optional Formula / Production Order-centric weighing retained alongside operational progress.
- Migration for production quantity/date fields and Formula Sheet production-lot/batch snapshots.
- Material Tag Issuance Stage A models for import previews, issuance drafts, immutable batches,
  child Tags, and print-render audit events.
- Decimal-only container-weight splitting, calendar expiry, and exact eleven-field Material Tag QR
  construction services.
- Admin-only Material Master `.xlsx` upload with secure workbook validation, normalized row-level
  persistent previews, confirmed idempotent Material-code upserts, audit events, and result UI.
- Disabled-by-default Material Tag Issuance feature gate to protect environments where the new
  foundation migration has not yet been applied.
- Stage B completion safeguards for all-or-nothing imports, SQL Server batch locking, persisted
  preview revalidation, hostile workbook rejection, paged results, and Thailand-time audit context.

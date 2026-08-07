# Changelog

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

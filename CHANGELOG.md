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

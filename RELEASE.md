# Release Status

## v1.0.0-rc.1 — UAT-approved prerelease

This release candidate has passed UAT. It is not a Production deployment or Production approval.

### Accepted capabilities

- Material-centric master-detail weighing with an FHD-friendly ten-Material queue, mandatory
  Material Tag validation, mismatch rejection, partial/completed progress, unsaved-weight warning,
  and audited, idempotent Work Set completion that makes completed Production Orders read-only.
- ADMIN-only Material Master `.xlsx` validation, persistent Preview, explicit Apply, row-level
  INSERT/UPDATE/UNCHANGED/REJECTED classification, all-or-nothing rejection handling, and a locked,
  transactional, audited, idempotent upsert by Material Code. The accepted workbook imported 329
  INSERT rows and normalized `R07047S1` to `PG740`.
- Material Tag search, receiving draft/preview/confirmation, six-calendar-months-minus-one-day
  expiry, exact Decimal reconciliation, immutable batches and child Tags, and an immutable exact
  eleven-field QR payload. The accepted `210.000 / 25.000 kg` case produced eight `25.000 kg` Tags
  and one `10.000 kg` Tag.
- Original batch print, reason-controlled individual/batch reprint, audited Print History, and
  exactly one `3in × 2.5in` label per page. Print Preview provides Print, batch details, history,
  and Home navigation while excluding screen controls from physical output.

### Deployment and configuration

- Required database migration head: `b0551011c146`.
- Back up each target environment and apply the approved migration before enabling Material Master
  Import or Material Tag functionality.
- The feature remains disabled by default. Enable it only through the approved
  `MATERIAL_TAG_ISSUANCE_ENABLED` environment configuration after migration and permission checks.
- Roll back operational exposure by disabling the feature through configuration. Do not delete
  issued Tags, imported Material evidence, audit records, or print history.

### Security and operator notes

- Runtime access remains protected by authentication, role, Station, and CSRF controls. Imports,
  immutable issuance, print, and reprint activity are audited; runtime database access does not
  require DELETE permission.
- Print on 3 × 2.5 inch media at 100% scale with no margins, browser headers/footers disabled, and
  Fit to Page disabled.
- `RENDERED` means the browser print page was prepared; it does not confirm physical printer
  delivery or hardware success.
- The current three-section Home layout is functionally accepted for this release candidate, but
  has not received final visual-design approval.

## Version 1 — In development

- Stage 1: Approved and pushed to `origin/main`.
- Stage 2: Approved and pushed to `origin/main`.
- Stage 3: Approved and pushed to `origin/main`.
- Stage 4: Redesigned after Product Owner workflow correction; Mock ERP + printable QR documents,
  exact PO / Formula Sheet validation, audit logging, and Weighing workflow implemented.
- Core Preweight Sticker Workflow: Immediate material validation, guarded weight entry, immutable
  ERP QR payload persistence, automatic print dialog, and reprint support are ready for UAT.
- Material-centric Workflow: Primary multi-PO work-set queue, persistent Material Tag session,
  station capabilities, and per-material/per-order progress implemented for UAT. Formula-centric
  weighing remains optional. ERP QR payload redesign is deferred.
- Material Tag Issuance Stage A: Additive data foundation and pure weight, expiry, and compatible
  eleven-field QR services implemented locally. The new migration has not been applied to live UAT.
- Material Tag Issuance Stage B: Secure Admin-only Excel Material Master validation, persistent
  row-level preview, confirmed idempotent upsert, audit events, and result UI implemented locally
  behind a disabled-by-default feature gate. Material Tag issuance UI remains out of scope.

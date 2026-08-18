# Release Status

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

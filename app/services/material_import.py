import hashlib
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import func, select
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import AuditLog, Material, MaterialImportBatch, MaterialImportRow, utcnow

REQUIRED_HEADERS = ("ITEM CODE", "CATEGORY_NO", "NAME")
ALLOWED_CATEGORY = "MAT"


class MaterialImportError(ValueError):
    """Raised when a Material Master workbook or import operation is invalid."""


@dataclass
class ParsedRow:
    row_number: int
    item_code: str | None
    category_no: str | None
    name: str | None
    result: str = "REJECTED"
    reason_code: str | None = None
    reason_detail: str | None = None


def _normalized(value, *, uppercase=False):
    if value is None:
        return None
    text_value = unicodedata.normalize("NFC", str(value)).strip()
    if not text_value:
        return None
    return text_value.upper() if uppercase else text_value


def _safe_filename(filename):
    cleaned = secure_filename(filename or "")
    return cleaned[:255] or "material-master.xlsx"


def _validate_xlsx_container(file_bytes, maximum_uncompressed_bytes):
    if not file_bytes.startswith(b"PK"):
        raise MaterialImportError("The uploaded file is not a valid .xlsx workbook.")
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
            members = archive.infolist()
            if len(members) > 1_000:
                raise MaterialImportError("The workbook contains too many internal files.")
            if any(
                member.filename.startswith(("/", "\\"))
                or ".." in member.filename.replace("\\", "/").split("/")
                for member in members
            ):
                raise MaterialImportError("The workbook contains an unsafe internal path.")
            if sum(member.file_size for member in members) > maximum_uncompressed_bytes:
                raise MaterialImportError("The workbook expands beyond the permitted size.")
            names = {member.filename for member in members}
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise MaterialImportError("The uploaded file is not a valid .xlsx workbook.")
            if any(name.lower().endswith("vbaproject.bin") for name in names):
                raise MaterialImportError("Macro-enabled workbooks are not accepted.")
    except (zipfile.BadZipFile, OSError) as exc:
        raise MaterialImportError("The uploaded file is not a valid .xlsx workbook.") from exc


def parse_material_workbook(
    file_bytes,
    *,
    maximum_bytes,
    maximum_rows,
    maximum_uncompressed_bytes,
):
    if not file_bytes:
        raise MaterialImportError("The uploaded workbook is empty.")
    if len(file_bytes) > maximum_bytes:
        raise MaterialImportError("The workbook exceeds the permitted upload size.")
    _validate_xlsx_container(file_bytes, maximum_uncompressed_bytes)

    try:
        workbook = load_workbook(
            BytesIO(file_bytes), read_only=True, data_only=False, keep_links=False
        )
    except (InvalidFileException, KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        raise MaterialImportError(
            "The uploaded file could not be read as an .xlsx workbook."
        ) from exc

    try:
        if workbook.sheetnames != ["Sheet1"]:
            raise MaterialImportError("The workbook must contain only the Sheet1 worksheet.")
        worksheet = workbook["Sheet1"]
        worksheet_rows = list(worksheet.iter_rows())
        if not worksheet_rows:
            raise MaterialImportError("The Sheet1 worksheet is empty.")

        header_cells = list(worksheet_rows[0])
        while header_cells and _normalized(header_cells[-1].value) is None:
            header_cells.pop()
        if any(cell.data_type == "f" for cell in header_cells):
            raise MaterialImportError("Header cells must not contain formulas.")
        headers = tuple(_normalized(cell.value, uppercase=True) for cell in header_cells)
        if headers != REQUIRED_HEADERS:
            raise MaterialImportError(
                "Sheet1 headers must be exactly: ITEM CODE, CATEGORY_NO, NAME."
            )

        data_rows = [list(row[:3]) for row in worksheet_rows[1:]]
        while data_rows and all(_normalized(cell.value) is None for cell in data_rows[-1]):
            data_rows.pop()
        if not data_rows:
            raise MaterialImportError("The workbook contains no Material rows.")
        if len(data_rows) > maximum_rows:
            raise MaterialImportError("The workbook contains more rows than permitted.")

        parsed = []
        for row_number, cells in enumerate(data_rows, start=2):
            values = [cell.value for cell in cells]
            code = _normalized(values[0], uppercase=True)
            category = _normalized(values[1], uppercase=True)
            name = _normalized(values[2])
            row = ParsedRow(row_number, code, category, name)
            if any(cell.data_type == "f" for cell in cells):
                row.reason_code = "FORMULA_NOT_ALLOWED"
                row.reason_detail = "Required cells must contain values, not formulas."
            elif code is None or category is None or name is None:
                row.reason_code = "REQUIRED_VALUE_MISSING"
                row.reason_detail = "ITEM CODE, CATEGORY_NO, and NAME are required."
            elif len(code) > 50 or len(category) > 30 or len(name) > 200:
                row.reason_code = "VALUE_TOO_LONG"
                row.reason_detail = "One or more values exceed the permitted field length."
            elif category != ALLOWED_CATEGORY:
                row.reason_code = "CATEGORY_NOT_ALLOWED"
                row.reason_detail = "CATEGORY_NO must be MAT."
            parsed.append(row)

        duplicates = {
            code
            for code, count in Counter(row.item_code for row in parsed if row.item_code).items()
            if count > 1
        }
        for row in parsed:
            if row.item_code in duplicates:
                row.result = "REJECTED"
                row.reason_code = "DUPLICATE_ITEM_CODE"
                row.reason_detail = "ITEM CODE occurs more than once in this workbook."
        return parsed
    finally:
        workbook.close()


def _add_audit(event_type, batch, user_id, station_id):
    detail = (
        f"status={batch.status};total={batch.total_rows};insert={batch.inserted_count};"
        f"update={batch.updated_count};unchanged={batch.unchanged_count};"
        f"rejected={batch.rejected_count};sha256={batch.file_sha256}"
    )
    audit = AuditLog(
        event_type=event_type,
        entity_type="MATERIAL_IMPORT_BATCH",
        entity_id=str(batch.id),
        user_id=user_id,
        station_id=station_id,
        occurred_at_utc=utcnow(),
        detail=detail,
    )
    if db.session.get_bind().dialect.name == "sqlite":
        audit.id = db.session.scalar(select(func.coalesce(func.max(AuditLog.id), 0) + 1))
    db.session.add(audit)


def _set_counts(batch):
    counts = Counter(row.result for row in batch.rows)
    batch.total_rows = len(batch.rows)
    batch.inserted_count = counts["INSERT"]
    batch.updated_count = counts["UPDATE"]
    batch.unchanged_count = counts["UNCHANGED"]
    batch.rejected_count = counts["REJECTED"]


def create_material_import_preview(
    *,
    file_bytes,
    filename,
    idempotency_key,
    user_id,
    station_id,
    maximum_bytes,
    maximum_rows,
    maximum_uncompressed_bytes,
):
    existing_batch = db.session.scalar(
        select(MaterialImportBatch).where(MaterialImportBatch.idempotency_key == idempotency_key)
    )
    if existing_batch is not None:
        return existing_batch

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    batch = MaterialImportBatch(
        original_filename=_safe_filename(filename),
        file_sha256=file_hash,
        status="PREVIEWED",
        total_rows=0,
        uploaded_by_user_id=user_id,
        uploaded_at_utc=utcnow(),
        idempotency_key=idempotency_key,
    )
    db.session.add(batch)
    try:
        parsed_rows = parse_material_workbook(
            file_bytes,
            maximum_bytes=maximum_bytes,
            maximum_rows=maximum_rows,
            maximum_uncompressed_bytes=maximum_uncompressed_bytes,
        )
    except MaterialImportError as exc:
        batch.status = "FAILED"
        batch.error_summary = str(exc)
        db.session.flush()
        _add_audit("MATERIAL_IMPORT_VALIDATION_FAILED", batch, user_id, station_id)
        db.session.commit()
        return batch

    valid_codes = [
        row.item_code
        for row in parsed_rows
        if row.reason_code is None and row.item_code is not None
    ]
    existing_materials = {
        material.code: material
        for material in db.session.scalars(select(Material).where(Material.code.in_(valid_codes)))
    }
    for parsed in parsed_rows:
        if parsed.reason_code is None:
            material = existing_materials.get(parsed.item_code)
            if material is None:
                parsed.result = "INSERT"
            elif material.name == parsed.name and material.source_category_no == parsed.category_no:
                parsed.result = "UNCHANGED"
            else:
                parsed.result = "UPDATE"
        batch.rows.append(
            MaterialImportRow(
                row_number=parsed.row_number,
                item_code_normalized=parsed.item_code,
                category_no_normalized=parsed.category_no,
                name_normalized=parsed.name,
                result=parsed.result,
                reason_code=parsed.reason_code,
                reason_detail=parsed.reason_detail,
            )
        )
    _set_counts(batch)
    db.session.flush()
    _add_audit("MATERIAL_IMPORT_PREVIEWED", batch, user_id, station_id)
    db.session.commit()
    return batch


def apply_material_import(*, batch_id, user_id, station_id):
    batch = db.session.scalar(
        select(MaterialImportBatch).where(MaterialImportBatch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise MaterialImportError("Material import preview was not found.")
    if batch.status == "APPLIED":
        return batch
    if batch.status != "PREVIEWED":
        raise MaterialImportError("Only a valid preview can be applied.")

    rows = sorted(batch.rows, key=lambda row: row.row_number)
    valid_rows = [row for row in rows if row.result != "REJECTED"]
    if not valid_rows:
        raise MaterialImportError("The preview contains no valid Material rows to apply.")
    codes = [row.item_code_normalized for row in valid_rows]
    existing_materials = {
        material.code: material
        for material in db.session.scalars(select(Material).where(Material.code.in_(codes)))
    }
    changed_at = utcnow()
    for row in valid_rows:
        material = existing_materials.get(row.item_code_normalized)
        if material is None:
            material = Material(
                code=row.item_code_normalized,
                name=row.name_normalized,
                unit="kg",
                classification="GENERAL",
                source_category_no=row.category_no_normalized,
                updated_at_utc=changed_at,
                updated_by_user_id=user_id,
            )
            db.session.add(material)
            existing_materials[material.code] = material
            row.result = "INSERT"
        elif (
            material.name != row.name_normalized
            or material.source_category_no != row.category_no_normalized
        ):
            material.name = row.name_normalized
            material.source_category_no = row.category_no_normalized
            material.updated_at_utc = changed_at
            material.updated_by_user_id = user_id
            row.result = "UPDATE"
        else:
            row.result = "UNCHANGED"

    _set_counts(batch)
    batch.status = "APPLIED"
    batch.applied_by_user_id = user_id
    batch.applied_at_utc = changed_at
    _add_audit("MATERIAL_IMPORT_APPLIED", batch, user_id, station_id)
    db.session.commit()
    return batch

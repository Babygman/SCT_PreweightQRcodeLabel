from datetime import UTC, date, datetime
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, text
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

UTC_DATETIME = db.DateTime().with_variant(mssql.DATETIME2(), "mssql")
SQL_DATE = db.Date().with_variant(mssql.DATE(), "mssql")
MAX_UNICODE = db.UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")
BIGINT_ID = db.BigInteger().with_variant(db.Integer(), "sqlite")


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.Unicode(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(db.Unicode(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(db.Unicode(255), nullable=False)
    display_name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, default=utcnow, nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(
        UTC_DATETIME, default=utcnow, onupdate=utcnow, nullable=False
    )
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")


class Station(db.Model):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.Unicode(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    printer_name: Mapped[str | None] = mapped_column(db.Unicode(255))
    material_classifications: Mapped[str | None] = mapped_column(
        db.Unicode(500), default="GENERAL", server_default=text("'GENERAL'"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)


class Material(db.Model):
    __tablename__ = "materials"
    __table_args__ = (Index("ix_materials_name", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.Unicode(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(200), nullable=False)
    unit: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    classification: Mapped[str | None] = mapped_column(
        db.Unicode(50), default="GENERAL", server_default=text("'GENERAL'"), nullable=True
    )
    source_category_no: Mapped[str | None] = mapped_column(db.Unicode(30))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)
    updated_at_utc: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    updated_by_user_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    updated_by: Mapped[User | None] = relationship(foreign_keys=[updated_by_user_id])


class MaterialImportBatch(db.Model):
    __tablename__ = "material_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('PREVIEWED', 'APPLIED', 'FAILED', 'EXPIRED')", name="status"),
        Index("ix_material_import_batches_file_sha256", "file_sha256"),
    )
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(db.Unicode(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(db.Unicode(64), nullable=False)
    status: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    total_rows: Mapped[int] = mapped_column(nullable=False)
    inserted_count: Mapped[int] = mapped_column(default=0, server_default=text("0"), nullable=False)
    updated_count: Mapped[int] = mapped_column(default=0, server_default=text("0"), nullable=False)
    unchanged_count: Mapped[int] = mapped_column(
        default=0, server_default=text("0"), nullable=False
    )
    rejected_count: Mapped[int] = mapped_column(default=0, server_default=text("0"), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    uploaded_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    applied_by_user_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    applied_at_utc: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    idempotency_key: Mapped[str] = mapped_column(db.Unicode(36), unique=True, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(db.Unicode(1000))
    uploaded_by: Mapped[User] = relationship(foreign_keys=[uploaded_by_user_id])
    applied_by: Mapped[User | None] = relationship(foreign_keys=[applied_by_user_id])
    rows: Mapped[list["MaterialImportRow"]] = relationship(back_populates="import_batch")


class MaterialImportRow(db.Model):
    __tablename__ = "material_import_rows"
    __table_args__ = (
        db.UniqueConstraint("import_batch_id", "row_number"),
        CheckConstraint("result IN ('INSERT', 'UPDATE', 'UNCHANGED', 'REJECTED')", name="result"),
    )
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(
        db.ForeignKey("material_import_batches.id"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(nullable=False)
    item_code_normalized: Mapped[str | None] = mapped_column(db.Unicode(50))
    category_no_normalized: Mapped[str | None] = mapped_column(db.Unicode(30))
    name_normalized: Mapped[str | None] = mapped_column(db.Unicode(200))
    result: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(db.Unicode(50))
    reason_detail: Mapped[str | None] = mapped_column(db.Unicode(500))
    import_batch: Mapped[MaterialImportBatch] = relationship(back_populates="rows")


class MaterialTagBatch(db.Model):
    __tablename__ = "material_tag_batches"
    __table_args__ = (
        CheckConstraint("total_received_weight > 0", name="total_received_weight_positive"),
        CheckConstraint("standard_container_weight > 0", name="standard_container_weight_positive"),
        CheckConstraint("tag_count BETWEEN 1 AND 200", name="tag_count_range"),
        CheckConstraint("expiry_date >= receiving_date", name="expiry_not_before_receiving"),
        Index("ix_material_tag_batches_material_receiving", "material_id", "receiving_date"),
        Index(
            "ix_material_tag_batches_code_vendor_lot",
            "material_code_snapshot",
            "vendor_lot",
        ),
        Index("ix_material_tag_batches_purchase_order", "purchase_order"),
        Index("ix_material_tag_batches_delivery_invoice", "delivery_invoice"),
        Index("ix_material_tag_batches_issued_by", "issued_by_user_id"),
    )
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(db.Unicode(40), unique=True, nullable=False)
    material_id: Mapped[int] = mapped_column(db.ForeignKey("materials.id"), nullable=False)
    material_code_snapshot: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(db.Unicode(200), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    category_no_snapshot: Mapped[str | None] = mapped_column(db.Unicode(30))
    receiving_date: Mapped[date] = mapped_column(SQL_DATE, nullable=False)
    expiry_date: Mapped[date] = mapped_column(SQL_DATE, nullable=False)
    purchase_order: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    purchase_order_line: Mapped[str] = mapped_column(db.Unicode(30), nullable=False)
    delivery_invoice: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    vendor_lot: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    supplier: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    comment: Mapped[str] = mapped_column(
        db.Unicode(200), default="", server_default=text("''"), nullable=False
    )
    warehouse: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    location: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    shelf: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    total_received_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    standard_container_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    tag_count: Mapped[int] = mapped_column(nullable=False)
    qr_payload: Mapped[str] = mapped_column(MAX_UNICODE, nullable=False)
    issued_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    issued_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    source_draft_token: Mapped[str] = mapped_column(db.Unicode(36), unique=True, nullable=False)
    material: Mapped[Material] = relationship()
    issued_by: Mapped[User] = relationship(foreign_keys=[issued_by_user_id])
    tags: Mapped[list["MaterialTag"]] = relationship(back_populates="batch")
    print_events: Mapped[list["MaterialTagPrintEvent"]] = relationship(back_populates="batch")


class MaterialTagDraft(db.Model):
    __tablename__ = "material_tag_drafts"
    __table_args__ = (
        CheckConstraint("total_received_weight > 0", name="total_received_weight_positive"),
        CheckConstraint("standard_container_weight > 0", name="standard_container_weight_positive"),
        CheckConstraint(
            "calculated_tag_count BETWEEN 1 AND 200", name="calculated_tag_count_range"
        ),
        CheckConstraint("status IN ('PREVIEWED', 'ISSUED', 'EXPIRED')", name="status"),
    )
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    draft_token: Mapped[str] = mapped_column(db.Unicode(36), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(db.Unicode(36), unique=True, nullable=False)
    material_id: Mapped[int] = mapped_column(db.ForeignKey("materials.id"), nullable=False)
    receiving_date: Mapped[date] = mapped_column(SQL_DATE, nullable=False)
    purchase_order: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    purchase_order_line: Mapped[str] = mapped_column(db.Unicode(30), nullable=False)
    material_code: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    delivery_invoice: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    vendor_lot: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    supplier: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    comment: Mapped[str] = mapped_column(
        db.Unicode(200), default="", server_default=text("''"), nullable=False
    )
    warehouse: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    location: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    shelf: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    total_received_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    standard_container_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    calculated_tag_count: Mapped[int] = mapped_column(nullable=False)
    calculated_weights_json: Mapped[str] = mapped_column(MAX_UNICODE, nullable=False)
    status: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    expires_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    issued_batch_id: Mapped[int | None] = mapped_column(db.ForeignKey("material_tag_batches.id"))
    material: Mapped[Material] = relationship()
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    issued_batch: Mapped[MaterialTagBatch | None] = relationship(foreign_keys=[issued_batch_id])


class MaterialTag(db.Model):
    __tablename__ = "material_tags"
    __table_args__ = (
        db.UniqueConstraint("batch_id", "sequence_no"),
        CheckConstraint("sequence_no > 0", name="sequence_no_positive"),
        CheckConstraint("container_weight > 0", name="container_weight_positive"),
    )
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(db.ForeignKey("material_tag_batches.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    container_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    batch: Mapped[MaterialTagBatch] = relationship(back_populates="tags")
    print_events: Mapped[list["MaterialTagPrintEvent"]] = relationship(
        back_populates="material_tag"
    )


class MaterialTagPrintEvent(db.Model):
    __tablename__ = "material_tag_print_events"
    __table_args__ = (
        CheckConstraint("print_scope IN ('BATCH', 'INDIVIDUAL')", name="print_scope"),
        CheckConstraint("print_type IN ('ORIGINAL', 'REPRINT')", name="print_type"),
        CheckConstraint("result IN ('RENDERED', 'FAILED')", name="result"),
        Index("ix_material_tag_print_events_batch", "batch_id", "requested_at_utc"),
        Index("ix_material_tag_print_events_tag", "material_tag_id", "requested_at_utc"),
        Index(
            "ix_material_tag_print_events_requester",
            "requested_by_user_id",
            "requested_at_utc",
        ),
    )
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(db.ForeignKey("material_tag_batches.id"), nullable=False)
    material_tag_id: Mapped[int | None] = mapped_column(db.ForeignKey("material_tags.id"))
    print_scope: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    print_type: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    result: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(db.Unicode(500))
    requested_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    requested_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    printer_name: Mapped[str | None] = mapped_column(db.Unicode(255))
    error_message: Mapped[str | None] = mapped_column(db.Unicode(1000))
    batch: Mapped[MaterialTagBatch] = relationship(back_populates="print_events")
    material_tag: Mapped[MaterialTag | None] = relationship(back_populates="print_events")
    requested_by: Mapped[User] = relationship(foreign_keys=[requested_by_user_id])


class RawMaterialLot(db.Model):
    __tablename__ = "raw_material_lots"
    __table_args__ = (
        db.UniqueConstraint("material_id", "lot_no"),
        CheckConstraint("qc_status IN ('PASS', 'HOLD', 'REJECT')", name="qc_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(db.ForeignKey("materials.id"), nullable=False)
    lot_no: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    qc_status: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(SQL_DATE)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)
    material: Mapped[Material] = relationship()


class Product(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.Unicode(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)


class Formula(db.Model):
    __tablename__ = "formulas"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.Unicode(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(200), nullable=False)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id"), nullable=False)
    production_lot: Mapped[str | None] = mapped_column(db.Unicode(100))
    batch_quantity: Mapped[Decimal | None] = mapped_column(db.Numeric(18, 3))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)
    product: Mapped[Product] = relationship()
    items: Mapped[list["FormulaItem"]] = relationship(back_populates="formula")


class FormulaItem(db.Model):
    __tablename__ = "formula_items"
    __table_args__ = (
        db.UniqueConstraint("formula_id", "line_no"),
        CheckConstraint("target_weight > 0", name="target_weight_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    formula_id: Mapped[int] = mapped_column(db.ForeignKey("formulas.id"), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False)
    material_id: Mapped[int] = mapped_column(db.ForeignKey("materials.id"), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    unit: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    formula: Mapped[Formula] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()


class ProductionOrder(db.Model):
    __tablename__ = "production_orders"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'READY', 'COMPLETED', 'CANCELLED')", name="status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    po_no: Mapped[str] = mapped_column(db.Unicode(50), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id"), nullable=False)
    production_lot: Mapped[str] = mapped_column(db.Unicode(100), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(db.Numeric(18, 3))
    production_date: Mapped[date | None] = mapped_column(SQL_DATE)
    expected_finish_date: Mapped[date | None] = mapped_column(SQL_DATE)
    formula_id: Mapped[int | None] = mapped_column(db.ForeignKey("formulas.id"))
    status: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    prepared_by_user_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    prepared_at_utc: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    work_set_station_id: Mapped[int | None] = mapped_column()
    work_set_code: Mapped[str | None] = mapped_column(db.Unicode(40))
    work_set_active: Mapped[bool | None] = mapped_column(
        default=False, server_default=text("0"), nullable=True
    )
    work_set_added_at_utc: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    product: Mapped[Product] = relationship()
    formula: Mapped[Formula | None] = relationship()


class WeighingTransaction(db.Model):
    __tablename__ = "weighing_transactions"
    __table_args__ = (
        CheckConstraint("actual_weight > 0", name="actual_weight_positive"),
        CheckConstraint("status IN ('COMPLETED', 'CONSUMED', 'VOIDED')", name="status"),
        Index(
            "uq_weighing_active_formula_line",
            "production_order_id",
            "formula_item_id",
            unique=True,
            mssql_where=text("status IN ('COMPLETED', 'CONSUMED')"),
            sqlite_where=text("status IN ('COMPLETED', 'CONSUMED')"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    preweight_id: Mapped[str] = mapped_column(db.Unicode(40), unique=True, nullable=False)
    production_order_id: Mapped[int] = mapped_column(
        db.ForeignKey("production_orders.id"), nullable=False
    )
    formula_item_id: Mapped[int] = mapped_column(db.ForeignKey("formula_items.id"), nullable=False)
    raw_material_lot_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("raw_material_lots.id"), nullable=True
    )
    material_tag_raw_payload: Mapped[str | None] = mapped_column(MAX_UNICODE)
    receiving_date_snapshot: Mapped[date | None] = mapped_column(SQL_DATE)
    purchase_order_snapshot: Mapped[str | None] = mapped_column(db.Unicode(100))
    purchase_order_line_snapshot: Mapped[str | None] = mapped_column(db.Unicode(30))
    material_code_snapshot: Mapped[str | None] = mapped_column(db.Unicode(50))
    delivery_invoice_snapshot: Mapped[str | None] = mapped_column(db.Unicode(100))
    vendor_lot_snapshot: Mapped[str | None] = mapped_column(db.Unicode(100))
    supplier_snapshot: Mapped[str | None] = mapped_column(db.Unicode(100))
    comment_snapshot: Mapped[str | None] = mapped_column(db.Unicode(200))
    warehouse_snapshot: Mapped[str | None] = mapped_column(db.Unicode(50))
    location_snapshot: Mapped[str | None] = mapped_column(db.Unicode(50))
    shelf_snapshot: Mapped[str | None] = mapped_column(db.Unicode(50))
    erp_qr_payload: Mapped[str | None] = mapped_column(MAX_UNICODE)
    target_weight_snapshot: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    actual_weight: Mapped[Decimal] = mapped_column(db.Numeric(18, 3), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    station_id: Mapped[int] = mapped_column(db.ForeignKey("stations.id"), nullable=False)
    weighed_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    weighed_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    status: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    consumed_by_user_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    consumed_at_utc: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    voided_by_user_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    voided_at_utc: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    void_reason: Mapped[str | None] = mapped_column(db.Unicode(500))


class LabelPrintLog(db.Model):
    __tablename__ = "label_print_logs"
    __table_args__ = (
        CheckConstraint("print_type IN ('ORIGINAL', 'RETRY', 'REPRINT')", name="print_type"),
        CheckConstraint("result IN ('SUCCESS', 'FAILED')", name="result"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    weighing_transaction_id: Mapped[int] = mapped_column(
        db.ForeignKey("weighing_transactions.id"), nullable=False
    )
    print_type: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    result: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    printer_name: Mapped[str | None] = mapped_column(db.Unicode(255))
    printed_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    printed_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    reason: Mapped[str | None] = mapped_column(db.Unicode(500))
    error_message: Mapped[str | None] = mapped_column(db.Unicode(1000))


class VerificationLog(db.Model):
    __tablename__ = "verification_logs"
    __table_args__ = (CheckConstraint("result IN ('PASS', 'FAIL')", name="result"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    expected_production_order_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("production_orders.id")
    )
    scanned_preweight_id: Mapped[str] = mapped_column(db.Unicode(40), nullable=False)
    weighing_transaction_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("weighing_transactions.id")
    )
    result: Mapped[str] = mapped_column(db.Unicode(10), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(db.Unicode(50))
    detail: Mapped[str | None] = mapped_column(db.Unicode(500))
    verified_by_user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    verified_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BIGINT_ID, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(db.Unicode(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(db.Unicode(100))
    user_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    station_id: Mapped[int | None] = mapped_column(db.ForeignKey("stations.id"))
    occurred_at_utc: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    detail: Mapped[str | None] = mapped_column(MAX_UNICODE)


__all__ = [
    "AuditLog",
    "Formula",
    "FormulaItem",
    "LabelPrintLog",
    "Material",
    "MaterialImportBatch",
    "MaterialImportRow",
    "MaterialTag",
    "MaterialTagBatch",
    "MaterialTagDraft",
    "MaterialTagPrintEvent",
    "Product",
    "ProductionOrder",
    "RawMaterialLot",
    "Role",
    "Station",
    "User",
    "VerificationLog",
    "WeighingTransaction",
    "user_roles",
]

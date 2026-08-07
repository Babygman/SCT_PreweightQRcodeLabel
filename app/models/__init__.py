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
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.Unicode(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.Unicode(200), nullable=False)
    unit: Mapped[str] = mapped_column(db.Unicode(20), nullable=False)
    classification: Mapped[str | None] = mapped_column(
        db.Unicode(50), default="GENERAL", server_default=text("'GENERAL'"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)


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
    work_set_station_id: Mapped[int | None] = mapped_column(db.ForeignKey("stations.id"))
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

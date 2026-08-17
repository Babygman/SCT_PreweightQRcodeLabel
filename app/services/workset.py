from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, true

from app.extensions import db
from app.models import (
    AuditLog,
    Material,
    ProductionOrder,
    Station,
    User,
    WeighingTransaction,
    utcnow,
)
from app.services.preparation import PreparationResult, prepare_production_order


@dataclass(frozen=True)
class WorkSetResult:
    success: bool
    code: str
    message: str
    production_order: ProductionOrder | None = None


@dataclass(frozen=True)
class MaterialRequirementSummary:
    material: Material
    completed_count: int
    required_count: int

    @property
    def status(self):
        if self.completed_count == self.required_count:
            return "Completed"
        if self.completed_count:
            return "Partially completed"
        return "Ready to scan"


@dataclass(frozen=True)
class WorkSetOverview:
    orders: tuple[ProductionOrder, ...]
    progress: dict[int, tuple[int, int]]
    completed_count: int
    required_count: int
    materials: tuple[MaterialRequirementSummary, ...]

    @property
    def session_code(self):
        return self.orders[0].work_set_code if self.orders else None

    @property
    def is_complete(self):
        return self.required_count > 0 and self.completed_count == self.required_count


@dataclass(frozen=True)
class WorkSetCompletionResult:
    success: bool
    code: str
    message: str
    session_code: str | None = None


@dataclass(frozen=True)
class CompletedWorkSetSummary:
    session_code: str
    station: Station
    completed_at_utc: datetime
    completed_by: User
    overview: WorkSetOverview


def active_work_set_orders(station_id):
    return db.session.scalars(
        select(ProductionOrder)
        .where(
            ProductionOrder.work_set_station_id == station_id,
            ProductionOrder.work_set_active == true(),
        )
        .order_by(ProductionOrder.work_set_added_at_utc, ProductionOrder.id)
    ).all()


def work_set_overview(orders):
    orders = tuple(orders)
    if not orders:
        return WorkSetOverview((), {}, 0, 0, ())

    order_ids = [order.id for order in orders]
    completed_keys = set(
        db.session.execute(
            select(
                WeighingTransaction.production_order_id,
                WeighingTransaction.formula_item_id,
            ).where(
                WeighingTransaction.production_order_id.in_(order_ids),
                WeighingTransaction.status.in_(("COMPLETED", "CONSUMED")),
            )
        ).all()
    )
    progress = {}
    material_totals = {}
    completed_count = 0
    required_count = 0
    for order in orders:
        items = tuple(order.formula.items) if order.formula else ()
        order_completed = sum((order.id, item.id) in completed_keys for item in items)
        progress[order.id] = (order_completed, len(items))
        completed_count += order_completed
        required_count += len(items)
        for item in items:
            summary = material_totals.setdefault(
                item.material_id,
                {"material": item.material, "completed": 0, "required": 0},
            )
            summary["required"] += 1
            summary["completed"] += (order.id, item.id) in completed_keys

    materials = tuple(
        MaterialRequirementSummary(
            summary["material"], summary["completed"], summary["required"]
        )
        for summary in sorted(material_totals.values(), key=lambda value: value["material"].code)
    )
    return WorkSetOverview(
        orders, progress, completed_count, required_count, materials
    )


def active_work_set_overview(station_id):
    return work_set_overview(active_work_set_orders(station_id))


def _active_work_set_code(station_id):
    order = db.session.scalar(
        select(ProductionOrder)
        .where(
            ProductionOrder.work_set_station_id == station_id,
            ProductionOrder.work_set_active == true(),
        )
        .order_by(ProductionOrder.work_set_added_at_utc.desc(), ProductionOrder.id.desc())
    )
    return order.work_set_code if order else None


def prepare_work_set_order(po_qr, formula_qr, user_id, station_id):
    result: PreparationResult = prepare_production_order(
        po_qr, formula_qr, user_id, station_id
    )
    if not result.success:
        return WorkSetResult(False, result.code, result.message, result.production_order)

    order = result.production_order
    if order.work_set_active and order.work_set_station_id == station_id:
        return WorkSetResult(
            False,
            "DUPLICATE_PREPARATION",
            "Production Order is already included in this weighing session.",
            order,
        )
    if order.work_set_active and order.work_set_station_id != station_id:
        return WorkSetResult(
            False,
            "PO_IN_ANOTHER_WORK_SET",
            "Production Order is already included in another station's weighing session.",
            order,
        )

    now = utcnow()
    order.work_set_station_id = station_id
    order.work_set_code = _active_work_set_code(station_id) or f"WS-{station_id}-{now:%Y%m%d%H%M%S}"
    order.work_set_active = True
    order.work_set_added_at_utc = now
    db.session.commit()
    return WorkSetResult(
        True,
        "WORK_SET_ADDED",
        "Production Order and Formula matched and were added to this weighing session.",
        order,
    )


def cancel_active_work_set(station_id):
    overview = active_work_set_overview(station_id)
    if not overview.orders:
        return WorkSetCompletionResult(
            False, "SESSION_UNAVAILABLE", "No active weighing session is available."
        )
    if overview.completed_count:
        return WorkSetCompletionResult(
            False,
            "SESSION_HAS_WEIGHINGS",
            "This weighing session cannot be cancelled because weighing records already exist.",
            overview.session_code,
        )
    orders = overview.orders
    for order in orders:
        order.work_set_active = False
    db.session.commit()
    return WorkSetCompletionResult(
        True,
        "SESSION_CANCELLED",
        f"Cancelled this weighing session ({len(orders)} Production Order(s) removed). "
        "Production Order statuses and weighing records were not changed.",
        overview.session_code,
    )


def _session_orders_statement(session_code, station_id, *, lock=False):
    statement = (
        select(ProductionOrder)
        .where(
            ProductionOrder.work_set_code == session_code,
            ProductionOrder.work_set_station_id == station_id,
        )
        .order_by(ProductionOrder.work_set_added_at_utc, ProductionOrder.id)
    )
    if lock and db.session.get_bind().dialect.name == "mssql":
        statement = statement.with_hint(
            ProductionOrder, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"
        )
    return statement


def complete_work_set(session_code, user_id, station_id):
    orders = tuple(
        db.session.scalars(
            _session_orders_statement(session_code, station_id, lock=True)
        ).all()
    )
    if not orders:
        return WorkSetCompletionResult(
            False, "SESSION_UNAVAILABLE", "Weighing session is unavailable."
        )

    existing_audit = db.session.scalar(
        select(AuditLog).where(
            AuditLog.event_type == "WEIGHING_SESSION_COMPLETED",
            AuditLog.entity_type == "WorkSet",
            AuditLog.entity_id == session_code,
            AuditLog.station_id == station_id,
        )
    )
    if existing_audit is not None and all(
        order.status == "COMPLETED" and not order.work_set_active for order in orders
    ):
        return WorkSetCompletionResult(
            True,
            "ALREADY_COMPLETED",
            "This weighing session is already completed.",
            session_code,
        )
    if existing_audit is not None:
        return WorkSetCompletionResult(
            False,
            "SESSION_INVALID",
            "Weighing session completion state is inconsistent.",
            session_code,
        )
    if not all(order.status == "READY" and order.work_set_active for order in orders):
        return WorkSetCompletionResult(
            False,
            "SESSION_INVALID",
            "Only an active, ready weighing session can be completed.",
            session_code,
        )

    overview = work_set_overview(orders)
    if not overview.is_complete:
        return WorkSetCompletionResult(
            False,
            "SESSION_INCOMPLETE",
            "Complete every required weighing before completing this weighing session.",
            session_code,
        )

    completed_at = utcnow()
    for order in orders:
        order.status = "COMPLETED"
        order.work_set_active = False
    db.session.add(
        AuditLog(
            event_type="WEIGHING_SESSION_COMPLETED",
            entity_type="WorkSet",
            entity_id=session_code,
            user_id=user_id,
            station_id=station_id,
            occurred_at_utc=completed_at,
            detail=(
                f"production_orders={len(orders)}; "
                f"completed_weighings={overview.completed_count}; "
                f"required_weighings={overview.required_count}"
            ),
        )
    )
    db.session.commit()
    return WorkSetCompletionResult(
        True,
        "SESSION_COMPLETED",
        "Weighing session completed.",
        session_code,
    )


def completed_work_set_summary(session_code, station_id):
    orders = tuple(
        db.session.scalars(_session_orders_statement(session_code, station_id)).all()
    )
    if not orders or not all(
        order.status == "COMPLETED" and not order.work_set_active for order in orders
    ):
        return None
    audit = db.session.scalar(
        select(AuditLog)
        .where(
            AuditLog.event_type == "WEIGHING_SESSION_COMPLETED",
            AuditLog.entity_type == "WorkSet",
            AuditLog.entity_id == session_code,
            AuditLog.station_id == station_id,
        )
        .order_by(AuditLog.occurred_at_utc.desc(), AuditLog.id.desc())
    )
    if audit is None:
        return None
    station = db.session.get(Station, station_id)
    user = db.session.get(User, audit.user_id)
    return CompletedWorkSetSummary(
        session_code,
        station,
        audit.occurred_at_utc,
        user,
        work_set_overview(orders),
    )


def work_set_progress(order):
    items = list(order.formula.items) if order.formula else []
    completed_item_ids = set(
        db.session.scalars(
            select(WeighingTransaction.formula_item_id).where(
                WeighingTransaction.production_order_id == order.id,
                WeighingTransaction.status.in_(("COMPLETED", "CONSUMED")),
            )
        ).all()
    )
    return len(completed_item_ids), len(items)

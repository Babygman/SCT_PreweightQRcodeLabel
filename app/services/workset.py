from dataclasses import dataclass

from sqlalchemy import select, true

from app.extensions import db
from app.models import Material, ProductionOrder, WeighingTransaction, utcnow
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


def active_work_set_orders(station_id):
    return db.session.scalars(
        select(ProductionOrder)
        .where(
            ProductionOrder.work_set_station_id == station_id,
            ProductionOrder.work_set_active == true(),
        )
        .order_by(ProductionOrder.work_set_added_at_utc, ProductionOrder.id)
    ).all()


def active_work_set_overview(station_id):
    orders = tuple(active_work_set_orders(station_id))
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


def close_active_work_set(station_id):
    orders = active_work_set_orders(station_id)
    for order in orders:
        order.work_set_active = False
    db.session.commit()
    return len(orders)


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

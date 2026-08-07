from dataclasses import dataclass

from sqlalchemy import select, true

from app.extensions import db
from app.models import ProductionOrder, WeighingTransaction, utcnow
from app.services.preparation import PreparationResult, prepare_production_order


@dataclass(frozen=True)
class WorkSetResult:
    success: bool
    code: str
    message: str
    production_order: ProductionOrder | None = None


def active_work_set_orders(station_id):
    return db.session.scalars(
        select(ProductionOrder)
        .where(
            ProductionOrder.work_set_station_id == station_id,
            ProductionOrder.work_set_active == true(),
        )
        .order_by(ProductionOrder.work_set_added_at_utc, ProductionOrder.id)
    ).all()


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
            "Production Order is already in the Active Work Set.",
            order,
        )
    if order.work_set_active and order.work_set_station_id != station_id:
        return WorkSetResult(
            False,
            "PO_IN_ANOTHER_WORK_SET",
            "Production Order is already in another station's Active Work Set.",
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
        "Production Order and Formula matched and were added to the Active Work Set.",
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

from dataclasses import dataclass

from sqlalchemy import and_, select, true

from app.extensions import db
from app.models import FormulaItem, Material, ProductionOrder, WeighingTransaction
from app.services.station_capability import station_can_weigh_material
from app.services.weighing import (
    MaterialTag,
    MaterialTagError,
    WeighingResult,
    parse_material_tag,
    save_weighing,
)


@dataclass(frozen=True)
class MaterialQueueItem:
    production_order: ProductionOrder
    formula_item: FormulaItem
    transaction: WeighingTransaction | None


@dataclass(frozen=True)
class MaterialQueueResult:
    success: bool
    code: str
    message: str
    tag: MaterialTag | None = None
    material: Material | None = None
    items: tuple[MaterialQueueItem, ...] = ()

    @property
    def completed_count(self):
        return sum(item.transaction is not None for item in self.items)

    @property
    def pending_count(self):
        return sum(item.transaction is None for item in self.items)


def build_material_queue(station_id, material_tag_payload, require_pending=True):
    try:
        tag = parse_material_tag(material_tag_payload)
    except MaterialTagError as exc:
        return MaterialQueueResult(False, "INVALID_MATERIAL_TAG", str(exc))

    material = db.session.scalar(select(Material).where(Material.code == tag.material_code))
    if material is None or not material.is_active:
        return MaterialQueueResult(False, "MATERIAL_NOT_FOUND", "Material is unavailable.", tag)
    if not station_can_weigh_material(station_id, material):
        return MaterialQueueResult(
            False,
            "STATION_NOT_AUTHORIZED",
            f"UN-MATCH — Current station cannot weigh {material.code}.",
            tag,
            material,
        )

    rows = db.session.execute(
        select(ProductionOrder, FormulaItem, WeighingTransaction)
        .join(FormulaItem, FormulaItem.formula_id == ProductionOrder.formula_id)
        .outerjoin(
            WeighingTransaction,
            and_(
                WeighingTransaction.production_order_id == ProductionOrder.id,
                WeighingTransaction.formula_item_id == FormulaItem.id,
                WeighingTransaction.status.in_(("COMPLETED", "CONSUMED")),
            ),
        )
        .where(
            ProductionOrder.work_set_station_id == station_id,
            ProductionOrder.work_set_active == true(),
            ProductionOrder.status == "READY",
            FormulaItem.material_id == material.id,
        )
        .order_by(ProductionOrder.work_set_added_at_utc, ProductionOrder.id, FormulaItem.line_no)
    ).all()
    items = tuple(MaterialQueueItem(*row) for row in rows)
    if not items:
        return MaterialQueueResult(
            False,
            "MATERIAL_NOT_REQUIRED",
            "UN-MATCH — Material is not required by the Active Work Set.",
            tag,
            material,
        )
    if require_pending and all(item.transaction is not None for item in items):
        return MaterialQueueResult(
            False,
            "MATERIAL_QUEUE_COMPLETED",
            f"{material.code} queue is already completed.",
            tag,
            material,
            items,
        )
    return MaterialQueueResult(
        True,
        "MATCH",
        f"MATCH — {material.code}",
        tag,
        material,
        items,
    )


def save_material_queue_item(
    station_id,
    po_id,
    formula_item_id,
    material_tag_payload,
    actual_weight,
    user_id,
):
    queue = build_material_queue(station_id, material_tag_payload, require_pending=False)
    if not queue.success:
        return WeighingResult(False, queue.code, queue.message)
    queue_item = next(
        (
            item
            for item in queue.items
            if item.production_order.id == po_id and item.formula_item.id == formula_item_id
        ),
        None,
    )
    if queue_item is None:
        return WeighingResult(False, "QUEUE_ITEM_UNAVAILABLE", "Queue item is unavailable.")
    if queue_item.transaction is not None:
        return WeighingResult(
            False,
            "FORMULA_LINE_ALREADY_WEIGHED",
            "This Production Order material is already completed.",
            queue_item.transaction,
        )
    return save_weighing(
        po_id,
        formula_item_id,
        material_tag_payload,
        actual_weight,
        user_id,
        station_id,
    )

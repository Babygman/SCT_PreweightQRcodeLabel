from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Formula,
    FormulaItem,
    Material,
    Product,
    ProductionOrder,
    ProductionOrderProductSnapshot,
)


class MockDocumentError(ValueError):
    pass


def _weights(total, count=30):
    total = Decimal(total).quantize(Decimal("0.001"))
    base = (total / count).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
    values = [base for _ in range(count)]
    values[-1] += total - sum(values)
    return values


def _mock_materials():
    materials = []
    for number in range(1, 31):
        code = f"MOCK-RM{number:03d}"
        material = db.session.scalar(select(Material).where(Material.code == code))
        if material is None:
            material = Material(code=code, name=f"Mock Raw Material {number:02d}", unit="kg")
            db.session.add(material)
        materials.append(material)
    return materials


def create_mock_order(
    *,
    po_no,
    product_id=None,
    product_code=None,
    product_name=None,
    production_lot,
    quantity,
    formula_code,
    production_date,
    expected_finish_date,
):
    if db.session.scalar(select(ProductionOrder).where(ProductionOrder.po_no == po_no)):
        raise MockDocumentError("Production Order No. already exists.")
    if db.session.scalar(select(Formula).where(Formula.code == formula_code)):
        raise MockDocumentError("Formula Sheet No. already exists.")

    if product_id is not None:
        product = db.session.get(Product, product_id)
        if (
            product is None
            or not product.is_active
            or product.finish_goods_profile is None
            or product.finish_goods_profile.source_category_no != "F/G"
        ):
            raise MockDocumentError("Select an Active Finish Good from the approved Master.")
    else:
        product = db.session.scalar(select(Product).where(Product.code == product_code))
        if product is None:
            product = Product(code=product_code, name=product_name)
            db.session.add(product)
        elif product.name != product_name:
            raise MockDocumentError("Finished Good Item Code already exists with another name.")

    quantity = Decimal(quantity).quantize(Decimal("0.001"))
    formula = Formula(
        code=formula_code,
        name=f"Mock Formula Sheet {formula_code}",
        product=product,
        production_lot=production_lot,
        batch_quantity=quantity,
    )
    order = ProductionOrder(
        po_no=po_no,
        product=product,
        production_lot=production_lot,
        quantity=quantity,
        production_date=production_date,
        expected_finish_date=expected_finish_date,
        formula=formula,
        status="OPEN",
    )
    if product_id is not None:
        order.product_snapshot = ProductionOrderProductSnapshot(
            product_code=product.code,
            product_name=product.name,
        )
    materials = _mock_materials()
    targets = _weights(quantity)
    for index, (material, target) in enumerate(zip(materials, targets, strict=True), start=1):
        db.session.add(
            FormulaItem(
                formula=formula,
                line_no=index * 10,
                material=material,
                target_weight=target,
                unit="kg",
            )
        )
    db.session.add(order)
    db.session.commit()
    return order

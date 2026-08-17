"""Prepare the approved disposable master-detail UAT dataset and QR artifacts."""

import base64
import html
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import qrcode
from sqlalchemy import select, true

from app.extensions import db
from app.models import Formula, FormulaItem, Material, Product, ProductionOrder, Station, User
from app.services.weighing import parse_material_tag
from app.services.workset import prepare_work_set_order

PO_CODES = ("UAT-MD-PD001", "UAT-MD-PD002")
PRODUCT_CODES = ("UAT-MD-FG001", "UAT-MD-FG002")
FORMULA_CODES = ("UAT-MD-FM001", "UAT-MD-FM002")
LOTS = ("UAT-MD-L001", "UAT-MD-L002")
MATERIAL_CODES = tuple(f"UAT-MD-RM{number:03d}" for number in range(1, 11))
TARGETS = tuple(Decimal(f"{number / 10:.3f}") for number in range(1, 11))


class UatMasterDetailError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedMasterDetailUat:
    work_set_code: str
    orders: tuple[ProductionOrder, ...]


def material_tag_payload(number):
    return (
        f"17/08/2026|UAT-MD-PO|{number * 10}|UAT-MD-RM{number:03d}|"
        f"UAT-MD-DN{number:03d}|UAT-MD-CONTAINER{number:03d}|UAT-MD-SUPPLIER|"
        f"UAT MASTER DETAIL ONLY|UAT-WH|UAT-LOC{number:03d}|UAT-SHELF{number:03d}"
    )


def _existing_named(model, attribute, values):
    return tuple(db.session.scalars(select(model).where(attribute.in_(values))).all())


def active_other_work_set_statement(station_id):
    return select(ProductionOrder).where(
        ProductionOrder.work_set_station_id == station_id,
        ProductionOrder.work_set_active == true(),
        ProductionOrder.po_no.not_in(PO_CODES),
    )


def _validate_existing_orders(orders, station):
    if len(orders) != 2:
        raise UatMasterDetailError("Named UAT dataset is incomplete; refusing automatic repair.")
    codes = {order.work_set_code for order in orders}
    if len(codes) != 1 or None in codes:
        raise UatMasterDetailError("Named UAT Production Orders do not share one Work Set.")
    if not all(
        order.status == "READY"
        and order.work_set_active
        and order.work_set_station_id == station.id
        for order in orders
    ):
        raise UatMasterDetailError("Named UAT Work Set is not active and ready.")
    if [len(order.formula.items) for order in orders] != [10, 1]:
        raise UatMasterDetailError("Named UAT Formula Items do not match the approved design.")
    return PreparedMasterDetailUat(next(iter(codes)), tuple(orders))


def prepare_master_detail_uat(*, uat_enabled):
    if not uat_enabled:
        raise UatMasterDetailError("Master-detail UAT preparation is disabled in production.")
    station = db.session.scalar(select(Station).where(Station.code == "UAT-ST01"))
    user = db.session.scalar(select(User).where(User.username == "uat_admin"))
    if station is None or user is None:
        raise UatMasterDetailError("UAT-ST01 and uat_admin must already exist.")

    named_orders = sorted(
        _existing_named(ProductionOrder, ProductionOrder.po_no, PO_CODES),
        key=lambda order: order.po_no,
    )
    active_other = db.session.scalars(active_other_work_set_statement(station.id)).all()
    if active_other:
        raise UatMasterDetailError("UAT-ST01 already has another active Work Set.")
    if named_orders:
        return _validate_existing_orders(named_orders, station)

    if any(
        (
            _existing_named(Product, Product.code, PRODUCT_CODES),
            _existing_named(Formula, Formula.code, FORMULA_CODES),
        )
    ):
        raise UatMasterDetailError("Named UAT master data already exists without its orders.")

    materials = []
    for number, code in enumerate(MATERIAL_CODES, start=1):
        material = db.session.scalar(select(Material).where(Material.code == code))
        expected_name = f"UAT Master Detail Material {number:02d}"
        if material is None:
            material = Material(code=code, name=expected_name, unit="kg", classification="GENERAL")
            db.session.add(material)
        elif material.name != expected_name or material.unit != "kg" or not material.is_active:
            raise UatMasterDetailError(f"Existing Material {code} conflicts with UAT design.")
        materials.append(material)

    products = [
        Product(code=code, name=f"UAT Master Detail Product {number:02d}")
        for number, code in enumerate(PRODUCT_CODES, start=1)
    ]
    formulas = [
        Formula(
            code=FORMULA_CODES[index],
            name=f"UAT Master Detail Formula {index + 1:02d}",
            product=products[index],
            production_lot=LOTS[index],
            batch_quantity=sum(TARGETS) if index == 0 else Decimal("0.150"),
        )
        for index in range(2)
    ]
    for number, (material, target) in enumerate(zip(materials, TARGETS, strict=True), start=1):
        db.session.add(
            FormulaItem(
                formula=formulas[0],
                line_no=number * 10,
                material=material,
                target_weight=target,
                unit="kg",
            )
        )
    db.session.add(
        FormulaItem(
            formula=formulas[1],
            line_no=10,
            material=materials[0],
            target_weight=Decimal("0.150"),
            unit="kg",
        )
    )
    orders = [
        ProductionOrder(
            po_no=PO_CODES[index],
            product=products[index],
            production_lot=LOTS[index],
            quantity=formulas[index].batch_quantity,
            production_date=date(2026, 8, 17),
            expected_finish_date=date(2026, 8, 18),
            formula=formulas[index],
            status="OPEN",
        )
        for index in range(2)
    ]
    db.session.add_all([*products, *formulas, *orders])
    db.session.commit()
    for order in orders:
        result = prepare_work_set_order(order.po_no, order.formula.code, user.id, station.id)
        if not result.success:
            raise UatMasterDetailError(result.message)
    return _validate_existing_orders(orders, station)


def _png(payload):
    stream = BytesIO()
    qrcode.make(payload).convert("RGB").save(stream, format="PNG")
    return stream.getvalue()


def _image_html(payload, filename, output):
    image = _png(payload)
    (output / filename).write_bytes(image)
    return base64.b64encode(image).decode("ascii")


def generate_master_detail_artifacts(output_directory, *, uat_enabled):
    if not uat_enabled:
        raise UatMasterDetailError("Master-detail UAT artifacts are disabled in production.")
    output = Path(output_directory)
    material_dir = output / "material-tags"
    document_dir = output / "documents"
    material_dir.mkdir(parents=True, exist_ok=True)
    document_dir.mkdir(parents=True, exist_ok=True)
    cards = []
    for number, code in enumerate(MATERIAL_CODES, start=1):
        payload = material_tag_payload(number)
        parsed = parse_material_tag(payload)
        if parsed.material_code != code:
            raise UatMasterDetailError(f"Material Tag payload mismatch for {code}.")
        image = _image_html(payload, f"{code}.png", material_dir)
        cards.append(
            f"<article><h2>UAT ONLY — {code}</h2><p>UAT Master Detail Material {number:02d}</p>"
            f'<img src="data:image/png;base64,{image}" alt="QR for {code}">'
            f'<p class="payload">{html.escape(payload)}</p></article>'
        )
    material_sheet = (
        """<!doctype html><html><head><meta charset="utf-8">
        <title>Master-detail UAT Material Tags</title><style>
        @page{size:A4;margin:10mm}body{font-family:Arial}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
        article{border:1px solid #777;padding:10px;break-inside:avoid}
        img{width:180px}.payload{font:10px monospace;overflow-wrap:anywhere}
        @media(max-width:700px){.grid{grid-template-columns:1fr}}
        </style></head><body><h1>UAT ONLY — Master-detail Material Tags</h1>
        <div class="grid">"""
        + "".join(cards)
        + "</div></body></html>"
    )
    (material_dir / "index.html").write_text(material_sheet, encoding="utf-8")

    for index, po_code in enumerate(PO_CODES):
        formula_code = FORMULA_CODES[index]
        for kind, code, payload in (
            ("production-order", po_code, f"SCTPO|{po_code}"),
            ("formula-sheet", formula_code, f"SCTFS|{formula_code}"),
        ):
            filename = f"{code}-{kind}"
            image = _image_html(payload, f"{filename}.png", document_dir)
            rows = ""
            if kind == "formula-sheet":
                targets = TARGETS if index == 0 else (Decimal("0.150"),)
                rows = (
                    "<table><tr><th>Material</th><th>Target</th></tr>"
                    + "".join(
                        f"<tr><td>{MATERIAL_CODES[n]}</td><td>{target:.3f} kg</td></tr>"
                        for n, target in enumerate(targets)
                    )
                    + "</table>"
                )
            document = f"""<!doctype html><html><head><meta charset="utf-8">
            <title>{code}</title><style>@page{{size:A4;margin:12mm}}
            body{{font-family:Arial}}img{{width:220px}}table{{border-collapse:collapse}}
            td,th{{border:1px solid #777;padding:5px}}
            @media print{{button{{display:none}}}}</style></head><body>
            <button onclick="window.print()">Print A4</button>
            <h1>{kind.replace("-", " ").upper()}</h1>
            <p>MOCK ERP — DEVELOPMENT / UAT</p><p><strong>{code}</strong></p>
            <p>Production Order: {po_code} · Formula: {formula_code} ·
            Lot: {LOTS[index]}</p><img src="data:image/png;base64,{image}"
            alt="QR for {code}"><p>QR payload: {payload}</p>{rows}</body></html>"""
            (document_dir / f"{filename}.html").write_text(document, encoding="utf-8")
    return material_dir / "index.html"

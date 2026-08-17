from datetime import date
from decimal import Decimal

import click
from flask import current_app
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Formula,
    FormulaItem,
    Material,
    Product,
    ProductionOrder,
    RawMaterialLot,
    Role,
    Station,
    User,
)
from scripts.uat_master_detail import (
    UatMasterDetailError,
    generate_master_detail_artifacts,
    prepare_master_detail_uat,
)
from scripts.uat_material_tags import generate_uat_material_tag_sheet


def register_commands(app):
    app.cli.add_command(seed_uat)
    app.cli.add_command(seed_stage3)
    app.cli.add_command(generate_uat_material_tags)
    app.cli.add_command(prepare_master_detail_workspace)


@click.command("prepare-uat-master-detail")
@click.option(
    "--output-directory",
    type=click.Path(file_okay=False, path_type=str),
    default="instance/uat_master_detail",
)
def prepare_master_detail_workspace(output_directory):
    """Prepare the controlled disposable master-detail UAT Work Set."""
    enabled = bool(current_app.config.get("UAT_AUTO_LOGIN"))
    try:
        prepared = prepare_master_detail_uat(uat_enabled=enabled)
        sheet = generate_master_detail_artifacts(output_directory, uat_enabled=enabled)
    except UatMasterDetailError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Master-detail UAT Work Set ready: {prepared.work_set_code}")
    click.echo(f"Material Tag sheet: {sheet.resolve()}")


@click.command("generate-uat-material-tags")
@click.option(
    "--output-directory",
    type=click.Path(file_okay=False, path_type=str),
    default="instance/uat_material_tags",
)
def generate_uat_material_tags(output_directory):
    """Generate an isolated screen/print sheet for approved UAT scans."""
    try:
        sheet_path = generate_uat_material_tag_sheet(
            output_directory,
            uat_enabled=bool(current_app.config.get("UAT_AUTO_LOGIN")),
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"UAT Material Tag sheet generated at {sheet_path.resolve()}")


@click.command("seed-uat")
def seed_uat():
    """Load clearly marked development/UAT records into an empty database."""
    if User.query.first() is not None:
        raise click.ClickException("Seed stopped: users already exist")

    roles = {
        code: Role(code=code, name=name)
        for code, name in (
            ("OPERATOR", "Operator"),
            ("PRODUCTION", "Production"),
            ("SUPERVISOR", "Supervisor"),
            ("ADMIN", "Administrator"),
        )
    }
    users = []
    for code in roles:
        username = f"uat_{code.lower()}"
        users.append(
            User(
                username=username,
                password_hash=generate_password_hash(f"Uat-{code}-Only!"),
                display_name=f"UAT {roles[code].name}",
                roles=[roles[code]],
            )
        )

    stations = [
        Station(code="UAT-ST01", name="UAT Weighing Station 1", printer_name="UAT-PRINTER-1"),
        Station(code="UAT-ST02", name="UAT Weighing Station 2", printer_name="UAT-PRINTER-2"),
    ]
    materials = [
        Material(code="UAT-RM001", name="UAT Material A", unit="kg"),
        Material(code="UAT-RM002", name="UAT Material B", unit="kg"),
    ]
    lots = [
        RawMaterialLot(
            material=materials[0],
            lot_no="UAT-PASS-001",
            qc_status="PASS",
            expiry_date=date(2099, 12, 31),
        ),
        RawMaterialLot(
            material=materials[0],
            lot_no="UAT-HOLD-001",
            qc_status="HOLD",
            expiry_date=date(2099, 12, 31),
        ),
        RawMaterialLot(
            material=materials[0],
            lot_no="UAT-REJECT-001",
            qc_status="REJECT",
            expiry_date=date(2099, 12, 31),
        ),
        RawMaterialLot(
            material=materials[1],
            lot_no="UAT-EXPIRED-001",
            qc_status="PASS",
            expiry_date=date(2020, 1, 1),
        ),
        RawMaterialLot(
            material=materials[1],
            lot_no="UAT-PASS-002",
            qc_status="PASS",
            expiry_date=date(2099, 12, 31),
        ),
    ]
    products = [
        Product(code="UAT-FG001", name="UAT Product A"),
        Product(code="UAT-FG002", name="UAT Product B"),
    ]
    formulas = [
        Formula(code="UAT-FM001", name="UAT Formula A", product=products[0]),
        Formula(code="UAT-FM002", name="UAT Formula B", product=products[1]),
        Formula(
            code="UAT-FM-INACTIVE",
            name="UAT Inactive Formula",
            product=products[0],
            is_active=False,
        ),
    ]
    items = [
        FormulaItem(
            formula=formulas[0],
            line_no=10,
            material=materials[0],
            target_weight=Decimal("10.000"),
            unit="kg",
        ),
        FormulaItem(
            formula=formulas[0],
            line_no=20,
            material=materials[1],
            target_weight=Decimal("5.000"),
            unit="kg",
        ),
        FormulaItem(
            formula=formulas[1],
            line_no=10,
            material=materials[0],
            target_weight=Decimal("8.000"),
            unit="kg",
        ),
    ]
    orders = [
        ProductionOrder(
            po_no="UAT-PO001", product=products[0], production_lot="UAT-LOT-A1", status="OPEN"
        ),
        ProductionOrder(
            po_no="UAT-PO002", product=products[0], production_lot="UAT-LOT-A2", status="OPEN"
        ),
        ProductionOrder(
            po_no="UAT-PO003", product=products[1], production_lot="UAT-LOT-B1", status="OPEN"
        ),
        ProductionOrder(
            po_no="UAT-PO-CANCELLED",
            product=products[0],
            production_lot="UAT-LOT-CANCELLED",
            status="CANCELLED",
        ),
        ProductionOrder(
            po_no="UAT-PO-COMPLETED",
            product=products[0],
            production_lot="UAT-LOT-COMPLETED",
            status="COMPLETED",
        ),
    ]

    db.session.add_all(
        [
            *roles.values(),
            *users,
            *stations,
            *materials,
            *lots,
            *products,
            *formulas,
            *items,
            *orders,
        ]
    )
    db.session.commit()
    current_app.logger.info("UAT seed data loaded")
    click.echo("UAT seed data loaded. Credentials are documented in README.md.")


@click.command("seed-stage3")
def seed_stage3():
    """Add Stage 3 UAT cases to an existing Stage 1/2 UAT database."""
    product = Product.query.filter_by(code="UAT-FG001").one_or_none()
    if product is None:
        raise click.ClickException("Run seed-uat before seed-stage3")

    additions = []
    if Formula.query.filter_by(code="UAT-FM-INACTIVE").one_or_none() is None:
        additions.append(
            Formula(
                code="UAT-FM-INACTIVE",
                name="UAT Inactive Formula",
                product=product,
                is_active=False,
            )
        )
    for po_no, production_lot, status in (
        ("UAT-PO-CANCELLED", "UAT-LOT-CANCELLED", "CANCELLED"),
        ("UAT-PO-COMPLETED", "UAT-LOT-COMPLETED", "COMPLETED"),
    ):
        if ProductionOrder.query.filter_by(po_no=po_no).one_or_none() is None:
            additions.append(
                ProductionOrder(
                    po_no=po_no,
                    product=product,
                    production_lot=production_lot,
                    status=status,
                )
            )
    db.session.add_all(additions)
    db.session.commit()
    click.echo(f"Stage 3 UAT data ready ({len(additions)} record(s) added).")

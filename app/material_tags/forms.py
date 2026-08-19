import unicodedata

from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SubmitField, TextAreaField, ValidationError
from wtforms.validators import DataRequired, Length, Optional

from app.form_fields import OperatorDateField


def _trim(value):
    return value.strip() if isinstance(value, str) else value


def _no_control_characters(_form, field):
    if field.data and any(
        unicodedata.category(character).startswith("C") for character in field.data
    ):
        raise ValidationError("Reprint reason must not contain control characters.")


class MaterialTagDraftForm(FlaskForm):
    material_id = HiddenField(validators=[DataRequired()])
    receiving_date = OperatorDateField("Receiving Date", validators=[DataRequired()])
    purchase_order = StringField("Purchase Order", validators=[DataRequired(), Length(max=100)])
    purchase_order_line = StringField("PO Line", validators=[DataRequired(), Length(max=30)])
    delivery_invoice = StringField("Delivery Invoice", validators=[DataRequired(), Length(max=100)])
    vendor_lot = StringField("Vendor Lot", validators=[DataRequired(), Length(max=100)])
    supplier = StringField("Supplier", validators=[DataRequired(), Length(max=100)])
    comment = TextAreaField("Comment", validators=[Optional(), Length(max=200)])
    warehouse = StringField("Warehouse", validators=[DataRequired(), Length(max=50)])
    location = StringField("Location", validators=[DataRequired(), Length(max=50)])
    shelf = StringField("Shelf", validators=[DataRequired(), Length(max=50)])
    total_received_weight = StringField(
        "Total Received Weight", validators=[DataRequired(), Length(max=30)]
    )
    standard_container_weight = StringField(
        "Standard Weight per Container", validators=[DataRequired(), Length(max=30)]
    )
    submit = SubmitField("Create Preview")


class MaterialTagConfirmForm(FlaskForm):
    submit = SubmitField("Confirm Issuance")


class MaterialTagPrintForm(FlaskForm):
    submit = SubmitField("Print Batch")


class MaterialTagReprintForm(FlaskForm):
    reason = TextAreaField(
        "Reprint reason",
        filters=[_trim],
        validators=[DataRequired(), Length(min=10, max=500), _no_control_characters],
    )
    submit = SubmitField("Render Reprint")

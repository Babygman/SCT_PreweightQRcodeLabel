import unicodedata

from wtforms import HiddenField, StringField, SubmitField, TextAreaField, ValidationError
from wtforms.validators import DataRequired, Length, Optional

from app.form_fields import OperatorDateField
from app.forms import BilingualForm
from app.i18n import translate as t


def _trim(value):
    return value.strip() if isinstance(value, str) else value


def _no_control_characters(_form, field):
    if field.data and any(
        unicodedata.category(character).startswith("C") for character in field.data
    ):
        raise ValidationError(t("Reprint reason must not contain control characters."))


class MaterialTagDraftForm(BilingualForm):
    material_id = HiddenField(validators=[DataRequired()])
    receiving_date = OperatorDateField(t("Receiving Date"), validators=[DataRequired()])
    purchase_order = StringField(t("Purchase Order"), validators=[DataRequired(), Length(max=100)])
    purchase_order_line = StringField(t("PO Line"), validators=[DataRequired(), Length(max=30)])
    delivery_invoice = StringField(
        t("Delivery Invoice"), validators=[DataRequired(), Length(max=100)]
    )
    vendor_lot = StringField(t("Vendor Lot"), validators=[DataRequired(), Length(max=100)])
    supplier = StringField(t("Supplier"), validators=[DataRequired(), Length(max=100)])
    comment = TextAreaField(t("Comment"), validators=[Optional(), Length(max=200)])
    warehouse = StringField(t("Warehouse"), validators=[DataRequired(), Length(max=50)])
    location = StringField(t("Location"), validators=[DataRequired(), Length(max=50)])
    shelf = StringField(t("Shelf"), validators=[DataRequired(), Length(max=50)])
    total_received_weight = StringField(
        t("Total Received Weight"), validators=[DataRequired(), Length(max=30)]
    )
    standard_container_weight = StringField(
        t("Standard Weight per Container"), validators=[DataRequired(), Length(max=30)]
    )
    submit = SubmitField(t("Create Preview"))


class MaterialTagConfirmForm(BilingualForm):
    submit = SubmitField(t("Confirm Issuance"))


class MaterialTagPrintForm(BilingualForm):
    submit = SubmitField(t("Print Batch"))


class MaterialTagReprintForm(BilingualForm):
    reason = TextAreaField(
        t("Reprint reason"),
        filters=[_trim],
        validators=[DataRequired(), Length(min=10, max=500), _no_control_characters],
    )
    submit = SubmitField(t("Render Reprint"))

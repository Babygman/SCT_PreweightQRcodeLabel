from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class MaterialTagDraftForm(FlaskForm):
    material_id = HiddenField(validators=[DataRequired()])
    receiving_date = StringField("Receiving Date", validators=[DataRequired(), Length(max=10)])
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

from datetime import date

from flask_wtf import FlaskForm
from wtforms import DecimalField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError

from app.form_fields import OperatorDateField


class MockOrderForm(FlaskForm):
    po_no = StringField("Production Order No.", validators=[DataRequired(), Length(max=50)])
    product_code = StringField(
        "Finished Good Item Code", validators=[DataRequired(), Length(max=50)]
    )
    product_name = StringField("Finished Good Name", validators=[DataRequired(), Length(max=200)])
    production_lot = StringField("Production Lot No.", validators=[DataRequired(), Length(max=100)])
    quantity = DecimalField(
        "Quantity to Produce (KG)", places=3, validators=[DataRequired(), NumberRange(min=0.001)]
    )
    formula_code = StringField("Formula Sheet No.", validators=[DataRequired(), Length(max=50)])
    production_date = OperatorDateField(
        "Production Date", validators=[DataRequired()], default=date.today
    )
    expected_finish_date = OperatorDateField(
        "Expected Finish Date", validators=[DataRequired()]
    )
    submit = SubmitField("Create Mock Production Documents")

    def validate_expected_finish_date(self, field):
        if self.production_date.data and field.data < self.production_date.data:
            raise ValidationError("Expected Finish Date must be on or after Production Date.")

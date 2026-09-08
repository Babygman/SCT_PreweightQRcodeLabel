from datetime import date

from wtforms import DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from app.form_fields import OperatorDateField
from app.forms import BilingualForm
from app.i18n import translate as t


class MockOrderForm(BilingualForm):
    po_no = StringField(t("Production Order No."), validators=[DataRequired(), Length(max=50)])
    product_id = SelectField(t("Finish Good"), coerce=int, validators=[Optional()], choices=[])
    product_code = StringField(
        t("Finished Good Item Code"), validators=[Optional(), Length(max=50)]
    )
    product_name = StringField(t("Finished Good Name"), validators=[Optional(), Length(max=200)])
    production_lot = StringField(
        t("Production Lot No."), validators=[DataRequired(), Length(max=100)]
    )
    quantity = DecimalField(
        t("Quantity to Produce (KG)"), places=3, validators=[DataRequired(), NumberRange(min=0.001)]
    )
    formula_code = StringField(t("Formula Sheet No."), validators=[DataRequired(), Length(max=50)])
    production_date = OperatorDateField(
        t("Production Date"), validators=[InputRequired()], default=date.today
    )
    expected_finish_date = OperatorDateField(
        t("Expected Finish Date"), validators=[InputRequired()]
    )
    submit = SubmitField(t("Create Mock Production Documents"))

    def validate_expected_finish_date(self, field):
        if (
            isinstance(self.production_date.data, date)
            and isinstance(field.data, date)
            and field.data < self.production_date.data
        ):
            raise ValidationError(
                t("Expected Finish Date cannot be earlier than Production Date.")
            )

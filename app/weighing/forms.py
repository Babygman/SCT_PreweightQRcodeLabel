from wtforms import DecimalField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

from app.forms import BilingualForm
from app.i18n import translate as t


class WeighingForm(BilingualForm):
    material_tag = StringField(
        t("Scan Material Tag QR"), validators=[DataRequired(), Length(max=2000)]
    )
    actual_weight = DecimalField(
        t("Actual Weight"), places=3, validators=[DataRequired(), NumberRange(min=0.001)]
    )
    submit = SubmitField(t("Save Weighing"))


class MaterialQueueWeightForm(BilingualForm):
    actual_weight = DecimalField(
        t("Actual Weight"), places=3, validators=[DataRequired(), NumberRange(min=0.001)]
    )
    submit = SubmitField(t("Save Weighing"))

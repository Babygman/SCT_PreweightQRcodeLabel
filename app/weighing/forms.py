from flask_wtf import FlaskForm
from wtforms import DecimalField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class WeighingForm(FlaskForm):
    material_tag = StringField(
        "Scan Material Tag QR", validators=[DataRequired(), Length(max=2000)]
    )
    actual_weight = DecimalField(
        "Actual Weight", places=3, validators=[DataRequired(), NumberRange(min=0.001)]
    )
    submit = SubmitField("Save Weighing")

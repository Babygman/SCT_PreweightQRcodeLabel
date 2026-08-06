from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class PreparationForm(FlaskForm):
    po_no = StringField("Scan Production Order QR", validators=[DataRequired(), Length(max=120)])
    formula_code = StringField(
        "Scan Formula Sheet QR", validators=[DataRequired(), Length(max=120)]
    )
    submit = SubmitField("Validate PO + Formula Sheet")

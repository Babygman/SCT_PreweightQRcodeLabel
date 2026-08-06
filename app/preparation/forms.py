from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class PreparationForm(FlaskForm):
    po_no = StringField("Production Order", validators=[DataRequired(), Length(max=50)])
    formula_code = StringField("Formula", validators=[DataRequired(), Length(max=50)])
    submit = SubmitField("Validate and Prepare")

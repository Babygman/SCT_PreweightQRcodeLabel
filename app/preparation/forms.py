from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

from app.forms import BilingualForm
from app.i18n import translate as t


class PreparationForm(BilingualForm):
    po_no = StringField(t("Scan Production Order QR"), validators=[DataRequired(), Length(max=120)])
    formula_code = StringField(
        t("Scan Formula Sheet QR"), validators=[DataRequired(), Length(max=120)]
    )
    submit = SubmitField(t("Validate PO + Formula Sheet"))

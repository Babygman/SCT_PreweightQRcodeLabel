from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from app.forms import BilingualForm
from app.i18n import translate as t


class LoginForm(BilingualForm):
    username = StringField(t("Username"), validators=[DataRequired(), Length(max=50)])
    password = PasswordField(t("Password"), validators=[DataRequired()])
    submit = SubmitField(t("Login"))


class StationForm(BilingualForm):
    station_id = SelectField(t("Station"), coerce=int, validators=[DataRequired()])
    submit = SubmitField(t("Continue"))

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=50)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class StationForm(FlaskForm):
    station_id = SelectField("Station", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Continue")

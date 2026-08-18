from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import HiddenField, SubmitField
from wtforms.validators import UUID, DataRequired


class MaterialImportUploadForm(FlaskForm):
    workbook = FileField(
        "Material Master workbook",
        validators=[
            FileRequired(message="Select a Material Master workbook."),
            FileAllowed(["xlsx"], message="Only .xlsx workbooks are accepted."),
        ],
    )
    idempotency_key = HiddenField(validators=[DataRequired(), UUID()])
    submit = SubmitField("Validate workbook")


class MaterialImportApplyForm(FlaskForm):
    submit = SubmitField("Confirm Apply")

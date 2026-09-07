from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import HiddenField, SubmitField
from wtforms.validators import UUID, DataRequired

from app.forms import BilingualForm
from app.i18n import translate as t


class MaterialImportUploadForm(BilingualForm):
    workbook = FileField(
        t("Material Master workbook"),
        validators=[
            FileRequired(message=t("Select a Material Master workbook.")),
            FileAllowed(["xlsx"], message=t("Only .xlsx workbooks are accepted.")),
        ],
    )
    idempotency_key = HiddenField(validators=[DataRequired(), UUID()])
    submit = SubmitField(t("Validate workbook"))


class MaterialImportApplyForm(BilingualForm):
    submit = SubmitField(t("Confirm Apply"))


class FinishGoodsImportUploadForm(BilingualForm):
    workbook = FileField(
        t("Finish Goods Master workbook"),
        validators=[
            FileRequired(message=t("Select a Finish Goods Master workbook.")),
            FileAllowed(["xlsx"], message=t("Only .xlsx workbooks are accepted.")),
        ],
    )
    idempotency_key = HiddenField(validators=[DataRequired(), UUID()])
    submit = SubmitField(t("Validate workbook"))


class FinishGoodsImportApplyForm(BilingualForm):
    submit = SubmitField(t("Confirm Apply"))

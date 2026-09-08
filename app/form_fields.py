from wtforms import DateField

from app.i18n import translate as t


class OperatorDateField(DateField):
    """ISO-backed date field rendered through the shared calendar picker."""

    def process_formdata(self, valuelist):
        try:
            super().process_formdata(valuelist)
        except ValueError as exc:
            raise ValueError(t("Please select a valid date from the calendar.")) from exc

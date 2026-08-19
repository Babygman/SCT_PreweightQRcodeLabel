from datetime import date

from wtforms import StringField

from app.presentation import format_local_date, parse_user_date


class OperatorDateField(StringField):
    """Text date field with strict, locale-independent dd/mm/yyyy parsing."""

    def process_formdata(self, valuelist):
        raw = valuelist[0].strip() if valuelist else ""
        if not raw:
            self.data = None
            return
        try:
            self.data = parse_user_date(raw)
        except ValueError as exc:
            self.data = raw
            raise ValueError(str(exc)) from exc

    def _value(self):
        if type(self.data) is date:
            return format_local_date(self.data)
        return "" if self.data is None else str(self.data)

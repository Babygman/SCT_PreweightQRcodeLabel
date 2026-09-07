"""Shared bilingual WTForms behavior."""

from flask_wtf import FlaskForm

from app.i18n import message


class BilingualForm(FlaskForm):
    """Ensure built-in and custom validator errors are bilingual."""

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)
        for field in self._fields.values():
            field.errors = tuple(message(error) for error in field.errors)
        return valid

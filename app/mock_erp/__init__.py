from flask import Blueprint

bp = Blueprint("mock_erp", __name__, url_prefix="/mock-erp")

from . import routes  # noqa: E402, F401

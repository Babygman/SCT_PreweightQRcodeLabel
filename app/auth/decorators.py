from functools import wraps

from flask import abort, redirect, request, session, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Station


def station_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        station_id = session.get("station_id")
        station = db.session.get(Station, station_id) if station_id else None
        if station is None or not station.is_active:
            session.pop("station_id", None)
            return redirect(url_for("auth.select_station", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*role_codes):
    allowed = set(role_codes)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.full_path))
            if not any(role.code in allowed for role in current_user.roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator

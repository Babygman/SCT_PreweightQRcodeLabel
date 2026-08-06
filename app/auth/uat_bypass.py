from flask import current_app, redirect, request, session, url_for
from flask_login import current_user, login_user
from sqlalchemy import select, true

from app.extensions import db
from app.models import Station, User


def _active_user_statement(username):
    return select(User).where(User.username == username, User.is_active == true())


def _active_station_statement(station_code):
    return select(Station).where(Station.code == station_code, Station.is_active == true())


def register_uat_bypass(app):
    @app.before_request
    def apply_uat_context():
        if not current_app.config.get("UAT_AUTO_LOGIN", False):
            return None

        username = current_app.config["UAT_AUTO_USERNAME"]
        station_code = current_app.config["UAT_AUTO_STATION_CODE"]
        user = db.session.scalar(_active_user_statement(username))
        station = db.session.scalar(_active_station_statement(station_code))
        if user is None or station is None:
            current_app.logger.error(
                "UAT auto-login unavailable: configured user or station is missing/inactive"
            )
            return None

        if not current_user.is_authenticated or current_user.id != user.id:
            login_user(user)
        session["station_id"] = station.id

        if request.endpoint in {"auth.login", "auth.select_station"}:
            return redirect(url_for("index"))
        return None

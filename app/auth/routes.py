from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select, true
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import AuditLog, Station, User, utcnow

from .forms import LoginForm, StationForm

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _active_stations_statement():
    return select(Station).where(Station.is_active == true()).order_by(Station.code)


def _safe_next(target):
    if not target:
        return None
    host = urlparse(request.host_url)
    destination = urlparse(urljoin(request.host_url, target))
    if destination.scheme in {"http", "https"} and destination.netloc == host.netloc:
        return destination.path
    return None


def _audit(event_type, user_id=None, station_id=None, detail=None):
    audit = AuditLog(
        event_type=event_type,
        entity_type="AUTHENTICATION",
        user_id=user_id,
        station_id=station_id,
        occurred_at_utc=utcnow(),
        detail=detail,
    )
    if db.session.get_bind().dialect.name == "sqlite":
        audit.id = db.session.scalar(select(func.coalesce(func.max(AuditLog.id), 0) + 1))
    db.session.add(audit)
    db.session.commit()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.select_station"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = db.session.scalar(select(User).where(User.username == username))
        if (
            user is not None
            and user.is_active
            and check_password_hash(user.password_hash, form.password.data)
        ):
            session.clear()
            login_user(user)
            _audit("LOGIN_SUCCESS", user_id=user.id)
            return redirect(_safe_next(request.args.get("next")) or url_for("auth.select_station"))

        _audit("LOGIN_FAILED", user_id=user.id if user else None, detail="Invalid credentials")
        current_app.logger.warning("Invalid login attempt")
        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html", form=form)


@bp.route("/station", methods=["GET", "POST"])
@login_required
def select_station():
    form = StationForm()
    stations = db.session.scalars(_active_stations_statement()).all()
    form.station_id.choices = [
        (station.id, f"{station.code} — {station.name}") for station in stations
    ]

    if form.validate_on_submit():
        station = db.session.get(Station, form.station_id.data)
        if station is None or not station.is_active:
            flash("Selected station is unavailable.", "danger")
        else:
            if session.get("station_id") != station.id:
                session.pop("active_material_tag", None)
                session.pop("weighing_mode", None)
            session["station_id"] = station.id
            _audit("STATION_SELECTED", user_id=current_user.id, station_id=station.id)
            return redirect(_safe_next(request.args.get("next")) or url_for("index"))
    elif request.method == "POST":
        flash("Selected station is unavailable.", "danger")

    return render_template("auth/station.html", form=form, stations=stations)


@bp.post("/logout")
@login_required
def logout():
    user_id = current_user.id
    station_id = session.get("station_id")
    _audit("LOGOUT", user_id=user_id, station_id=station_id)
    logout_user()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))

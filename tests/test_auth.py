from werkzeug.security import generate_password_hash

from app.auth.decorators import roles_required
from app.extensions import db
from app.models import AuditLog, Role, Station, User


def create_identity(active=True, role_code="OPERATOR"):
    role = Role(code=role_code, name=role_code.title())
    user = User(
        username="tester",
        password_hash=generate_password_hash("Correct-Password!"),
        display_name="Test User",
        is_active=active,
        roles=[role],
    )
    stations = [
        Station(code="ST01", name="Active Station", is_active=True),
        Station(code="ST02", name="Inactive Station", is_active=False),
    ]
    db.session.add_all([role, user, *stations])
    db.session.commit()
    return user, stations


def login(client, password="Correct-Password!"):
    return client.post(
        "/auth/login",
        data={"username": "tester", "password": password},
        follow_redirects=False,
    )


def test_valid_login_station_context_and_logout(app, client):
    with app.app_context():
        user, stations = create_identity()
        user_id = user.id
        station_id = stations[0].id

    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/station")

    response = client.post("/auth/station", data={"station_id": station_id})
    assert response.status_code == 302
    response = client.get("/")
    assert response.status_code == 200
    assert b"Test User" in response.data
    assert b"ST01" in response.data

    response = client.post("/auth/logout")
    assert response.status_code == 302
    assert client.get("/").status_code == 302
    with app.app_context():
        assert AuditLog.query.filter_by(user_id=user_id, event_type="LOGIN_SUCCESS").count() == 1
        assert AuditLog.query.filter_by(user_id=user_id, event_type="STATION_SELECTED").count() == 1
        assert AuditLog.query.filter_by(user_id=user_id, event_type="LOGOUT").count() == 1


def test_invalid_login_uses_generic_message_and_audit(app, client):
    with app.app_context():
        create_identity()
    response = login(client, password="Wrong")
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data
    with app.app_context():
        log = AuditLog.query.filter_by(event_type="LOGIN_FAILED").one()
        assert log.detail == "Invalid credentials"


def test_inactive_user_cannot_login(app, client):
    with app.app_context():
        create_identity(active=False)
    response = login(client)
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_inactive_station_cannot_be_selected(app, client):
    with app.app_context():
        _, stations = create_identity()
        inactive_station_id = stations[1].id
    login(client)
    response = client.post("/auth/station", data={"station_id": inactive_station_id})
    assert response.status_code == 200
    assert b"Selected station is unavailable" in response.data


def test_station_is_required_for_home(app, client):
    with app.app_context():
        create_identity()
    login(client)
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/station" in response.headers["Location"]


def test_role_authorization_is_enforced_server_side(app, client):
    @app.get("/supervisor-only")
    @roles_required("SUPERVISOR")
    def supervisor_only():
        return "allowed"

    with app.app_context():
        create_identity(role_code="OPERATOR")
    login(client)
    response = client.get("/supervisor-only")
    assert response.status_code == 403


def test_external_next_url_is_not_followed(app, client):
    with app.app_context():
        create_identity()
    response = client.post(
        "/auth/login?next=https://evil.example/steal",
        data={"username": "tester", "password": "Correct-Password!"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/station")


def test_user_deactivated_after_login_loses_session_access(app, client):
    with app.app_context():
        user, _ = create_identity()
        user_id = user.id
    login(client)
    with app.app_context():
        user = db.session.get(User, user_id)
        user.is_active = False
        db.session.commit()
    response = client.get("/auth/station")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout_requires_csrf_when_protection_is_enabled(app, client):
    with app.app_context():
        user, _ = create_identity()
        user_id = user.id
    with client.session_transaction() as user_session:
        user_session["_user_id"] = str(user_id)
        user_session["_fresh"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post("/auth/logout")
    assert response.status_code == 400

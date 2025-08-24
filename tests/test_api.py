import pytest

from app import create_app, db
from app.models import Course, Grade, Student, User


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_and_login_admin(client, app):
    with app.app_context():
        u = User(username="admin", email="admin@example.com", role="admin")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()
    resp = client.post(
        "/auth/login", data={"username": "admin", "password": "secret"}, follow_redirects=True
    )
    assert resp.status_code == 200


def test_student_crud(client, app):
    create_and_login_admin(client, app)

    # Create
    r = client.post(
        "/api/students",
        json={
            "student_id": "20240001",
            "name": "Alice",
            "class_name": "Class A",
            "email": "a@example.com",
        },
    )
    assert r.status_code == 201
    sid = r.get_json()["id"]

    # List
    r = client.get("/api/students")
    assert r.status_code == 200
    data = r.get_json()
    assert any(s["id"] == sid for s in data)

    # Get detail
    r = client.get(f"/api/students/{sid}")
    assert r.status_code == 200
    assert r.get_json()["name"] == "Alice"

    # Update
    r = client.put(f"/api/students/{sid}", json={"name": "Alice Zhang"})
    assert r.status_code == 200
    r = client.get(f"/api/students/{sid}")
    assert r.get_json()["name"] == "Alice Zhang"

    # Delete
    r = client.delete(f"/api/students/{sid}")
    assert r.status_code == 200
    # Ensure deleted
    r = client.get("/api/students")
    ids = [s["id"] for s in r.get_json()]
    assert sid not in ids


def test_course_crud(client, app):
    create_and_login_admin(client, app)

    # Create
    r = client.post("/api/courses", json={"code": "C001", "name": "Math", "description": "desc"})
    assert r.status_code == 201
    cid = r.get_json()["id"]

    # List
    r = client.get("/api/courses")
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.get_json())

    # Detail
    r = client.get(f"/api/courses/{cid}")
    assert r.status_code == 200
    assert r.get_json()["name"] == "Math"

    # Update
    r = client.put(f"/api/courses/{cid}", json={"name": "Advanced Math"})
    assert r.status_code == 200
    r = client.get(f"/api/courses/{cid}")
    assert r.get_json()["name"] == "Advanced Math"

    # Delete
    r = client.delete(f"/api/courses/{cid}")
    assert r.status_code == 200


def test_grade_crud_and_analysis(client, app):
    create_and_login_admin(client, app)

    # Prepare student and course
    rs = client.post(
        "/api/students",
        json={
            "student_id": "20240002",
            "name": "Bob",
            "class_name": "Class B",
            "email": "b@example.com",
        },
    )
    rc = client.post("/api/courses", json={"code": "C100", "name": "Physics"})
    assert rs.status_code == 201 and rc.status_code == 201
    sid = rs.get_json()["id"]
    cid = rc.get_json()["id"]

    # Create grade
    rg = client.post(
        "/api/grades", json={"student_id": sid, "course_id": cid, "score": 85, "exam_type": "final"}
    )
    assert rg.status_code == 201
    gid = rg.get_json()["id"]

    # List grades
    r = client.get("/api/grades")
    assert r.status_code == 200
    assert any(g["id"] == gid for g in r.get_json())

    # Detail
    r = client.get(f"/api/grades/{gid}")
    assert r.status_code == 200
    assert r.get_json()["score"] == 85

    # Update
    r = client.put(f"/api/grades/{gid}", json={"score": 90})
    assert r.status_code == 200
    r = client.get(f"/api/grades/{gid}")
    assert r.get_json()["score"] == 90

    # Analysis: statistics
    r = client.get(f"/api/analysis/statistics?course_id={cid}")
    assert r.status_code == 200
    payload = r.get_json()
    assert "stats" in payload and "distribution" in payload
    assert payload["stats"]["count"] >= 1

    # Analysis: ranking
    r = client.get(f"/api/analysis/ranking?course_id={cid}")
    assert r.status_code == 200
    rankings = r.get_json()["rankings"]
    assert isinstance(rankings, list) and len(rankings) >= 1

    # Delete
    r = client.delete(f"/api/grades/{gid}")
    assert r.status_code == 200

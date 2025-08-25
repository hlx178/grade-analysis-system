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


def login(client, username: str, password: str):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def setup_data(app):
    with app.app_context():
        s1 = Student(student_id="S1", name="A", class_name="一班", grade_level="七年级")
        s2 = Student(student_id="S2", name="B", class_name="二班", grade_level="八年级")
        total = Course(code="TOTAL", name="总分")
        db.session.add_all([s1, s2, total])
        db.session.commit()
        db.session.add_all(
            [
                Grade(student=s1, course=total, score=200, exam_type="regular", exam_name="期末"),
                Grade(student=s2, course=total, score=300, exam_type="regular", exam_name="期末"),
            ]
        )
        db.session.commit()
        return s1, s2, total


def test_my_summary_teacher_within_scope(client, app):
    s1, s2, _total = setup_data(app)
    with app.app_context():
        t = User(
            username="t1",
            email="t1@example.com",
            role="teacher",
            allowed_grade_levels="七年级",
            allowed_class_names="一班",
        )
        t.set_password("pwd")
        db.session.add(t)
        db.session.commit()

    r = login(client, "t1", "pwd")
    assert r.status_code == 200

    # teacher views S1 (within scope)
    rv = client.get("/api/my/summary", query_string={"student_id": "S1", "subject_code": "TOTAL", "exam_name": "期末"})
    assert rv.status_code == 200
    items = rv.get_json().get("items") or []
    assert len(items) == 1 and items[0]["student_id"] == "S1"

    # teacher views S2 (out of scope)
    rv2 = client.get("/api/my/summary", query_string={"student_id": "S2", "subject_code": "TOTAL", "exam_name": "期末"})
    assert rv2.status_code == 403


def test_my_summary_student_cannot_view_others(client, app):
    s1, s2, _total = setup_data(app)
    with app.app_context():
        u = User(username="S1", email="s1@example.com", role="student")
        u.set_password("pwd")
        db.session.add(u)
        db.session.commit()

    r = login(client, "S1", "pwd")
    assert r.status_code == 200

    rv = client.get("/api/my/summary", query_string={"student_id": "S2", "subject_code": "TOTAL", "exam_name": "期末"})
    assert rv.status_code == 403


def test_my_summary_admin_can_view_any(client, app):
    s1, s2, _total = setup_data(app)
    with app.app_context():
        a = User(username="admin", email="admin@example.com", role="admin")
        a.set_password("pwd")
        db.session.add(a)
        db.session.commit()

    r = login(client, "admin", "pwd")
    assert r.status_code == 200

    rv1 = client.get("/api/my/summary", query_string={"student_id": "S1", "subject_code": "TOTAL", "exam_name": "期末"})
    assert rv1.status_code == 200
    rv2 = client.get("/api/my/summary", query_string={"student_id": "S2", "subject_code": "TOTAL", "exam_name": "期末"})
    assert rv2.status_code == 200


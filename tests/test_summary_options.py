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


def test_summary_options(client, app):
    with app.app_context():
        u = User(username="t", email="t@example.com", role="teacher")
        u.set_password("x")
        db.session.add(u)
        s = Student(student_id="S1", name="A", class_name="一班", grade_level="七年级")
        c = Course(code="TOTAL", name="总分")
        db.session.add_all([s, c])
        db.session.commit()
        db.session.add(Grade(student=s, course=c, score=100, exam_type="regular", exam_name="期末"))
        db.session.commit()
    r = client.post("/auth/login", data={"username": "t", "password": "x"}, follow_redirects=True)
    assert r.status_code == 200

    r2 = client.get("/api/summary/options")
    assert r2.status_code == 200
    data = r2.get_json()
    assert "期末" in data["exam_names"]
    assert "七年级" in data["grade_levels"]
    assert "一班" in data["class_names"]

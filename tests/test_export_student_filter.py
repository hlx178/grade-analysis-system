import io
import csv
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
                Grade(student=s1, course=total, score=200, exam_type="regular", exam_name="E1"),
                Grade(student=s2, course=total, score=300, exam_type="regular", exam_name="E1"),
            ]
        )
        db.session.commit()
        return s1, s2, total


def read_csv_bytes(b: bytes):
    s = io.StringIO(b.decode("utf-8-sig"))
    reader = csv.reader(s)
    rows = list(reader)
    return rows


def test_export_filter_by_student_as_admin(client, app):
    s1, s2, _total = setup_data(app)
    with app.app_context():
        a = User(username="admin", email="admin@example.com", role="admin")
        a.set_password("pwd")
        db.session.add(a)
        db.session.commit()
    assert login(client, "admin", "pwd").status_code == 200

    r = client.get(
        "/api/summary/export",
        query_string={"exam_name": "E1", "subject_code": "TOTAL", "student_id": "S1", "format": "csv"},
    )
    assert r.status_code == 200
    # 文件名应包含 SID 片段
    cd = r.headers.get("Content-Disposition", "")
    assert "SID-S1" in cd
    rows = read_csv_bytes(r.data)
    # header + 1 row
    assert len(rows) == 2
    assert any("S1" in c for c in rows[1])
    assert all("S2" not in c for c in rows[1])


def test_export_filter_by_student_as_teacher_within_scope(client, app):
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
    assert login(client, "t1", "pwd").status_code == 200

    r = client.get(
        "/api/summary/export",
        query_string={"exam_name": "E1", "subject_code": "TOTAL", "student_id": "S1", "format": "csv"},
    )
    assert r.status_code == 200
    rows = read_csv_bytes(r.data)
    assert len(rows) == 2
    assert any("S1" in c for c in rows[1])


def test_export_filter_by_student_as_teacher_out_of_scope_forbidden(client, app):
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
    assert login(client, "t1", "pwd").status_code == 200

    r = client.get(
        "/api/summary/export",
        query_string={"exam_name": "E1", "subject_code": "TOTAL", "student_id": "S2", "format": "csv"},
    )
    assert r.status_code == 403


def test_export_filter_by_student_as_student_only_self(client, app):
    s1, s2, _total = setup_data(app)
    with app.app_context():
        u = User(username="S1", email="s1@example.com", role="student")
        u.set_password("pwd")
        db.session.add(u)
        db.session.commit()
    assert login(client, "S1", "pwd").status_code == 200

    r = client.get(
        "/api/summary/export",
        query_string={"exam_name": "E1", "subject_code": "TOTAL", "student_id": "S2", "format": "csv"},
    )
    assert r.status_code == 403

    r2 = client.get(
        "/api/summary/export",
        query_string={"exam_name": "E1", "subject_code": "TOTAL", "student_id": "S1", "format": "csv"},
    )
    assert r2.status_code == 200
    rows = read_csv_bytes(r2.data)
    assert len(rows) == 2
    assert any("S1" in c for c in rows[1])


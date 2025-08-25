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


def setup_students_and_courses(app):
    with app.app_context():
        s1 = Student(student_id="S1", name="Alice", class_name="一班", grade_level="七年级")
        s2 = Student(student_id="S2", name="Bob", class_name="二班", grade_level="八年级")
        total = Course(code="TOTAL", name="总分")
        cn = Course(code="CN", name="语文")
        db.session.add_all([s1, s2, total, cn])
        db.session.commit()
        return s1, s2, total, cn


def test_my_summary_student_only_self_total(client, app):
    s1, s2, total, _ = setup_students_and_courses(app)
    # add TOTAL grades for two students in the same exam
    with app.app_context():
        db.session.add_all(
            [
                Grade(student=s1, course=total, score=280, exam_type="regular", exam_name="期末"),
                Grade(student=s2, course=total, score=300, exam_type="regular", exam_name="期末"),
            ]
        )
        # create user for S1 (student)
        u = User(username="S1", email="s1@example.com", role="student")
        u.set_password("pwd")
        db.session.add(u)
        db.session.commit()

    # login as S1
    r = login(client, "S1", "pwd")
    assert r.status_code == 200

    # query my summary for TOTAL
    rv = client.get("/api/my/summary", query_string={"subject_code": "TOTAL", "exam_name": "期末"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, dict)
    items = data.get("items") or []
    assert len(items) == 1
    it = items[0]
    assert it["student_id"] == "S1"
    assert it["exam_name"] == "期末"
    assert it["subject_code"] == "TOTAL"
    assert it["score"] == 280
    # ranks should be present (computed against all students before filtering)
    assert it.get("class_rank") is not None or it.get("grade_rank") is not None


def test_my_summary_multi_exams_and_ordering(client, app):
    s1, _s2, total, _ = setup_students_and_courses(app)
    with app.app_context():
        # two exams for S1
        db.session.add_all(
            [
                Grade(student=s1, course=total, score=260, exam_type="regular", exam_name="E1"),
                Grade(student=s1, course=total, score=280, exam_type="regular", exam_name="E2"),
            ]
        )
        u = User(username="S1", email="s1@example.com", role="student")
        u.set_password("pwd")
        db.session.add(u)
        db.session.commit()

    r = login(client, "S1", "pwd")
    assert r.status_code == 200

    # multiple exams via comma-separated
    rv = client.get(
        "/api/my/summary",
        query_string={"subject_code": "TOTAL", "exam_name": "E1,E2", "order_by": "score_desc"},
    )
    assert rv.status_code == 200
    items = rv.get_json().get("items") or []
    assert len(items) == 2
    # score_desc ordering
    assert items[0]["score"] >= items[1]["score"]


def test_my_summary_subject_specific_cn(client, app):
    s1, s2, _total, cn = setup_students_and_courses(app)
    with app.app_context():
        # subject CN grades
        db.session.add_all(
            [
                Grade(student=s1, course=cn, score=88, exam_type="regular", exam_name="E1"),
                Grade(student=s2, course=cn, score=77, exam_type="regular", exam_name="E1"),
            ]
        )
        u = User(username="S1", email="s1@example.com", role="student")
        u.set_password("pwd")
        db.session.add(u)
        db.session.commit()

    r = login(client, "S1", "pwd")
    assert r.status_code == 200

    rv = client.get("/api/my/summary", query_string={"subject_code": "CN", "exam_name": "E1"})
    assert rv.status_code == 200
    items = rv.get_json().get("items") or []
    assert len(items) == 1
    it = items[0]
    assert it["student_id"] == "S1"
    assert it["subject_code"] == "CN"
    assert it["score"] == 88


def test_my_summary_teacher_no_student_match_returns_empty(client, app):
    s1, _s2, total, _ = setup_students_and_courses(app)
    with app.app_context():
        db.session.add(Grade(student=s1, course=total, score=270, exam_type="regular", exam_name="期末"))
        # teacher user whose username does not correspond to any student_id
        t = User(username="teacher1", email="t@example.com", role="teacher")
        t.set_password("pwd")
        db.session.add(t)
        db.session.commit()

    r = login(client, "teacher1", "pwd")
    assert r.status_code == 200

    rv = client.get("/api/my/summary", query_string={"subject_code": "TOTAL", "exam_name": "期末"})
    assert rv.status_code == 200
    items = rv.get_json().get("items") or []
    assert items == []


import pytest

from app import create_app, db
from app.models import Course, ExamScheme, Grade, GradeBandSet, Student, User


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


def login_admin(client, app):
    with app.app_context():
        u = User(username="admin", email="admin@example.com", role="admin")
        u.set_password("secret")
        db.session.add(u)
        s = Student(student_id="S1", name="A", class_name="一班", grade_level="七年级")
        c_total = Course(code="TOTAL", name="总分")
        db.session.add_all([s, c_total])
        db.session.add(
            ExamScheme(
                exam_type="regular", subject_code="TOTAL", subject_name="总分", max_score=300
            )
        )
        db.session.commit()
        g = Grade(student=s, course=c_total, score=270, exam_type="regular", exam_name="期末")
        db.session.add(g)
        # 发布一个版本供展示
        db.session.add(
            GradeBandSet(exam_name="期末", version=1, status="published", rules_json="[]")
        )
        db.session.commit()
    r = client.post(
        "/auth/login", data={"username": "admin", "password": "secret"}, follow_redirects=True
    )
    assert r.status_code == 200


def test_summary_percentage_and_version(client, app):
    login_admin(client, app)
    r = client.get(
        "/api/summary",
        query_string={"exam_name": "期末", "subject_code": "TOTAL", "order_by": "score_desc"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["items"][0]["percentage"] == 90.0
    assert data["rule_version"] == 1

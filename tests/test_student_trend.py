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


def login(client, username, password):
    return client.post(
        "/auth/login", data={"username": username, "password": password}, follow_redirects=True
    )


def seed_student_course_grades(app, *, student_id="20240011", name="StuA", class_name="Class A", grade_level="G7", course_code="CN"):
    with app.app_context():
        # student
        s = Student(student_id=student_id, name=name, class_name=class_name, grade_level=grade_level)
        db.session.add(s)
        db.session.commit()
        sid = s.id
        # course (reuse if exists)
        c = Course.query.filter_by(code=course_code).first()
        if not c:
            c = Course(code=course_code, name=course_code)
            db.session.add(c)
            db.session.commit()
        # grades (two exams; include spring/fall forms)
        g1 = Grade(student_id=sid, course_id=c.id, score=80, exam_name="2024上 期中", exam_type="midterm")
        g2 = Grade(student_id=sid, course_id=c.id, score=90, exam_name="2024-10-01 期末", exam_type="final")
        db.session.add_all([g1, g2])
        db.session.commit()
        return sid, c.code


def create_user(app, username, role, password="secret", **extra):
    with app.app_context():
        u = User(username=username, email=f"{username}@example.com", role=role)
        u.set_password(password)
        for k, v in extra.items():
            setattr(u, k, v)
        db.session.add(u)
        db.session.commit()
        return u


def test_student_trend_admin_ok(client, app):
    # admin
    create_user(app, "admin", "admin")
    assert login(client, "admin", "secret").status_code in (200, 302)
    # seed
    sid, code = seed_student_course_grades(app, student_id="20240021", name="Alice", class_name="A1", grade_level="G7", course_code="CN")
    # call
    r = client.get(f"/api/analysis/student-trend?id={sid}&subject_code={code}")
    assert r.status_code == 200
    j = r.get_json()
    assert j["student"]["student_id"] == "20240021"
    assert j["subject_code"] == code
    assert isinstance(j.get("series"), list) and len(j["series"]) >= 2
    assert "report" in j and "summary" in j["report"]


def test_student_trend_student_self_only(client, app):
    # seed
    s1_id, code = seed_student_course_grades(app, student_id="20240031", name="Bob", class_name="B1", grade_level="G8", course_code="MA")
    s2_id, _ = seed_student_course_grades(app, student_id="20240032", name="Eve", class_name="B2", grade_level="G8", course_code="MA")
    # create student user = s1
    # 学生登录要求：若账号为学号，需携带姓名且与学生档案一致
    create_user(app, "20240031", "student")
    assert login(client, "20240031", "secret").status_code in (200, 302) or \
           client.post("/auth/login", data={"username": "20240031", "password": "secret", "name": "Bob"}, follow_redirects=True).status_code in (200, 302)
    # self ok
    r_ok = client.get(f"/api/analysis/student-trend?id={s1_id}&subject_code={code}")
    assert r_ok.status_code == 200
    # other forbidden
    r_forbid = client.get(f"/api/analysis/student-trend?id={s2_id}&subject_code={code}")
    assert r_forbid.status_code == 403


def test_student_trend_teacher_scope(client, app):
    # seed one student in A1/G7, one in C9/G9
    s_ok_id, code = seed_student_course_grades(app, student_id="20240041", name="Tom", class_name="A1", grade_level="G7", course_code="EN")
    s_no_id, _ = seed_student_course_grades(app, student_id="20240042", name="Jerry", class_name="C9", grade_level="G9", course_code="EN")
    # teacher with allowed A1 & G7
    create_user(app, "t1", "teacher", allowed_class_names="A1", allowed_grade_levels="G7")
    assert login(client, "t1", "secret").status_code in (200, 302)
    # in-scope ok
    r1 = client.get(f"/api/analysis/student-trend?id={s_ok_id}&subject_code={code}")
    assert r1.status_code == 200
    # out-of-scope forbidden
    r2 = client.get(f"/api/analysis/student-trend?id={s_no_id}&subject_code={code}")
    assert r2.status_code == 403


def test_student_trend_filters_year_and_term(client, app):
    # admin
    create_user(app, "admin", "admin")
    assert login(client, "admin", "secret").status_code in (200, 302)
    # seed
    sid, code = seed_student_course_grades(app, student_id="20240051", name="Nina", class_name="C1", grade_level="G8", course_code="SC")
    # spring only
    r = client.get(f"/api/analysis/student-trend?id={sid}&subject_code={code}&term=spring")
    assert r.status_code == 200
    j = r.get_json()
    labs = [x["exam_name"] for x in j.get("series", [])]
    assert any("上" in n or "S" in n for n in labs)
    # year window (2024)
    r2 = client.get(f"/api/analysis/student-trend?id={sid}&subject_code={code}&year_from=2024&year_to=2024")
    assert r2.status_code == 200
    j2 = r2.get_json()
    labs2 = [x["exam_name"] for x in j2.get("series", [])]
    assert all("2024" in n for n in labs2)


import pytest
from app import create_app, db
from app.models import User, Course, Grade, GradeBandRule, Student


@pytest.fixture()
def app():
    app = create_app('testing')
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
        u = User(username='admin', email='admin@example.com', role='admin')
        u.set_password('secret')
        db.session.add(u)
        # 准备课程与学生
        c = Course(code='CN', name='语文')
        s1 = Student(student_id='S1', name='A', class_name='C1')
        s2 = Student(student_id='S2', name='B', class_name='C1')
        db.session.add_all([c, s1, s2])
        db.session.commit()
    r = client.post('/auth/login', data={'username': 'admin', 'password': 'secret'}, follow_redirects=True)
    assert r.status_code == 200


def test_range_method_letter(client, app):
    login_admin(client, app)
    # 写入成绩
    with app.app_context():
        c = Course.query.filter_by(code='CN').first()
        s1 = Student.query.filter_by(student_id='S1').first()
        s2 = Student.query.filter_by(student_id='S2').first()
        db.session.add_all([
            Grade(student=s1, course=c, score=95, exam_name='期末', exam_type='regular'),
            Grade(student=s2, course=c, score=72, exam_name='期末', exam_type='regular'),
        ])
        # 设定范围法规则
        db.session.add(GradeBandRule(exam_name='期末', subject_code='CN', method='range', a_min=90, b_min=80, c_min=70, d_min=60))
        db.session.commit()
        g1 = Grade.query.filter_by(student_id=s1.id, course_id=c.id).first()
        g2 = Grade.query.filter_by(student_id=s2.id, course_id=c.id).first()
        assert g1.letter_grade == 'A'
        assert g2.letter_grade == 'C'


def test_percentile_distribution(client, app):
    login_admin(client, app)
    with app.app_context():
        c = Course.query.filter_by(code='CN').first()
        # 三个学生
        s1 = Student.query.filter_by(student_id='S1').first()
        s2 = Student.query.filter_by(student_id='S2').first()
        s3 = Student(student_id='S3', name='C', class_name='C1')
        db.session.add(s3)
        db.session.add_all([
            Grade(student=s1, course=c, score=95, exam_name='期末', exam_type='regular'),
            Grade(student=s2, course=c, score=85, exam_name='期末', exam_type='regular'),
            Grade(student=s3, course=c, score=65, exam_name='期末', exam_type='regular'),
        ])
        db.session.add(GradeBandRule(exam_name='期末', subject_code='CN', method='percentile', a_pct=34, b_pct=33, c_pct=33, d_pct=0, e_pct=0))
        db.session.commit()

    # 使用分析接口触发分布
    r = client.get('/api/analysis/statistics?course_id=1&exam_name=期末')
    assert r.status_code == 200
    dist = r.get_json()['distribution']
    # 34/33/33 约分配为 1/1/1
    assert dist['A'] + dist['B'] + dist['C'] + dist['D'] + dist['E'] == 3


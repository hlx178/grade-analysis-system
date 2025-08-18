import pytest
from app import create_app, db
from app.models import User, Student, Course, Grade


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
        # data
        s1 = Student(student_id='S1', name='A', class_name='一班', grade_level='七年级')
        s2 = Student(student_id='S2', name='B', class_name='二班', grade_level='七年级')
        s3 = Student(student_id='S3', name='C', class_name='一班', grade_level='八年级')
        c_total = Course(code='TOTAL', name='总分')
        db.session.add_all([s1,s2,s3,c_total])
        db.session.commit()
        g = [
            Grade(student=s1, course=c_total, score=280, exam_type='regular', exam_name='期末'),
            Grade(student=s2, course=c_total, score=250, exam_type='regular', exam_name='期末'),
            Grade(student=s3, course=c_total, score=300, exam_type='regular', exam_name='期末'),
        ]
        db.session.add_all(g)
        db.session.commit()
    r = client.post('/auth/login', data={'username': 'admin', 'password': 'secret'}, follow_redirects=True)
    assert r.status_code == 200


def test_summary_multi_filters(client, app):
    login_admin(client, app)
    # filter 七年级 + 一班,二班
    r = client.get('/api/summary', query_string={
        'exam_name': '期末',
        'grade_level': ['七年级'],
        'class_name': ['一班','二班'],
        'subject_code': 'TOTAL',
        'order_by': 'score_desc'
    })
    assert r.status_code == 200
    items = r.get_json()['items']
    # S1(280)、S2(250) 属于七年级；S3为八年级不在结果
    assert len(items) == 2
    assert items[0]['student_id'] == 'S1'
    assert items[1]['student_id'] == 'S2'


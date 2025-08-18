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


def setup_data(app):
    with app.app_context():
        s1 = Student(student_id='S1', name='A', class_name='一班', grade_level='七年级')
        s2 = Student(student_id='S2', name='B', class_name='二班', grade_level='八年级')
        c = Course(code='TOTAL', name='总分')
        db.session.add_all([s1,s2,c])
        db.session.commit()
        db.session.add_all([
            Grade(student=s1, course=c, score=200, exam_type='regular', exam_name='期末'),
            Grade(student=s2, course=c, score=300, exam_type='regular', exam_name='期末'),
        ])
        db.session.commit()


def test_summary_permissions(client, app):
    setup_data(app)
    # 教师仅可见七年级与一班
    with app.app_context():
        u = User(username='t', email='t@example.com', role='teacher', allowed_grade_levels='七年级', allowed_class_names='一班')
        u.set_password('x'); db.session.add(u); db.session.commit()
    r = client.post('/auth/login', data={'username': 't', 'password': 'x'}, follow_redirects=True)
    assert r.status_code == 200

    r2 = client.get('/api/summary', query_string={'exam_name':'期末','subject_code':'TOTAL'})
    assert r2.status_code == 200
    items = r2.get_json()['items']
    # 只能看到S1
    assert len(items) == 1
    assert items[0]['student_id'] == 'S1'

    # options 也应该受限
    r3 = client.get('/api/summary/options')
    data = r3.get_json()
    assert '七年级' in data['grade_levels'] and '八年级' not in data['grade_levels']
    assert '一班' in data['class_names'] and '二班' not in data['class_names']


import pytest
from app import create_app, db
from app.models import User


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


def test_perm_publish_requires_admin(client, app):
    # 未登录
    r = client.post('/api/grade-bands/sets', json={'exam_name': '期末'})
    assert r.status_code == 403 or r.status_code == 302

    # 登录教师
    with app.app_context():
        u = User(username='t1', email='t1@example.com', role='teacher')
        u.set_password('xx')
        db.session.add(u)
        db.session.commit()
    r = client.post('/auth/login', data={'username': 't1', 'password': 'xx'}, follow_redirects=True)
    assert r.status_code == 200

    r2 = client.post('/api/grade-bands/sets', json={'exam_name': '期末'})
    assert r2.status_code == 403


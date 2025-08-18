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

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def test_login_page_accessible(client):
    resp = client.get('/auth/login')
    assert resp.status_code == 200


def test_redirect_when_not_logged_in(client):
    resp = client.get('/')
    # Flask-Login redirects to login page
    assert resp.status_code in (302, 401)


def test_create_admin_and_login(client, app):
    # create user
    with app.app_context():
        u = User(username='admin', email='admin@example.com', role='admin')
        u.set_password('secret')
        db.session.add(u)
        db.session.commit()

    # login via form
    resp = client.post('/auth/login', data={'username': 'admin', 'password': 'secret'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'登录成功' in resp.data

    # dashboard accessible after login
    resp2 = client.get('/')
    assert resp2.status_code == 200


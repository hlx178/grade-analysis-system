import io
from app import create_app, db
import pytest

@pytest.fixture()
def client():
    app = create_app('testing') if 'testing' in getattr(create_app, '__code__', None).co_varnames else create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
    })
    with app.app_context():
        db.create_all()
    client = app.test_client()
    # 登录管理员
    from app.models import User
    with app.app_context():
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin', email='admin@example.com', role='admin')
            u.set_password('admin')
            db.session.add(u); db.session.commit()
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
    return client

def test_logo_upload_validation(client):
    # 非 PNG 类型
    data = {'file': (io.BytesIO(b'not png'), 'logo.jpg')}
    r = client.post('/api/config/branding/logo', data=data, content_type='multipart/form-data')
    assert r.status_code == 400
    assert 'only PNG' in (r.get_json() or {}).get('error','')
    # 超过 1MB
    big = io.BytesIO(b'\x89PNG\r\n' + b'A' * (1024*1024 + 10))
    r2 = client.post('/api/config/branding/logo', data={'file': (big, 'logo.png')}, content_type='multipart/form-data')
    assert r2.status_code == 400
    assert 'too large' in (r2.get_json() or {}).get('error','')


import io
import zipfile
from app import create_app, db
import pytest

@pytest.fixture()
def client():
    app = create_app('testing') if 'testing' in getattr(create_app, '__code__', None).co_varnames else create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SYSTEM_NAME': '成绩分析系统',
        'SYSTEM_VERSION': 'v1',
    })
    with app.app_context():
        db.create_all()
        # 创建管理员并登录
        from app.models import User
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin', email='admin@example.com', role='admin')
            u.set_password('admin')
            db.session.add(u); db.session.commit()
    c = app.test_client()
    c.post('/auth/login', data={'username':'admin','password':'admin'}, follow_redirects=True)
    return c

def test_readme_has_system_and_user(client):
    # 设置品牌
    client.put('/api/config/branding', json={'school_name': '测试学校', 'subtitle': '报告副标题'})
    r = client.get('/api/analysis/export-all')
    assert r.status_code == 200
    buf = io.BytesIO(r.data)
    with zipfile.ZipFile(buf, 'r') as zf:
        readme = zf.read('README.md').decode('utf-8', errors='ignore')
        assert '系统：成绩分析系统' in readme
        assert '版本：v1' in readme
        assert '导出用户：admin' in readme


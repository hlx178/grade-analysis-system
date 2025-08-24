import io
import os

import pytest

from app import create_app, db


@pytest.fixture()
def client(tmp_path):
    app = (
        create_app("testing")
        if "testing" in getattr(create_app, "__code__", None).co_varnames
        else create_app()
    )
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )
    with app.app_context():
        db.create_all()
        # 放一个假的 logo 文件
        static_dir = os.path.join(app.root_path, "static")
        os.makedirs(static_dir, exist_ok=True)
        with open(os.path.join(static_dir, "logo.png"), "wb") as f:
            f.write(b"\x89PNG\r\nfake")
    client = app.test_client()
    # 登录管理员
    from app.models import User

    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", email="admin@example.com", role="admin")
            u.set_password("admin")
            db.session.add(u)
            db.session.commit()
    client.post(
        "/auth/login", data={"username": "admin", "password": "admin"}, follow_redirects=True
    )
    return client


def test_delete_logo(client):
    r = client.delete("/api/config/branding/logo")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("message") == "deleted"

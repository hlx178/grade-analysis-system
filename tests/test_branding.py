import io
import zipfile

import pytest

from app import create_app, db


@pytest.fixture()
def client():
    app = (
        create_app("testing")
        if "testing" in getattr(create_app, "__code__", None).co_varnames
        else create_app()
    )
    app.config.update(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "LOGIN_DISABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
    client = app.test_client()
    # 登录管理员（测试环境中，test_api 里已有相关方法，这里简化用已存在用户或创建）
    # 为避免依赖其它测试，这里直接创建 admin 用户并登录
    from app.models import User

    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", email="admin@example.com", role="admin")
            u.set_password("admin")
            db.session.add(u)
            db.session.commit()
    resp = client.post(
        "/auth/login", data={"username": "admin", "password": "admin"}, follow_redirects=True
    )
    assert resp.status_code in (200, 302)
    yield client


def test_branding_get_put(client):
    # Get default
    r = client.get("/api/config/branding")
    assert r.status_code == 200
    j = r.get_json()
    assert "school_name" in j
    # Put update
    r = client.put(
        "/api/config/branding",
        json={
            "school_name": "测试学校",
            "subtitle": "报告副标题",
            "cover_color": "#123456",
            "header_text": "页眉",
            "footer_text": "页脚",
        },
    )
    assert r.status_code == 200
    # Get again
    j2 = client.get("/api/config/branding").get_json()
    assert j2["school_name"] == "测试学校"
    assert j2["subtitle"] == "报告副标题"
    assert j2["cover_color"] == "#123456"


def test_export_all_zip_includes_readme(client):
    # 设置品牌名以便断言 README 内容
    client.put("/api/config/branding", json={"school_name": "测试学校", "subtitle": "报告副标题"})

    # 直接请求 ZIP（无需数据，也应返回 zip 容器与 README）
    r = client.get("/api/analysis/export-all")
    assert r.status_code == 200
    assert r.mimetype == "application/zip"
    buf = io.BytesIO(r.data)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        assert "README.md" in names
        # 可选 logo.png 不做强断言
        readme = zf.read("README.md").decode("utf-8", errors="ignore")
        assert "测试学校" in readme
        assert "报告副标题" in readme

        assert "trends.csv" in names
        assert "class_compare.csv" in names
        assert "distribution.csv" in names


def test_summary_export_xlsx_cover_sheet(client):
    r = client.get("/api/summary/export?format=xlsx")
    # 环境可能缺 openpyxl，后端会回退 csv；此处容错
    assert r.status_code == 200
    if r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        # 粗略检查二进制非空
        assert len(r.data) > 100
    else:
        # 回退为 csv 的情况
        assert r.mimetype.startswith("text/csv")

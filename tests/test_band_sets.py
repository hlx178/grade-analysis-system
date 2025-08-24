import json

import pytest

from app import create_app, db
from app.models import GradeBandSet, User


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


def login_admin(client, app):
    with app.app_context():
        u = User(username="admin", email="admin@example.com", role="admin")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()
    r = client.post(
        "/auth/login", data={"username": "admin", "password": "secret"}, follow_redirects=True
    )
    assert r.status_code == 200


def test_create_publish_rollback(client, app):
    login_admin(client, app)
    # 创建草稿
    r = client.post("/api/grade-bands/sets", json={"exam_name": "期中", "note": "v1 draft"})
    assert r.status_code == 201
    draft = r.get_json()

    # 在草稿上保存规则（快照）
    items = [
        {
            "subject_code": "CN",
            "method": "range",
            "a_min": 85,
            "b_min": 70,
            "c_min": 50,
            "d_min": 30,
        },
        {
            "subject_code": "TOTAL",
            "method": "percentile",
            "a_pct": 30,
            "b_pct": 30,
            "c_pct": 20,
            "d_pct": 10,
            "e_pct": 10,
        },
    ]
    r = client.put(
        "/api/grade-bands/bulk",
        json={"exam_name": "期中", "rule_set_id": draft["id"], "items": items},
    )
    assert r.status_code == 200

    # 发布该版本
    r = client.put(f"/api/grade-bands/sets/{draft['id']}/publish")
    assert r.status_code == 200

    # 拉取活跃规则，应该能拿到两条
    r = client.get("/api/grade-bands?exam_name=期中")
    rules = r.get_json()
    assert len(rules) == 2

    # 回滚：复制为新草稿
    r = client.put(f"/api/grade-bands/sets/{draft['id']}/rollback")
    assert r.status_code == 200

    # 列表检查有>=2个版本
    r = client.get("/api/grade-bands/sets?exam_name=期中")
    assert r.status_code == 200
    sets = r.get_json()
    assert len(sets) >= 2

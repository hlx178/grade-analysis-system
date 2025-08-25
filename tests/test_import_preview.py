import io
import pytest
from app import create_app, db
from app.models import User


def make_xlsx_bytes(sheets):
    from openpyxl import Workbook
    wb = Workbook()
    # remove default sheet
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for r in rows:
            ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


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


def login(client, username: str, password: str):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def test_import_preview_and_inspect(client, app):
    with app.app_context():
        u = User(username="admin", email="a@a", role="admin")
        u.set_password("pwd")
        db.session.add(u)
        db.session.commit()
    assert login(client, "admin", "pwd").status_code == 200

    # create xlsx with one sheet
    xbytes = make_xlsx_bytes({
        "Sheet1": [["学号","姓名","班级","数学"],["S1","Alice","一班",95]]
    })
    data = {
        "file": (io.BytesIO(xbytes), "scores.xlsx")
    }
    rv = client.post("/api/import/preview", data=data, content_type='multipart/form-data')
    assert rv.status_code == 200
    j = rv.get_json()
    file_id = j["file_id"]
    assert "Sheet1" in j["sheets"]

    # inspect
    rv2 = client.post("/api/import/preview/inspect", json={"file_id": file_id, "sheet_name": "Sheet1"})
    assert rv2.status_code == 200
    j2 = rv2.get_json()
    assert j2.get("columns_normalized")
    assert j2.get("can_import") is not False


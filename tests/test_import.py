import io

import pandas as pd
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


def login_admin(client, app):
    with app.app_context():
        u = User(username='admin', email='admin@example.com', role='admin')
        u.set_password('secret')
        db.session.add(u)
        db.session.commit()
    r = client.post('/auth/login', data={'username': 'admin', 'password': 'secret'}, follow_redirects=True)
    assert r.status_code == 200


def make_excel_multiple_sheets():
    # sheet1 with required columns
    df1 = pd.DataFrame([
        {"学号": "S01", "姓名": "Tom", "班级": "Class A", "课程代码": "C01", "课程名称": "Math", "成绩": 88},
        {"学号": "S02", "姓名": "Amy", "班级": "Class A", "课程代码": "C01", "课程名称": "Math", "成绩": 92},
    ])
    df2 = pd.DataFrame([{"foo": 1}])  # irrelevant sheet
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='scores')
        df2.to_excel(writer, index=False, sheet_name='others')
    output.seek(0)
    return output


def test_preview_and_import_specific_sheet(client, app, tmp_path):
    login_admin(client, app)

    file_bytes = make_excel_multiple_sheets().read()
    data = {
        'file': (io.BytesIO(file_bytes), 'grades.xlsx')
    }
    r = client.post('/api/import/preview', data=data, content_type='multipart/form-data')
    assert r.status_code == 200
    payload = r.get_json()
    assert 'file_id' in payload and 'sheets' in payload and 'scores' in payload['sheets']

    # choose specific sheet
    r2 = client.post('/api/import/grades', json={'file_id': payload['file_id'], 'sheet_name': 'scores'})
    assert r2.status_code == 200
    result = r2.get_json()
    assert result['created'] >= 2


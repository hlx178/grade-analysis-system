import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db

app = create_app('production')

with app.app_context():
    print('DATABASE_URL =', app.config.get('SQLALCHEMY_DATABASE_URI'))
    print('REDIS_URL    =', app.config.get('REDIS_URL'))
    # DB
    try:
        from sqlalchemy import text as _text
        db.session.execute(_text('SELECT 1'))
        print('DB_OK')
    except Exception as e:
        print('DB_ERR:', repr(e))
    # Redis
    try:
        import redis
        r = redis.from_url(app.config.get('REDIS_URL'))
        r.ping()
        print('REDIS_OK')
    except Exception as e:
        print('REDIS_ERR:', repr(e))


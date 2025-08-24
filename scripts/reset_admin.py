from app import create_app, db
from app.models import User

app = create_app("production")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username="admin").first()
        if not u:
            u = User(username="admin", email="admin@example.com", role="admin")
        u.set_password("Admin123!")
        db.session.add(u)
        db.session.commit()
        print("Admin user is ready. Username: admin / Password: Admin123!")

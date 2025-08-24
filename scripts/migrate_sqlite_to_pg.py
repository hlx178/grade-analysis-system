import os
import sqlite3
import sys
from contextlib import closing

from flask import Flask

# Ensure app importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db  # type: ignore
from app.models import (
    AuditLog,
    BrandSetting,
    ClassMaster,
    Course,
    DiagnosticPreset,
    ExamScheme,
    ExportJob,
    Grade,
    GradeBandRule,
    GradeBandSet,
    GradeMaster,
    ModuleSetting,
    RolePermission,
    Student,
    User,
    UserPreference,
)


def log(msg):
    print(f"[migrate] {msg}")


def get_sqlite_path() -> str:
    p = os.environ.get("SOURCE_SQLITE")
    if p:
        return p
    # default to repo data dir
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "grade_analysis.db")
    )


def fetch_rows(conn, table: str):
    conn.row_factory = sqlite3.Row
    with closing(conn.cursor()) as cur:
        cur.execute(f"SELECT * FROM {table}")
        for row in cur.fetchall():
            yield dict(row)


def upsert(session, obj):
    session.add(obj)


def set_pg_seq(session, table: str, id_col: str = "id"):
    try:
        session.execute(
            db.text(
                "SELECT setval(pg_get_serial_sequence(:t, :c), COALESCE((SELECT MAX(id) FROM "
                + table
                + "), 1))"
            ),
            {"t": table, "c": id_col},
        )
    except Exception:
        session.rollback()


def migrate():
    app: Flask = create_app("production")
    with app.app_context():
        sqlite_path = get_sqlite_path()
        if not os.path.exists(sqlite_path):
            log(f"SQLite file not found: {sqlite_path}")
            sys.exit(1)
        log(f"Reading from SQLite: {sqlite_path}")
        log(f"Target DB: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

        # Ensure tables exist on PG
        try:
            import subprocess

            subprocess.run(["alembic", "upgrade", "head"], check=False)
        except Exception:
            db.create_all()

        with closing(sqlite3.connect(sqlite_path)) as conn:
            s = db.session

            # order matters (respect FKs)
            def copy_table(name, model, key="id", mapper=None, unique_keys=None):
                copied = 0
                skipped = 0
                unique_keys = unique_keys or []
                for r in fetch_rows(conn, name):
                    if mapper:
                        r = mapper(r)
                    # check by PK or unique keys
                    exists = None
                    if key in r and r[key] is not None:
                        exists = model.query.get(r[key])
                    if not exists:
                        for uk in unique_keys:
                            val = r.get(uk)
                            if val:
                                exists = model.query.filter(getattr(model, uk) == val).first()
                                if exists:
                                    break
                    if exists:
                        skipped += 1
                        continue
                    try:
                        obj = model()
                        for k, v in r.items():
                            if hasattr(model, k):
                                setattr(obj, k, v)
                        upsert(s, obj)
                        copied += 1
                        if copied % 100 == 0:
                            s.flush()
                    except Exception as e:
                        s.rollback()
                        log(f"{name}: row failed -> {e}")
                try:
                    s.commit()
                except Exception as e:
                    s.rollback()
                    log(f"{name}: commit failed -> {e}")
                if key == "id":
                    set_pg_seq(s, model.__tablename__)
                log(f"{name}: copied={copied}, skipped={skipped}")

            # Copy data
            copy_table("users", User, unique_keys=["username", "email"])
            copy_table("students", Student, unique_keys=["student_id", "email"])
            copy_table("courses", Course, unique_keys=["code"])
            copy_table("exam_schemes", ExamScheme)
            copy_table("user_preferences", UserPreference)
            copy_table("diagnostic_presets", DiagnosticPreset)
            copy_table("grade_band_rules", GradeBandRule)
            copy_table("grade_band_sets", GradeBandSet)
            copy_table("export_jobs", ExportJob, key="id")  # id is string
            copy_table("audit_logs", AuditLog)
            copy_table("grade_master", GradeMaster)
            copy_table("class_master", ClassMaster)
            copy_table("module_settings", ModuleSetting)
            copy_table("brand_settings", BrandSetting, key="key")
            copy_table("role_permissions", RolePermission, key="role")
            # Grades last (has FKs to students/courses)
            copy_table("grades", Grade)

        log("Migration completed.")


if __name__ == "__main__":
    migrate()

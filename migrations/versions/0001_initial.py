"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-18 00:00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="teacher"),
        sa.Column("allowed_grade_levels", sa.Text()),
        sa.Column("allowed_class_names", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("last_login", sa.DateTime()),
        sa.UniqueConstraint("username", name="uix_users_username"),
        sa.UniqueConstraint("email", name="uix_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # students
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("class_name", sa.String(length=50), nullable=False),
        sa.Column("grade_level", sa.String(length=20)),
        sa.Column("email", sa.String(length=120)),
        sa.Column("phone", sa.String(length=20)),
        sa.Column("gender", sa.String(length=10)),
        sa.Column("birth_date", sa.Date()),
        sa.Column("enrollment_date", sa.Date()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("student_id", name="uix_students_student_id"),
        sa.UniqueConstraint("email", name="uix_students_email"),
    )
    op.create_index("ix_students_student_id", "students", ["student_id"])
    op.create_index("ix_students_class_name", "students", ["class_name"])
    op.create_index("ix_students_grade_level", "students", ["grade_level"])

    # courses
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("credits", sa.Float(), server_default=sa.text("1.0")),
        sa.Column("semester", sa.String(length=20)),
        sa.Column("academic_year", sa.String(length=10)),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("code", name="uix_courses_code"),
    )
    op.create_index("ix_courses_code", "courses", ["code"])

    # exam_schemes
    op.create_table(
        "exam_schemes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_type", sa.String(length=20), nullable=False),
        sa.Column("subject_code", sa.String(length=20), nullable=False),
        sa.Column("subject_name", sa.String(length=50), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False, server_default=sa.text("100.0")),
        sa.UniqueConstraint("exam_type", "subject_code", name="uix_examtype_subject"),
    )
    op.create_index("ix_exam_schemes_exam_type", "exam_schemes", ["exam_type"])

    # user_preferences
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.UniqueConstraint("user_id", "key", name="uix_user_pref_key"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

    # diagnostic_presets
    op.create_table(
        "diagnostic_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("group_name", sa.String(length=100)),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index("ix_diagnostic_presets_user_id", "diagnostic_presets", ["user_id"])

    # grades
    op.create_table(
        "grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("exam_type", sa.String(length=20), server_default="final"),
        sa.Column("exam_name", sa.String(length=100), server_default="default"),
        sa.Column("exam_date", sa.Date()),
        sa.Column("remarks", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("idx_student_course", "grades", ["student_id", "course_id"])
    op.create_index("idx_course_exam", "grades", ["course_id", "exam_type"])
    op.create_index("idx_course_examname", "grades", ["course_id", "exam_name"])
    op.create_index("idx_course_examname_score", "grades", ["course_id", "exam_name", "score"])
    op.create_index("idx_exam_name", "grades", ["exam_name"])

    # grade_band_rules
    op.create_table(
        "grade_band_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_name", sa.String(length=100), nullable=False),
        sa.Column("subject_code", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False, server_default="range"),
        sa.Column("a_min", sa.Float()),
        sa.Column("b_min", sa.Float()),
        sa.Column("c_min", sa.Float()),
        sa.Column("d_min", sa.Float()),
        sa.Column("a_pct", sa.Float()),
        sa.Column("b_pct", sa.Float()),
        sa.Column("c_pct", sa.Float()),
        sa.Column("d_pct", sa.Float()),
        sa.Column("e_pct", sa.Float()),
        sa.UniqueConstraint("exam_name", "subject_code", name="uix_examname_subject"),
    )
    op.create_index("ix_grade_band_rules_exam_name", "grade_band_rules", ["exam_name"])
    op.create_index("ix_grade_band_rules_subject_code", "grade_band_rules", ["subject_code"])

    # grade_band_sets
    op.create_table(
        "grade_band_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("note", sa.String(length=255)),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("published_at", sa.DateTime()),
        sa.UniqueConstraint("exam_name", "version", name="uix_examname_version"),
    )
    op.create_index("ix_grade_band_sets_exam_name", "grade_band_sets", ["exam_name"])

    # export_jobs
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("params", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending"),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0")),
        sa.Column("file_path", sa.String(length=255)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
    )
    op.create_index("ix_export_jobs_user_id", "export_jobs", ["user_id"])
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(length=80)),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade() -> None:
    # drop in reverse order of dependencies
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_export_jobs_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_user_id", table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_index("ix_grade_band_sets_exam_name", table_name="grade_band_sets")
    op.drop_table("grade_band_sets")

    op.drop_index("ix_grade_band_rules_subject_code", table_name="grade_band_rules")
    op.drop_index("ix_grade_band_rules_exam_name", table_name="grade_band_rules")
    op.drop_table("grade_band_rules")

    op.drop_index("idx_exam_name", table_name="grades")
    op.drop_index("idx_course_examname_score", table_name="grades")
    op.drop_index("idx_course_examname", table_name="grades")
    op.drop_index("idx_course_exam", table_name="grades")
    op.drop_index("idx_student_course", table_name="grades")
    op.drop_table("grades")

    op.drop_index("ix_diagnostic_presets_user_id", table_name="diagnostic_presets")
    op.drop_table("diagnostic_presets")

    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")

    op.drop_index("ix_exam_schemes_exam_type", table_name="exam_schemes")
    op.drop_table("exam_schemes")

    op.drop_index("ix_courses_code", table_name="courses")
    op.drop_table("courses")

    op.drop_index("ix_students_grade_level", table_name="students")
    op.drop_index("ix_students_class_name", table_name="students")
    op.drop_index("ix_students_student_id", table_name="students")
    op.drop_table("students")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

"""add performance indexes

Revision ID: 15659fd570a5
Revises: 0001_initial
Create Date: 2025-08-25 13:17:51.863383

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '15659fd570a5'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 添加性能索引
    op.create_index('idx_grades_student_course', 'grades', ['student_id', 'course_id'])
    op.create_index('idx_grades_exam_name', 'grades', ['exam_name'])
    op.create_index('idx_grades_exam_type', 'grades', ['exam_type'])
    op.create_index('idx_grades_score', 'grades', ['score'])
    op.create_index('idx_students_student_id', 'students', ['student_id'])
    op.create_index('idx_students_class_name', 'students', ['class_name'])
    op.create_index('idx_courses_code', 'courses', ['code'])
    op.create_index('idx_exam_schemes_type_subject', 'exam_schemes', ['exam_type', 'subject_code'])

def downgrade() -> None:
    # 删除性能索引
    op.drop_index('idx_exam_schemes_type_subject', table_name='exam_schemes')
    op.drop_index('idx_courses_code', table_name='courses')
    op.drop_index('idx_students_class_name', table_name='students')
    op.drop_index('idx_students_student_id', table_name='students')
    op.drop_index('idx_grades_score', table_name='grades')
    op.drop_index('idx_grades_exam_type', table_name='grades')
    op.drop_index('idx_grades_exam_name', table_name='grades')
    op.drop_index('idx_grades_student_course', table_name='grades')


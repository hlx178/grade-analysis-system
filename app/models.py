"""
数据模型定义
"""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class ExamScheme(db.Model):
    """考试配置：按考试类型设置各学科及总分的满分"""
    __tablename__ = 'exam_schemes'

    id = db.Column(db.Integer, primary_key=True)
    exam_type = db.Column(db.String(20), nullable=False, index=True)  # 'regular' / 'mock'
    subject_code = db.Column(db.String(20), nullable=False)  # e.g., CN, MA, EN, SC, SOC, MOR, TOTAL
    subject_name = db.Column(db.String(50), nullable=False)
    max_score = db.Column(db.Float, nullable=False, default=100.0)

    __table_args__ = (
        db.UniqueConstraint('exam_type', 'subject_code', name='uix_examtype_subject'),
    )

    def __repr__(self):
        return f'<ExamScheme {self.exam_type}:{self.subject_code}={self.max_score}>'


class User(UserMixin, db.Model):
    """用户模型"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")  # admin, teacher, student
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Student(db.Model):
    """学生模型"""

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    birth_date = db.Column(db.Date)
    enrollment_date = db.Column(db.Date, default=datetime.utcnow().date())
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    grades = db.relationship(
        "Grade", backref="student", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Student {self.student_id}: {self.name}>"


class Course(db.Model):
    """课程模型"""

    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    credits = db.Column(db.Float, default=1.0)
    semester = db.Column(db.String(20))  # 学期
    academic_year = db.Column(db.String(10))  # 学年
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    grades = db.relationship(
        "Grade", backref="course", lazy="dynamic", cascade="all, delete-orphan"
    )
    teacher = db.relationship("User", backref="courses")

    def __repr__(self):
        return f"<Course {self.code}: {self.name}>"


class Grade(db.Model):
    """成绩模型"""

    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    exam_type = db.Column(db.String(20), default="final")  # midterm, final, quiz, assignment
    exam_date = db.Column(db.Date, default=datetime.utcnow().date())
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 复合索引
    __table_args__ = (
        db.Index("idx_student_course", "student_id", "course_id"),
        db.Index("idx_course_exam", "course_id", "exam_type"),
    )

    @property
    def letter_grade(self):
        """计算等级成绩"""
        if self.score >= 90:
            return "A"
        elif self.score >= 80:
            return "B"
        elif self.score >= 70:
            return "C"
        elif self.score >= 60:
            return "D"
        else:
            return "F"

    @property
    def is_pass(self):
        """是否及格"""
        return self.score >= 60

    def __repr__(self):
        return f"<Grade {self.student.name}-{self.course.name}: {self.score}>"

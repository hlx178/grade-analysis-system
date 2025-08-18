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
    exam_name = db.Column(db.String(100), default="default", index=True)  # 自定义考试名称
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
        """按规则或默认阈值计算等级"""
        # 延迟导入避免循环
        from app.utils import grade_letter_for

        subject_code = self.course.code  # e.g., CN/MA/... or TOTAL
        return grade_letter_for(
            exam_name=self.exam_name or "default",
            subject_code=subject_code,
            score=self.score,
        )

    @property
    def is_pass(self):
        """是否及格（默认60分及格）"""
        return self.score >= 60

    def __repr__(self):
        return f"<Grade {self.student.name}-{self.course.name}: {self.score}>"


class GradeBandRule(db.Model):
    """等级换算规则：按考试名称+学科配置ABCDE两种方法之一（当前活跃规则）"""

    __tablename__ = 'grade_band_rules'

    id = db.Column(db.Integer, primary_key=True)
    exam_name = db.Column(db.String(100), nullable=False, index=True)
    subject_code = db.Column(db.String(20), nullable=False, index=True)  # 学科或 TOTAL
    method = db.Column(db.String(20), nullable=False, default='range')  # 'range' or 'percentile'
    # 分数段法：设定A/B/C/D的最低分，E为其余
    a_min = db.Column(db.Float)
    b_min = db.Column(db.Float)
    c_min = db.Column(db.Float)
    d_min = db.Column(db.Float)
    # 百分比分配法：A/B/C/D/E所占百分比，合计应为100
    a_pct = db.Column(db.Float)
    b_pct = db.Column(db.Float)
    c_pct = db.Column(db.Float)
    d_pct = db.Column(db.Float)
    e_pct = db.Column(db.Float)

    __table_args__ = (
        db.UniqueConstraint('exam_name', 'subject_code', name='uix_examname_subject'),
    )

    def __repr__(self):
        return f'<GradeBandRule {self.exam_name}:{self.subject_code} {self.method}>'


class GradeBandSet(db.Model):
    """等级规则版本集（快照）。草稿/发布；发布时覆盖活跃规则。"""

    __tablename__ = 'grade_band_sets'

    id = db.Column(db.Integer, primary_key=True)
    exam_name = db.Column(db.String(100), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default='draft')  # draft/published
    note = db.Column(db.String(255))
    rules_json = db.Column(db.Text, nullable=False)  # 存放 items 的JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('exam_name', 'version', name='uix_examname_version'),
    )

    def __repr__(self):
        return f'<GradeBandSet {self.exam_name} v{self.version} {self.status}>'

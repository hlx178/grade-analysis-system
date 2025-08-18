"""
路由与API定义
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import db
from app.models import Course, Grade, Student, User
from app.utils import (
    calculate_statistics,
    get_course_statistics,
    get_grade_distribution,
    get_student_ranking,
    validate_score,
)

# 蓝图定义
main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__)
api_bp = Blueprint("api", __name__)


# 首页仪表盘
@main_bp.route("/")
@login_required
def dashboard():
    course_stats = get_course_statistics()
    return render_template("dashboard.html", course_stats=course_stats)


# 学生管理页面
@main_bp.route("/students")
@login_required
def students():
    students = Student.query.order_by(Student.class_name, Student.student_id).all()
    return render_template("students.html", students=students)


# 课程管理页面
@main_bp.route("/courses")
@login_required
def courses():
    courses = Course.query.order_by(Course.code).all()
    return render_template("courses.html", courses=courses)


# 成绩管理页面
@main_bp.route("/grades")
@login_required
def grades():
    grades = Grade.query.order_by(Grade.created_at.desc()).limit(100).all()
    return render_template("grades.html", grades=grades)


# 登录/登出
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("登录成功", "success")
            next_page = request.args.get("next") or url_for("main.dashboard")
            return redirect(next_page)
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("您已退出登录", "info")
    return redirect(url_for("auth.login"))


# API: 学生
@api_bp.route("/students", methods=["GET", "POST"])
@login_required
def api_students():
    if request.method == "POST":
        data = request.get_json() or request.form
        student = Student(
            student_id=data.get("student_id"),
            name=data.get("name"),
            class_name=data.get("class_name"),
            email=data.get("email"),
        )
        db.session.add(student)
        db.session.commit()
        return jsonify({"message": "Student created", "id": student.id}), 201
    # GET
    students = Student.query.all()
    return jsonify(
        [
            {
                "id": s.id,
                "student_id": s.student_id,
                "name": s.name,
                "class_name": s.class_name,
                "email": s.email,
            }
            for s in students
        ]
    )


@api_bp.route("/students/<int:student_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "GET":
        return jsonify(
            {
                "id": student.id,
                "student_id": student.student_id,
                "name": student.name,
                "class_name": student.class_name,
                "email": student.email,
            }
        )
    elif request.method == "PUT":
        data = request.get_json() or request.form
        student.student_id = data.get("student_id", student.student_id)
        student.name = data.get("name", student.name)
        student.class_name = data.get("class_name", student.class_name)
        student.email = data.get("email", student.email)
        db.session.commit()
        return jsonify({"message": "Student updated"})
    else:  # DELETE
        db.session.delete(student)
        db.session.commit()
        return jsonify({"message": "Student deleted"})


# API: 课程
@api_bp.route("/courses", methods=["GET", "POST"])
@login_required
def api_courses():
    if request.method == "POST":
        data = request.get_json() or request.form
        course = Course(
            code=data.get("code"), name=data.get("name"), description=data.get("description")
        )
        db.session.add(course)
        db.session.commit()
        return jsonify({"message": "Course created", "id": course.id}), 201
    # GET
    courses = Course.query.all()
    return jsonify(
        [
            {"id": c.id, "code": c.code, "name": c.name, "description": c.description}
            for c in courses
        ]
    )


@api_bp.route("/courses/<int:course_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "GET":
        return jsonify(
            {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "description": course.description,
            }
        )
    elif request.method == "PUT":
        data = request.get_json() or request.form
        course.code = data.get("code", course.code)
        course.name = data.get("name", course.name)
        course.description = data.get("description", course.description)
        db.session.commit()
        return jsonify({"message": "Course updated"})
    else:  # DELETE
        db.session.delete(course)
        db.session.commit()
        return jsonify({"message": "Course deleted"})


# API: 成绩
@api_bp.route("/grades", methods=["GET", "POST"])
@login_required
def api_grades():
    if request.method == "POST":
        data = request.get_json() or request.form
        try:
            score = float(data.get("score"))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid score"}), 400
        if not validate_score(score):
            return jsonify({"error": "Score must be between 0 and 100"}), 400
        grade = Grade(
            student_id=data.get("student_id"),
            course_id=data.get("course_id"),
            score=score,
            exam_type=data.get("exam_type", "final"),
        )
        db.session.add(grade)
        db.session.commit()
        return jsonify({"message": "Grade created", "id": grade.id}), 201
    # GET
    grades = Grade.query.all()
    return jsonify(
        [
            {
                "id": g.id,
                "student_id": g.student_id,
                "course_id": g.course_id,
                "score": g.score,
                "exam_type": g.exam_type,
                "created_at": g.created_at.isoformat(),
            }
            for g in grades
        ]
    )


@api_bp.route("/grades/<int:grade_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_grade_detail(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if request.method == "GET":
        return jsonify(
            {
                "id": grade.id,
                "student_id": grade.student_id,
                "course_id": grade.course_id,
                "score": grade.score,
                "exam_type": grade.exam_type,
                "created_at": grade.created_at.isoformat(),
            }
        )
    elif request.method == "PUT":
        data = request.get_json() or request.form
        if "score" in data and not validate_score(data["score"]):
            return jsonify({"error": "Score must be between 0 and 100"}), 400
        grade.score = data.get("score", grade.score)
        grade.exam_type = data.get("exam_type", grade.exam_type)
        db.session.commit()
        return jsonify({"message": "Grade updated"})
    else:  # DELETE
        db.session.delete(grade)
        db.session.commit()
        return jsonify({"message": "Grade deleted"})


# API: 分析
@api_bp.route("/analysis/statistics", methods=["GET"])
@login_required
def api_analysis_statistics():
    course_id = request.args.get("course_id", type=int)
    class_name = request.args.get("class_name")
    query = Grade.query
    if course_id:
        query = query.filter_by(course_id=course_id)
    if class_name:
        query = query.join(Student).filter(Student.class_name == class_name)
    grades = query.all()
    stats = calculate_statistics(grades)
    distribution = get_grade_distribution(grades)
    return jsonify({"stats": stats, "distribution": distribution})


@api_bp.route("/analysis/ranking", methods=["GET"])
@login_required
def api_analysis_ranking():
    course_id = request.args.get("course_id", type=int)
    class_name = request.args.get("class_name")
    rankings = get_student_ranking(course_id=course_id, class_name=class_name)
    return jsonify({"rankings": rankings})

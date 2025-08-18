"""
路由与API定义
"""

import os
import uuid
from io import BytesIO

import pandas as pd
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import db
from app.models import Course, Grade, Student, User, ExamScheme, GradeBandRule
from app.utils import (
    SUBJECTS,
    TOTAL_SUBJECT,
    calculate_statistics,
    ensure_default_exam_scheme,
    get_class_list,
    get_course_statistics,
    get_grade_distribution,
    get_student_ranking,
    normalize_exam_type,
    validate_score,
)

# 蓝图定义
main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__)
api_bp = Blueprint("api", __name__)
import_bp = Blueprint("importer", __name__)


# 首页仪表盘
@main_bp.route("/")
@login_required
def dashboard():
    course_stats = get_course_statistics()
    courses = Course.query.order_by(Course.code).all()
    classes = get_class_list()
    return render_template(
        "dashboard.html",
        course_stats=course_stats,
        courses=courses,
        classes=classes,
    )


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


# 导入页面
@main_bp.route("/import")
@login_required
def import_page():
    return render_template("import.html")


@main_bp.route("/exam-schemes")
@login_required
def exam_schemes_page():
    # 初始显示常规考试，若无则创建默认方案
    ensure_default_exam_scheme("regular")
    return render_template("exam_schemes.html")


@main_bp.route("/grade-bands")
@login_required
def grade_bands_page():
    courses = Course.query.order_by(Course.code).all()
    return render_template("grade_bands.html", courses=courses, subjects=SUBJECTS + [TOTAL_SUBJECT])


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
    exam_name = request.args.get("exam_name")
    subject_code = None
    if course_id:
        course = Course.query.get(course_id)
        subject_code = course.code if course else None
    distribution = get_grade_distribution(grades, exam_name=exam_name, subject_code=subject_code)
    return jsonify({"stats": stats, "distribution": distribution})


# 导入: 预览工作表列表，保存临时文件并返回 file_id
@api_bp.route("/import/preview", methods=["POST"])
@login_required
def api_import_preview():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    # 保存到上传目录
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    # 统一使用 .xlsx 扩展名
    file_path = os.path.join(upload_dir, f"{file_id}.xlsx")
    f.save(file_path)

    try:
        # 读取工作表列表
        xls = pd.ExcelFile(file_path, engine="openpyxl")
        sheets = xls.sheet_names
    except Exception as e:
        # 清理坏文件
        try:
            os.remove(file_path)
        except Exception:
            pass
        return jsonify({"error": f"Failed to read excel: {e}"}), 400

    return jsonify({"file_id": file_id, "sheets": sheets})


# 导入: 根据选择的工作表执行导入
@api_bp.route("/import/grades", methods=["POST"])
@login_required
def api_import_grades():
    data = request.get_json() or request.form
    file_id = data.get("file_id")
    sheet_name = data.get("sheet_name")
    if not file_id or not sheet_name:
        return jsonify({"error": "file_id and sheet_name are required"}), 400

    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    file_path = os.path.join(upload_dir, f"{file_id}.xlsx")
    if not os.path.exists(file_path):
        return jsonify({"error": "Uploaded file not found or expired"}), 400

    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        return jsonify({"error": f"Failed to read sheet: {e}"}), 400

    # 期望列（模板方式）：学号、姓名、班级、语文、数学、英语、科学、社会、道法，可选：考试类型
    # 兼容旧方式（含 课程代码/课程名称/成绩）
    template_cols = ["学号", "姓名", "班级", "语文", "数学", "英语", "科学", "社会", "道法"]
    legacy_required_cols = ["学号", "姓名", "班级", "课程代码", "课程名称", "成绩"]

    # 判断模板方式或旧方式
    is_template = all(col in df.columns for col in template_cols)
    if not is_template:
        # 非模板方式则要求旧字段存在
        for col in legacy_required_cols:
            if col not in df.columns:
                return jsonify({"error": f"Missing required column: {col}"}), 400

    created = 0
    updated = 0
    if is_template:
        # 处理考试类型与考试方案
        exam_type = normalize_exam_type(df.get("考试类型").iloc[0] if "考试类型" in df.columns else "regular")
        exam_name = str(df.get("考试名称").iloc[0] if "考试名称" in df.columns else "default").strip() or "default"
        ensure_default_exam_scheme(exam_type)

        # 为模板中的各学科准备/获取Course
        subject_courses = {}
        for col_name, code, name in SUBJECTS:
            course = Course.query.filter_by(code=code).first()
            if not course:
                course = Course(code=code, name=name)
                db.session.add(course)
                db.session.flush()
            subject_courses[col_name] = course

        # 逐行导入
        for _, row in df.iterrows():
            sid = str(row["学号"]).strip()
            student = Student.query.filter_by(student_id=sid).first()
            if not student:
                student = Student(
                    student_id=sid,
                    name=str(row.get("姓名") or "").strip(),
                    class_name=str(row.get("班级") or "").strip(),
                    email=None,
                )
                db.session.add(student)
                db.session.flush()

            total_score = 0.0
            for col_name, code, _ in SUBJECTS:
                val = row.get(col_name)
                try:
                    score_val = float(val) if pd.notna(val) else None
                except Exception:
                    score_val = None
                if score_val is None:
                    continue
                course = subject_courses[col_name]
                grade = Grade.query.filter_by(student_id=student.id, course_id=course.id).first()
                if not grade:
                    grade = Grade(student=student, course=course, score=score_val, exam_type=exam_type, exam_name=exam_name)
                    db.session.add(grade)
                    created += 1
                else:
                    grade.score = score_val
                    grade.exam_type = exam_type
                    updated += 1
                total_score += score_val

            # 总分作为一个虚拟课程TOTAL写入（可选）
            total_code = TOTAL_SUBJECT[1]
            total_course = Course.query.filter_by(code=total_code).first()
            if not total_course:
                total_course = Course(code=total_code, name=TOTAL_SUBJECT[2])
                db.session.add(total_course)
                db.session.flush()
            grade_total = Grade.query.filter_by(student_id=student.id, course_id=total_course.id).first()
            if not grade_total:
                grade_total = Grade(student=student, course=total_course, score=total_score, exam_type=exam_type, exam_name=exam_name)
                db.session.add(grade_total)
                created += 1
            else:
                grade_total.score = total_score
                grade_total.exam_type = exam_type
                updated += 1
    else:
        # 兼容旧方式
        for _, row in df.iterrows():
            student = Student.query.filter_by(student_id=str(row["学号"]).strip()).first()
            if not student:
                student = Student(
                    student_id=str(row["学号"]).strip(),
                    name=str(row.get("姓名") or "").strip(),
                    class_name=str(row.get("班级") or "").strip(),
                    email=None,
                )
                db.session.add(student)
                db.session.flush()

            course_code = str(row["课程代码"]).strip()
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                course = Course(code=course_code, name=str(row.get("课程名称") or "").strip())
                db.session.add(course)
                db.session.flush()

            try:
                score_val = float(row["成绩"])
            except Exception:
                score_val = None
            if score_val is None:
                continue

            exam_type = normalize_exam_type(row.get("考试类型") or "regular")
            exam_name = str(row.get("考试名称") or "default").strip() or "default"

            grade = Grade.query.filter_by(student_id=student.id, course_id=course.id).first()
            if not grade:
                grade = Grade(student=student, course=course, score=score_val, exam_type=exam_type, exam_name=exam_name)
                db.session.add(grade)
                created += 1
            else:
                grade.score = score_val
                grade.exam_type = exam_type
                updated += 1

    db.session.commit()

    # 导入完成后可清理临时文件
    try:
        os.remove(file_path)
    except Exception:
        pass

    return jsonify({"message": "Import finished", "created": created, "updated": updated})


@api_bp.route("/analysis/ranking", methods=["GET"])
@login_required
def api_analysis_ranking():
    course_id = request.args.get("course_id", type=int)
    class_name = request.args.get("class_name")
    rankings = get_student_ranking(course_id=course_id, class_name=class_name)
    return jsonify({"rankings": rankings})


# 等级规则：查询
@api_bp.route("/grade-bands", methods=["GET"])
@login_required
def api_grade_bands_get():
    exam_name = request.args.get("exam_name") or "default"
    rules = GradeBandRule.query.filter_by(exam_name=exam_name).all()
    data = []
    for r in rules:
        data.append({
            "id": r.id,
            "exam_name": r.exam_name,
            "subject_code": r.subject_code,
            "method": r.method,
            "a_min": r.a_min, "b_min": r.b_min, "c_min": r.c_min, "d_min": r.d_min,
            "a_pct": r.a_pct, "b_pct": r.b_pct, "c_pct": r.c_pct, "d_pct": r.d_pct, "e_pct": r.e_pct,
        })
    return jsonify(data)


# 等级规则：批量保存（覆盖写）
@api_bp.route("/grade-bands/bulk", methods=["PUT"])
@login_required
def api_grade_bands_bulk_put():
    payload = request.get_json(force=True)
    exam_name = payload.get("exam_name") or "default"
    items = payload.get("items") or []
    # 基本校验
    for it in items:
        method = it.get("method")
        if method == 'range':
            a = it.get("a_min"); b = it.get("b_min"); c = it.get("c_min"); d = it.get("d_min")
            # 允许缺省，缺省时沿用默认 80/60/40/20
            # 若提供了必须满足顺序
            seq = [x for x in [a,b,c,d] if x is not None]
            if len(seq) == 4 and not (a >= b >= c >= d):
                return jsonify({"error": "Range thresholds must satisfy A>=B>=C>=D"}), 400
        elif method == 'percentile':
            ap, bp, cp, dp, ep = [it.get(k) for k in ["a_pct","b_pct","c_pct","d_pct","e_pct"]]
            if None in [ap,bp,cp,dp,ep]:
                return jsonify({"error": "Percentile requires all five percentages"}), 400
            total = ap + bp + cp + dp + ep
            if round(total) != 100:
                return jsonify({"error": "Percentile sums must be 100"}), 400
        else:
            return jsonify({"error": "Unknown method"}), 400

    # 清理旧规则并写入新规则
    GradeBandRule.query.filter_by(exam_name=exam_name).delete()
    for it in items:
        rule = GradeBandRule(
            exam_name=exam_name,
            subject_code=it.get("subject_code"),
            method=it.get("method"),
            a_min=it.get("a_min"), b_min=it.get("b_min"), c_min=it.get("c_min"), d_min=it.get("d_min"),
            a_pct=it.get("a_pct"), b_pct=it.get("b_pct"), c_pct=it.get("c_pct"), d_pct=it.get("d_pct"), e_pct=it.get("e_pct"),
        )
        db.session.add(rule)
    db.session.commit()
    return jsonify({"message": "saved", "count": len(items)})


# 等级规则：预览（不落库）
@api_bp.route("/grade-bands/preview", methods=["POST"])
@login_required
def api_grade_bands_preview():
    payload = request.get_json(force=True)
    items = payload.get("items") or []
    course_id = payload.get("course_id")
    class_name = payload.get("class_name")
    # 构造一个临时的规则索引
    tmp_rules = {}
    for it in items:
        tmp_rules[(payload.get("exam_name") or "default", it.get("subject_code"))] = it

    # 准备数据集
    query = Grade.query
    if course_id:
        query = query.filter(Grade.course_id == course_id)
    if class_name:
        query = query.join(Student).filter(Student.class_name == class_name)
    grades = query.all()

    # 应用规则生成分布（仅支持range/percentile两类）
    from collections import defaultdict
    dist = defaultdict(int)
    for g in grades:
        subject_code = g.course.code
        key = (g.exam_name or 'default', subject_code)
        rule = tmp_rules.get(key)
        s = g.score
        if rule and rule.get('method') == 'range':
            a = rule.get('a_min', 80); b = rule.get('b_min', 60); c = rule.get('c_min', 40); d = rule.get('d_min', 20)
            if s >= a: dist['A'] += 1
            elif s >= b: dist['B'] += 1
            elif s >= c: dist['C'] += 1
            elif s >= d: dist['D'] += 1
            else: dist['E'] += 1
        else:
            # 对于percentile/未知：统一在前端给出说明，本接口可选择不处理或返回占位
            pass
    return jsonify({"distribution": dict(dist), "total": len(grades)})


# ExamScheme CRUD
@api_bp.route("/exam-schemes", methods=["GET", "POST"])
@login_required
def api_exam_schemes():
    if request.method == "POST":
        data = request.get_json() or request.form
        exam_type = normalize_exam_type(data.get("exam_type"))
        subject_code = data.get("subject_code")
        subject_name = data.get("subject_name")
        max_score = float(data.get("max_score", 100))
        item = ExamScheme(
            exam_type=exam_type, subject_code=subject_code, subject_name=subject_name, max_score=max_score
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({"id": item.id}), 201
    # GET
    exam_type = normalize_exam_type(request.args.get("exam_type") or "regular")
    items = ExamScheme.query.filter_by(exam_type=exam_type).all()
    return jsonify(
        [
            {
                "id": it.id,
                "exam_type": it.exam_type,
                "subject_code": it.subject_code,
                "subject_name": it.subject_name,
                "max_score": it.max_score,
            }
            for it in items
        ]
    )


@api_bp.route("/exam-schemes/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def api_exam_scheme_detail(item_id):
    item = ExamScheme.query.get_or_404(item_id)
    if request.method == "PUT":
        data = request.get_json() or request.form
        if "max_score" in data:
            item.max_score = float(data.get("max_score"))
        if "subject_name" in data:
            item.subject_name = data.get("subject_name")
        if "exam_type" in data:
            item.exam_type = normalize_exam_type(data.get("exam_type"))
        db.session.commit()
        return jsonify({"message": "updated"})
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "deleted"})

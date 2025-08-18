"""
路由与API定义
"""

import os
import uuid
import io
from io import BytesIO

import pandas as pd
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for, send_file, Response, abort, stream_with_context
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models import Course, Grade, Student, User, ExamScheme, GradeBandRule, GradeBandSet
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
    # 可选：提供已存在的考试名称列表
    exam_names = [row[0] for row in db.session.query(GradeBandRule.exam_name).distinct().all()]
    grade_levels = [row[0] for row in db.session.query(Student.grade_level).distinct().all() if row[0]]
    return render_template(
        "dashboard.html",
        course_stats=course_stats,
        courses=courses,
        classes=classes,
        exam_names=exam_names,
        grade_levels=grade_levels,
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


@main_bp.route("/summary")
@login_required
def summary_page():
    return render_template("summary.html")


@main_bp.route("/users")
@login_required
def users_page():
    if current_user.role != 'admin':
        abort(403)
    return render_template("users.html")


@main_bp.route("/diagnostics")
@login_required
def diagnostics_page():
    if current_user.role != 'admin':
        abort(403)
    return render_template("diagnostics.html")


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
    # 版本信息初步加载（默认exam_name=default）
    sets = GradeBandSet.query.filter_by(exam_name='default').order_by(GradeBandSet.version.desc()).all()
    return render_template("grade_bands.html", courses=courses, subjects=SUBJECTS + [TOTAL_SUBJECT], sets=sets)


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
    template_cols = ["学号", "姓名", "班级", "年级", "语文", "数学", "英语", "科学", "社会", "道法"]
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
                    grade_level=str(row.get("年级") or "").strip() or None,
                    email=None,
                )
                db.session.add(student)
                db.session.flush()
            else:
                # 更新年级信息（若存在）
                gl = str(row.get("年级") or "").strip()
                if gl:
                    student.grade_level = gl

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
    grade_level = request.args.get("grade_level")
    exam_name = request.args.get("exam_name")
    rankings = get_student_ranking(course_id=course_id, class_name=class_name, grade_level=grade_level, exam_name=exam_name)
    return jsonify({"rankings": rankings})


# 等级规则：查询
@api_bp.route("/grade-bands", methods=["GET"])
@login_required
def api_grade_bands_get():
    exam_name = request.args.get("exam_name") or "default"
    rule_set_id = request.args.get("rule_set_id", type=int)
    if rule_set_id:
        # 从版本集读取
        s = GradeBandSet.query.get_or_404(rule_set_id)
        import json
        return jsonify(json.loads(s.rules_json))
    # 默认读取活跃规则
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
    rule_set_id = payload.get("rule_set_id")
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

    # 若指定 rule_set_id，则保存快照至版本集；否则覆盖活跃规则
    import json
    if rule_set_id:
        s = GradeBandSet.query.get_or_404(rule_set_id)
        s.rules_json = json.dumps(items, ensure_ascii=False)
        db.session.commit()
        return jsonify({"message": "saved to set", "set_id": s.id, "count": len(items)})
    else:
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


# 汇总 API
@api_bp.route('/summary', methods=['GET'])
@login_required
def api_summary_list():
    from sqlalchemy import desc
    def _multi(param_name: str):
        # 支持 ?param=a&param=b 或 ?param=a,b
        vals = request.args.getlist(param_name)
        out = []
        for v in vals:
            out.extend([s.strip() for s in v.split(',') if s.strip()])
        return out

    exam_names = _multi('exam_name')
    grade_levels = _multi('grade_level')
    class_names = _multi('class_name')
    subject_code = request.args.get('subject_code') or 'TOTAL'
    order_by = request.args.get('order_by') or 'score_desc'

    # 查询匹配的成绩（按考试名称与科目）
    q = Grade.query.join(Student).join(Course)
    if exam_names:
        q = q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        q = q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        q = q.filter(Student.class_name.in_(class_names))
    # 非管理员可见范围限制
    if not current_user.is_anonymous and current_user.role != 'admin':
        if current_user.allowed_grade_levels:
            allowed = [s.strip() for s in current_user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if current_user.allowed_class_names:
            allowed = [s.strip() for s in current_user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))
    if subject_code:
        q = q.filter(Course.code == subject_code)

    # 分页参数
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 50, 1), 1000)

    total = q.count()
    rows = q.offset((page-1)*page_size).limit(page_size).all()
    items = []

    # 规则版本（发布的最新版本号），便于展示来源
    published_set = None
    rule_version = None
    if exam_names and len(exam_names) == 1:
        published_set = GradeBandSet.query.filter_by(exam_name=exam_names[0], status='published').order_by(GradeBandSet.version.desc()).first()
        if published_set:
            rule_version = published_set.version

    # 准备满分缓存 (exam_type, subject_code) -> max_score
    max_cache = {}

    # 计算班级/年级排名：需要同班/同年级的集合
    # 先聚合：key -> list of (student_id, score)
    from collections import defaultdict
    by_class = defaultdict(list)
    by_grade = defaultdict(list)
    for g in rows:
        by_class[g.student.class_name].append((g.student_id, g.score))
        by_grade[g.student.grade_level].append((g.student_id, g.score))

    # 排名映射
    def rank_map(pairs):
        # pairs: list[(student_id, score)]
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        rank = {}
        for i, (sid, _) in enumerate(pairs_sorted, 1):
            rank[sid] = i
        return rank

    class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
    grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}

    from app.utils import grade_letter_for
    for g in rows:
        letter = grade_letter_for(g.exam_name or 'default', g.course.code, g.score)
        # 百分比（若配置了满分）
        perc = None
        key = (g.exam_type or 'regular', g.course.code)
        if key in max_cache:
            max_score = max_cache[key]
        else:
            s = ExamScheme.query.filter_by(exam_type=key[0], subject_code=key[1]).first()
            max_score = s.max_score if s else None
            max_cache[key] = max_score
        if max_score and max_score > 0:
            perc = round(float(g.score) / float(max_score) * 100.0, 2)

        items.append({
            'student_id': g.student.student_id,
            'name': g.student.name,
            'class_name': g.student.class_name,
            'grade_level': g.student.grade_level,
            'score': g.score,
            'percentage': perc,
            'letter': letter,
            'class_rank': class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            'grade_rank': grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            'rule_version': rule_version,
        })

    # 排序
    if order_by == 'score_desc':
        items.sort(key=lambda x: x['score'], reverse=True)
    elif order_by == 'score_asc':
        items.sort(key=lambda x: x['score'])
    elif order_by == 'class_rank':
        items.sort(key=lambda x: (x['class_name'] or '', x['class_rank'] or 1e9))
    elif order_by == 'grade_rank':
        items.sort(key=lambda x: (x['grade_level'] or '', x['grade_rank'] or 1e9))

    return jsonify({'items': items, 'total': total, 'page': page, 'page_size': page_size, 'rule_version': rule_version})


@api_bp.route('/summary/prefs', methods=['GET', 'PUT'])
@login_required
def api_summary_prefs():
    from app.models import UserPreference
    import json
    key = 'summary_columns'
    if request.method == 'PUT':
        data = request.get_json(force=True)
        pref = UserPreference.query.filter_by(user_id=current_user.id, key=key).first()
        if not pref:
            pref = UserPreference(user_id=current_user.id, key=key, value='{}')
            db.session.add(pref)
        pref.value = json.dumps(data, ensure_ascii=False)
        db.session.commit()
        return jsonify({'message': 'ok'})
    # GET
    pref = UserPreference.query.filter_by(user_id=current_user.id, key=key).first()
    if not pref:
        return jsonify({'letter': True, 'class_rank': True, 'grade_rank': True})
    import json
    return jsonify(json.loads(pref.value))


@api_bp.route('/summary/export', methods=['GET'])
@login_required
def api_summary_export():
    # 复用过滤逻辑
    def _multi(param_name: str):
        vals = request.args.getlist(param_name)
        out = []
        for v in vals:
            out.extend([s.strip() for s in v.split(',') if s.strip()])
        return out

    exam_names = _multi('exam_name')
    grade_levels = _multi('grade_level')
    class_names = _multi('class_name')
    subject_code = request.args.get('subject_code') or 'TOTAL'
    fmt = request.args.get('format') or 'csv'

    q = Grade.query.join(Student).join(Course)
    if exam_names:
        q = q.filter(Grade.exam_name.in_(exam_names))
    if grade_levels:
        q = q.filter(Student.grade_level.in_(grade_levels))
    if class_names:
        q = q.filter(Student.class_name.in_(class_names))
    if subject_code:
        q = q.filter(Course.code == subject_code)
    # 非管理员可见范围限制
    if not current_user.is_anonymous and current_user.role != 'admin':
        if current_user.allowed_grade_levels:
            allowed = [s.strip() for s in current_user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.grade_level.in_(allowed))
        if current_user.allowed_class_names:
            allowed = [s.strip() for s in current_user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                q = q.filter(Student.class_name.in_(allowed))

    # scope: current_page | all
    scope = request.args.get('scope') or 'all'
    order_by = request.args.get('order_by') or 'score_desc'
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 50, 1), 1000)

    # 排序
    if order_by == 'score_desc':
        q = q.order_by(Grade.score.desc())
    elif order_by == 'score_asc':
        q = q.order_by(Grade.score.asc())

    if scope == 'current_page':
        q = q.offset((page-1)*page_size).limit(page_size)

    rows = q.all()

    # 计算班级/年级排名
    from collections import defaultdict
    by_class = defaultdict(list)
    by_grade = defaultdict(list)
    for g in rows:
        by_class[g.student.class_name].append((g.student_id, g.score))
        by_grade[g.student.grade_level].append((g.student_id, g.score))

    def rank_map(pairs):
        pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
        rank = {}
        for i, (sid, _) in enumerate(pairs_sorted, 1):
            rank[sid] = i
        return rank

    class_rank_map = {k: rank_map(v) for k, v in by_class.items()}
    grade_rank_map = {k: rank_map(v) for k, v in by_grade.items()}

    # 规则版本（仅单考试名时）
    rule_version = None
    if exam_names and len(exam_names) == 1:
        published_set = GradeBandSet.query.filter_by(exam_name=exam_names[0], status='published').order_by(GradeBandSet.version.desc()).first()
        if published_set:
            rule_version = published_set.version

    # 百分比计算缓存
    max_cache = {}

    # 列选择
    columns_param = request.args.get('columns')
    selected_cols = [c.strip() for c in columns_param.split(',')] if columns_param else None

    # 内部字段与导出表头映射
    header_map = {
        'student_id': '学号',
        'name': '姓名',
        'class_name': '班级',
        'grade_level': '年级',
        'score': '分数',
        'percentage': '百分比',
        'letter': '等第',
        'class_rank': '班级排名',
        'grade_rank': '年级排名',
        'rule_version': '规则版本',
    }

    # 默认列
    default_cols = ['student_id','name','class_name','grade_level','score','letter']
    use_cols = [c for c in (selected_cols or default_cols) if c in header_map]

    # 组装数据
    from app.utils import grade_letter_for
    data_rows = []
    for g in rows:
        # 百分比
        perc = None
        key = (g.exam_type or 'regular', g.course.code)
        if key in max_cache:
            max_score = max_cache[key]
        else:
            s = ExamScheme.query.filter_by(exam_type=key[0], subject_code=key[1]).first()
            max_score = s.max_score if s else None
            max_cache[key] = max_score
        if max_score and max_score > 0:
            perc = round(float(g.score) / float(max_score) * 100.0, 2)

        rec = {
            'student_id': g.student.student_id,
            'name': g.student.name,
            'class_name': g.student.class_name,
            'grade_level': g.student.grade_level,
            'score': g.score,
            'percentage': perc,
            'letter': grade_letter_for(g.exam_name or 'default', g.course.code, g.score),
            'class_rank': class_rank_map.get(g.student.class_name, {}).get(g.student_id),
            'grade_rank': grade_rank_map.get(g.student.grade_level, {}).get(g.student_id),
            'rule_version': rule_version,
        }
        data_rows.append(rec)

    # 生成导出结构
    export_rows = []
    for rec in data_rows:
        row = { header_map[col]: rec.get(col, '') for col in use_cols }
        export_rows.append(row)

    # 组装文件名片段（包含考试、学科、年级、班级）
    def _safe_name(s: str) -> str:
        import re
        return re.sub(r'[^\w\-\u4e00-\u9fa5]+', '_', s)[:40]
    import datetime as _dt
    ts = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    name_exam = '-'.join(exam_names) if exam_names else '全部考试'
    name_subject = subject_code or '全部学科'
    name_gl = '-'.join(grade_levels) if grade_levels else '全部年级'
    name_cl = '-'.join(class_names) if class_names else '全部班级'
    scope = request.args.get('scope') or 'all'
    order_by = request.args.get('order_by') or 'score_desc'
    base_name = f"{_safe_name(name_exam)}_{_safe_name(name_subject)}_{_safe_name(name_gl)}_{_safe_name(name_cl)}_{_safe_name(scope)}_{_safe_name(order_by)}_{ts}"

    if fmt == 'xlsx':
        # 优先使用 openpyxl 流式写入，内存更友好；不可用时回退 pandas
        try:
            from openpyxl import Workbook
            wb = Workbook(write_only=True)
            ws = wb.create_sheet()
            ws.append([header_map[c] for c in use_cols])
            for rec in data_rows:
                ws.append([rec.get(c, '') for c in use_cols])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return send_file(buf, as_attachment=True, download_name=f'{base_name}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception:
            import pandas as pd
            buf = io.BytesIO()
            pd.DataFrame([{header_map[c]: r.get(c, '') for c in use_cols} for r in data_rows]).to_excel(buf, index=False)
            buf.seek(0)
            return send_file(buf, as_attachment=True, download_name=f'{base_name}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    # 默认csv（流式写出，降低内存占用）
    import csv
    def generate_csv():
        yield '\ufeff'
        header = [header_map[c] for c in use_cols]
        sio = io.StringIO()
        writer = csv.writer(sio)
        writer.writerow(header)
        yield sio.getvalue()
        sio.seek(0); sio.truncate(0)
        for rec in data_rows:
            writer.writerow([rec.get(c, '') for c in use_cols])
            yield sio.getvalue()
            sio.seek(0); sio.truncate(0)
    return Response(stream_with_context(generate_csv()), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={base_name}.csv'})


@api_bp.route('/summary/options', methods=['GET'])
@login_required
def api_summary_options():
    # 枚举考试名称、年级、班级（应用非管理员可见范围）
    exam_q = db.session.query(Grade.exam_name).distinct()
    gl_q = db.session.query(Student.grade_level).distinct()
    cl_q = db.session.query(Student.class_name).distinct()

    if not current_user.is_anonymous and current_user.role != 'admin':
        if current_user.allowed_grade_levels:
            allowed = [s.strip() for s in current_user.allowed_grade_levels.split(',') if s.strip()]
            if allowed:
                gl_q = gl_q.filter(Student.grade_level.in_(allowed))
        if current_user.allowed_class_names:
            allowed = [s.strip() for s in current_user.allowed_class_names.split(',') if s.strip()]
            if allowed:
                cl_q = cl_q.filter(Student.class_name.in_(allowed))

    exam_names = sorted({ n[0] for n in exam_q.all() if n[0] })
    grade_levels = sorted({ n[0] for n in gl_q.all() if n[0] })
    class_names = sorted({ n[0] for n in cl_q.all() if n[0] })
    return jsonify({ 'exam_names': exam_names, 'grade_levels': grade_levels, 'class_names': class_names })


# 诊断 API（管理员）：构造典型查询，返回 EXPLAIN 计划与耗时
@api_bp.route('/diagnostics/run', methods=['POST'])
@login_required
def api_diagnostics_run():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    import time
    from sqlalchemy import text
    payload = request.get_json(force=True) or {}
    exam_names = payload.get('exam_names') or []
    grade_levels = payload.get('grade_levels') or []
    class_names = payload.get('class_names') or []
    subject_code = payload.get('subject_code') or 'TOTAL'
    order_by = payload.get('order_by') or 'score_desc'
    page = int(payload.get('page') or 1)
    page_size = int(payload.get('page_size') or 50)

    def build_q(base_q):
        q = base_q
        if exam_names:
            q = q.filter(Grade.exam_name.in_(exam_names))
        if grade_levels:
            q = q.filter(Student.grade_level.in_(grade_levels))
        if class_names:
            q = q.filter(Student.class_name.in_(class_names))
        if subject_code:
            q = q.filter(Course.code == subject_code)
        if order_by == 'score_desc':
            q = q.order_by(Grade.score.desc())
        elif order_by == 'score_asc':
            q = q.order_by(Grade.score.asc())
        return q

    base_q = Grade.query.join(Student).join(Course)
    list_q = build_q(base_q)

    # 计时：count、分页列表
    t0 = time.time()
    total = list_q.with_entities(db.func.count()).scalar()
    t_count = (time.time() - t0) * 1000

    t1 = time.time()
    page_rows = list_q.offset((page-1)*page_size).limit(page_size).all()
    t_page = (time.time() - t1) * 1000

    # EXPLAIN
    engine = db.engine
    dialect = engine.name  # 'sqlite', 'postgresql', 'mysql', ...
    compiled = list_q.statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    if dialect == 'sqlite':
        explain_sql = f"EXPLAIN QUERY PLAN {sql}"
    elif dialect == 'postgresql':
        explain_sql = f"EXPLAIN (FORMAT TEXT) {sql}"
    else:
        explain_sql = f"EXPLAIN {sql}"
    rows = engine.execute(text(explain_sql)).fetchall()
    plan = [" ".join([str(x) for x in r]) for r in rows]

    return jsonify({
        'filters': {
            'exam_names': exam_names,
            'grade_levels': grade_levels,
            'class_names': class_names,
            'subject_code': subject_code,
            'order_by': order_by,
            'page': page,
            'page_size': page_size,
        },
        'count_ms': round(t_count, 2),
        'page_ms': round(t_page, 2),
        'plan': plan,
        'total': total,
        'page_rows': len(page_rows),
        'dialect': dialect,
        'sql': sql,
    })


# 诊断预设 CRUD（管理员）
@api_bp.route('/diagnostics/presets', methods=['GET'])
@login_required
def api_diag_presets_list():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    presets = DiagnosticPreset.query.filter_by(user_id=current_user.id).order_by(DiagnosticPreset.id.desc()).all()
    import json
    return jsonify([{ 'id': p.id, 'name': p.name, 'payload': json.loads(p.payload) } for p in presets])


@api_bp.route('/diagnostics/presets', methods=['POST'])
@login_required
def api_diag_preset_create():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    payload = data.get('payload') or {}
    if not name:
        return jsonify({'error': 'name required'}), 400
    import json
    p = DiagnosticPreset(user_id=current_user.id, name=name, payload=json.dumps(payload, ensure_ascii=False))
    db.session.add(p); db.session.commit()
    return jsonify({'id': p.id, 'name': p.name})


# 用户管理 API（管理员）
@api_bp.route('/users', methods=['GET'])
@login_required
def api_users_list():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    qstr = request.args.get('q', '').strip()
    page = request.args.get('page', type=int) or 1
    page_size = min(max(request.args.get('page_size', type=int) or 20, 1), 200)
    q = User.query
    if qstr:
        like = f"%{qstr}%"
        q = q.filter((User.username.ilike(like)) | (User.email.ilike(like)))
    total = q.count()
    users = q.order_by(User.id.asc()).offset((page-1)*page_size).limit(page_size).all()
    return jsonify({
        'items': [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'allowed_grade_levels': u.allowed_grade_levels or '',
                'allowed_class_names': u.allowed_class_names or '',
            } for u in users
        ],
        'total': total,
        'page': page,
        'page_size': page_size,
    })


@api_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
def api_user_update(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    u = User.query.get_or_404(user_id)
    data = request.get_json(force=True)
    # 仅允许更新可见范围与角色（可选）
    if 'allowed_grade_levels' in data:
        u.allowed_grade_levels = data.get('allowed_grade_levels')
    if 'allowed_class_names' in data:
        u.allowed_class_names = data.get('allowed_class_names')
    if 'role' in data:
        u.role = data.get('role')
    db.session.commit()
    return jsonify({'message': 'updated'})


@api_bp.route('/users/batch', methods=['PUT'])
@login_required
def api_users_batch_update():
    if current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json(force=True)
    items = data.get('items') or []
    for it in items:
        u = User.query.get(it.get('id'))
        if not u:
            continue
        if 'role' in it and it.get('role'):
            u.role = it.get('role')
        if 'allowed_grade_levels' in it:
            u.allowed_grade_levels = it.get('allowed_grade_levels')
        if 'allowed_class_names' in it:
            u.allowed_class_names = it.get('allowed_class_names')
    db.session.commit()
    return jsonify({'message': 'batch updated', 'count': len(items)})


# 版本管理：列出/新建草稿/发布/回滚
@api_bp.route('/grade-bands/sets', methods=['GET', 'POST'])
@login_required
def api_band_sets():
    if request.method == 'POST':
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'forbidden'}), 403
        data = request.get_json(force=True)
        exam_name = data.get('exam_name') or 'default'
        note = data.get('note')
        import json
        # version = 当前该考试的最大版本+1（草稿态）
        max_ver = db.session.query(db.func.max(GradeBandSet.version)).filter_by(exam_name=exam_name).scalar() or 0
        s = GradeBandSet(exam_name=exam_name, version=max_ver+1, status='draft', note=note, rules_json=json.dumps([], ensure_ascii=False))
        db.session.add(s)
        db.session.commit()
        return jsonify({'id': s.id, 'version': s.version, 'status': s.status}), 201
    # GET
    exam_name = request.args.get('exam_name') or 'default'
    sets = GradeBandSet.query.filter_by(exam_name=exam_name).order_by(GradeBandSet.version.desc()).all()
    return jsonify([
        { 'id': s.id, 'exam_name': s.exam_name, 'version': s.version, 'status': s.status, 'note': s.note, 'created_at': s.created_at.isoformat(), 'published_at': (s.published_at.isoformat() if s.published_at else None) }
        for s in sets
    ])


@api_bp.route('/grade-bands/sets/<int:set_id>/publish', methods=['PUT'])
@login_required
def api_band_set_publish(set_id):
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    s = GradeBandSet.query.get_or_404(set_id)
    import json, datetime as dt
    # 将快照覆盖到活跃规则
    items = json.loads(s.rules_json)
    GradeBandRule.query.filter_by(exam_name=s.exam_name).delete()
    for it in items:
        db.session.add(GradeBandRule(
            exam_name=s.exam_name,
            subject_code=it.get('subject_code'),
            method=it.get('method'),
            a_min=it.get('a_min'), b_min=it.get('b_min'), c_min=it.get('c_min'), d_min=it.get('d_min'),
            a_pct=it.get('a_pct'), b_pct=it.get('b_pct'), c_pct=it.get('c_pct'), d_pct=it.get('d_pct'), e_pct=it.get('e_pct'),
        ))
    s.status = 'published'
    s.published_at = dt.datetime.utcnow()
    db.session.commit()
    # 审计
    from app.models import AuditLog
    db.session.add(AuditLog(user_id=current_user.id, username=current_user.username, action='publish', resource=f'GradeBandSet:{s.id}', details=f'{s.exam_name} v{s.version}'))
    db.session.commit()
    return jsonify({'message': 'published'})


@api_bp.route('/grade-bands/sets/<int:set_id>/rollback', methods=['PUT'])
@login_required
def api_band_set_rollback(set_id):
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    # 将历史版本复制为新的草稿
    src = GradeBandSet.query.get_or_404(set_id)
    import json
    max_ver = db.session.query(db.func.max(GradeBandSet.version)).filter_by(exam_name=src.exam_name).scalar() or 0
    s = GradeBandSet(
        exam_name=src.exam_name,
        version=max_ver+1,
        status='draft',
        note=f'Rollback from v{src.version}',
        rules_json=src.rules_json,
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({'id': s.id, 'version': s.version, 'status': s.status})


@api_bp.route('/grade-bands/sets/<int:set_id>/export-json', methods=['GET'])
@login_required
def api_band_set_export_json(set_id):
    if not current_user.is_authenticated or current_user.role not in ['admin','teacher']:
        return jsonify({'error': 'forbidden'}), 403
    s = GradeBandSet.query.get_or_404(set_id)
    import json
    return jsonify({ 'exam_name': s.exam_name, 'version': s.version, 'items': json.loads(s.rules_json) })


@api_bp.route('/grade-bands/sets/<int:set_id>/import-json', methods=['POST'])
@login_required
def api_band_set_import_json(set_id):
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    s = GradeBandSet.query.get_or_404(set_id)
    data = request.get_json(force=True)
    items = data.get('items') or []
    import json
    s.rules_json = json.dumps(items, ensure_ascii=False)
    db.session.commit()
    return jsonify({'message': 'imported', 'count': len(items)})


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
